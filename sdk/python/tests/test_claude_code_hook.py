"""Tests for the Claude Code session-governance hook (``rmacd.claude_code``).

Two layers:

- **Subprocess tests** feed recorded PreToolUse JSON events to
  ``python3 -m rmacd.claude_code.hook`` on stdin — the exact contract Claude
  Code exercises — and assert on the stdout JSON / stderr / exit code.
- **Direct tests** exercise ``session`` / ``mapping`` / ``hook.decide`` /
  ``status`` in-process for the finer-grained branches.

Covered fail modes (normative table in the c2 spec): unbound passthrough with
one-time stderr notice, bound-but-broken fail-close, unknown-MCP-tool default
deny with ``RMACD_UNKNOWN_TOOL=ask`` override, malformed stdin.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from rmacd.claude_code import hook, mapping, session, status
from rmacd.models import DataClassification, Operation
from rmacd.registry.tools import ToolCapability, ToolDefinition

# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

PROFILE_3D: dict[str, Any] = {
    "profile_id": "rmacd-3d-test-v1",
    "profile_name": "Claude Code hook test profile",
    "model": "three-dimensional",
    "version": "1.0",
    "permissions": {
        "public": ["R", "M", "A", "C", "D"],
        "internal": ["R", "M", "A", "C"],
        "confidential": ["R"],
        "restricted": ["R"],
    },
}

PROFILE_2D: dict[str, Any] = {
    "profile_id": "rmacd-2d-test-v1",
    "profile_name": "2D test profile",
    "model": "two-dimensional",
    "version": "1.0",
    "permissions": ["R", "M", "A", "C"],
}

PROFILE_DC2D: dict[str, Any] = {
    "profile_id": "rmacd-dc2d-test-v1",
    "profile_name": "DC2D test profile",
    "model": "data-classification-2d",
    "version": "1.0",
    "data_access": {
        "public": {"allowed": True, "autonomy": "autonomous"},
        "internal": {"allowed": True, "autonomy": "logged"},
        "confidential": {"allowed": True, "autonomy": "approval"},
        "restricted": {"allowed": False, "autonomy": "prohibited"},
    },
    "constraints": {
        "egress_controls": {
            "allowed_destinations": ["docs.example.com"],
            "block_external_models": False,
        }
    },
}


@pytest.fixture()
def profile_path(tmp_path: Path) -> Path:
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(PROFILE_3D), encoding="utf-8")
    return path


def make_binding(
    tmp_path: Path,
    profile: Mapping[str, Any] = PROFILE_3D,
    env_overrides: dict[str, str] | None = None,
) -> session.SessionBinding:
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(profile), encoding="utf-8")
    env = {session.ENV_PROFILE_PATH: str(path), **(env_overrides or {})}
    binding = session.bind_session(cwd=tmp_path, env=env)
    assert binding is not None
    return binding


def event(tool_name: str, tool_input: dict[str, Any], cwd: str = "/tmp") -> dict[str, Any]:
    """A realistic Claude Code PreToolUse stdin event."""
    return {
        "session_id": "test-session-1",
        "transcript_path": "/tmp/transcript.jsonl",
        "cwd": cwd,
        "hook_event_name": "PreToolUse",
        "tool_name": tool_name,
        "tool_input": tool_input,
    }


def run_hook(
    stdin_text: str,
    tmp_path: Path,
    *,
    env_overrides: dict[str, str] | None = None,
    module: str = "rmacd.claude_code.hook",
    args: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the hook as Claude Code does: a subprocess with the event on stdin."""
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("RMACD_") and k != "CLAUDE_PROJECT_DIR"
    }
    # Isolate the one-time-notice marker files per test.
    env["TMPDIR"] = str(tmp_path)
    env.update(env_overrides or {})
    return subprocess.run(
        [sys.executable, "-m", module, *(args or [])],
        input=stdin_text,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(tmp_path),
        timeout=120,
    )


