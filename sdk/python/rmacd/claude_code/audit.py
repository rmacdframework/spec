"""Audit trail for governed Claude Code sessions.

Until now a governed session produced **no** audit records at all: the
`PreToolUse` hook is deliberately side-effect-free and uses ``evaluate_only``,
so nothing was ever written. For a product whose headline claim is audit
evidence, that was the largest gap between claim and behaviour.

Two hooks, two record kinds, joined on ``tool_use_id``:

* ``PreToolUse`` writes the **decision** — ALLOW, DENY, or QUEUED. This is the
  half that matters most, because a denied call never reaches ``PostToolUse``:
  a PostToolUse-only trail would silently omit every denial, which is precisely
  the evidence an auditor asks for.
* ``PostToolUse`` writes the **execution** outcome for calls that ran.

Records carry the Claude Code ``session_id``, ``tool_use_id``, and — when the
call came from a subagent — its ``agent_id`` and ``agent_type``, so a decision
made inside a subagent is attributable rather than indistinguishable from the
main conversation.

Writing is **best-effort and never fails the hook**. An audit sink that cannot
be written is a deployment problem; turning it into a denial would take a
working session down over bookkeeping, and turning it into an exception would
fail the hook closed for the same reason. Failures go to stderr.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, TextIO

from rmacd.audit import AuditExecution, JSONLAuditLogger, build_audit_record
from rmacd.models import (
    AutonomyLevel,
    DataClassification,
    Operation,
    PolicyDecision,
)

#: Explicit sink path. Wins over the default location.
ENV_AUDIT_PATH = "RMACD_AUDIT_PATH"
#: Set to a false-y value ("0", "off", "false", "no") to disable session audit.
ENV_AUDIT = "RMACD_AUDIT"

#: Default sink, resolved next to the bound profile. A session is only audited
#: because a profile bound it, so the profile's directory is where the evidence
#: belongs.
DEFAULT_AUDIT_RELNAME = "rmacd-audit.jsonl"

_FALSEY = {"0", "off", "false", "no"}


def audit_enabled(env: dict[str, str] | None = None) -> bool:
    """Whether session audit is switched on (default: yes)."""
    environ = env if env is not None else dict(os.environ)
    return environ.get(ENV_AUDIT, "").strip().lower() not in _FALSEY


def resolve_audit_path(
    profile_path: Path | None, env: dict[str, str] | None = None
) -> Path | None:
    """The sink this session writes to, or None when audit is off.

    ``RMACD_AUDIT_PATH`` wins outright; otherwise the record lands beside the
    profile that bound the session.
    """
    environ = env if env is not None else dict(os.environ)
    if not audit_enabled(environ):
        return None

    explicit = environ.get(ENV_AUDIT_PATH, "").strip()
    if explicit:
        return Path(explicit)

    if profile_path is None:
        return None
    return profile_path.parent / DEFAULT_AUDIT_RELNAME


def session_context(event: dict[str, Any]) -> dict[str, Any]:
    """Session/subagent identity carried on a hook event.

    ``agent_id``/``agent_type`` are present only when the tool call was made
    inside a subagent, so their absence is itself meaningful: the call came from
    the main conversation.
    """
    context: dict[str, Any] = {}
    for key in ("session_id", "tool_use_id", "tool_name", "agent_id", "agent_type"):
        value = event.get(key)
        if isinstance(value, str) and value:
            context[key] = value
    cwd = event.get("cwd")
    if isinstance(cwd, str) and cwd:
        context["cwd"] = cwd
    return context


class SessionAuditor:
    """Best-effort audit sink for one hook invocation."""

    def __init__(self, path: Path | None, stderr: TextIO | None = None) -> None:
        self._path = path
        self._stderr = stderr
        self._logger: JSONLAuditLogger | None = None

    @property
    def enabled(self) -> bool:
        return self._path is not None

    def _sink(self) -> JSONLAuditLogger | None:
        if self._path is None:
            return None
        if self._logger is None:
            self._logger = JSONLAuditLogger(self._path)
        return self._logger

    def _write(self, record: Any) -> None:
        sink = self._sink()
        if sink is None:
            return
        try:
            sink.log(record)
        except OSError as exc:  # unwritable sink must not break the session
            if self._stderr is not None:
                print(
                    f"RMACD: audit write failed ({self._path}): {exc}",
                    file=self._stderr,
                )

    def decision(
        self,
        *,
        agent_id: str,
        profile_id: str,
        operation: Operation,
        target: str,
        classification: DataClassification | None,
        decision: PolicyDecision | None,
        result: str,
        blocked_reason: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Record one governance decision.

        ``decision`` is None for the paths that deny before an evaluation runs
        (unknown tool, capability ceiling); a synthetic PROHIBITED decision
        stands in so those denials are still first-class records rather than
        gaps in the trail.
        """
        if not self.enabled:
            return

        if decision is None:
            decision = PolicyDecision(
                allowed=False,
                operation=operation,
                data_classification=classification,
                autonomy_level=AutonomyLevel.PROHIBITED,
                requires_approval=False,
                requires_notification=False,
                blocked_reason=blocked_reason,
            )

        self._write(
            build_audit_record(
                agent_id=agent_id,
                profile_id=profile_id,
                operation=operation,
                target=target,
                classification=classification,
                decision=decision,
                result=result,
                extra=context or None,
            )
        )

    def execution(
        self,
        *,
        agent_id: str,
        profile_id: str,
        operation: Operation,
        target: str,
        classification: DataClassification | None,
        status: str,
        error: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Record the outcome of a call that actually ran."""
        if not self.enabled:
            return

        decision = PolicyDecision(
            allowed=True,
            operation=operation,
            data_classification=classification,
            autonomy_level=AutonomyLevel.AUTONOMOUS,
            requires_approval=False,
            requires_notification=False,
        )
        self._write(
            build_audit_record(
                agent_id=agent_id,
                profile_id=profile_id,
                operation=operation,
                target=target,
                classification=classification,
                decision=decision,
                result="EXECUTED",
                execution=AuditExecution(status=status, error=error),
                extra=context or None,
            )
        )


__all__ = [
    "DEFAULT_AUDIT_RELNAME",
    "ENV_AUDIT",
    "ENV_AUDIT_PATH",
    "SessionAuditor",
    "audit_enabled",
    "resolve_audit_path",
    "session_context",
]
