"""PostToolUse hook: records the execution outcome of a governed tool call.

The `PreToolUse` hook (``rmacd.claude_code.hook``) records the *decision*. This
one records what happened when the call actually ran, joined to the decision by
``tool_use_id``.

Unlike `PreToolUse`, this hook never emits a permission decision — the call has
already run, so there is nothing left to gate. It writes one record and exits 0.
Every failure path is silent-but-noted on stderr: an audit problem must not
disturb a session whose governance already did its job.
"""

from __future__ import annotations

import json
import sys
from typing import Any, TextIO

from rmacd.claude_code import mapping, session
from rmacd.claude_code.audit import SessionAuditor, resolve_audit_path, session_context
from rmacd.models import Operation


def _execution_status(event: dict[str, Any]) -> tuple[str, str | None]:
    """Map a PostToolUse event to an (status, error) pair.

    Claude Code reports failures in different shapes depending on the tool, so
    treat any of the documented error signals as a failure and fall back to
    SUCCESS only when none is present.
    """
    response = event.get("tool_response")

    if isinstance(response, dict):
        for key in ("error", "errorMessage", "error_message"):
            value = response.get(key)
            if isinstance(value, str) and value:
                return "FAILURE", value
        # Some tools report a boolean flag alongside a separate message.
        if response.get("is_error") or response.get("isError"):
            detail = response.get("message") or response.get("content")
            return "FAILURE", str(detail) if detail else "tool reported an error"

    if isinstance(response, str) and response.startswith("Error:"):
        return "FAILURE", response

    return "SUCCESS", None


def run(stdin: TextIO, stdout: TextIO, stderr: TextIO) -> int:
    """Read one PostToolUse event, append one execution record. Exit 0 always."""
    del stdout  # this hook emits no decision

    raw = stdin.read()
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return 0
    if not isinstance(parsed, dict):
        return 0
    event: dict[str, Any] = parsed

    cwd = event.get("cwd")
    try:
        binding = session.bind_session(cwd=cwd if isinstance(cwd, str) else None)
    except session.SessionBindingError:
        # PreToolUse already denied everything in this session; there is no
        # execution to record.
        return 0
    if binding is None:
        return 0  # unbound session: nothing is governed, nothing to audit

    auditor = SessionAuditor(resolve_audit_path(binding.profile_path), stderr)
    if not auditor.enabled:
        return 0

    tool_name = str(event.get("tool_name") or "")
    raw_input = event.get("tool_input")
    tool_input: dict[str, Any] = raw_input if isinstance(raw_input, dict) else {}

    # Re-map the call so the execution record carries the same operation,
    # target and tier as its decision record — the two are meant to be read
    # together. A tool that cannot be mapped here was denied at PreToolUse and
    # so cannot have executed; recording it would be a false entry.
    try:
        call = mapping.map_tool_call(tool_name, tool_input, binding)
    except (mapping.UnknownToolError, mapping.CapabilityCeilingError):
        return 0
    except Exception as exc:  # never let audit mapping break the session
        print(f"RMACD: audit mapping failed for '{tool_name}': {exc}", file=stderr)
        return 0

    tier = call.tier
    if tier is None and not binding.is_2d:
        tier = binding.default_tier

    status, error = _execution_status(event)
    auditor.execution(
        agent_id=binding.agent_id,
        profile_id=binding.profile_id,
        operation=call.operation if isinstance(call.operation, Operation) else Operation.READ,
        target=call.target,
        classification=tier,
        status=status,
        error=error,
        context=session_context(event),
    )
    return 0


def main() -> int:
    return run(sys.stdin, sys.stdout, sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