def decision_of(proc: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    payload = json.loads(proc.stdout)
    out = payload["hookSpecificOutput"]
    assert out["hookEventName"] == "PreToolUse"
    assert isinstance(out, dict)
    return out


# ---------------------------------------------------------------------------
# subprocess: decision contract
# ---------------------------------------------------------------------------


def test_subprocess_allow_bash_read(tmp_path: Path, profile_path: Path) -> None:
    proc = run_hook(
        json.dumps(event("Bash", {"command": "ls -la"})),
        tmp_path,
        env_overrides={session.ENV_PROFILE_PATH: str(profile_path)},
    )
    assert proc.returncode == 0
    out = decision_of(proc)
    assert out["permissionDecision"] == "allow"
    assert "permissionDecisionReason" not in out


def test_subprocess_section_12_5_deny(tmp_path: Path, profile_path: Path) -> None:
    proc = run_hook(
        json.dumps(event("Bash", {"command": "rm -rf /data/secret"})),
        tmp_path,
        env_overrides={
            session.ENV_PROFILE_PATH: str(profile_path),
            session.ENV_CLASSIFICATION_MAP: json.dumps({"/data/secret/*": "restricted"}),
        },
    )
    out = decision_of(proc)
    assert out["permissionDecision"] == "deny"
    reason = out["permissionDecisionReason"]
    # The reason must cite operation, tier, rule, and profile id (c2 contract).
    assert "Delete" in reason
    assert "restricted" in reason
    assert "§12.5" in reason
    assert "cannot be granted by exception" in reason
    assert "rmacd-3d-test-v1" in reason
    assert "/data/secret" in reason


def test_subprocess_approval_becomes_ask(tmp_path: Path, profile_path: Path) -> None:
    # internal.C defaults to 'approval' in the 3D matrix -> "ask".
    proc = run_hook(
        json.dumps(event("Bash", {"command": "git push origin main"})),
        tmp_path,
        env_overrides={session.ENV_PROFILE_PATH: str(profile_path)},
    )
    out = decision_of(proc)
    assert out["permissionDecision"] == "ask"
    reason = out["permissionDecisionReason"]
    assert "Change" in reason
    assert "internal" in reason
    assert "approval" in reason
    assert "rmacd-3d-test-v1" in reason


def test_subprocess_unbound_passthrough_and_one_time_notice(tmp_path: Path) -> None:
    stdin_text = json.dumps(event("Bash", {"command": "ls"}, cwd=str(tmp_path)))
    first = run_hook(stdin_text, tmp_path)
    assert first.returncode == 0
    assert first.stdout.strip() == ""  # no decision -> Claude Code flow unchanged
    assert "unbound" in first.stderr
    second = run_hook(stdin_text, tmp_path)
    assert second.returncode == 0
    assert second.stdout.strip() == ""
    assert second.stderr.strip() == ""  # notice is one-time per session


def test_subprocess_bound_but_broken_fails_closed(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.json"
    proc = run_hook(
        json.dumps(event("Bash", {"command": "ls"})),
        tmp_path,
        env_overrides={session.ENV_PROFILE_PATH: str(missing)},
    )
    out = decision_of(proc)
    assert out["permissionDecision"] == "deny"
    assert "fail-closed" in out["permissionDecisionReason"]
    assert "could not be bound" in out["permissionDecisionReason"]


def test_subprocess_invalid_profile_json_fails_closed(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    proc = run_hook(
        json.dumps(event("Read", {"file_path": "/etc/hosts"})),
        tmp_path,
        env_overrides={session.ENV_PROFILE_PATH: str(bad)},
    )
    out = decision_of(proc)
    assert out["permissionDecision"] == "deny"
    assert "fail-closed" in out["permissionDecisionReason"]


def test_subprocess_mcp_prefix_resolves_via_packs(tmp_path: Path, profile_path: Path) -> None:
    # read_file is registered by the built-in filesystem pack (R on internal).
    proc = run_hook(
        json.dumps(event("mcp__myfs__read_file", {"path": str(tmp_path / "x.txt")})),
        tmp_path,
        env_overrides={session.ENV_PROFILE_PATH: str(profile_path)},
    )
    assert decision_of(proc)["permissionDecision"] == "allow"


def test_subprocess_unknown_mcp_tool_denies_by_default(
    tmp_path: Path, profile_path: Path
) -> None:
    proc = run_hook(
        json.dumps(event("mcp__foo__frobnicate", {})),
        tmp_path,
        env_overrides={session.ENV_PROFILE_PATH: str(profile_path)},
    )
    out = decision_of(proc)
    assert out["permissionDecision"] == "deny"
    assert "not registered" in out["permissionDecisionReason"]
    assert "RMACD_UNKNOWN_TOOL" in out["permissionDecisionReason"]


def test_subprocess_unknown_mcp_tool_ask_override(tmp_path: Path, profile_path: Path) -> None:
    proc = run_hook(
        json.dumps(event("mcp__foo__frobnicate", {})),
        tmp_path,
        env_overrides={
            session.ENV_PROFILE_PATH: str(profile_path),
            session.ENV_UNKNOWN_TOOL: "ask",
        },
    )
    assert decision_of(proc)["permissionDecision"] == "ask"


def test_subprocess_malformed_stdin_bound_fails_closed(
    tmp_path: Path, profile_path: Path
) -> None:
    proc = run_hook(
        "this is not JSON {",
        tmp_path,
        env_overrides={session.ENV_PROFILE_PATH: str(profile_path)},
    )
    out = decision_of(proc)
    assert out["permissionDecision"] == "deny"
    assert "malformed" in out["permissionDecisionReason"]
    assert "rmacd-3d-test-v1" in out["permissionDecisionReason"]


def test_subprocess_malformed_stdin_unbound_passes_through(tmp_path: Path) -> None:
    proc = run_hook("this is not JSON {", tmp_path)
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_subprocess_package_dispatcher_hook_and_status(
    tmp_path: Path, profile_path: Path
) -> None:
    env = {session.ENV_PROFILE_PATH: str(profile_path)}
    proc = run_hook(
        json.dumps(event("Read", {"file_path": "/etc/hosts"})),
        tmp_path,
        env_overrides=env,
        module="rmacd.claude_code",
        args=["hook"],
    )
    assert decision_of(proc)["permissionDecision"] == "allow"
    proc = run_hook("", tmp_path, env_overrides=env, module="rmacd.claude_code", args=["status"])
    assert proc.returncode == 0
    assert "rmacd-3d-test-v1" in proc.stdout


def test_subprocess_status_module_runs_unbound(tmp_path: Path) -> None:
    proc = run_hook("", tmp_path, module="rmacd.claude_code.status")
    assert proc.returncode == 0
    assert "UNBOUND" in proc.stdout


def test_subprocess_project_profile_binding(tmp_path: Path) -> None:
    # Without RMACD_PROFILE_PATH, .claude/rmacd-profile.json in the event cwd binds.
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "rmacd-profile.json").write_text(json.dumps(PROFILE_3D), encoding="utf-8")
    proc = run_hook(
        json.dumps(event("Bash", {"command": "rm -rf ./build"}, cwd=str(tmp_path))),
        tmp_path,
        env_overrides={
            session.ENV_CLASSIFICATION_MAP: json.dumps({"./build*": "internal"})
        },
    )
    out = decision_of(proc)
    # Delete on internal is not granted by the test profile -> deny (not passthrough).
    assert out["permissionDecision"] == "deny"
    assert "rmacd-3d-test-v1" in out["permissionDecisionReason"]


# ---------------------------------------------------------------------------
# direct: session binding
# ---------------------------------------------------------------------------


def test_resolve_profile_path_env_wins(tmp_path: Path) -> None:
    project_file = tmp_path / ".claude" / "rmacd-profile.json"
    project_file.parent.mkdir()
    project_file.write_text("{}", encoding="utf-8")
    resolved = session.resolve_profile_path(
        tmp_path, {session.ENV_PROFILE_PATH: "/explicit/profile.json"}
    )
    assert resolved == Path("/explicit/profile.json")
    assert session.resolve_profile_path(tmp_path, {}) == project_file


def test_bind_session_unbound_returns_none(tmp_path: Path) -> None:
    assert session.bind_session(cwd=tmp_path, env={}) is None


def test_bind_session_default_packs_and_extras(tmp_path: Path) -> None:
    binding = make_binding(tmp_path, env_overrides={session.ENV_PACKS: "git, github"})
    assert binding.pack_sources[:2] == ["shell", "filesystem"]
    assert "git" in binding.pack_sources
    assert "github" in binding.pack_sources
    assert len(binding.registry) > 0


def test_bind_session_invalid_default_tier_raises(tmp_path: Path) -> None:
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(PROFILE_3D), encoding="utf-8")
    with pytest.raises(session.SessionBindingError):
        session.bind_session(
            cwd=tmp_path,
            env={session.ENV_PROFILE_PATH: str(path), session.ENV_DEFAULT_TIER: "ultra"},
        )


def test_bind_session_invalid_map_raises(tmp_path: Path) -> None:
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(PROFILE_3D), encoding="utf-8")
    with pytest.raises(session.SessionBindingError):
        session.bind_session(
            cwd=tmp_path,
            env={
                session.ENV_PROFILE_PATH: str(path),
                session.ENV_CLASSIFICATION_MAP: "{broken",
            },
        )


