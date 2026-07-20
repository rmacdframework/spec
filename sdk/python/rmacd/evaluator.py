"""Policy evaluator for RMACD Framework profiles."""

from datetime import datetime, time
from zoneinfo import ZoneInfo

from rmacd.models import (
    AutonomyLevel,
    DataClassification,
    EmergencyEscalationDC2D,
    EvaluationContext,
    Operation,
    PolicyDecision,
    Profile2D,
    Profile3D,
    ProfileDC2D,
)

AnyProfile = Profile2D | Profile3D | ProfileDC2D


# Default autonomy matrix from RMACD Framework spec
DEFAULT_AUTONOMY_3D: dict[str, dict[str, AutonomyLevel]] = {
    "public": {
        "R": AutonomyLevel.AUTONOMOUS,
        "M": AutonomyLevel.AUTONOMOUS,
        "A": AutonomyLevel.NOTIFICATION,
        "C": AutonomyLevel.APPROVAL,
        "D": AutonomyLevel.APPROVAL,
    },
    "internal": {
        "R": AutonomyLevel.AUTONOMOUS,
        "M": AutonomyLevel.NOTIFICATION,
        "A": AutonomyLevel.APPROVAL,
        "C": AutonomyLevel.APPROVAL,
        "D": AutonomyLevel.ELEVATED_APPROVAL,
    },
    "confidential": {
        "R": AutonomyLevel.LOGGED,
        "M": AutonomyLevel.APPROVAL,
        "A": AutonomyLevel.ELEVATED_APPROVAL,
        "C": AutonomyLevel.ELEVATED_APPROVAL,
        "D": AutonomyLevel.ELEVATED_APPROVAL,
    },
    "restricted": {
        "R": AutonomyLevel.NOTIFICATION,
        "M": AutonomyLevel.ELEVATED_APPROVAL,
        "A": AutonomyLevel.PROHIBITED,
        "C": AutonomyLevel.PROHIBITED,
        "D": AutonomyLevel.PROHIBITED,
    },
}

# Default autonomy for 2D profiles (no data classification)
DEFAULT_AUTONOMY_2D: dict[str, AutonomyLevel] = {
    "R": AutonomyLevel.LOGGED,
    "M": AutonomyLevel.NOTIFICATION,
    "A": AutonomyLevel.APPROVAL,
    "C": AutonomyLevel.APPROVAL,
    "D": AutonomyLevel.ELEVATED_APPROVAL,
}

# Default autonomy for DC2D profiles (Appendix D recommended defaults)
DEFAULT_AUTONOMY_DC2D: dict[str, AutonomyLevel] = {
    "public": AutonomyLevel.AUTONOMOUS,
    "internal": AutonomyLevel.LOGGED,
    "confidential": AutonomyLevel.APPROVAL,
    "restricted": AutonomyLevel.ELEVATED_APPROVAL,
}

# Immutable safety floor (RMACD §12.5). These (classification, operation)
# combinations are PROHIBITED for *any* agent and cannot be granted by a
# profile's permissions, autonomy_overrides, or the emergency-escalation
# process. The evaluator enforces this independently of the schema so a
# hand-authored or programmatically-built profile cannot bypass it.
IMMUTABLE_PROHIBITIONS: frozenset[tuple[DataClassification, Operation]] = frozenset(
    {
        (DataClassification.RESTRICTED, Operation.ADD),
        (DataClassification.RESTRICTED, Operation.CHANGE),
        (DataClassification.RESTRICTED, Operation.DELETE),
    }
)


# Autonomy level ordering (index = restrictiveness, higher = more restrictive)
AUTONOMY_ORDER = [
    AutonomyLevel.AUTONOMOUS,
    AutonomyLevel.LOGGED,
    AutonomyLevel.NOTIFICATION,
    AutonomyLevel.APPROVAL,
    AutonomyLevel.ELEVATED_APPROVAL,
    AutonomyLevel.PROHIBITED,
]


