"""Audit logging for RMACD policy decisions.

Every enforced operation generates an ``AuditRecord``. The format mirrors the
spec Appendix C.6 audit_record example so records produced by this SDK drop
into the spec's audit-pipeline architecture without translation.

``AuditLogger`` is a ``Protocol`` so callers can plug in their own sink
(syslog, SIEM, OpenTelemetry, etc.). Two implementations ship with the SDK:

- ``JSONLAuditLogger`` writes JSON Lines to a path or file-like object. Use
  it when the deployment's audit pipeline accepts JSONL on disk or via a
  tailing collector. Deployments subject to ``immutable_logging`` audit
  requirements from §10 implement ``AuditLogger`` against a WORM-backed
  sink (S3 Object Lock, Azure Immutable Blob, an immutable-log appliance).
- ``NullAuditLogger`` discards records. Used as the default when no logger is
  configured so the enforcer never blocks on audit-side failures.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Any, Protocol

from pydantic import BaseModel, Field

from rmacd.models import (
    AutonomyLevel,
    DataClassification,
    Operation,
    PolicyDecision,
)


class AuditOperation(BaseModel):
    """Operation block in an audit record."""

    type: Operation
    target: str = Field(description="Resource identifier the operation acted on")
    classification: DataClassification | None = None


class AuditPolicyDecision(BaseModel):
    """Policy-decision block in an audit record."""

    result: str = Field(description="ALLOW | DENY | QUEUED | APPROVED | REJECTED")
    autonomy_level: AutonomyLevel
    blocked_reason: str | None = None
    approval_id: str | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    constraints_applied: list[str] = Field(default_factory=list)
    emergency_mode: bool = False


class AuditExecution(BaseModel):
    """Execution-result block. Populated after the underlying operation runs."""

    status: str = Field(description="SUCCESS | FAILURE | SKIPPED")
    duration_ms: int | None = None
    error: str | None = None


class AuditRecord(BaseModel):
    """One enforced operation. Schema-compatible with spec Appendix C.6."""

    record_id: str = Field(default_factory=lambda: f"aud-{uuid.uuid4().hex[:16]}")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    agent_id: str
    profile_id: str
    operation: AuditOperation
    policy_decision: AuditPolicyDecision
    execution: AuditExecution | None = None
    compliance_tags: list[str] = Field(default_factory=list)
    #: Sink-specific context that is not part of the C.6 shape — session id,
    #: tool-use id, subagent identity. Omitted entirely from serialized output
    #: when unset, so records from callers that do not use it stay byte-for-byte
    #: identical to Appendix C.6.
    extra: dict[str, Any] | None = None


class AuditLogger(Protocol):
    """Sink for audit records.

    Implementations should be non-blocking on the hot path. If the underlying
    write may fail or be slow, buffer or hand off to a background worker rather
    than letting the enforcer's caller stall.
    """

    def log(self, record: AuditRecord) -> None:
        """Persist ``record``. Must not raise on the hot path."""
        ...


class NullAuditLogger:
    """Drops every record. The enforcer's default when no logger is configured.

    Why default to a no-op rather than raise: an unconfigured audit sink is a
    deployment misconfiguration, but failing closed (blocking every operation)
    would be worse than allowing operations to proceed unaudited. Surfacing
    this should be a deployment check, not a hot-path failure.
    """

    def log(self, record: AuditRecord) -> None:  # noqa: D401 - intentional no-op
        return None


def compliance_tags_for(profile: object) -> list[str]:
    """The profile's declared compliance tags, or an empty list.

    Every audit record should carry these so a trail can be sliced per
    regulation (§10.4). Kept here rather than on the enforcer because the
    Claude Code session auditor needs it too and does not construct one.
    """
    requirements = getattr(profile, "audit_requirements", None)
    tags = getattr(requirements, "compliance_tags", None) if requirements else None
    return [t.value for t in tags] if tags else []


class JSONLAuditLogger:
    """Writes audit records as JSON Lines.

    Accepts either a filesystem path (opens in append mode) or any pre-opened
    file-like object with a ``.write()`` method (useful for ``sys.stdout`` in
    development and for in-memory testing).
    """

    def __init__(self, sink: str | Path | IO[str]) -> None:
        self._path: Path | None
        self._stream: IO[str] | None
        if isinstance(sink, (str, Path)):
            self._path = Path(sink)
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._stream = None
        else:
            self._path = None
            self._stream = sink

    def log(self, record: AuditRecord) -> None:
        # `extra` is dropped when unset rather than serialized as null, so a
        # record from a caller that never uses it matches Appendix C.6 exactly.
        exclude = {"extra"} if record.extra is None else None
        line = record.model_dump_json(exclude=exclude) + "\n"
        if self._stream is not None:
            self._stream.write(line)
            self._stream.flush()
            return
        assert self._path is not None
        with self._path.open("a", encoding="utf-8") as f:
            f.write(line)


def build_audit_record(
    *,
    agent_id: str,
    profile_id: str,
    operation: Operation,
    target: str,
    classification: DataClassification | None,
    decision: PolicyDecision,
    result: str,
    approval_id: str | None = None,
    approver: str | None = None,
    approved_at: datetime | None = None,
    execution: AuditExecution | None = None,
    compliance_tags: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> AuditRecord:
    """Construct an ``AuditRecord`` from a ``PolicyDecision``.

    Centralises the policy→audit mapping so every code path produces records
    with the same shape. ``extra`` carries sink-specific context outside the
    C.6 shape (session id, tool-use id, subagent identity); it is omitted from
    serialized output when unset.
    """
    return AuditRecord(
        extra=extra,
        agent_id=agent_id,
        profile_id=profile_id,
        operation=AuditOperation(
            type=operation,
            target=target,
            classification=classification,
        ),
        policy_decision=AuditPolicyDecision(
            result=result,
            autonomy_level=decision.autonomy_level,
            blocked_reason=decision.blocked_reason,
            approval_id=approval_id,
            approved_by=approver,
            approved_at=approved_at,
            constraints_applied=list(decision.constraints_applied),
            emergency_mode=decision.emergency_mode,
        ),
        execution=execution,
        compliance_tags=compliance_tags or [],
    )


def json_default(value: Any) -> str:
    """JSON encoder fallback for stdlib ``json.dumps`` callers."""
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


__all__ = [
    "AuditExecution",
    "AuditLogger",
    "AuditOperation",
    "AuditPolicyDecision",
    "AuditRecord",
    "JSONLAuditLogger",
    "NullAuditLogger",
    "build_audit_record",
    "json_default",
]


# Silence pyflakes for the conditionally-used json import; keep available for
# downstream subclassers who want to extend the writer.
_ = json