def test_bind_session_unknown_tool_value_clamps_to_deny(tmp_path: Path) -> None:
    binding = make_binding(tmp_path, env_overrides={session.ENV_UNKNOWN_TOOL: "allow"})
    assert binding.unknown_tool_decision == "deny"  # fail-closed clamp


def test_classification_map_from_file_and_dir_pattern(tmp_path: Path) -> None:
    map_file = tmp_path / "map.json"
    map_file.write_text(
        json.dumps({"/data/secret/*": "restricted", "/data/*": "confidential"}),
        encoding="utf-8",
    )
    binding = make_binding(tmp_path, env_overrides={session.ENV_CLASSIFICATION_MAP: str(map_file)})
    # Highest matching tier wins; the /* pattern covers the directory itself.
    assert binding.classify_path("/data/secret") == DataClassification.RESTRICTED
    assert binding.classify_path("/data/secret/deep/file") == DataClassification.RESTRICTED
    assert binding.classify_path("/data/report.csv") == DataClassification.CONFIDENTIAL
    assert binding.classify_path("/elsewhere") is None


# ---------------------------------------------------------------------------
# direct: mapping
# ---------------------------------------------------------------------------


def test_mapping_write_new_path_is_add(tmp_path: Path) -> None:
    binding = make_binding(tmp_path)
    call = mapping.map_tool_call(
        "Write", {"file_path": str(tmp_path / "new.txt"), "content": "x"}, binding
    )
    assert call.operation == Operation.ADD


def test_mapping_edit_existing_path_is_change(tmp_path: Path) -> None:
    existing = tmp_path / "existing.txt"
    existing.write_text("x", encoding="utf-8")
    binding = make_binding(tmp_path)
    call = mapping.map_tool_call("Edit", {"file_path": str(existing)}, binding)
    assert call.operation == Operation.CHANGE
    assert call.target == str(existing)


def test_mapping_read_tools_are_read(tmp_path: Path) -> None:
    binding = make_binding(tmp_path)
    for tool, args in (
        ("Read", {"file_path": "/etc/hosts"}),
        ("Glob", {"pattern": "**/*.py"}),
        ("Grep", {"pattern": "TODO", "path": "/src"}),
    ):
        assert mapping.map_tool_call(tool, args, binding).operation == Operation.READ


def test_mapping_webfetch_carries_egress_destination(tmp_path: Path) -> None:
    binding = make_binding(tmp_path)
    call = mapping.map_tool_call("WebFetch", {"url": "https://evil.example.net/x"}, binding)
    assert call.operation == Operation.READ
    assert call.egress_destination == "evil.example.net"


def test_mapping_session_internal_tools_are_public_read(tmp_path: Path) -> None:
    binding = make_binding(tmp_path)
    call = mapping.map_tool_call("TodoWrite", {"todos": []}, binding)
    assert call.operation == Operation.READ
    assert call.tier == DataClassification.PUBLIC


def test_mapping_unknown_tool_raises(tmp_path: Path) -> None:
    binding = make_binding(tmp_path)
    with pytest.raises(mapping.UnknownToolError):
        mapping.map_tool_call("FrobnicateEverything", {}, binding)


