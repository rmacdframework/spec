"""Exception hierarchy raised by the RMACD enforcement layer.

The hierarchy distinguishes *why* a policy operation could not proceed so callers
can react differently. A wrapper around a Claude tool call, for instance, may want
to surface a denial back to the LLM as a tool error (so the agent can adapt and
try a different approach), while a hard prohibition or constraint violation
should be surfaced to the user.

    RMACDError                          base for everything raised by the SDK
    └── RMACDPolicyError                base for policy-driven failures
        ├── RMACDPermissionDeniedError  agent's profile does not grant this (op, tier)
        ├── RMACDProhibitedError        autonomy matrix prohibits this combination
        ├── RMACDConstraintError        env / time window / quota constraint blocked it
        ├── RMACDApprovalRequiredError  approval is needed and no gateway was wired up
        ├── RMACDApprovalDeniedError    human approver said no
        └── RMACDApprovalTimeoutError   approval request timed out
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rmacd.models import PolicyDecision


class RMACDError(Exception):
    """Base for all RMACD-raised errors."""


class RMACDPolicyError(RMACDError):
    """Base for errors driven by a policy decision.

    Carries the underlying ``PolicyDecision`` so callers can inspect the
    autonomy level, blocked reason, and constraints that were evaluated. This
    matters because the *same* tool call site may need to render different
    user-facing messages for "your profile doesn't grant this" vs. "this is
    prohibited for any agent" vs. "approval timed out."
    """

    def __init__(self, message: str, decision: PolicyDecision | None = None) -> None:
        super().__init__(message)
        self.decision = decision


class RMACDPermissionDeniedError(RMACDPolicyError):
    """The agent's profile does not include the requested (operation, classification).

    Distinct from ``RMACDProhibitedError`` because this is a *profile-scoped*
    denial: another agent with a broader profile could perform the same action.
    """


class RMACDProhibitedError(RMACDPolicyError):
    """The autonomy matrix marks this (operation, classification) Prohibited.

    Prohibited means no agent may perform this action autonomously — a human
    must execute it directly. Per spec §12.5 this cannot be bypassed via the
    exception process.
    """


class RMACDConstraintError(RMACDPolicyError):
    """An operational constraint (environment, time window, quota) blocked the call."""


class RMACDToolCapabilityError(RMACDPolicyError):
    """The tool's own capability ceiling does not permit this (operation, tier).

    Distinct from ``RMACDPermissionDeniedError`` (the *agent's profile* doesn't
    grant it) and ``RMACDProhibitedError`` (no agent may ever do it): this means
    *this tool* may not represent the resolved operation — e.g. a read-only tool
    was asked to perform a Change. Raised by
    ``PolicyEnforcer.enforce_tool_call`` when the registry's capability gate
    fails, independently of the agent profile.
    """


class RMACDApprovalRequiredError(RMACDPolicyError):
    """Approval is required but no ``ApprovalGateway`` was configured.

    Raised when ``PolicyEnforcer.enforce()`` is called for an operation whose
    autonomy level is ``approval`` or ``elevated_approval`` and the enforcer
    was constructed without a gateway. Wiring a gateway resolves this; the
    enforcer never silently allows an approval-gated operation.
    """


class RMACDApprovalDeniedError(RMACDPolicyError):
    """The human approver denied the operation."""

    def __init__(
        self,
        message: str,
        decision: PolicyDecision | None = None,
        approver: str | None = None,
        note: str | None = None,
    ) -> None:
        super().__init__(message, decision)
        self.approver = approver
        self.note = note


class RMACDApprovalTimeoutError(RMACDPolicyError):
    """The approval request was not answered within the configured timeout."""

    def __init__(
        self,
        message: str,
        decision: PolicyDecision | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        super().__init__(message, decision)
        self.timeout_seconds = timeout_seconds


class RMACDEgressBlockedError(RMACDPolicyError):
    """A DC2D ``egress_controls`` rule blocked data flow to the destination.

    Raised by callers that use ``PolicyEnforcer.check_egress()`` and choose
    to convert a denial into an exception. The decision object on this
    exception is *not* a ``PolicyDecision`` — egress is checked separately
    from the access decision. Inspect ``destination``, ``tier``, and
    ``matched_rule`` for the specifics.
    """

    def __init__(
        self,
        message: str,
        destination: str | None = None,
        tier: str | None = None,
        matched_rule: str | None = None,
    ) -> None:
        super().__init__(message, decision=None)
        self.destination = destination
        self.tier = tier
        self.matched_rule = matched_rule
