#!/usr/bin/env python3
"""PostToolUse entry point: records the outcome of a governed tool call.

Companion to ``rmacd_guard.py``. That hook decides and must fail **closed**;
this one only records, so it fails **silent**.

The asymmetry is deliberate. If the SDK cannot be imported here, the PreToolUse
guard has already denied every call in this session — there is no execution to
record, and emitting an error per tool call would be noise on top of a problem
the user has already been told about, once, at SessionStart.

Like the guard, this checks for a bound profile *before* importing the SDK. An
unbound session governs nothing and therefore audits nothing, so paying ~0.3s of
import per tool call to rediscover that would be pure overhead — and it is the
second such charge on the same call, after the PreToolUse hook.
"""

from __future__ import annotations

import io
import json
import sys

from rmacd_guard import event_cwd, profile_source


def main() -> int:
    raw = sys.stdin.read()

    try:
        event = json.loads(raw)
    except Exception:  # noqa: BLE001
        event = None

    if profile_source(event_cwd(event)) is None:
        return 0  # unbound: nothing was governed, so there is nothing to record

    try:
        from rmacd.claude_code import post_hook
    except Exception:  # noqa: BLE001 - see module docstring
        return 0

    try:
        return post_hook.run(io.StringIO(raw), sys.stdout, sys.stderr)
    except Exception as exc:  # noqa: BLE001 - auditing must never break a session
        print(f"RMACD: audit hook error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