def test_mapping_mcp_classification_map_overlays_pack_tier(tmp_path: Path) -> None:
    binding = make_binding(
        tmp_path,
        env_overrides={session.ENV_CLASSIFICATION_MAP: json.dumps({"/vault/*": "restricted"})},
    )
    call = mapping.map_tool_call("mcp__fs__read_file", {"path": "/vault/creds"}, binding)
    assert call.operation == Operation.READ
    assert call.tier == DataClassification.RESTRICTED  # raised from the pack's 'internal'


def test_mapping_capability_ceiling_denies(tmp_path: Path) -> None:
    binding = make_binding(tmp_path)
    binding.registry.register_tool(
        ToolDefinition(
            tool_id="readonly_probe",
            tool_name="readonly_probe",
            rmacd_level=Operation.READ,
            capability=ToolCapability(operations={Operation.READ}),
            classifier=lambda args: (Operation.CHANGE, "internal", "probe://x"),
        )
    )
    with pytest.raises(mapping.CapabilityCeilingError):
        mapping.map_tool_call("mcp__probe__readonly_probe", {}, binding)


def test_mapping_bash_restricted_path_token(tmp_path: Path) -> None:
    binding = make_binding(
        tmp_path,
        env_overrides={
            session.ENV_CLASSIFICATION_MAP: json.dumps({"/data/secret/*": "restricted"})
        },
    )
    call = mapping.map_tool_call("Bash", {"command": "rm -rf /data/secret"}, binding)
    assert call.operation == Operation.DELETE
    assert call.tier == DataClassification.RESTRICTED
    assert call.target == "/data/secret"


# ---------------------------------------------------------------------------
# direct: hook.decide
# ---------------------------------------------------------------------------


def _decision(binding: session.SessionBinding, name: str, args: dict[str, Any]) -> dict[str, Any]:
    out = hook.decide(event(name, args), binding)
    result: dict[str, Any] = out["hookSpecificOutput"]
    return result


def test_decide_capability_ceiling_reason_cites_rule_and_profile(tmp_path: Path) -> None:
    binding = make_binding(tmp_path)
    binding.registry.register_tool(
        ToolDefinition(
            tool_id="readonly_probe",
            tool_name="readonly_probe",
            rmacd_level=Operation.READ,
            capability=ToolCapability(operations={Operation.READ}),
            classifier=lambda args: (Operation.CHANGE, "internal", "probe://x"),
        )
    )
    out = _decision(binding, "mcp__probe__readonly_probe", {})
    assert out["permissionDecision"] == "deny"
    assert "capability ceiling" in out["permissionDecisionReason"]
    assert "rmacd-3d-test-v1" in out["permissionDecisionReason"]


def test_decide_2d_profile_allows_read_without_tier(tmp_path: Path) -> None:
    binding = make_binding(tmp_path, profile=PROFILE_2D)
    out = _decision(binding, "Bash", {"command": "cat README.md"})
    assert out["permissionDecision"] == "allow"


def test_decide_2d_profile_asks_for_change(tmp_path: Path) -> None:
    # DEFAULT_AUTONOMY_2D: C -> approval.
    binding = make_binding(tmp_path, profile=PROFILE_2D)
    out = _decision(binding, "Bash", {"command": "chmod +x deploy.sh"})
    assert out["permissionDecision"] == "ask"


def test_decide_dc2d_egress_denied_off_allowlist(tmp_path: Path) -> None:
    binding = make_binding(tmp_path, profile=PROFILE_DC2D)
    out = _decision(binding, "WebFetch", {"url": "https://exfil.example.net/drop"})
    assert out["permissionDecision"] == "deny"
    assert "egress" in out["permissionDecisionReason"]
    assert "rmacd-dc2d-test-v1" in out["permissionDecisionReason"]


def test_decide_dc2d_egress_allowed_on_allowlist(tmp_path: Path) -> None:
    binding = make_binding(
        tmp_path,
        profile=PROFILE_DC2D,
        env_overrides={session.ENV_DEFAULT_TIER: "internal"},
    )
    out = _decision(binding, "WebFetch", {"url": "https://docs.example.com/page"})
    # internal tier on a DC2D profile -> 'logged' autonomy -> allow.
    assert out["permissionDecision"] == "allow"


def test_decide_deny_reason_cites_operation_tier_rule_profile(tmp_path: Path) -> None:
    binding = make_binding(tmp_path)
    # Delete on internal: not granted by the test profile (internal has no D).
    out = _decision(binding, "Bash", {"command": "rm -rf ./build"})
    assert out["permissionDecision"] == "deny"
    reason = out["permissionDecisionReason"]
    assert "Delete" in reason
    assert "internal" in reason
    assert "Rule:" in reason
    assert "rmacd-3d-test-v1" in reason


def test_decide_restricted_read_is_allowed_with_notification(tmp_path: Path) -> None:
    binding = make_binding(
        tmp_path,
        env_overrides={
            session.ENV_CLASSIFICATION_MAP: json.dumps({"/data/secret/*": "restricted"})
        },
    )
    out = _decision(binding, "Read", {"file_path": "/data/secret/report.txt"})
    # restricted.R defaults to 'notification' -> allowed, no approval prompt.
    assert out["permissionDecision"] == "allow"


# ---------------------------------------------------------------------------
# direct: the one-time unbound notice
# ---------------------------------------------------------------------------


def test_unbound_notice_is_emitted_once_per_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(hook.tempfile, "gettempdir", lambda: str(tmp_path))
    event = {"session_id": "sess-notice"}

    first, second = io.StringIO(), io.StringIO()
    hook._emit_unbound_notice_once(event, first)
    hook._emit_unbound_notice_once(event, second)

    assert "unbound" in first.getvalue()
    assert second.getvalue() == ""