class PolicyEvaluator:
    """Evaluates policy decisions based on RMACD profiles."""

    def __init__(self, profile: AnyProfile) -> None:
        """Initialize the evaluator with a profile.

        Args:
            profile: An RMACD profile (2D, 3D, or DC2D)
        """
        self.profile = profile
        self._is_3d = isinstance(profile, Profile3D)
        self._is_dc2d = isinstance(profile, ProfileDC2D)

    def evaluate(
        self,
        operation: str | Operation,
        data_classification: str | DataClassification | None = None,
        context: EvaluationContext | None = None,
    ) -> PolicyDecision:
        """Evaluate whether an operation is permitted.

        For 3D and DC2D profiles, data_classification is required. For DC2D, the
        operation argument is informational only (used for traceability in the
        returned decision); the autonomy decision depends solely on classification.

        Args:
            operation: The RMACD operation (R, M, A, C, or D)
            data_classification: The data classification tier (required for 3D and DC2D profiles)
            context: Optional evaluation context (timestamp, environment, emergency state)

        Returns:
            PolicyDecision with the evaluation result

        Raises:
            ValueError: If data_classification is required but not provided
        """
        # Normalize inputs
        if isinstance(operation, str):
            operation = Operation(operation)

        if data_classification is not None and isinstance(data_classification, str):
            data_classification = DataClassification(data_classification)

        if context is None:
            context = EvaluationContext()

        # DC2D profiles require data classification; operation is metadata only
        if self._is_dc2d:
            if data_classification is None:
                raise ValueError("data_classification is required for DC2D profiles")
            return self._evaluate_dc2d(operation, data_classification, context)

        # 3D profiles require data classification
        if self._is_3d and data_classification is None:
            raise ValueError("data_classification is required for 3D profiles")

        constraints_applied: list[str] = []
        blocked_reason: str | None = None

        # Check if operation is permitted by profile
        if self._is_3d:
            assert isinstance(self.profile, Profile3D)
            assert data_classification is not None
            classification_perms = self.profile.permissions.get(data_classification, [])
            has_permission = operation in classification_perms
        else:
            assert isinstance(self.profile, Profile2D)
            has_permission = operation in self.profile.permissions

        if not has_permission:
            # Check emergency escalation
            if context.emergency_active and self._check_emergency_permission(
                operation, data_classification, context
            ):
                has_permission = True
                constraints_applied.append("emergency_escalation")
            else:
                return PolicyDecision(
                    allowed=False,
                    operation=operation,
                    data_classification=data_classification,
                    autonomy_level=AutonomyLevel.PROHIBITED,
                    requires_approval=False,
                    requires_notification=False,
                    blocked_reason=f"Operation {operation.value} not permitted for this profile",
                )

        # Determine autonomy level
        autonomy = self._get_autonomy_level(operation, data_classification, context)

        # Check constraints
        if self.profile.constraints:
            constraint_result = self._check_constraints(operation, context)
            if constraint_result:
                blocked_reason = constraint_result
                constraints_applied.append("constraints")
                return PolicyDecision(
                    allowed=False,
                    operation=operation,
                    data_classification=data_classification,
                    autonomy_level=autonomy,
                    requires_approval=autonomy in [
                        AutonomyLevel.APPROVAL,
                        AutonomyLevel.ELEVATED_APPROVAL,
                    ],
                    requires_notification=autonomy
                    in [
                        AutonomyLevel.NOTIFICATION,
                        AutonomyLevel.APPROVAL,
                        AutonomyLevel.ELEVATED_APPROVAL,
                    ],
                    blocked_reason=blocked_reason,
                    constraints_applied=constraints_applied,
                    emergency_mode=context.emergency_active,
                )

        # Check if prohibited
        if autonomy == AutonomyLevel.PROHIBITED:
            return PolicyDecision(
                allowed=False,
                operation=operation,
                data_classification=data_classification,
                autonomy_level=autonomy,
                requires_approval=False,
                requires_notification=False,
                blocked_reason="Operation prohibited by autonomy policy",
                constraints_applied=constraints_applied,
                emergency_mode=context.emergency_active,
            )

        return PolicyDecision(
            allowed=True,
            operation=operation,
            data_classification=data_classification,
            autonomy_level=autonomy,
            requires_approval=autonomy
            in [AutonomyLevel.APPROVAL, AutonomyLevel.ELEVATED_APPROVAL],
            requires_notification=autonomy
            in [
                AutonomyLevel.NOTIFICATION,
                AutonomyLevel.APPROVAL,
                AutonomyLevel.ELEVATED_APPROVAL,
            ],
            constraints_applied=constraints_applied,
            emergency_mode=context.emergency_active,
        )

    def _evaluate_dc2d(
        self,
        operation: Operation,
        data_classification: DataClassification,
        context: EvaluationContext,
    ) -> PolicyDecision:
        """Evaluate a DC2D profile decision keyed on data classification only."""
        assert isinstance(self.profile, ProfileDC2D)
        constraints_applied: list[str] = []

        # RMACD §12.5 immutable floor applies to EVERY deployment shape, before
        # any tier policy, emergency escalation, or autonomy computation. DC2D
        # treats the operation as metadata for the *autonomy* decision, but the
        # floor is a hard, framework-level prohibition: when a concrete
        # Add/Change/Delete on Restricted is presented — e.g. a registry-resolved
        # operation via enforce_tool_call — it can never be granted, regardless
        # of the profile's per-tier policy. (Code review C1, 2026-07-19.)
        if (data_classification, operation) in IMMUTABLE_PROHIBITIONS:
            return PolicyDecision(
                allowed=False,
                operation=operation,
                data_classification=data_classification,
                autonomy_level=AutonomyLevel.PROHIBITED,
                requires_approval=False,
                requires_notification=False,
                blocked_reason=(
                    f"{operation.value} on {data_classification.value} is prohibited by "
                    "the RMACD §12.5 immutable floor and cannot be granted by any profile"
                ),
                constraints_applied=["immutable_prohibition"],
                emergency_mode=context.emergency_active,
            )

        tier_policy = self.profile.data_access.for_tier(data_classification)
        allowed = tier_policy.allowed
        autonomy = tier_policy.autonomy

        # Emergency escalation can grant access to otherwise-denied tiers
        if not allowed and context.emergency_active:
            esc = self.profile.emergency_escalation
            if esc and esc.enabled and esc.escalated_tiers:
                trigger_ok = (
                    not esc.trigger_conditions
                    or context.emergency_trigger is None
                    or context.emergency_trigger in esc.trigger_conditions
                )
                if trigger_ok and data_classification in esc.escalated_tiers:
                    allowed = True
                    autonomy = esc.escalated_autonomy or autonomy
                    constraints_applied.append("emergency_escalation")

        if not allowed:
            return PolicyDecision(
                allowed=False,
                operation=operation,
                data_classification=data_classification,
                autonomy_level=AutonomyLevel.PROHIBITED,
                requires_approval=False,
                requires_notification=False,
                blocked_reason=(
                    f"Access to {data_classification.value} tier not permitted by this profile"
                ),
                constraints_applied=constraints_applied,
                emergency_mode=context.emergency_active,
            )

        # Constraint checks (environment, time windows). Operation-specific
        # constraints don't exist on DC2D profiles by design.
        if self.profile.constraints:
            constraint_result = self._check_constraints_dc2d(context)
            if constraint_result:
                constraints_applied.append("constraints")
                return PolicyDecision(
                    allowed=False,
                    operation=operation,
                    data_classification=data_classification,
                    autonomy_level=autonomy,
                    requires_approval=autonomy
                    in [AutonomyLevel.APPROVAL, AutonomyLevel.ELEVATED_APPROVAL],
                    requires_notification=autonomy
                    in [
                        AutonomyLevel.NOTIFICATION,
                        AutonomyLevel.APPROVAL,
                        AutonomyLevel.ELEVATED_APPROVAL,
                    ],
                    blocked_reason=constraint_result,
                    constraints_applied=constraints_applied,
                    emergency_mode=context.emergency_active,
                )

        if autonomy == AutonomyLevel.PROHIBITED:
            return PolicyDecision(
                allowed=False,
                operation=operation,
                data_classification=data_classification,
                autonomy_level=autonomy,
                requires_approval=False,
                requires_notification=False,
                blocked_reason="Access prohibited by autonomy policy for this tier",
                constraints_applied=constraints_applied,
                emergency_mode=context.emergency_active,
            )

        return PolicyDecision(
            allowed=True,
            operation=operation,
            data_classification=data_classification,
            autonomy_level=autonomy,
            requires_approval=autonomy
            in [AutonomyLevel.APPROVAL, AutonomyLevel.ELEVATED_APPROVAL],
            requires_notification=autonomy
            in [
                AutonomyLevel.NOTIFICATION,
                AutonomyLevel.APPROVAL,
                AutonomyLevel.ELEVATED_APPROVAL,
            ],
            constraints_applied=constraints_applied,
            emergency_mode=context.emergency_active,
        )

    def _check_constraints_dc2d(self, context: EvaluationContext) -> str | None:
        """Check DC2D constraints (environment + time windows). Returns error message if blocked."""
        assert isinstance(self.profile, ProfileDC2D)
        return self._check_env_time_constraints(context)

    def _check_env_time_constraints(self, context: EvaluationContext) -> str | None:
        """Shared environment + time-window constraint check.

        Used by both the 3D (``_check_constraints``) and DC2D
        (``_check_constraints_dc2d``) paths, whose environment/time logic is
        identical.
        """
        constraints = self.profile.constraints
        if not constraints:
            return None

        if (
            constraints.environments
            and context.environment
            and context.environment not in constraints.environments
        ):
            return f"Environment {context.environment.value} not permitted"

        if constraints.time_windows:
            time_error = self._check_time_windows(context.timestamp)
            if time_error:
                return time_error

        return None

    def _get_autonomy_level(
        self,
        operation: Operation,
        data_classification: DataClassification | None,
        context: EvaluationContext,
    ) -> AutonomyLevel:
        """Determine the autonomy level for an operation.

        Checks autonomy overrides first, then falls back to defaults.
        """
        # Immutable safety floor (§12.5): some (classification, operation)
        # combinations are prohibited for any agent and cannot be raised by an
        # override. Enforce this before consulting overrides or defaults so a
        # crafted profile cannot grant e.g. Change/Delete on Restricted data.
        if (
            data_classification is not None
            and (data_classification, operation) in IMMUTABLE_PROHIBITIONS
        ):
            return AutonomyLevel.PROHIBITED

        op_key = operation.value

        # Check for profile-specific autonomy overrides (DC2D profiles have
        # no autonomy_overrides — their autonomy lives in per-tier policies).
        profile = self.profile
        if isinstance(profile, Profile3D) and profile.autonomy_overrides:
            if data_classification:
                # 3D override format: "classification.operation" (e.g., "internal.C")
                override_key = f"{data_classification.value}.{op_key}"
                if override_key in profile.autonomy_overrides:
                    return AutonomyLevel(profile.autonomy_overrides[override_key])
            elif op_key in profile.autonomy_overrides:
                # 3D profile evaluated without a tier: operation-only key
                return AutonomyLevel(profile.autonomy_overrides[op_key])
        elif (
            isinstance(profile, Profile2D)
            and profile.autonomy_overrides
            # 2D override format: just the operation (e.g., "C")
            and operation in profile.autonomy_overrides
        ):
            return AutonomyLevel(profile.autonomy_overrides[operation])

        # Fall back to defaults
        if self._is_3d and data_classification:
            return DEFAULT_AUTONOMY_3D.get(data_classification.value, {}).get(
                op_key, AutonomyLevel.PROHIBITED
            )
        else:
            return DEFAULT_AUTONOMY_2D.get(op_key, AutonomyLevel.APPROVAL)

    def _check_emergency_permission(
        self,
        operation: Operation,
        data_classification: DataClassification | None,
        context: EvaluationContext,
    ) -> bool:
        """Check if emergency escalation grants the requested permission."""
        escalation = self.profile.emergency_escalation
        if not escalation or not escalation.enabled:
            return False

        # DC2D escalation is tier-based (escalated_tiers/escalated_autonomy)
        # and is applied by the DC2D evaluation path, not by operation grants.
        if isinstance(escalation, EmergencyEscalationDC2D):
            return False

        # Verify trigger condition is valid
        if (
            context.emergency_trigger
            and escalation.trigger_conditions
            and context.emergency_trigger not in escalation.trigger_conditions
        ):
            return False

        # Check escalated permissions
        if escalation.escalated_permissions:
            if self._is_3d and data_classification:
                # 3D: escalated_permissions is dict[classification, list[operation]]
                assert isinstance(self.profile, Profile3D)
                if isinstance(escalation.escalated_permissions, dict):
                    perms = escalation.escalated_permissions.get(data_classification, [])
                    return operation in perms
            else:
                # 2D: escalated_permissions is list[operation]
                if isinstance(escalation.escalated_permissions, list):
                    return operation in escalation.escalated_permissions

        return False

    def _check_constraints(
        self,
        operation: Operation,
        context: EvaluationContext,
    ) -> str | None:
        """Check operational constraints. Returns error message if blocked.

        ``operation`` is currently unused (env/time constraints are not
        operation-specific) but kept for symmetry and future op-scoped rules.
        """
        del operation
        return self._check_env_time_constraints(context)

    def _check_time_windows(self, timestamp: datetime) -> str | None:
        """Check if operation is within allowed time windows."""
        time_windows = self.profile.constraints.time_windows if self.profile.constraints else None
        if not time_windows:
            return None

        # Convert to configured timezone
        tz = ZoneInfo(time_windows.timezone) if time_windows.timezone else ZoneInfo("UTC")
        local_time = timestamp.astimezone(tz)

        # Check allowed days
        if time_windows.allowed_days:
            day_name = local_time.strftime("%A").lower()
            if day_name not in time_windows.allowed_days:
                return f"Operations not permitted on {day_name}"

        # Check allowed hours
        if time_windows.allowed_hours:
            start_parts = time_windows.allowed_hours.start.split(":")
            end_parts = time_windows.allowed_hours.end.split(":")
            start_time = time(int(start_parts[0]), int(start_parts[1]))
            end_time = time(int(end_parts[0]), int(end_parts[1]))
            current_time = local_time.time()

            if start_time <= end_time:
                in_window = start_time <= current_time <= end_time
            else:
                # Window wraps past midnight (e.g. 22:00–06:00): permitted if
                # the current time is after the start OR before the end.
                in_window = current_time >= start_time or current_time <= end_time
            if not in_window:
                return (
                    f"Operations only permitted between {time_windows.allowed_hours.start} "
                    f"and {time_windows.allowed_hours.end}"
                )

        # Check blackout dates
        if time_windows.blackout_dates:
            current_date = local_time.date().isoformat()
            if current_date in time_windows.blackout_dates:
                return f"Operations blocked on blackout date {current_date}"

        return None

    def get_all_permissions(self) -> dict[str, list[str]]:
        """Get all permissions defined in the profile.

        Returns:
            For 3D: dict mapping classification to list of operations
            For 2D: dict with single key "default" mapping to operations
            For DC2D: dict mapping classification to ["allowed"] or [] (per-tier access)
        """
        if self._is_dc2d:
            assert isinstance(self.profile, ProfileDC2D)
            result: dict[str, list[str]] = {}
            for tier in DataClassification:
                policy = self.profile.data_access.for_tier(tier)
                result[tier.value] = ["allowed"] if policy.allowed else []
            return result
        if self._is_3d:
            assert isinstance(self.profile, Profile3D)
            return {
                k.value if isinstance(k, DataClassification) else k: [
                    o.value if isinstance(o, Operation) else o for o in v
                ]
                for k, v in self.profile.permissions.items()
            }
        assert isinstance(self.profile, Profile2D)
        return {
            "default": [
                o.value if isinstance(o, Operation) else o for o in self.profile.permissions
            ]
        }

    def get_effective_autonomy_matrix(
        self,
    ) -> dict[str, dict[str, str]] | dict[str, str]:
        """Get the effective autonomy matrix including overrides.

        Returns:
            For 3D: nested dict of classification -> operation -> autonomy level
            For 2D: dict of operation -> autonomy level
            For DC2D: dict of classification -> autonomy level
        """
        if self._is_dc2d:
            assert isinstance(self.profile, ProfileDC2D)
            dc2d_result: dict[str, str] = {}
            for tier in DataClassification:
                policy = self.profile.data_access.for_tier(tier)
                dc2d_result[tier.value] = policy.autonomy.value
            return dc2d_result
        empty_ctx = EvaluationContext()
        if self._is_3d:
            result: dict[str, dict[str, str]] = {}
            for classification in DataClassification:
                result[classification.value] = {}
                for operation in Operation:
                    autonomy = self._get_autonomy_level(
                        operation, classification, empty_ctx
                    )
                    result[classification.value][operation.value] = autonomy.value
            return result
        result_2d: dict[str, str] = {}
        for operation in Operation:
            autonomy = self._get_autonomy_level(operation, None, empty_ctx)
            result_2d[operation.value] = autonomy.value
        return result_2d
