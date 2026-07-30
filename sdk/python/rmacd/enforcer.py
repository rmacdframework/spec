"""Policy enforcement layer for RMACD profiles.

``PolicyEvaluator`` answers "is this allowed?" as a pure decision function.
``PolicyEnforcer`` is the layer on top that actually *does* something with that
decision: routes approval-gated operations through an ``ApprovalGateway``,
emits ``AuditRecord``s, and raises the appropriate exception when an operation
cannot proceed.

This is the class that the Appendix C.4 ``@enforcer.guard`` SDK example
references but that did not previously exist in the SDK — it is the
integration point every agent framework needs (Claude Agent SDK, LangChain,
AutoGen, etc.) so they can drop RMACD enforcement into a tool-call site
without reimplementing the decision→action plumbing each time.

Three call shapes are supported:

1. ``enforcer.enforce(operation, target, classification)`` — imperative.
   Returns the ``PolicyDecision`` if allowed, raises a subclass of
   ``RMACDPolicyError`` otherwise. The "evaluate then act" pattern most
   integrations will use.
2. ``@enforcer.guard(operation, classifier)`` — decorator that wraps a Python
   function. The classifier callable receives the wrapped function's keyword
   arguments and returns ``(target, classification)``. This is the Appendix
   C.4 shape; convenient for hand-written tool functions.
3. ``enforcer.evaluate_only(...)`` — runs the decision without side effects
   (no audit log, no approval). Useful for "dry run" UX surfaces where the
   agent wants to know whether something *would* be allowed before committing.
"""

from __future__ import annotations

import functools
import inspect
import logging
import os
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, TypeVar

from rmacd.approval import (
    ApprovalDecision,
    ApprovalGateway,
    ApprovalOutcome,
    ApprovalRequest,
    RejectAllApprovalGateway,
)
from rmacd.audit import (
    AuditExecution,
    AuditLogger,
    NullAuditLogger,
    build_audit_record,
)
from rmacd.egress import EgressDecision, EgressGate, PolicyDrivenEgressGate
from rmacd.evaluator import DEFAULT_AUTONOMY_3D, AnyProfile, PolicyEvaluator
from rmacd.exceptions import (
    RMACDApprovalDeniedError,
    RMACDApprovalRequiredError,
    RMACDApprovalTimeoutError,
    RMACDConstraintError,
    RMACDEgressBlockedError,
    RMACDPermissionDeniedError,
    RMACDProhibitedError,
    RMACDToolCapabilityError,
)
from rmacd.loader import ProfileLoader
from rmacd.models import (
    AutonomyLevel,
    DataClassification,
    EgressControls,
    Environment,
    EvaluationContext,
    Operation,
    PolicyDecision,
    Profile3D,
    ProfileDC2D,
    RedactionPolicy,
)
from rmacd.redaction import NullRedactor, RedactionResult, Redactor, RegexRedactor
from rmacd.registry.tools import ToolsRegistry

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

# Type alias for the classifier function used by @guard. It receives the
# wrapped function's call kwargs and returns (target, classification). The
# return type is permissive (str | None for classification) because some
# operations (e.g., 2D profiles, public-only tools) don't need a tier.
ClassifierFn = Callable[..., "tuple[str, DataClassification | str | None]"]