def test_unbound_notice_marker_does_not_follow_a_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The marker lives in a shared temp dir, so the path may not be ours.

    Without O_NOFOLLOW a symlink planted at the marker path redirects the write
    to any file the user can write, truncating it.
    """
    monkeypatch.setattr(hook.tempfile, "gettempdir", lambda: str(tmp_path))
    event = {"session_id": "sess-symlink"}
    victim = tmp_path / "victim"
    victim.write_text("precious")
    Path(hook._notice_marker_path(event)).symlink_to(victim)

    err = io.StringIO()
    hook._emit_unbound_notice_once(event, err)

    assert victim.read_text() == "precious"
    # The notice still has to reach the user; a hostile marker must not silence it.
    assert "unbound" in err.getvalue()


# ---------------------------------------------------------------------------
# direct: status rendering
# ---------------------------------------------------------------------------


def test_status_bound_lists_profile_matrix_and_packs(
    tmp_path: Path, profile_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in list(os.environ):
        if key.startswith("RMACD_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv(session.ENV_PROFILE_PATH, str(profile_path))
    text = status.render_status(cwd=str(tmp_path))
    assert "rmacd-3d-test-v1" in text
    assert "3D (three-dimensional)" in text
    assert "prohibited" in text  # restricted row of the matrix
    assert "shell, filesystem" in text
    assert '"ask"' in text
    # The audit sink is part of the posture: a status that omits it cannot answer
    # "where is this session's evidence going?".
    assert str(profile_path.parent / "rmacd-audit.jsonl") in text


def test_status_reports_disabled_audit(
    tmp_path: Path, profile_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in list(os.environ):
        if key.startswith("RMACD_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv(session.ENV_PROFILE_PATH, str(profile_path))
    monkeypatch.setenv("RMACD_AUDIT", "off")
    text = status.render_status(cwd=str(tmp_path))
    assert "DISABLED" in text
    assert "records no evidence" in text


@pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root bypasses the permission bits this test relies on",
)
def test_status_warns_when_the_audit_sink_is_unwritable(
    tmp_path: Path, profile_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unwritable sink degrades silently at runtime, so status must say so."""
    for key in list(os.environ):
        if key.startswith("RMACD_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv(session.ENV_PROFILE_PATH, str(profile_path))
    sealed = tmp_path / "sealed"
    sealed.mkdir(mode=0o500)
    monkeypatch.setenv("RMACD_AUDIT_PATH", str(sealed / "audit.jsonl"))
    text = status.render_status(cwd=str(tmp_path))
    assert "WARNING: not writable" in text


def test_status_unbound_explains_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in list(os.environ):
        if key.startswith("RMACD_"):
            monkeypatch.delenv(key, raising=False)
    text = status.render_status(cwd=str(tmp_path))
    assert "UNBOUND" in text
    assert "RMACD_PROFILE_PATH" in text


def test_status_broken_binding_reports_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in list(os.environ):
        if key.startswith("RMACD_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv(session.ENV_PROFILE_PATH, str(tmp_path / "missing.json"))
    text = status.render_status(cwd=str(tmp_path))
    assert "FAILING CLOSED" in text


# ---------------------------------------------------------------------------
# introspection carve-out (0.13.1): the governance layer's own read surfaces
# ---------------------------------------------------------------------------

READONLY_PROFILE: dict[str, Any] = {
    "profile_id": "rmacd-3d-readonly-v1",
    "profile_name": "Read-only introspection test profile",
    "model": "three-dimensional",
    "version": "1.0",
    "permissions": {
        "public": ["R"],
        "internal": ["R"],
        "confidential": ["R"],
        "restricted": ["R"],
    },
}


@pytest.mark.parametrize(
    "command,detail",
    [
        ("python3 -m rmacd.claude_code.status", "rmacd status renderer"),
        ("python -m rmacd.claude_code status", "rmacd status renderer"),
        ("rmacd matrix profile.json", "rmacd matrix"),
        ("rmacd --version", "rmacd --version"),
        ("rmacd validate profile.json", "rmacd validate"),
        ("python3 -m rmacd.cli info profile.json", "rmacd info"),
        ("rmacd pack verify -k key.pub pack.json", "rmacd pack verify"),
        ("rmacd audit summarize audit.jsonl", "rmacd audit summarize"),
    ],
)
def test_introspection_commands_classify_as_read(
    tmp_path: Path, command: str, detail: str
) -> None:
    binding = make_binding(tmp_path, profile=READONLY_PROFILE)
    call = mapping.map_tool_call("Bash", {"command": command}, binding)
    assert call.operation is Operation.READ
    assert call.target == "rmacd:introspection"
    assert detail in call.rule


@pytest.mark.parametrize(
    "command",
    [
        "rmacd matrix p.json && rm -rf /",  # compound: no carve-out
        "rmacd matrix p.json; rm x",
        "rmacd matrix $(cat f)",
        "rmacd pack sign -k key pack.json",  # writes a signature
        "rmacd classify --source tools.json",  # network/LLM
        "rmacd mcp-serve",  # long-running server
        "python3 -m rmacd.claude_code.hook",  # not a read surface
        "python3 script.py",
    ],
)
def test_non_introspection_commands_take_classifier_path(
    tmp_path: Path, command: str
) -> None:
    binding = make_binding(tmp_path, profile=READONLY_PROFILE)
    call = mapping.map_tool_call("Bash", {"command": command}, binding)
    assert call.target != "rmacd:introspection"


def test_status_command_allowed_under_readonly_profile(tmp_path: Path) -> None:
    """The bug found in live E2E: /rmacd:status must not be denied by the
    fail-closed bash default when a read-only profile is bound."""
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(READONLY_PROFILE), encoding="utf-8")
    proc = run_hook(
        json.dumps(event("Bash", {"command": "python3 -m rmacd.claude_code.status"})),
        tmp_path,
        env_overrides={session.ENV_PROFILE_PATH: str(path)},
    )
    out = json.loads(proc.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"


# ---------------------------------------------------------------------------
# Bypass regressions (0.14.0). Each test below reproduces a way a governed
# session could be silently ungoverned or a §12.5 deny downgraded to an
# approvable prompt. They assert the *fixed* behaviour.
# ---------------------------------------------------------------------------


def _project_with_profile(tmp_path: Path) -> Path:
    """A project root carrying .claude/rmacd-profile.json, plus a subdirectory."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "rmacd-profile.json").write_text(json.dumps(PROFILE_3D), encoding="utf-8")
    nested = tmp_path / "src" / "deep"
    nested.mkdir(parents=True)
    return nested


def test_subdirectory_cwd_still_binds_the_project_profile(tmp_path: Path) -> None:
    """Regression: a cwd below the project root silently unbound the session.

    resolve_profile_path only probed ``<cwd>/.claude/rmacd-profile.json``, so
    working from a subdirectory produced NO decision at all — Claude Code's own
    flow proceeded ungoverned for the rest of the session.
    """
    nested = _project_with_profile(tmp_path)
    proc = run_hook(
        json.dumps(event("Bash", {"command": "rm -rf /etc"}, cwd=str(nested))),
        tmp_path,
    )
    assert proc.stdout.strip(), "hook emitted no decision — session was unbound"
    out = decision_of(proc)
    assert out["permissionDecision"] in ("deny", "ask")


def test_cwd_outside_project_falls_back_to_claude_project_dir(tmp_path: Path) -> None:
    """A cwd outside the project tree still binds via CLAUDE_PROJECT_DIR."""
    _project_with_profile(tmp_path)
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    proc = run_hook(
        json.dumps(event("Bash", {"command": "rm -rf /etc"}, cwd=str(outside))),
        tmp_path,
        env_overrides={"CLAUDE_PROJECT_DIR": str(tmp_path)},
    )
    assert proc.stdout.strip(), "hook emitted no decision — session was unbound"
    assert decision_of(proc)["permissionDecision"] in ("deny", "ask")


def test_resolve_profile_path_walks_up_and_prefers_nearest(tmp_path: Path) -> None:
    """The nearest .claude profile wins, so a subproject may bind a stricter one."""
    root_claude = tmp_path / ".claude"
    root_claude.mkdir()
    (root_claude / "rmacd-profile.json").write_text(json.dumps(PROFILE_3D), encoding="utf-8")
    sub = tmp_path / "sub"
    sub_claude = sub / ".claude"
    sub_claude.mkdir(parents=True)
    (sub_claude / "rmacd-profile.json").write_text(json.dumps(PROFILE_3D), encoding="utf-8")
    deep = sub / "a" / "b"
    deep.mkdir(parents=True)

    assert session.resolve_profile_path(deep, {}) == sub_claude / "rmacd-profile.json"
    assert session.resolve_profile_path(tmp_path, {}) == root_claude / "rmacd-profile.json"


@pytest.mark.parametrize(
    "command",
    [
        "rm -rf /data/secret",  # the canonical form (already denied pre-fix)
        "rm -rf /data/../data/secret",  # .. traversal
        "rm -rf /data/./secret",  # redundant .
        "rm -rf //data//secret",  # duplicate separators
        'bash -c "rm -rf /data/secret"',  # nested shell script
        "sh -c 'rm -rf /data/secret'",
        'bash -c "sh -c \'rm -rf /data/secret\'"',  # doubly nested
    ],
)
def test_path_spellings_cannot_evade_the_immutable_floor(
    tmp_path: Path, command: str
) -> None:
    """Regression: `..`, `./` and `sh -c` hid the target from the map.

    Each spelling names the same restricted path, so each must hit the §12.5
    floor. Before the fix the tier fell back to the session default and the
    hard deny became an approvable 'ask'.
    """
    binding = make_binding(
        tmp_path,
        env_overrides={
            session.ENV_CLASSIFICATION_MAP: json.dumps({"/data/secret/*": "restricted"})
        },
    )
    out = hook.decide(event("Bash", {"command": command}), binding)["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny", f"{command!r} was not denied"
    assert "§12.5" in out["permissionDecisionReason"]


def test_relative_target_resolves_against_session_cwd(tmp_path: Path) -> None:
    """`./secret` under cwd=/data must classify as /data/secret would."""
    data = tmp_path / "data"
    (data / "secret").mkdir(parents=True)
    path = tmp_path / "p.json"
    path.write_text(json.dumps(PROFILE_3D), encoding="utf-8")
    binding = session.bind_session(
        cwd=data,
        env={
            session.ENV_PROFILE_PATH: str(path),
            session.ENV_CLASSIFICATION_MAP: json.dumps(
                {str(data / "secret") + "/*": "restricted"}
            ),
        },
    )
    assert binding is not None
    assert binding.classify_path("./secret") is DataClassification.RESTRICTED
    assert binding.classify_path("secret/key.pem") is DataClassification.RESTRICTED
    assert binding.classify_path("../data/secret") is DataClassification.RESTRICTED


def test_write_to_relative_restricted_path_is_denied(tmp_path: Path) -> None:
    data = tmp_path / "data"
    (data / "secret").mkdir(parents=True)
    path = tmp_path / "p.json"
    path.write_text(json.dumps(PROFILE_3D), encoding="utf-8")
    binding = session.bind_session(
        cwd=data,
        env={
            session.ENV_PROFILE_PATH: str(path),
            session.ENV_CLASSIFICATION_MAP: json.dumps(
                {str(data / "secret") + "/*": "restricted"}
            ),
        },
    )
    assert binding is not None
    out = hook.decide(
        event("Write", {"file_path": "secret/creds.txt"}, cwd=str(data)), binding
    )["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny"
    assert "§12.5" in out["permissionDecisionReason"]


# ---------------------------------------------------------------------------
# nested tool arguments and file:// targets (2026-08-11)
# ---------------------------------------------------------------------------


def _mcp_tier(tmp_path: Path, args: dict[str, Any]) -> DataClassification | None:
    binding = make_binding(
        tmp_path,
        env_overrides={
            session.ENV_CLASSIFICATION_MAP: json.dumps({"/data/secret/*": "restricted"})
        },
    )
    return mapping.map_tool_call("mcp__fs__read_file", args, binding).tier


@pytest.mark.parametrize(
    "args",
    [
        {"path": "/data/secret/x"},
        {"paths": ["/data/secret/x"]},
        {"opts": {"path": "/data/secret/x"}},
        {"a": {"b": {"c": ["/data/secret/x"]}}},
    ],
    ids=["top-level", "list", "nested-dict", "deep"],
)
def test_classification_map_reaches_nested_tool_arguments(
    tmp_path: Path, args: dict[str, Any]
) -> None:
    """A path one level down must not evade the map.

    Scanning only top-level strings let `{"paths": [...]}` fall through to the
    session default tier — the same §12.5-downgrade shape as the `sh -c`
    evasion closed in 0.14.0.
    """
    assert _mcp_tier(tmp_path, args) == DataClassification.RESTRICTED


def test_unmapped_nested_path_still_takes_the_default_tier(tmp_path: Path) -> None:
    """The walk must not classify everything it touches as sensitive."""
    assert _mcp_tier(tmp_path, {"paths": ["/data/public/x"]}) != DataClassification.RESTRICTED


def test_nested_argument_walk_is_depth_bounded(tmp_path: Path) -> None:
    deep: Any = "/data/secret/x"
    for _ in range(50):
        deep = {"n": deep}
    assert _mcp_tier(tmp_path, {"a": deep}) != DataClassification.RESTRICTED


@pytest.mark.parametrize(
    "target,expected",
    [
        ("/data/secret/x", DataClassification.RESTRICTED),
        # Packs render URI-shaped targets (90 of the built-in templates do), so
        # bailing on every "://" made target-based classification a no-op.
        ("file:///data/secret/x", DataClassification.RESTRICTED),
        ("file://host/data/secret/x", DataClassification.RESTRICTED),
        ("file:///data/public/x", None),
        # A remote scheme is not a local path: s3://data/secret is not /data/secret.
        ("s3://data/secret/x", None),
        # Inputs a rendered target can genuinely contain must not raise —
        # classification runs in the decision path, where an exception denies.
        ("file://['/data/secret/x']", DataClassification.RESTRICTED),
        ("file://{path}", None),
        ("file://", None),
        ("", None),
    ],
)
def test_classify_path_handles_file_urls_without_raising(
    tmp_path: Path, target: str, expected: DataClassification | None
) -> None:
    binding = make_binding(
        tmp_path,
        env_overrides={
            session.ENV_CLASSIFICATION_MAP: json.dumps({"/data/secret/*": "restricted"})
        },
    )
    assert binding.classify_path(target) == expected


# ---------------------------------------------------------------------------
# current Claude Code tool surface (2026-08-11)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "tool",
    [
        "ToolSearch", "SendMessage", "Workflow", "ReportFindings", "ScheduleWakeup",
        "TaskCreate", "TaskGet", "TaskList", "TaskUpdate", "EndConversation",
    ],
)
def test_session_internal_tools_are_governed_not_denied(tmp_path: Path, tool: str) -> None:
    """These orchestrate the session; hard-denying them makes it unusable.

    Every one of them was falling through to the unknown-tool deny.
    """
    call = mapping.map_tool_call(tool, {}, make_binding(tmp_path))
    assert call.operation == Operation.READ
    assert call.tier == DataClassification.PUBLIC


@pytest.mark.parametrize(
    "tool", ["ListMcpResourcesTool", "ReadMcpResourceTool", "ReadMcpResourceDirTool"]
)
def test_mcp_resource_tools_map_to_read(tmp_path: Path, tool: str) -> None:
    """The real names carry a `Tool` suffix; the old entry never matched."""
    assert mapping.map_tool_call(tool, {}, make_binding(tmp_path)).operation == Operation.READ


def test_mcp_resource_read_is_classified_by_its_uri(tmp_path: Path) -> None:
    """An MCP resource read names its target in `uri`, not `file_path`.

    Without that key the read had no path at all and took the session default
    tier, so reading a restricted resource evaluated as `internal`.
    """
    binding = make_binding(
        tmp_path,
        env_overrides={
            session.ENV_CLASSIFICATION_MAP: json.dumps({"/data/secret/*": "restricted"})
        },
    )
    call = mapping.map_tool_call(
        "ReadMcpResourceTool", {"uri": "file:///data/secret/x.txt"}, binding
    )
    assert call.operation == Operation.READ
    assert call.tier == DataClassification.RESTRICTED


def test_monitor_goes_through_the_bash_classifier(tmp_path: Path) -> None:
    """Monitor runs a shell command — it must not ride the session-internal path.

    Classified as internal it would be Read/public, so
    `Monitor({command: "rm -rf /data/secret"})` would sail past every control
    that `Bash` with the same string trips.
    """
    binding = make_binding(
        tmp_path,
        env_overrides={
            session.ENV_CLASSIFICATION_MAP: json.dumps({"/data/secret/*": "restricted"})
        },
    )
    call = mapping.map_tool_call("Monitor", {"command": "rm -rf /data/secret"}, binding)
    assert call.operation == Operation.DELETE
    assert call.tier == DataClassification.RESTRICTED


def test_artifact_publish_is_an_outbound_flow_not_a_read(tmp_path: Path) -> None:
    """Publishing a file to the web is Add + egress, never Read on public."""
    binding = make_binding(
        tmp_path,
        env_overrides={
            session.ENV_CLASSIFICATION_MAP: json.dumps({"/data/secret/*": "restricted"})
        },
    )
    call = mapping.map_tool_call(
        "Artifact", {"action": "publish", "file_path": "/data/secret/report.html"}, binding
    )
    assert call.operation == Operation.ADD
    assert call.tier == DataClassification.RESTRICTED
    assert call.egress_destination == "claude.ai"


@pytest.mark.parametrize(
    "action,expected",
    [
        # Inspection actions: they name a `url`, not a `file_path`.
        ("read", Operation.READ),
        ("list", Operation.READ),
        ("comments", Operation.READ),
        ("status", Operation.READ),
        ("watch", Operation.READ),
        ("unwatch", Operation.READ),
        ("resolve", Operation.READ),
        ("list_assets", Operation.READ),
        ("read_asset", Operation.READ),
        # Outbound actions.
        ("publish", Operation.ADD),
        ("reply", Operation.ADD),
        ("upload_asset", Operation.ADD),
        ("resume_replies", Operation.ADD),
        ("delete_asset", Operation.DELETE),
    ],
)
def test_artifact_is_classified_by_its_action(
    tmp_path: Path, action: str, expected: Operation
) -> None:
    """`Artifact` multiplexes on `action`; a uniform Add over-enforces the reads."""
    call = mapping.map_tool_call(
        "Artifact", {"action": action, "url": "https://claude.ai/x"}, make_binding(tmp_path)
    )
    assert call.operation == expected
    assert call.egress_destination == ("claude.ai" if expected is Operation.ADD else None)


@pytest.mark.parametrize("tool_input", [{}, {"action": "teleport"}])
def test_artifact_unknown_action_falls_back_to_add(
    tmp_path: Path, tool_input: dict[str, Any]
) -> None:
    """Fail closed toward the most severe common case, so a new action is never Read."""
    call = mapping.map_tool_call("Artifact", tool_input, make_binding(tmp_path))
    assert call.operation == Operation.ADD
    assert call.egress_destination == "claude.ai"


def test_push_notification_is_an_egress_add(tmp_path: Path) -> None:
    """A notification body can carry arbitrary session content off the machine."""
    call = mapping.map_tool_call(
        "PushNotification", {"message": "done"}, make_binding(tmp_path)
    )
    assert call.operation == Operation.ADD
    assert call.tier is None  # session default tier — the conservative basis
    assert call.egress_destination == "user-device"


@pytest.mark.parametrize(
    "tool,expected",
    [
        ("EnterWorktree", Operation.ADD),
        ("ExitWorktree", Operation.DELETE),  # no action -> the destructive default
        ("CronCreate", Operation.ADD),
        ("CronDelete", Operation.DELETE),
        ("CronList", Operation.READ),
    ],
)
def test_effects_that_outlive_the_session_are_not_internal(
    tmp_path: Path, tool: str, expected: Operation
) -> None:
    call = mapping.map_tool_call(tool, {}, make_binding(tmp_path))
    assert call.operation == expected
    assert call.tier == DataClassification.INTERNAL


@pytest.mark.parametrize(
    "action,expected",
    [
        ("keep", Operation.READ),
        ("remove", Operation.DELETE),
        ("evaporate", Operation.DELETE),  # unknown -> fail closed
    ],
)
def test_exit_worktree_follows_its_action(
    tmp_path: Path, action: str, expected: Operation
) -> None:
    call = mapping.map_tool_call("ExitWorktree", {"action": action}, make_binding(tmp_path))
    assert call.operation == expected


@pytest.mark.parametrize("tool", ["EnterWorktree", "ExitWorktree", "CronCreate"])
def test_effect_tools_pin_a_tier_instead_of_inheriting_the_default(
    tmp_path: Path, tool: str
) -> None:
    """Their target is `session://<Tool>`, not the data the default tier describes.

    Inheriting a `restricted` default put them under the §12.5 immutable floor,
    which no exception process can lift: `ExitWorktree` became Delete on
    Restricted, so a session could enter a worktree and never leave it.
    """
    binding = make_binding(
        tmp_path, env_overrides={session.ENV_DEFAULT_TIER: "restricted"}
    )
    assert mapping.map_tool_call(tool, {}, binding).tier == DataClassification.INTERNAL


@pytest.mark.parametrize("tool", ["RemoteTrigger", "DesignSync"])
def test_unclassified_outward_tools_still_fail_closed(tmp_path: Path, tool: str) -> None:
    """Deliberately unmapped: each changes something off this machine, and
    denying beats guessing at their semantics."""
    with pytest.raises(mapping.UnknownToolError):
        mapping.map_tool_call(tool, {}, make_binding(tmp_path))
