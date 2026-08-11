#!/usr/bin/env python3
"""SessionStart notice for RMACD governance state.

Binding problems previously surfaced only as per-tool-call stderr, visible only
under ``--debug``. This says once, at session start, what the governance state
actually is — most importantly when a profile is configured but the SDK is
missing, which is the case that would otherwise run silently ungoverned.

Stdlib-only for the same reason as ``rmacd_guard.py``: it has to work in exactly
the situation where the SDK does not import.

The session's directory is taken from the event, the same source the PreToolUse
guard uses. Resolving it from ``CLAUDE_PROJECT_DIR`` alone — as this did before —
disagreed with the guard whenever a subdirectory carried its own profile: the
banner announced an ungoverned session while every tool call in it was in fact
being governed. That matters more now than it reads, because the guard
short-circuits unbound sessions before the SDK loads, so this notice is the only
statement of governance state a plugin user ever sees.
"""

from __future__ import annotations

import contextlib
import json
import sys
from typing import Any

from rmacd_guard import INSTALL_HINT, event_cwd, profile_source


def read_event() -> dict[str, Any] | None:
    """The hook event on stdin, or None if there isn't a usable one.

    Never blocks on an interactive terminal: this script is also run by hand
    when diagnosing a session, and a bare ``read()`` against a tty would hang
    instead of reporting anything.
    """
    stream = sys.stdin
    if stream is None:
        return None
    with contextlib.suppress(Exception):
        if stream.isatty():
            return None
    try:
        parsed = json.loads(stream.read())
    except Exception:  # noqa: BLE001 - any unreadable event just falls back
        return None
    return parsed if isinstance(parsed, dict) else None


def main() -> int:
    source = profile_source(event_cwd(read_event()))

    try:
        import rmacd  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        if source is not None:
            print(
                f"RMACD: a governance profile is configured ({source}) but the rmacd "
                f"SDK could not be imported by {sys.executable}: "
                f"{type(exc).__name__}: {exc}\n"
                f"RMACD: every tool call in this session will be DENIED until you run "
                f"`{INSTALL_HINT}`.",
                file=sys.stderr,
            )
        # Unbound + no SDK is a non-event: the user installed the plugin but has
        # not opted into governance. Say nothing.
        return 0

    if source is None:
        print(
            "RMACD: no profile bound — this session is ungoverned. "
            "Run /rmacd:init to bind one.",
            file=sys.stderr,
        )
    else:
        print(f"RMACD: governance active (profile source: {source}).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
