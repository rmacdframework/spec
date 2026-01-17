"""Policy evaluator for RMACD Framework profiles."""

from datetime import datetime, time
from typing import Union
from zoneinfo import ZoneInfo

from rmacd.models import (
    AutonomyLevel,
    DataClassification,
    Environment,
    EvaluationContext,
    Operation,
    PolicyDecision,
    Profile2D,
    Profile3D,
    TriggerCondition,
)


# Default autonomy matrix from RMACD Framework spec
DEFAULT_AUTONOMY_3D: dict[str, dict[str, AutonomyLevel]] = {
    "public": {
        "R": AutonomyLevel.AUTONOMOUS,
        "M": AutonomyLevel.LOGGED,
        "A": AutonomyLevel.NOTIFICATION,
        "C": AutonomyLevel.NOTIFICATION,
        "D": AutonomyLevel.APPROVAL,
    },
    "internal": {
        "R": AutonomyLevel.LOGGED,
        "M": AutonomyLevel.NOTIFICATION,
        "A": AutonomyLevel.APPROVAL,
        "C": AutonomyLevel.APPROVAL,
        "D": AutonomyLevel.ELEVATED_APPROVAL,
    },
    "confidential": {
        "R": AutonomyLevel.NOTIFICATION,
        "M": AutonomyLevel.APPROVAL,
        "A": AutonomyLevel.ELEVATED_APPROVAL,
        "C": AutonomyLevel.ELEVATED_APPROVAL,
        "D": AutonomyLevel.PROHIBITED,
    },
    "restricted": {
        "R": AutonomyLevel.APPROVAL,
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

    def __init__(self, profile: Union[Profile2D, Profile3D]) -> None:
        """Initialize the evaluator with a profile.

        Args:
            profile: An RMACD profile (2D or 3D)
        """
        self.profile = profile
        self._is_3d = isinstance(profile, Profile3D)

    def evaluate(
        self,
        operation: str | Operation,
        data_classification: str | DataClassification | None = None,
        context: EvaluationContext | None = None,
    ) -> PolicyDecision:
        """Evaluate whether an operation is permitted.

        Args:
            operation: The RMACD operation (R, M, A, C, or D)
            data_classification: The data classification tier (required for 3D profiles)
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

    def _get_autonomy_level(
        self,
        operation: Operation,
        data_classification: DataClassification | None,
        context: EvaluationContext,
    ) -> AutonomyLevel:
        """Determine the autonomy level for an operation.

        Checks autonomy overrides first, then falls back to defaults.
        """
        op_key = operation.value

        # Check for profile-specific autonomy overrides
        if self.profile.autonomy_overrides:
            if self._is_3d and data_classification:
                # 3D override format: "classification.operation" (e.g., "internal.C")
                override_key = f"{data_classification.value}.{op_key}"
                if override_key in self.profile.autonomy_overrides:
                    return AutonomyLevel(self.profile.autonomy_overrides[override_key])
            else:
                # 2D override format: just operation (e.g., "C")
                if op_key in self.profile.autonomy_overrides:
                    return AutonomyLevel(self.profile.autonomy_overrides[op_key])

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

        # Verify trigger condition is valid
        if context.emergency_trigger and escalation.trigger_conditions:
            if context.emergency_trigger not in escalation.trigger_conditions:
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
        """Check operational constraints. Returns error message if blocked."""
        constraints = self.profile.constraints
        if not constraints:
            return None

        # Check environment
        if constraints.environments and context.environment:
            if context.environment not in constraints.environments:
                return f"Environment {context.environment.value} not permitted"

        # Check time windows
        if constraints.time_windows:
            time_error = self._check_time_windows(context.timestamp)
            if time_error:
                return time_error

        return None

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

            if not (start_time <= current_time <= end_time):
                return f"Operations only permitted between {time_windows.allowed_hours.start} and {time_windows.allowed_hours.end}"

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
        """
        if self._is_3d:
            assert isinstance(self.profile, Profile3D)
            return {
                k.value if isinstance(k, DataClassification) else k: [
                    o.value if isinstance(o, Operation) else o for o in v
                ]
                for k, v in self.profile.permissions.items()
            }
        else:
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
        """
        if self._is_3d:
            result: dict[str, dict[str, str]] = {}
            for classification in DataClassification:
                result[classification.value] = {}
                for operation in Operation:
                    autonomy = self._get_autonomy_level(
                        operation, classification, EvaluationContext()
                    )
                    result[classification.value][operation.value] = autonomy.value
            return result
        else:
            result_2d: dict[str, str] = {}
            for operation in Operation:
                autonomy = self._get_autonomy_level(operation, None, EvaluationContext())
                result_2d[operation.value] = autonomy.value
            return result_2d
