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
import os
import time
from pathlib import Path

import pytest

from rmacd.claude_code import handoff, hook, post_hook
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
    # The decision has to come first: an execution record is written from the
    # decision handed forward by PreToolUse, never re-derived here.
    _pre(session_dir, "cat missing", tool_use_id="tu-7")
    _post(session_dir, "cat missing", response, tool_use_id="tu-7")
    execution = _audit_lines(session_dir)[-1]["execution"]
    assert execution["status"] == "FAILURE"
    assert expected_error in execution["error"]


def test_execution_record_keeps_the_decision_operation(session_dir: Path) -> None:
    """Write-to-a-new-file is Add in both records, not Add then Change.

    The mapping is path-state dependent: Write maps to Add when the file does
    not exist and Change when it does. Re-deriving in PostToolUse — after the
    write — turned every file creation into a decision/execution pair that
    disagreed about what the agent did.
    """
    import io

    created = session_dir / "brand-new.txt"
    event = {
        "tool_name": "Write",
        "tool_input": {"file_path": str(created), "content": "x"},
        "cwd": str(session_dir),
        "session_id": "sess-1",
        "tool_use_id": "tu-write",
    }
    hook.run(io.StringIO(json.dumps(event)), io.StringIO(), io.StringIO())

    created.write_text("x")  # the tool runs: the path now exists

    post_hook.run(
        io.StringIO(json.dumps({**event, "tool_response": {"ok": True}})),
        io.StringIO(),
        io.StringIO(),
    )

    decision, execution = _audit_lines(session_dir)
    assert decision["operation"]["type"] == "A"
    assert execution["operation"]["type"] == "A"


def test_execution_record_carries_the_decision_autonomy(session_dir: Path) -> None:
    """An approved call must not be filed as having run autonomously.

    ``touch`` on an unmapped target is Add/internal, which the profile routes to
    approval — the execution record has to say so, because "what did this agent
    do without asking?" is answered by reading these rows.
    """
    out = _pre(session_dir, "touch newfile.txt", tool_use_id="tu-ask")
    assert out["hookSpecificOutput"]["permissionDecision"] == "ask"

    _post(session_dir, "touch newfile.txt", {"ok": True}, tool_use_id="tu-ask")

    decision, execution = _audit_lines(session_dir)
    assert decision["policy_decision"]["result"] == "QUEUED"
    # C.6 serializes autonomy_level (not requires_approval), so this field is
    # the whole of what an auditor reading the execution row can see.
    assert execution["policy_decision"]["autonomy_level"] == "approval"
    assert execution["policy_decision"]["result"] == "EXECUTED"


def test_execution_without_a_decision_records_nothing(session_dir: Path) -> None:
    """No handoff means the call was never governed here; inventing a row would lie."""
    _post(session_dir, "cat README.md", {"stdout": "hi"}, tool_use_id="tu-orphan")
    assert _audit_lines(session_dir) == []


def test_declined_ask_leaves_no_execution_record(session_dir: Path) -> None:
    """A user who declines the prompt never triggers PostToolUse; only the QUEUED row stands."""
    _pre(session_dir, "touch other.txt", tool_use_id="tu-declined")
    records = _audit_lines(session_dir)
    assert len(records) == 1
    assert records[0]["policy_decision"]["result"] == "QUEUED"


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


def test_records_carry_the_profile_compliance_tags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both record kinds must be sliceable per regulation (§10.4).

    Session records shipped `compliance_tags: []` even when the profile
    declared them, which breaks the "one unified log per framework" premise.
    The execution record gets them via the handoff, since PostToolUse
    deliberately loads no profile.
    """
    import io

    claude = tmp_path / ".claude"
    claude.mkdir()
    tagged = dict(PROFILE, audit_requirements={"compliance_tags": ["SOX", "ISO27001"]})
    (claude / "rmacd-profile.json").write_text(json.dumps(tagged))
    monkeypatch.chdir(tmp_path)
    for var in ("RMACD_AUDIT", "RMACD_AUDIT_PATH", "RMACD_PROFILE_PATH"):
        monkeypatch.delenv(var, raising=False)

    event = {
        "tool_name": "Bash",
        "tool_input": {"command": "cat README.md"},
        "cwd": str(tmp_path),
        "session_id": "sess-tags",
        "tool_use_id": "tu-tags",
    }
    hook.run(io.StringIO(json.dumps(event)), io.StringIO(), io.StringIO())
    post_hook.run(
        io.StringIO(json.dumps({**event, "tool_response": {"ok": True}})),
        io.StringIO(),
        io.StringIO(),
    )

    records = _audit_lines(tmp_path)
    assert [r["policy_decision"]["result"] for r in records] == ["ALLOW", "EXECUTED"]
    for record in records:
        assert record["compliance_tags"] == ["SOX", "ISO27001"], record["policy_decision"]["result"]


def test_handoff_round_trip_is_single_use() -> None:
    """Taking a sidecar consumes it, so it cannot be replayed onto a later call."""
    assert handoff.store("sess-rt", "tu-rt", {"v": 1, "target": "/x"}) is True
    assert handoff.take("sess-rt", "tu-rt") == {"v": 1, "target": "/x"}
    assert handoff.take("sess-rt", "tu-rt") is None


def test_handoff_requires_both_ids() -> None:
    """Without a join key an execution record could not be correlated anyway."""
    assert handoff.store("sess-rt", None, {"v": 1}) is False
    assert handoff.store(None, "tu-rt", {"v": 1}) is False
    assert handoff.take("sess-rt", None) is None


def test_handoff_ids_cannot_escape_their_directory() -> None:
    """Ids arrive from the hook event, so they are untrusted path components."""
    assert handoff.store("../../etc", "../../passwd", {"v": 1}) is True
    assert handoff.take("../../etc", "../../passwd") == {"v": 1}
    assert not Path("/tmp/passwd.json").exists()


def test_handoff_sweeps_expired_sidecars(monkeypatch: pytest.MonkeyPatch) -> None:
    """A declined `ask` leaves an orphan; the TTL sweep reclaims it."""
    handoff.store("sess-sweep", "tu-old", {"v": 1})
    stale = handoff._session_dir("sess-sweep") / "tu-old.json"
    assert stale.exists()

    ancient = time.time() - handoff.TTL_SECONDS - 60
    os.utime(stale, (ancient, ancient))
    handoff.store("sess-sweep", "tu-new", {"v": 1})  # sweeps on write

    assert not stale.exists()
    assert handoff.take("sess-sweep", "tu-new") is not None


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
