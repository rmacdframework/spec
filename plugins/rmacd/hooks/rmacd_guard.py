#!/usr/bin/env python3
"""Fail-closed entry point for RMACD session governance.

The plugin used to invoke ``python3 -m rmacd.claude_code.hook`` directly. If the
SDK was not importable by *that* interpreter — not installed, installed in a
different venv, a broken install — the process exited non-zero, which Claude
Code treats as a **non-blocking** error. The session then ran completely
ungoverned, and nothing in-session said so. A governance control whose absence
is silent is not a control.

This wrapper closes that hole using only the standard library, so it cannot
itself fail to import:

* SDK importable  -> delegate to the real hook, unchanged behaviour.
* SDK missing AND this session looks bound (a profile source exists) -> ``deny``
  every tool call, with a reason that says how to fix it.
* SDK missing and no profile source -> stay silent. An unbound session is
  explicitly a zero-friction passthrough, and someone who never opted into RMACD
  should not be blocked by a plugin they installed but did not configure.

The bound-detection below deliberately mirrors ``session.resolve_profile_path``
in search order. It only needs to answer "did the user intend governance here?",
so it checks for the *presence* of a profile source rather than parsing it —
a malformed profile is the real hook's problem, and that path already fails
closed on its own.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
from pathlib import Path

# Kept in sync with rmacd.claude_code.session.
ENV_PROFILE_PATH = "RMACD_PROFILE_PATH"
ENV_PROJECT_DIR = "CLAUDE_PROJECT_DIR"
PROJECT_PROFILE_RELPATH = Path(".claude") / "rmacd-profile.json"

INSTALL_HINT = 'pip install "rmacd-framework>=0.14"'


def profile_source(cwd: str | None) -> str | None:
    """Return a description of the profile source, or None when unbound."""
    explicit = os.environ.get(ENV_PROFILE_PATH, "").strip()
    if explicit:
        return f"{ENV_PROFILE_PATH}={explicit}"

    start = Path(cwd) if cwd else Path.cwd()
    # An unreadable or vanished cwd falls back to the literal path.
    with contextlib.suppress(OSError):
        start = start.resolve()

    roots = [start, *start.parents]
    project_dir = os.environ.get(ENV_PROJECT_DIR, "").strip()
    if project_dir:
        roots.append(Path(project_dir))

    for root in roots:
        candidate = root / PROJECT_PROFILE_RELPATH
        try:
            if candidate.is_file():
                return str(candidate)
        except OSError:
            continue
    return None


def event_cwd(event: object) -> str | None:
    """The session cwd carried by the event, if it has one."""
    if isinstance(event, dict) and isinstance(event.get("cwd"), str):
        return event["cwd"]
    return os.environ.get(ENV_PROJECT_DIR) or None


def deny(reason: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def main() -> int:
    raw = sys.stdin.read()

    try:
        import rmacd.claude_code.hook as real_hook
    except Exception as exc:  # noqa: BLE001 - any import failure must fail closed
        try:
            event = json.loads(raw)
        except Exception:  # noqa: BLE001
            event = None

        source = profile_source(event_cwd(event))
        if source is None:
            # Unbound: passthrough, exactly as the real hook would do.
            return 0

        print(
            json.dumps(
                deny(
                    f"RMACD: fail-closed — a governance profile is configured for this "
                    f"session ({source}) but the rmacd SDK could not be imported by "
                    f"{sys.executable}: {type(exc).__name__}: {exc}. Install it with "
                    f"`{INSTALL_HINT}` (or point the hook at the right interpreter via "
                    f"RMACD_PYTHON). Rule: a bound session never runs ungoverned."
                )
            )
        )
        return 0

    # SDK present — hand the already-consumed stdin to the real implementation.
    return real_hook.run(io.StringIO(raw), sys.stdout, sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
