"""Tests for the governed-session audit trail.

A governed Claude Code session previously wrote **no** audit records at all,
which made "audit evidence" a claim the session surface did not support. These
tests pin the two properties that make the trail worth having:

1. Denials are recorded. A denied call never runs, so it never reaches
   ``PostToolUse`` — a trail built only from executions would omit exactly the
   evidence an auditor wants.
2. Subagent calls are attributable, via the event's ``agent_id``/``agent_type``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rmacd.claude_code import hook, post_hook
from rmacd.claude_code.audit import (
    DEFAULT_AUDIT_RELNAME,
    SessionAuditor,
    audit_enabled,
    resolve_audit_path,
    session_context,
)

PROFILE = {
    "profile_id": "rmacd-3d-sessionaudit-v1",
    "profile_name": "Session Audit",
    "model": "three-dimensional",
    "version": "1.0",
    "permissions": {
        "public": ["R", "M", "A", "C", "D"],
        "internal": ["R", "M", "A"],
        "confidential": ["R"],
        "restricted": ["R"],
    },
}


@pytest.fixture
def session_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "rmacd-profile.json").write_text(json.dumps(PROFILE))
    monkeypatch.chdir(tmp_path)
    # Keep the sink inside tmp_path and unaffected by the developer's own env.
    for var in ("RMACD_AUDIT", "RMACD_AUDIT_PATH", "RMACD_PROFILE_PATH"):
        monkeypatch.delenv(var, raising=False)
    return tmp_path


def _audit_lines(session_dir: Path) -> list[dict]:
    sink = session_dir / ".claude" / DEFAULT_AUDIT_RELNAME
    if not sink.exists():
        return []
    return [json.loads(line) for line in sink.read_text().splitlines() if line.strip()]


def _pre(session_dir: Path, command: str, **extra: object) -> dict:
    event = {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "cwd": str(session_dir),
        "session_id": "sess-1",
        **extra,
    }
    import io

    out, err = io.StringIO(), io.StringIO()
    hook.run(io.StringIO(json.dumps(event)), out, err)
    return json.loads(out.getvalue())


def _post(session_dir: Path, command: str, response: object, **extra: object) -> None:
    import io

    event = {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "cwd": str(session_dir),
        "session_id": "sess-1",
        "tool_response": response,
        **extra,
    }
    post_hook.run(io.StringIO(json.dumps(event)), io.StringIO(), io.StringIO())


# --- the core gap this closes ------------------------------------------------


def test_allowed_call_is_recorded(session_dir: Path) -> None:
    _pre(session_dir, "cat README.md", tool_use_id="tu-1")
    records = _audit_lines(session_dir)
    assert len(records) == 1
    assert records[0]["policy_decision"]["result"] == "ALLOW"
    assert records[0]["operation"]["type"] == "R"


def test_denied_call_is_recorded(session_dir: Path) -> None:
    """The record that matters most — and the one PostToolUse can never see."""
    output = _pre(session_dir, "rm -rf /tmp/x", tool_use_id="tu-2")
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    records = _audit_lines(session_dir)
    assert len(records) == 1
    decision = records[0]["policy_decision"]
    assert decision["result"] == "DENY"
    assert decision["blocked_reason"]
    assert records[0]["operation"]["type"] == "D"


def test_unknown_tool_denial_is_recorded(session_dir: Path) -> None:
    """A tool we could not classify still produces evidence, not a gap."""
    import io

    event = {
        "tool_name": "mcp__nonexistent__do_thing",
        "tool_input": {},
        "cwd": str(session_dir),
        "session_id": "sess-1",
        "tool_use_id": "tu-3",
    }
    out = io.StringIO()
    hook.run(io.StringIO(json.dumps(event)), out, io.StringIO())
    assert json.loads(out.getvalue())["hookSpecificOutput"]["permissionDecision"] == "deny"

    records = _audit_lines(session_dir)
    assert len(records) == 1
    assert records[0]["policy_decision"]["result"] == "DENY"
    # Recorded at the most severe operation so it cannot be misread as a read.
    assert records[0]["operation"]["type"] == "D"


def test_subagent_call_is_attributable(session_dir: Path) -> None:
    _pre(
        session_dir,
        "rm -rf /tmp/x",
        tool_use_id="tu-4",
        agent_id="agt-9",
        agent_type="general-purpose",
    )
    extra = _audit_lines(session_dir)[0]["extra"]
    assert extra["agent_id"] == "agt-9"
    assert extra["agent_type"] == "general-purpose"
    assert extra["session_id"] == "sess-1"
    assert extra["tool_use_id"] == "tu-4"


def test_main_conversation_call_has_no_agent_fields(session_dir: Path) -> None:
    """Absence is meaningful: no agent_id means the main conversation."""
    _pre(session_dir, "cat README.md", tool_use_id="tu-5")
    extra = _audit_lines(session_dir)[0]["extra"]
    assert "agent_id" not in extra
    assert "agent_type" not in extra


# --- execution half ----------------------------------------------------------


def test_execution_outcome_is_recorded_and_correlated(session_dir: Path) -> None:
    _pre(session_dir, "cat README.md", tool_use_id="tu-6")
    _post(session_dir, "cat README.md", {"stdout": "hi"}, tool_use_id="tu-6")

    records = _audit_lines(session_dir)
    assert len(records) == 2
    decision, execution = records
    assert decision["policy_decision"]["result"] == "ALLOW"
    assert execution["policy_decision"]["result"] == "EXECUTED"
    assert execution["execution"]["status"] == "SUCCESS"
    # The join key.
    assert decision["extra"]["tool_use_id"] == execution["extra"]["tool_use_id"] == "tu-6"


@pytest.mark.parametrize(
    "response,expected_error",
    [
        ({"error": "No such file"}, "No such file"),
        ({"errorMessage": "boom"}, "boom"),
        ({"is_error": True, "message": "exit 1"}, "exit 1"),
        ("Error: something broke", "Error: something broke"),
    ],
)
def test_execution_failure_shapes(
    session_dir: Path, response: object, expected_error: str
) -> None:
    """Claude Code reports tool failure in several shapes; all must be caught."""
    _post(session_dir, "cat missing", response, tool_use_id="tu-7")
    execution = _audit_lines(session_dir)[0]["execution"]
    assert execution["status"] == "FAILURE"
    assert expected_error in execution["error"]


def test_post_hook_emits_no_permission_decision(session_dir: Path) -> None:
    """The call already ran; there is nothing left to gate."""
    import io

    out = io.StringIO()
    post_hook.run(
        io.StringIO(
            json.dumps(
                {
                    "tool_name": "Bash",
                    "tool_input": {"command": "cat x"},
                    "cwd": str(session_dir),
                    "tool_response": {"stdout": ""},
                }
            )
        ),
        out,
        io.StringIO(),
    )
    assert out.getvalue() == ""


# --- configuration and failure modes ----------------------------------------


def test_audit_can_be_disabled(session_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RMACD_AUDIT", "off")
    _pre(session_dir, "cat README.md", tool_use_id="tu-8")
    assert _audit_lines(session_dir) == []


def test_explicit_audit_path_wins(
    session_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sink = tmp_path / "elsewhere" / "trail.jsonl"
    monkeypatch.setenv("RMACD_AUDIT_PATH", str(sink))
    _pre(session_dir, "cat README.md", tool_use_id="tu-9")
    assert sink.exists()
    assert _audit_lines(session_dir) == []  # default location unused


def test_unbound_session_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No profile means nothing is governed, so there is nothing to audit."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("RMACD_PROFILE_PATH", raising=False)
    import io

    err = io.StringIO()
    hook.run(
        io.StringIO(json.dumps({"tool_name": "Bash", "tool_input": {"command": "rm -rf /"},
                                "cwd": str(tmp_path)})),
        io.StringIO(),
        err,
    )
    assert list(tmp_path.rglob("*.jsonl")) == []


def test_unwritable_sink_does_not_break_the_hook(
    session_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An audit problem must never take a working session down."""
    monkeypatch.setenv("RMACD_AUDIT_PATH", "/proc/nonexistent/cannot-write.jsonl")
    output = _pre(session_dir, "rm -rf /tmp/x", tool_use_id="tu-10")
    # The governance decision still stands.
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


# --- helpers -----------------------------------------------------------------


def test_resolve_audit_path_defaults_beside_the_profile(tmp_path: Path) -> None:
    profile = tmp_path / ".claude" / "rmacd-profile.json"
    resolved = resolve_audit_path(profile, env={})
    assert resolved == tmp_path / ".claude" / DEFAULT_AUDIT_RELNAME


@pytest.mark.parametrize("value", ["0", "off", "false", "no", "OFF"])
def test_audit_enabled_falsey_values(value: str) -> None:
    assert audit_enabled({"RMACD_AUDIT": value}) is False


def test_audit_enabled_by_default() -> None:
    assert audit_enabled({}) is True


def test_session_context_omits_absent_fields() -> None:
    assert session_context({"session_id": "s"}) == {"session_id": "s"}
    assert session_context({}) == {}


def test_disabled_auditor_is_a_noop() -> None:
    auditor = SessionAuditor(None)
    assert auditor.enabled is False
