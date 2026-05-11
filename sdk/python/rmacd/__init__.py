"""RMACD Framework SDK - Policy evaluation and enforcement for autonomous AI agents.

This SDK provides tools for:
- Loading and validating RMACD permission profiles (2D, 3D, and DC2D models)
- Evaluating policy decisions (can agent X perform operation Y on data Z?)
- Enforcing decisions at runtime: approval gateways, audit logging, exceptions
- Managing autonomy levels and HITL controls
- Handling emergency escalation logic
- Enforcing time windows and rate limits
- Tool registry for governance and risk assessment

Two layers, two use cases:

1. ``PolicyEvaluator`` — pure decision function. Pass an operation + tier,
   get back a ``PolicyDecision``. No side effects.
2. ``PolicyEnforcer`` — decision + side effects. Routes approval-gated
   operations through an ``ApprovalGateway``, emits ``AuditRecord``s, and
   raises a subclass of ``RMACDPolicyError`` when an operation cannot
   proceed. This is the layer agent frameworks (Claude Agent SDK, LangChain,
   AutoGen) integrate against.

Example - evaluate only::

    from rmacd import ProfileLoader, PolicyEvaluator

    profile = ProfileLoader().load_file("profiles/devops-agent.json")
    decision = PolicyEvaluator(profile).evaluate(operation="C", data_classification="internal")
    print(decision.allowed, decision.autonomy_level)

Example - full enforcement with audit and CLI approval::

    from rmacd import PolicyEnforcer, ProfileLoader
    from rmacd.audit import JSONLAuditLogger

    enforcer = PolicyEnforcer(
        profile=ProfileLoader().load_file("profiles/devops-agent.json"),
        agent_id="devops-agent-001",
        audit_logger=JSONLAuditLogger("audit.jsonl"),
    )
    enforcer.enforce(operation="R", target="server://web-01", classification="internal")

Example - decorator form (spec Appendix C.4)::

    @enforcer.guard(
        operation="C",
        classifier=lambda *, server_id, **_: (f"server://{server_id}", "internal"),
    )
    def update_config(*, server_id: str, config: dict) -> None: ...

Tools Registry usage::

    from rmacd.registry import ToolsRegistry, quick_register

    registry = ToolsRegistry("my-registry")
    quick_register(registry, "file_reader", "File Reader", "R", data_access="internal")
    allowed, reason = registry.validate_tool_access("file_reader", ["R", "M"], "internal")
"""

from rmacd.approval import (
    ApprovalDecision,
    ApprovalGateway,
    ApprovalOutcome,
    ApprovalRequest,
    AutoApproveGateway,
    RejectAllApprovalGateway,
)
from rmacd.audit import (
    AuditExecution,
    AuditLogger,
    AuditOperation,
    AuditPolicyDecision,
    AuditRecord,
    JSONLAuditLogger,
    NullAuditLogger,
)
from rmacd.egress import EgressDecision, EgressGate, PolicyDrivenEgressGate
from rmacd.enforcer import PolicyEnforcer
from rmacd.evaluator import PolicyEvaluator
from rmacd.exceptions import (
    RMACDApprovalDeniedError,
    RMACDApprovalRequiredError,
    RMACDApprovalTimeoutError,
    RMACDConstraintError,
    RMACDEgressBlockedError,
    RMACDError,
    RMACDPermissionDeniedError,
    RMACDPolicyError,
    RMACDProhibitedError,
)
from rmacd.loader import ProfileLoader
from rmacd.models import (
    AutonomyLevel,
    DataAccess,
    DataClassification,
    Operation,
    PolicyDecision,
    Profile2D,
    Profile3D,
    ProfileDC2D,
    TierPolicy,
)
from rmacd.redaction import NullRedactor, RedactionResult, Redactor, RegexRedactor
from rmacd.validator import ProfileValidator

__version__ = "0.5.0"
__all__ = [
    # Core models
    "AutonomyLevel",
    "DataAccess",
    "DataClassification",
    "Operation",
    "PolicyDecision",
    "Profile2D",
    "Profile3D",
    "ProfileDC2D",
    "TierPolicy",
    # Decision / enforcement
    "PolicyEvaluator",
    "PolicyEnforcer",
    "ProfileLoader",
    "ProfileValidator",
    # Approval
    "ApprovalDecision",
    "ApprovalGateway",
    "ApprovalOutcome",
    "ApprovalRequest",
    "AutoApproveGateway",
    "RejectAllApprovalGateway",
    # Audit
    "AuditExecution",
    "AuditLogger",
    "AuditOperation",
    "AuditPolicyDecision",
    "AuditRecord",
    "JSONLAuditLogger",
    "NullAuditLogger",
    # Exceptions
    "RMACDError",
    "RMACDPolicyError",
    "RMACDPermissionDeniedError",
    "RMACDProhibitedError",
    "RMACDConstraintError",
    "RMACDApprovalRequiredError",
    "RMACDApprovalDeniedError",
    "RMACDApprovalTimeoutError",
    "RMACDEgressBlockedError",
    # DC2D data-flow controls
    "NullRedactor",
    "RedactionResult",
    "Redactor",
    "RegexRedactor",
    "EgressDecision",
    "EgressGate",
    "PolicyDrivenEgressGate",
    # Registry available via rmacd.registry
]
