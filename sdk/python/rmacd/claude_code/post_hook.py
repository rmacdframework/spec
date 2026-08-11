"""PostToolUse hook: records the execution outcome of a governed tool call.

The `PreToolUse` hook (``rmacd.claude_code.hook``) records the *decision*. This
one records what happened when the call actually ran, joined to the decision by
``tool_use_id``.

It does not re-derive the call's RMACD terms. `PreToolUse` already classified
it, and re-classifying afterwards produced records that disagreed with their own
decision — see :mod:`rmacd.claude_code.handoff`. Everything this hook needs,
including the resolved audit sink, arrives in the sidecar that `PreToolUse`
wrote, so no profile is loaded and no registry is built here.

No sidecar means nothing to record, and that is the correct outcome in every
case it can happen: the session is unbound, auditing is off, the call was denied
(so it never ran), or the decision hook never got to write one. A fabricated
record would be worse than a missing one.

Unlike `PreToolUse`, this hook never emits a permission decision — the call has
already run, so there is nothing left to gate. Every failure path is
silent-but-noted on stderr: an audit problem must not disturb a session whose
governance already did its job.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, TextIO

from rmacd.claude_code import handoff
from rmacd.claude_code.audit import SessionAuditor, session_context
from rmacd.models import AutonomyLevel, DataClassification, Operation


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


def _enum(factory: Any, raw: object, default: Any) -> Any:
    """Rebuild an enum from its serialized value, tolerating an older sidecar."""
    if not isinstance(raw, str):
        return default
    try:
        return factory(raw)
    except ValueError:
        return default


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

    decision = handoff.take(event.get("session_id"), event.get("tool_use_id"))
    if decision is None:
        return 0

    audit_path = decision.get("audit_path")
    if not isinstance(audit_path, str) or not audit_path:
        return 0

    tier_raw = decision.get("classification")
    status, error = _execution_status(event)

    try:
        tags = decision.get("compliance_tags")
        SessionAuditor(
            Path(audit_path),
            stderr,
            compliance_tags=[t for t in tags if isinstance(t, str)]
            if isinstance(tags, list)
            else None,
        ).execution(
            agent_id=str(decision.get("agent_id") or "claude-code"),
            profile_id=str(decision.get("profile_id") or "unknown"),
            operation=_enum(Operation, decision.get("operation"), Operation.READ),
            target=str(decision.get("target") or ""),
            classification=(
                _enum(DataClassification, tier_raw, None) if tier_raw is not None else None
            ),
            status=status,
            error=error,
            context=session_context(event),
            autonomy_level=_enum(
                AutonomyLevel, decision.get("autonomy_level"), AutonomyLevel.AUTONOMOUS
            ),
            requires_approval=bool(decision.get("requires_approval")),
        )
    except Exception as exc:  # auditing must never break a session
        print(f"RMACD: audit execution record failed: {exc}", file=stderr)
    return 0


def main() -> int:
    return run(sys.stdin, sys.stdout, sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
