"""Approval gateway for RMACD operations whose autonomy level requires a human.

When the evaluator returns a decision with ``requires_approval=True``, the
enforcer hands an ``ApprovalRequest`` to a gateway implementation and waits for
an ``ApprovalDecision``. The gateway is a pluggable ``Protocol`` so integrators
can wire approvals to whatever workflow system they already use (ServiceNow,
Jira, Slack, a webhook, a CLI prompt, an in-memory queue for tests).

The synchronous interface here is deliberate: it keeps the enforcer's contract
simple and matches the Appendix C.5 approval-request shape. For long-running
approvals an integrator should subclass ``ApprovalGateway`` so the ``request``
call internally suspends or polls — the enforcer simply waits for the
``ApprovalDecision`` to arrive, whether that takes 30 seconds or 30 minutes.

Two reference gateways ship with the SDK:

- ``RejectAllApprovalGateway`` — used as the enforcer's default. Approvals
  always fail unless an integrator explicitly opts in to one. Failing closed
  is the right default for a governance SDK: an approval-gated operation that
  silently proceeds is a worse failure than one that raises.
- ``AutoApproveGateway`` — approves every request without human review.
  Used in unit tests and deterministic scripted demos where the goal is
  to verify the approval *flow* fires; not appropriate where an actual
  approval decision is required.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol

from pydantic import BaseModel, Field

from rmacd.models import AutonomyLevel, DataClassification, Operation


class ApprovalOutcome(str, Enum):
    """Terminal states for an approval request."""

    APPROVED = "approved"
    DENIED = "denied"
    TIMEOUT = "timeout"


class ApprovalRequest(BaseModel):
    """One approval request. Shape mirrors spec Appendix C.5."""

    request_id: str = Field(default_factory=lambda: f"apr-{uuid.uuid4().hex[:16]}")
    agent_id: str
    profile_id: str
    operation: Operation
    target: str = Field(description="Resource identifier (URI, path, ID)")
    classification: DataClassification | None = None
    autonomy_level: AutonomyLevel = Field(
        description="approval | elevated_approval — drives approver routing"
    )
    justification: str | None = None
    timeout_seconds: int = Field(default=300, ge=1)
    metadata: dict[str, Any] | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ApprovalDecision(BaseModel):
    """Result of an approval request."""

    request_id: str
    outcome: ApprovalOutcome
    approver: str | None = None
    decided_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    note: str | None = None


class ApprovalGateway(Protocol):
    """Pluggable approval surface.

    Implementations must return an ``ApprovalDecision`` within a bounded time;
    the enforcer relies on this to avoid hanging indefinitely. A gateway that
    cannot reach an approver within ``request.timeout_seconds`` should return
    ``ApprovalOutcome.TIMEOUT`` rather than raise.
    """

    def request(self, req: ApprovalRequest) -> ApprovalDecision: ...


class RejectAllApprovalGateway:
    """Denies every approval. The enforcer's default.

    Why this is the default: a freshly-instantiated enforcer with no approval
    gateway configured should not silently allow approval-gated operations.
    Forcing the integrator to opt in to a gateway makes the wiring explicit.
    """

    def request(self, req: ApprovalRequest) -> ApprovalDecision:
        return ApprovalDecision(
            request_id=req.request_id,
            outcome=ApprovalOutcome.DENIED,
            approver=None,
            note="No approval gateway configured (RejectAllApprovalGateway is the default).",
        )


class AutoApproveGateway:
    """Approves every request without human review.

    Tagged with ``approver="auto-approve-gateway"`` so audit records make
    it unambiguous that no human was involved. Use in unit tests and in
    deterministic scripted demos where the agent must reach the
    post-approval code path; do not use where an actual approval
    decision is required.
    """

    def request(self, req: ApprovalRequest) -> ApprovalDecision:
        return ApprovalDecision(
            request_id=req.request_id,
            outcome=ApprovalOutcome.APPROVED,
            approver="auto-approve-gateway",
            note="Approved without human review by AutoApproveGateway.",
        )


__all__ = [
    "ApprovalDecision",
    "ApprovalGateway",
    "ApprovalOutcome",
    "ApprovalRequest",
    "AutoApproveGateway",
    "RejectAllApprovalGateway",
]
