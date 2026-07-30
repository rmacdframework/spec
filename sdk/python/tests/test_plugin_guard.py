"""Tests for the plugin's stdlib-only fail-closed hook wrapper.

``plugins/rmacd/hooks/rmacd_guard.py`` exists because a non-zero hook exit is a
*non-blocking* error in Claude Code: invoking ``python3 -m rmacd.claude_code.hook``
directly meant a missing or broken SDK silently ran the whole session
ungoverned. These tests pin the four states that wrapper has to distinguish.

The wrapper is run as a real subprocess, the way Claude Code runs it.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
GUARD = REPO_ROOT / "plugins" / "rmacd" / "hooks" / "rmacd_guard.py"
SESSION_START = REPO_ROOT / "plugins" / "rmacd" / "hooks" / "rmacd_session_start.py"

PROFILE = {
    "profile_id": "rmacd-3d-guardwrapper-v1",
    "profile_name": "Guard Wrapper Test",
    "model": "three-dimensional",
    "version": "1.0",
    "permissions": {
        "public": ["R"],
        "internal": ["R"],
        "confidential": ["R"],
        "restricted": ["R"],
    },
}

DESTRUCTIVE_EVENT = {
    "tool_name": "Bash",
    "tool_input": {"command": "rm -rf /etc"},
    "session_id": "test-session",
}


@pytest.fixture
def bound_dir(tmp_path: Path) -> Path:
    """A project directory carrying a valid RMACD profile."""
    claude_dir = tmp_path / "bound" / ".claude"
    claude_dir.mkdir(parents=True)
    (claude_dir / "rmacd-profile.json").write_text(json.dumps(PROFILE))
    return tmp_path / "bound"


@pytest.fixture
def unbound_dir(tmp_path: Path) -> Path:
    """A project directory with no profile anywhere above it."""
    d = tmp_path / "unbound"
    d.mkdir()
    return d


@pytest.fixture
def broken_sdk_path(tmp_path: Path) -> str:
    """A PYTHONPATH entry that shadows ``rmacd`` with a failing import.

    Simulating "SDK not installed" by manipulating PYTHONPATH alone does not
    work — the test environment has rmacd installed. Shadowing it with a package
    that raises on import exercises the same `except Exception` path the wrapper
    uses, and does so deterministically regardless of the host environment.
    """
    shadow = tmp_path / "shadow"
    (shadow / "rmacd").mkdir(parents=True)
    (shadow / "rmacd" / "__init__.py").write_text(
        'raise ImportError("simulated missing SDK")'
    )
    return str(shadow)


def run_guard(cwd: Path, *, env_extra: dict[str, str] | None = None) -> str:
    """Run the wrapper with a destructive event and return its stdout."""
    event = dict(DESTRUCTIVE_EVENT, cwd=str(cwd))
    env = {"PATH": "/usr/bin:/bin", "HOME": str(cwd)}
    if env_extra:
        env.update(env_extra)
    result = subprocess.run(
        [sys.executable, str(GUARD)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert result.returncode == 0, f"wrapper must always exit 0: {result.stderr}"
    return result.stdout.strip()


def test_sdk_present_and_bound_delegates_to_real_hook(bound_dir: Path) -> None:
    """With the SDK importable the wrapper is transparent."""
    out = run_guard(bound_dir)
    decision = json.loads(out)["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny"
    # The reason must come from the real evaluator, not the wrapper's fallback.
    assert "fail-closed" not in decision["permissionDecisionReason"]
    assert PROFILE["profile_id"] in decision["permissionDecisionReason"]


def test_sdk_missing_and_bound_denies(bound_dir: Path, broken_sdk_path: str) -> None:
    """The regression this wrapper exists for.

    Previously the hook process exited non-zero, Claude Code treated that as a
    non-blocking error, and the tool call proceeded with no governance at all.
    """
    out = run_guard(bound_dir, env_extra={"PYTHONPATH": broken_sdk_path})
    decision = json.loads(out)["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny"
    reason = decision["permissionDecisionReason"]
    assert "fail-closed" in reason
    # It must say where the profile came from and how to fix the install.
    assert "rmacd-profile.json" in reason
    assert "pip install" in reason


def test_sdk_missing_and_unbound_passes_through(
    unbound_dir: Path, broken_sdk_path: str
) -> None:
    """An unconfigured session must not be blocked by a plugin's absence.

    Unbound is an explicit zero-friction passthrough; emitting no decision keeps
    Claude Code's own permission flow unchanged.
    """
    assert run_guard(unbound_dir, env_extra={"PYTHONPATH": broken_sdk_path}) == ""


def test_sdk_present_and_unbound_passes_through(unbound_dir: Path) -> None:
    """Unbound with a working SDK is also a passthrough."""
    assert run_guard(unbound_dir) == ""


def test_explicit_profile_path_env_counts_as_bound(
    unbound_dir: Path, broken_sdk_path: str, tmp_path: Path
) -> None:
    """RMACD_PROFILE_PATH binds a session even with no .claude directory."""
    profile = tmp_path / "explicit.json"
    profile.write_text(json.dumps(PROFILE))
    out = run_guard(
        unbound_dir,
        env_extra={
            "PYTHONPATH": broken_sdk_path,
            "RMACD_PROFILE_PATH": str(profile),
        },
    )
    decision = json.loads(out)["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny"
    assert "RMACD_PROFILE_PATH" in decision["permissionDecisionReason"]


def test_profile_is_found_from_a_subdirectory(
    bound_dir: Path, broken_sdk_path: str
) -> None:
    """Bound-detection walks upward, matching resolve_profile_path.

    Claude Code changes session cwd routinely; if the wrapper only checked the
    exact cwd it would re-introduce the unbinding bug fixed in 0.14.0.
    """
    deep = bound_dir / "a" / "b" / "c"
    deep.mkdir(parents=True)
    out = run_guard(deep, env_extra={"PYTHONPATH": broken_sdk_path})
    assert json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_malformed_event_with_bound_profile_still_denies(
    bound_dir: Path, broken_sdk_path: str
) -> None:
    """Unparseable stdin must not become a passthrough while bound."""
    result = subprocess.run(
        [sys.executable, str(GUARD)],
        input="not json at all",
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(bound_dir),
            "PYTHONPATH": broken_sdk_path,
            "CLAUDE_PROJECT_DIR": str(bound_dir),
        },
        timeout=60,
    )
    assert result.returncode == 0
    decision = json.loads(result.stdout)["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny"


def test_session_start_warns_when_sdk_missing_but_bound(
    bound_dir: Path, broken_sdk_path: str
) -> None:
    """The SessionStart notice names the problem once, up front."""
    result = subprocess.run(
        [sys.executable, str(SESSION_START)],
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(bound_dir),
            "PYTHONPATH": broken_sdk_path,
            "CLAUDE_PROJECT_DIR": str(bound_dir),
        },
        timeout=60,
    )
    assert result.returncode == 0
    assert "DENIED" in result.stderr
    assert "pip install" in result.stderr


def test_session_start_is_silent_when_unbound_and_sdk_missing(
    unbound_dir: Path, broken_sdk_path: str
) -> None:
    """Installing the plugin without configuring it must not nag."""
    result = subprocess.run(
        [sys.executable, str(SESSION_START)],
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(unbound_dir),
            "PYTHONPATH": broken_sdk_path,
            "CLAUDE_PROJECT_DIR": str(unbound_dir),
        },
        timeout=60,
    )
    assert result.returncode == 0
    assert result.stderr.strip() == ""
