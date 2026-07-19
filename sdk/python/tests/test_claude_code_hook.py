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
