"""RMACD session governance for Claude Code.

This package makes RMACD govern a Claude Code session *itself*: a bound
profile gates the session's own Bash/Edit/Write/MCP tool calls through a
``PreToolUse`` command hook, and ``/rmacd:status`` reports the binding.

Entry points (both stdlib-invocable, no extra dependencies):

- ``python3 -m rmacd.claude_code.hook`` — reads the Claude Code PreToolUse
  JSON event on stdin and writes the hook JSON decision on stdout.
- ``python3 -m rmacd.claude_code.status`` — renders the bound profile, its
  effective autonomy matrix, bound packs, and the session's fail-mode knobs.
- ``python3 -m rmacd.claude_code [hook|status]`` — dispatching alias.

Fail modes (normative, from the c2 spec):

- No profile bound → passthrough (the hook emits no decision; Claude Code's
  own permission flow proceeds unchanged) with a one-time stderr notice.
- Profile bound but the hook errors → **fail closed** (deny with diagnostic).
- Profile bound, unknown MCP tool → deny by default; ``RMACD_UNKNOWN_TOOL=ask``
  downgrades to Claude Code's own permission prompt.
- SDK not installed **and a profile is bound** → **fail closed**. A non-zero
  hook exit is a *non-blocking* error in Claude Code, so this used to run the
  whole session ungoverned. The plugin now invokes a stdlib-only wrapper
  (``plugins/rmacd/hooks/rmacd_guard.py``) that denies when ``import rmacd``
  fails while a profile source exists, and warns once at ``SessionStart``.
- SDK not installed and **no** profile bound → passthrough, unchanged.
"""

from rmacd.claude_code.mapping import (
    CapabilityCeilingError,
    MappedCall,
    UnknownToolError,
    map_tool_call,
)
from rmacd.claude_code.session import (
    SessionBinding,
    SessionBindingError,
    bind_session,
    resolve_profile_path,
)

__all__ = [
    "CapabilityCeilingError",
    "MappedCall",
    "SessionBinding",
    "SessionBindingError",
    "UnknownToolError",
    "bind_session",
    "map_tool_call",
    "resolve_profile_path",
]