class PolicyEnforcer:
    """Decision + side-effects layer over a ``PolicyEvaluator``.

    Holds the agent's identity (so audit records are attributable), an
    ``ApprovalGateway`` (default ``RejectAllApprovalGateway`` so unconfigured
    deployments fail closed), and an ``AuditLogger`` (default
    ``NullAuditLogger`` so the hot path never blocks on audit failures).
    """

    def __init__(
        self,
        profile: AnyProfile,
        agent_id: str,
        *,
        approval_gateway: ApprovalGateway | None = None,
        audit_logger: AuditLogger | None = None,
        environment: Environment | None = None,
        redactor: Redactor | None = None,
        egress_gate: EgressGate | None = None,
        registry: ToolsRegistry | None = None,
    ) -> None:
        self.profile = profile
        self.agent_id = agent_id
        self.evaluator = PolicyEvaluator(profile)
        # Optional tools registry: the authoritative tool→RMACD classifier and
        # capability ceiling consulted by ``enforce_tool_call``.
        self.registry = registry
        self.approval_gateway: ApprovalGateway = (
            approval_gateway if approval_gateway is not None else RejectAllApprovalGateway()
        )
        self.audit_logger: AuditLogger = (
            audit_logger if audit_logger is not None else NullAuditLogger()
        )
        self.environment = environment
        self._compliance_tags = self._extract_compliance_tags(profile)
        # DC2D-specific surfaces. The default redactor depends on the
        # profile type: NullRedactor (pass-through) for non-DC2D profiles
        # so callers who never asked for redaction don't get it, and
        # RegexRedactor for DC2D profiles to cover the standard PII
        # patterns. Pass ``redactor=`` to substitute a dedicated PII
        # engine (Presidio, Macie, Purview, etc.).
        self._is_dc2d = isinstance(profile, ProfileDC2D)
        if redactor is not None:
            self.redactor: Redactor = redactor
        elif self._is_dc2d:
            self.redactor = RegexRedactor()
        else:
            self.redactor = NullRedactor()
        self.egress_gate: EgressGate = (
            egress_gate if egress_gate is not None else PolicyDrivenEgressGate()
        )

    # ----- construction helpers ------------------------------------------------

    @classmethod
    def from_env(
        cls,
        *,
        agent_id_var: str = "RMACD_AGENT_ID",
        profile_var: str = "RMACD_PROFILE_PATH",
        environment_var: str = "RMACD_ENVIRONMENT",
        approval_gateway: ApprovalGateway | None = None,
        audit_logger: AuditLogger | None = None,
    ) -> PolicyEnforcer:
        """Construct an enforcer from environment variables.

        Closes the profile-binding gap (spec §C.2 leaves "how does the agent
        know its profile?" implicit): set ``RMACD_PROFILE_PATH`` and
        ``RMACD_AGENT_ID`` and the agent self-binds at startup. Explicit
        constructor arguments remain available for callers who load profiles
        from a policy store rather than the filesystem.
        """
        agent_id = os.environ.get(agent_id_var)
        if not agent_id:
            raise ValueError(
                f"Environment variable {agent_id_var} is not set; "
                f"either set it or pass agent_id explicitly to PolicyEnforcer()."
            )
        profile_path = os.environ.get(profile_var)
        if not profile_path:
            raise ValueError(
                f"Environment variable {profile_var} is not set; "
                f"either set it or pass profile explicitly to PolicyEnforcer()."
            )
        profile = ProfileLoader().load_file(Path(profile_path))
        env: Environment | None = None
        env_value = os.environ.get(environment_var)
        if env_value:
            env = Environment(env_value)
        return cls(
            profile=profile,
            agent_id=agent_id,
            approval_gateway=approval_gateway,
            audit_logger=audit_logger,
            environment=env,
        )

    # ----- core API ------------------------------------------------------------

    def evaluate_only(
        self,
        operation: Operation | str,
        target: str,
        classification: DataClassification | str | None = None,
        *,
        context: EvaluationContext | None = None,
    ) -> PolicyDecision:
        """Run the decision without approval or audit side effects.

        Useful for dry-run surfaces ("would this be allowed?") and for cases
        where the caller wants to render different UX before paying the cost
        of an approval round-trip.
        """
        del target  # decision is target-agnostic; arg kept for symmetry
        return self.evaluator.evaluate(
            operation=operation,
            data_classification=classification,
            context=context or self._default_context(),
        )

    def enforce(
        self,
        operation: Operation | str,
        target: str,
        classification: DataClassification | str | None = None,
        *,
        justification: str | None = None,
        context: EvaluationContext | None = None,
    ) -> PolicyDecision:
        """Evaluate, run approvals if required, audit, and either return or raise.

        Returns the ``PolicyDecision`` for allowed operations (the caller can
        inspect ``autonomy_level`` to e.g. trigger an enhanced-logging branch).
        Raises a subclass of ``RMACDPolicyError`` for any non-allowed outcome.

        The exception type tells the caller *why* the operation was blocked,
        which is what lets a tool-call wrapper render distinct user-facing
        messages for "your profile doesn't grant this" vs. "this is prohibited
        for any agent" vs. "approval was denied."
        """
        op = Operation(operation) if isinstance(operation, str) else operation
        tier: DataClassification | None
        if isinstance(classification, str):
            tier = DataClassification(classification)
        else:
            tier = classification

        decision = self.evaluator.evaluate(
            operation=op,
            data_classification=tier,
            context=context or self._default_context(),
        )

        # Hard failures: profile doesn't grant, autonomy says prohibited,
        # constraints (env / time / quota) blocked it.
        if not decision.allowed:
            self._audit(
                operation=op,
                target=target,
                classification=tier,
                decision=decision,
                result="DENY",
            )
            raise self._classify_denial(decision)

        # Approval-gated path: synchronous request through the gateway. The
        # gateway is responsible for honouring its own timeout; the enforcer
        # just translates the returned outcome.
        if decision.requires_approval:
            req = ApprovalRequest(
                agent_id=self.agent_id,
                profile_id=self._profile_id(),
                operation=op,
                target=target,
                classification=tier,
                autonomy_level=decision.autonomy_level,
                justification=justification,
            )
            self._audit(
                operation=op,
                target=target,
                classification=tier,
                decision=decision,
                result="QUEUED",
                approval_id=req.request_id,
            )
            try:
                approval = self.approval_gateway.request(req)
            except Exception as exc:  # gateway crashed — treat as denial
                self._audit(
                    operation=op,
                    target=target,
                    classification=tier,
                    decision=decision,
                    result="DENY",
                    approval_id=req.request_id,
                )
                raise RMACDApprovalRequiredError(
                    f"Approval gateway raised while requesting approval: {exc}",
                    decision=decision,
                ) from exc
            self._handle_approval_outcome(approval, decision, op, target, tier, req)

        # Allowed (or just-approved). Final audit record + return.
        self._audit(
            operation=op,
            target=target,
            classification=tier,
            decision=decision,
            result="ALLOW",
        )
        return decision

    # ----- registry-backed tool-call enforcement ------------------------------

    def enforce_tool_call(
        self,
        tool_name: str,
        args: dict[str, Any] | None = None,
        *,
        justification: str | None = None,
        context: EvaluationContext | None = None,
    ) -> PolicyDecision:
        """Classify a tool call via the registry, then enforce *profile ∩ tool*.

        This is the integration point for an agent framework's tool-call hook
        (Claude Agent SDK ``PreToolUse``, OpenAI Agents SDK tool guardrail /
        ``needs_approval``, Microsoft Agent Framework ``FunctionMiddleware``).
        The flow:

        1. Look up the tool in the registry. An unknown tool fails closed
           (``RMACDPermissionDeniedError``) — better the agent sees a denial it
           can react to than enforcement silently passing through.
        2. Resolve ``(operation, tier, target)`` from the tool's classifier.
        3. **Capability gate** — if the tool's own ceiling forbids the resolved
           ``(operation, tier)``, deny with ``RMACDToolCapabilityError`` (this
           tool may never do that, independent of the agent).
        4. **Profile gate** — delegate to :meth:`enforce`, which routes
           approvals, emits the audit record, maps denials to the right
           exception, and applies the §12.5 immutable safety floor.

        Returns the allowed ``PolicyDecision``; raises a subclass of
        ``RMACDPolicyError`` for any non-allowed outcome.
        """
        if self.registry is None:
            raise ValueError(
                "enforce_tool_call requires a ToolsRegistry; pass registry= to "
                "PolicyEnforcer(...) or call enforce() with an explicit operation."
            )

        tool = self.registry.get_tool(tool_name)
        if tool is None:
            # Fail closed: a tool with no RMACD registration cannot be governed.
            logger.warning("RMACD: refusing unregistered tool '%s' (fail-closed)", tool_name)
            raise RMACDPermissionDeniedError(
                f"Tool '{tool_name}' is not registered in the RMACD tools "
                f"registry; refusing the call (fail-closed)."
            )

        resolved = tool.resolve_call(args or {})

        # Capability gate (defence in depth): the tool's own ceiling. For a
        # composed multi-pack tool the resolution carries the matching pack's
        # ceiling, and that per-call ceiling (never a cross-pack union) gates.
        if not tool.permits_call(resolved):
            tier_label = resolved.tier.value if resolved.tier else "any"
            cap_reason = (
                f"Tool '{tool.tool_id}' capability does not permit "
                f"{resolved.operation.value} on {tier_label}."
            )
            decision = PolicyDecision(
                allowed=False,
                operation=resolved.operation,
                data_classification=resolved.tier,
                autonomy_level=AutonomyLevel.PROHIBITED,
                requires_approval=False,
                requires_notification=False,
                blocked_reason=cap_reason,
            )
            self._audit(
                operation=resolved.operation,
                target=resolved.target,
                classification=resolved.tier,
                decision=decision,
                result="DENY",
            )
            raise RMACDToolCapabilityError(cap_reason, decision=decision)

        # Profile gate: reuse enforce() (approval, audit, exception mapping,
        # §12.5 floor). justification defaults to a compact call summary.
        return self.enforce(
            operation=resolved.operation,
            target=resolved.target,
            classification=resolved.tier,
            justification=justification or self._summarise_call(tool_name, args or {}),
            context=context,
        )

    def evaluate_tool_call(
        self,
        tool_name: str,
        args: dict[str, Any] | None = None,
        *,
        context: EvaluationContext | None = None,
    ) -> PolicyDecision:
        """Dry-run of :meth:`enforce_tool_call` — no approval, no audit, no raise.

        Returns the ``PolicyDecision`` the call *would* get (the capability gate
        is reflected as ``allowed=False`` / ``PROHIBITED``). Useful for an
        OpenAI ``needs_approval`` callback or a "would this be allowed?" UI.
        Raises ``RMACDPermissionDeniedError`` only for an unregistered tool.
        """
        if self.registry is None:
            raise ValueError("evaluate_tool_call requires a ToolsRegistry.")
        tool = self.registry.get_tool(tool_name)
        if tool is None:
            raise RMACDPermissionDeniedError(
                f"Tool '{tool_name}' is not registered in the RMACD tools registry."
            )
        resolved = tool.resolve_call(args or {})
        if not tool.permits_call(resolved):
            tier_label = resolved.tier.value if resolved.tier else "any"
            return PolicyDecision(
                allowed=False,
                operation=resolved.operation,
                data_classification=resolved.tier,
                autonomy_level=AutonomyLevel.PROHIBITED,
                requires_approval=False,
                requires_notification=False,
                blocked_reason=(
                    f"Tool '{tool.tool_id}' capability does not permit "
                    f"{resolved.operation.value} on {tier_label}."
                ),
            )
        return self.evaluator.evaluate(
            operation=resolved.operation,
            data_classification=resolved.tier,
            context=context or self._default_context(),
        )

    @staticmethod
    def _summarise_call(tool_name: str, args: dict[str, Any]) -> str:
        if not args:
            return f"agent invoked {tool_name}"
        preview = ", ".join(f"{k}={v}" for k, v in list(args.items())[:4])
        return f"agent invoked {tool_name}({preview})"

    # ----- DC2D data-flow controls --------------------------------------------

    def apply_redaction(
        self,
        content: str,
        tier: DataClassification | str,
    ) -> RedactionResult:
        """Apply the profile's redaction policy to tool output before it is exposed.

        Called by the integration site *after* a read operation has been
        allowed by ``enforce()`` and *before* the read content reaches the
        agent's response surface (or the user). The transform is driven by
        the DC2D profile's ``constraints.redaction`` block — for 3D and 2D
        profiles, or DC2D profiles without a redaction block, this returns
        the content unchanged.

        Why this is a separate method rather than something ``enforce()``
        does automatically: redaction operates on data that flows *back*
        from a tool call, which is not visible to the access decision at
        the time it's made. The integration site has the content; the
        access decision doesn't. Keeping the surfaces separate matches
        that data-flow asymmetry.
        """
        tier_enum = DataClassification(tier) if isinstance(tier, str) else tier
        policy = self._redaction_policy()
        if policy is None:
            return RedactionResult(content=content, redactions_applied=[], tier=tier_enum)
        return self.redactor.redact(content, tier_enum, policy)

    def check_egress(
        self,
        tier: DataClassification | str,
        destination: str,
        *,
        raise_on_deny: bool = False,
    ) -> EgressDecision:
        """Check whether classified data may flow to ``destination``.

        Called by the integration site before sending data to an external
        endpoint (a downstream LLM, a vendor API, a customer-facing channel).
        Returns an ``EgressDecision``; with ``raise_on_deny=True`` the
        method raises ``RMACDEgressBlockedError`` on a denial, which is
        often more ergonomic at call sites that want fail-fast semantics.

        For 3D and 2D profiles, or DC2D profiles without an
        ``egress_controls`` block, the gate sees no controls and allows
        the egress. This matches the "no policy configured = no
        enforcement" stance of the rest of the SDK.
        """
        tier_enum = DataClassification(tier) if isinstance(tier, str) else tier
        controls = self._egress_controls()
        decision = self.egress_gate.check(destination, tier_enum, controls)
        if raise_on_deny and not decision.allowed:
            raise RMACDEgressBlockedError(
                decision.reason or f"Egress to {destination} blocked.",
                destination=destination,
                tier=tier_enum.value,
                matched_rule=decision.matched_rule,
            )
        return decision

    def _redaction_policy(self) -> RedactionPolicy | None:
        # Only DC2D profiles carry a redaction block. Read it off the
        # constraints; return None for non-DC2D or unconstrained profiles.
        if not isinstance(self.profile, ProfileDC2D):
            return None
        if self.profile.constraints is None:
            return None
        return self.profile.constraints.redaction

    def _egress_controls(self) -> EgressControls | None:
        if not isinstance(self.profile, ProfileDC2D):
            return None
        if self.profile.constraints is None:
            return None
        return self.profile.constraints.egress_controls

    # ----- decorator form (Appendix C.4 shape) ---------------------------------

    def guard(
        self,
        operation: Operation | str,
        classifier: ClassifierFn,
        *,
        justification: str | None = None,
    ) -> Callable[[F], F]:
        """Decorator that enforces RMACD before the wrapped function runs.

        ``classifier`` receives the same kwargs the wrapped function was
        called with and returns ``(target, classification)``. This is how the
        decorator closes the resource-classification-lookup gap: every tool
        site declares how to derive its target and tier from its own
        arguments, rather than relying on a global tag registry.

        Example::

            @enforcer.guard(
                operation="C",
                classifier=lambda *, server_id, **_: (
                    f"server://{server_id}",
                    "confidential" if server_id.startswith("prod-") else "internal",
                ),
            )
            def update_config(*, server_id: str, config: dict) -> None: ...
        """
        op = Operation(operation) if isinstance(operation, str) else operation

        def decorator(fn: F) -> F:
            def _tier(
                tier: DataClassification | str | None,
            ) -> DataClassification | None:
                # A classifier may legitimately return None for the tier (2D
                # profiles have no classification axis); _audit_execution takes
                # an optional classification, so pass it straight through.
                return DataClassification(tier) if isinstance(tier, str) else tier

            # An async tool needs an async wrapper. With a plain `def` wrapper,
            # `fn(...)` only returns a coroutine — it has not run yet — so the
            # success record fires immediately with duration_ms≈0 and the
            # `except` arm can never observe a failure raised inside the
            # coroutine. A guarded async tool that raised still recorded
            # EXECUTED/SUCCESS. In an audit-evidence product that is forged
            # evidence, so the two cases are dispatched separately below.
            if inspect.iscoroutinefunction(fn):

                @functools.wraps(fn)
                async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                    target, tier = classifier(*args, **kwargs)
                    self.enforce(
                        operation=op,
                        target=target,
                        classification=tier,
                        justification=justification,
                    )
                    # Start the clock after enforcement so the recorded duration
                    # measures the tool, not any approval round-trip.
                    start = time.perf_counter()
                    try:
                        result = await fn(*args, **kwargs)
                    except Exception as exc:
                        self._audit_execution(
                            operation=op,
                            target=target,
                            classification=_tier(tier),
                            status="FAILURE",
                            duration_ms=int((time.perf_counter() - start) * 1000),
                            error=str(exc),
                        )
                        raise
                    self._audit_execution(
                        operation=op,
                        target=target,
                        classification=_tier(tier),
                        status="SUCCESS",
                        duration_ms=int((time.perf_counter() - start) * 1000),
                    )
                    return result

                return async_wrapper  # type: ignore[return-value]

            @functools.wraps(fn)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                target, tier = classifier(*args, **kwargs)
                self.enforce(
                    operation=op,
                    target=target,
                    classification=tier,
                    justification=justification,
                )
                start = time.perf_counter()
                # Run the wrapped function and record execution outcome.
                try:
                    result = fn(*args, **kwargs)
                except Exception as exc:
                    self._audit_execution(
                        operation=op,
                        target=target,
                        classification=_tier(tier),
                        status="FAILURE",
                        duration_ms=int((time.perf_counter() - start) * 1000),
                        error=str(exc),
                    )
                    raise
                self._audit_execution(
                    operation=op,
                    target=target,
                    classification=_tier(tier),
                    status="SUCCESS",
                    duration_ms=int((time.perf_counter() - start) * 1000),
                )
                return result

            return wrapper  # type: ignore[return-value]

        return decorator

    # ----- internals -----------------------------------------------------------

    def _default_context(self) -> EvaluationContext:
        return EvaluationContext(environment=self.environment)

    def _profile_id(self) -> str:
        return self.profile.profile_id

    def _classify_denial(self, decision: PolicyDecision) -> Exception:
        """Pick the right exception subclass for a non-allowed decision.

        The split matters because callers (a tool-call wrapper, an MCP bridge,
        an agent system-prompt-aware UI) often want to react differently:
        return an error tool result for permission denial, show a hard stop
        for prohibition, surface a constraint hint for env/time failures.

        The evaluator sets ``autonomy_level == PROHIBITED`` for two distinct
        causes: (a) the matrix actually prohibits this combination (e.g.
        Change on Restricted) and (b) the agent's profile simply doesn't grant
        the requested operation. We disambiguate on the ``blocked_reason``
        sentinel because the failure modes need different surfaces — a
        profile gap is a candidate for an exception request, while a matrix
        prohibition is a hard safety boundary that cannot be bypassed.
        """
        if "constraints" in decision.constraints_applied:
            return RMACDConstraintError(
                decision.blocked_reason or "Operational constraint blocked the operation.",
                decision=decision,
            )
        reason = decision.blocked_reason or ""
        # The evaluator emits this exact sentinel when the operation is
        # missing from the profile's permission set. We still want to flag
        # cases where the *underlying matrix* prohibits the combination, so
        # callers can tell "you could ask for an exception" (profile gap)
        # apart from "this is a hard safety boundary" (matrix prohibition).
        profile_denied = "not permitted for this profile" in reason
        if profile_denied and decision.data_classification is not None:
            matrix_autonomy = DEFAULT_AUTONOMY_3D.get(
                decision.data_classification.value, {}
            ).get(decision.operation.value)
            if matrix_autonomy == AutonomyLevel.PROHIBITED:
                return RMACDProhibitedError(
                    f"{decision.operation.value} on {decision.data_classification.value} "
                    f"is prohibited by the RMACD governance matrix (no agent may perform "
                    f"this operation; human execution only).",
                    decision=decision,
                )
        if profile_denied:
            return RMACDPermissionDeniedError(reason, decision=decision)
        if decision.autonomy_level == AutonomyLevel.PROHIBITED:
            return RMACDProhibitedError(
                reason or "Operation prohibited by autonomy policy.",
                decision=decision,
            )
        return RMACDPermissionDeniedError(
            reason or "Operation not permitted by this profile.",
            decision=decision,
        )

    def _handle_approval_outcome(
        self,
        approval: ApprovalDecision,
        decision: PolicyDecision,
        op: Operation,
        target: str,
        tier: DataClassification | None,
        req: ApprovalRequest,
    ) -> None:
        if approval.outcome == ApprovalOutcome.APPROVED:
            self._audit(
                operation=op,
                target=target,
                classification=tier,
                decision=decision,
                result="APPROVED",
                approval_id=req.request_id,
                approver=approval.approver,
                approved_at=approval.decided_at,
            )
            return
        if approval.outcome == ApprovalOutcome.TIMEOUT:
            self._audit(
                operation=op,
                target=target,
                classification=tier,
                decision=decision,
                result="DENY",
                approval_id=req.request_id,
            )
            raise RMACDApprovalTimeoutError(
                f"Approval for {op.value} on {target} timed out.",
                decision=decision,
                timeout_seconds=req.timeout_seconds,
            )
        # DENIED
        self._audit(
            operation=op,
            target=target,
            classification=tier,
            decision=decision,
            result="REJECTED",
            approval_id=req.request_id,
            approver=approval.approver,
            approved_at=approval.decided_at,
        )
        raise RMACDApprovalDeniedError(
            f"Approval for {op.value} on {target} was denied"
            + (f" by {approval.approver}" if approval.approver else "")
            + ".",
            decision=decision,
            approver=approval.approver,
            note=approval.note,
        )

    def _audit(
        self,
        *,
        operation: Operation,
        target: str,
        classification: DataClassification | None,
        decision: PolicyDecision,
        result: str,
        approval_id: str | None = None,
        approver: str | None = None,
        approved_at: datetime | None = None,
    ) -> None:
        try:
            record = build_audit_record(
                agent_id=self.agent_id,
                profile_id=self._profile_id(),
                operation=operation,
                target=target,
                classification=classification,
                decision=decision,
                result=result,
                approval_id=approval_id,
                approver=approver,
                approved_at=approved_at,
                compliance_tags=self._compliance_tags,
            )
            self.audit_logger.log(record)
        except Exception:  # pragma: no cover - audit must never block enforcement
            # Audit-side failures are deployment problems, not policy problems.
            # Surfacing them here would let a broken sink turn into a global
            # outage, so we never re-raise. We do log a warning so a failing
            # sink is observable rather than silently dropping records.
            logger.warning(
                "RMACD audit logging failed for %s on %s", operation, target, exc_info=True
            )

    def _audit_execution(
        self,
        *,
        operation: Operation,
        target: str,
        classification: DataClassification | None,
        status: str,
        duration_ms: int,
        error: str | None = None,
    ) -> None:
        try:
            execution = AuditExecution(
                status=status,
                duration_ms=duration_ms,
                error=error,
            )
            # Build a synthetic allow-decision so the schema is uniform.
            record = build_audit_record(
                agent_id=self.agent_id,
                profile_id=self._profile_id(),
                operation=operation,
                target=target,
                classification=classification,
                decision=PolicyDecision(
                    allowed=True,
                    operation=operation,
                    data_classification=classification,
                    autonomy_level=AutonomyLevel.AUTONOMOUS,
                    requires_approval=False,
                    requires_notification=False,
                ),
                result="EXECUTED",
                execution=execution,
                compliance_tags=self._compliance_tags,
            )
            self.audit_logger.log(record)
        except Exception:  # pragma: no cover
            logger.warning(
                "RMACD execution audit logging failed for %s on %s",
                operation, target, exc_info=True,
            )

    @staticmethod
    def _extract_compliance_tags(profile: AnyProfile) -> list[str]:
        if profile.audit_requirements and profile.audit_requirements.compliance_tags:
            return [t.value for t in profile.audit_requirements.compliance_tags]
        return []


__all__ = ["PolicyEnforcer"]


# Reference the import only used for an isinstance branch in narrow paths so
# the strict mypy config does not flag it as unused.
_ = Profile3D
