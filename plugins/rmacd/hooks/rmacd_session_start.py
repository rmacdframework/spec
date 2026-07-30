#!/usr/bin/env python3
"""SessionStart notice for RMACD governance state.

Binding problems previously surfaced only as per-tool-call stderr, visible only
under ``--debug``. This says once, at session start, what the governance state
actually is — most importantly when a profile is configured but the SDK is
missing, which is the case that would otherwise run silently ungoverned.

Stdlib-only for the same reason as ``rmacd_guard.py``: it has to work in exactly
the situation where the SDK does not import.
"""

from __future__ import annotations

import sys

from rmacd_guard import INSTALL_HINT, event_cwd, profile_source


def main() -> int:
    source = profile_source(event_cwd(None))

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
