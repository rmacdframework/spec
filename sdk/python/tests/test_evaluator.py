"""Tests for the PolicyEvaluator."""

from datetime import datetime, timezone

import pytest

from rmacd.evaluator import PolicyEvaluator
from rmacd.models import (
    AllowedHours,
    AutonomyLevel,
    Constraints,
    DataAccess,
    DataClassification,
    EmergencyEscalation3D,
    EmergencyEscalationDC2D,
    Environment,
    EvaluationContext,
    Operation,
    Profile2D,
    Profile3D,
    ProfileDC2D,
    TierPolicy,
    TimeWindows,
    TriggerCondition,
)


@pytest.fixture
def basic_3d_profile() -> Profile3D:
    """Create a basic 3D profile for testing."""
    return Profile3D(
        profile_id="rmacd-3d-test-v1",
        profile_name="Test Profile",
        model="three-dimensional",
        version="1.0",
        permissions={
            DataClassification.PUBLIC: [Operation.READ, Operation.MOVE, Operation.ADD],
            DataClassification.INTERNAL: [Operation.READ, Operation.MOVE],
            DataClassification.CONFIDENTIAL: [Operation.READ],
            DataClassification.RESTRICTED: [Operation.READ],
        },
    )


@pytest.fixture
def basic_2d_profile() -> Profile2D:
    """Create a basic 2D profile for testing."""
    return Profile2D(
        profile_id="rmacd-2d-test-v1",
        profile_name="Test Profile 2D",
        model="two-dimensional",
        version="1.0",
        permissions=[Operation.READ, Operation.MOVE, Operation.ADD],
    )


class TestPolicyEvaluator3D:
    """Tests for 3D profile evaluation."""

    def test_allowed_operation(self, basic_3d_profile: Profile3D) -> None:
        """Test that allowed operations return allowed=True."""
        evaluator = PolicyEvaluator(basic_3d_profile)
        decision = evaluator.evaluate("R", "public")

        assert decision.allowed is True
        assert decision.operation == Operation.READ
        assert decision.data_classification == DataClassification.PUBLIC

    def test_denied_operation(self, basic_3d_profile: Profile3D) -> None:
        """Test that denied operations return allowed=False."""
        evaluator = PolicyEvaluator(basic_3d_profile)
        decision = evaluator.evaluate("D", "public")

        assert decision.allowed is False
        assert decision.blocked_reason is not None

    def test_missing_classification_raises(self, basic_3d_profile: Profile3D) -> None:
        """Test that 3D evaluation without classification raises ValueError."""
        evaluator = PolicyEvaluator(basic_3d_profile)

        with pytest.raises(ValueError, match="data_classification is required"):
            evaluator.evaluate("R")

    def test_autonomy_levels(self, basic_3d_profile: Profile3D) -> None:
        """Test default autonomy levels are applied correctly."""
        evaluator = PolicyEvaluator(basic_3d_profile)

        # Public read should be autonomous
        decision = evaluator.evaluate("R", "public")
        assert decision.autonomy_level == AutonomyLevel.AUTONOMOUS
        assert decision.requires_approval is False

        # Internal move should require notification
        decision = evaluator.evaluate("M", "internal")
        assert decision.autonomy_level == AutonomyLevel.NOTIFICATION
        assert decision.requires_notification is True

    def test_default_autonomy_matrix_matches_spec(self, basic_3d_profile: Profile3D) -> None:
        """Verify the default autonomy matrix matches the RMACD governance matrix in the spec."""
        profile = Profile3D(
            profile_id="rmacd-3d-full-v1",
            profile_name="Full",
            model="three-dimensional",
            version="1.0",
            permissions={
                tier: list(Operation) for tier in DataClassification
            },
        )
        evaluator = PolicyEvaluator(profile)

        expected = {
            # (classification, operation): autonomy_level
            ("public", "R"): AutonomyLevel.AUTONOMOUS,
            ("public", "M"): AutonomyLevel.AUTONOMOUS,
            ("public", "A"): AutonomyLevel.NOTIFICATION,
            ("public", "C"): AutonomyLevel.APPROVAL,
            ("public", "D"): AutonomyLevel.APPROVAL,
            ("internal", "R"): AutonomyLevel.AUTONOMOUS,
            ("internal", "M"): AutonomyLevel.NOTIFICATION,
            ("internal", "A"): AutonomyLevel.APPROVAL,
            ("internal", "C"): AutonomyLevel.APPROVAL,
            ("internal", "D"): AutonomyLevel.ELEVATED_APPROVAL,
            ("confidential", "R"): AutonomyLevel.LOGGED,
            ("confidential", "M"): AutonomyLevel.APPROVAL,
            ("confidential", "A"): AutonomyLevel.ELEVATED_APPROVAL,
            ("confidential", "C"): AutonomyLevel.ELEVATED_APPROVAL,
            ("confidential", "D"): AutonomyLevel.ELEVATED_APPROVAL,
            ("restricted", "R"): AutonomyLevel.NOTIFICATION,
            ("restricted", "M"): AutonomyLevel.ELEVATED_APPROVAL,
            ("restricted", "A"): AutonomyLevel.PROHIBITED,
            ("restricted", "C"): AutonomyLevel.PROHIBITED,
            ("restricted", "D"): AutonomyLevel.PROHIBITED,
        }

        for (classification, operation), expected_level in expected.items():
            decision = evaluator.evaluate(operation, classification)
            assert decision.autonomy_level == expected_level, (
                f"{classification}.{operation}: expected {expected_level.value}, "
                f"got {decision.autonomy_level.value}"
            )

    def test_autonomy_override(self) -> None:
        """Test that autonomy overrides are respected."""
        profile = Profile3D(
            profile_id="rmacd-3d-override-v1",
            profile_name="Override Test",
            model="three-dimensional",
            version="1.0",
            permissions={
                DataClassification.PUBLIC: [Operation.READ, Operation.CHANGE],
            },
            autonomy_overrides={
                "public.C": AutonomyLevel.AUTONOMOUS,  # Override default
            },
        )
        evaluator = PolicyEvaluator(profile)

        decision = evaluator.evaluate("C", "public")
        assert decision.autonomy_level == AutonomyLevel.AUTONOMOUS

    def test_prohibited_operation(self) -> None:
        """Test that prohibited operations are blocked."""
        profile = Profile3D(
            profile_id="rmacd-3d-prohibited-v1",
            profile_name="Prohibited Test",
            model="three-dimensional",
            version="1.0",
            permissions={
                DataClassification.RESTRICTED: [Operation.DELETE],
            },
            autonomy_overrides={
                "restricted.D": AutonomyLevel.PROHIBITED,
            },
        )
        evaluator = PolicyEvaluator(profile)

        decision = evaluator.evaluate("D", "restricted")
        assert decision.allowed is False
        assert decision.autonomy_level == AutonomyLevel.PROHIBITED


class TestImmutableSafetyBoundary:
    """§12.5: Add/Change/Delete on Restricted is prohibited for any agent and
    cannot be granted via permissions, autonomy_overrides, or emergency
    escalation. These tests assert the evaluator floors the autonomy to
    PROHIBITED even when a crafted profile tries to grant it."""

    @pytest.mark.parametrize("op", ["A", "C", "D"])
    def test_override_cannot_bypass_restricted_floor(self, op: str) -> None:
        """A profile that grants the op and overrides autonomy to autonomous
        must still be prohibited on Restricted data."""
        profile = Profile3D(
            profile_id="rmacd-3d-bypass-attempt-v1",
            profile_name="Bypass Attempt",
            model="three-dimensional",
            version="1.0",
            permissions={
                DataClassification.RESTRICTED: [Operation(op)],
            },
            autonomy_overrides={
                f"restricted.{op}": AutonomyLevel.AUTONOMOUS,
            },
        )
        evaluator = PolicyEvaluator(profile)

        decision = evaluator.evaluate(op, "restricted")
        assert decision.allowed is False
        assert decision.autonomy_level == AutonomyLevel.PROHIBITED

    @pytest.mark.parametrize("op", ["A", "C", "D"])
    def test_emergency_escalation_cannot_bypass_restricted_floor(self, op: str) -> None:
        """Emergency escalation that grants the op on Restricted must still be
        prohibited."""
        profile = Profile3D(
            profile_id="rmacd-3d-emergency-bypass-v1",
            profile_name="Emergency Bypass Attempt",
            model="three-dimensional",
            version="1.0",
            permissions={
                DataClassification.RESTRICTED: [Operation.READ],
            },
            emergency_escalation=EmergencyEscalation3D(
                enabled=True,
                trigger_conditions=[TriggerCondition.SOC_DECLARED_INCIDENT],
                escalated_permissions={
                    DataClassification.RESTRICTED: [Operation(op)],
                },
            ),
        )
        evaluator = PolicyEvaluator(profile)

        ctx = EvaluationContext(
            emergency_active=True,
            emergency_trigger=TriggerCondition.SOC_DECLARED_INCIDENT,
        )
        decision = evaluator.evaluate(op, "restricted", ctx)
        assert decision.allowed is False
        assert decision.autonomy_level == AutonomyLevel.PROHIBITED

    @pytest.mark.parametrize("op", ["A", "C", "D"])
    def test_effective_matrix_reflects_floor(self, op: str) -> None:
        """The effective autonomy matrix must show the prohibition even when a
        profile overrides it."""
        profile = Profile3D(
            profile_id="rmacd-3d-matrix-floor-v1",
            profile_name="Matrix Floor",
            model="three-dimensional",
            version="1.0",
            permissions={DataClassification.RESTRICTED: [Operation(op)]},
            autonomy_overrides={f"restricted.{op}": AutonomyLevel.AUTONOMOUS},
        )
        evaluator = PolicyEvaluator(profile)
        matrix = evaluator.get_effective_autonomy_matrix()
        assert matrix["restricted"][op] == AutonomyLevel.PROHIBITED.value


class TestPolicyEvaluator2D:
    """Tests for 2D profile evaluation."""

    def test_allowed_operation(self, basic_2d_profile: Profile2D) -> None:
        """Test that allowed operations return allowed=True."""
        evaluator = PolicyEvaluator(basic_2d_profile)
        decision = evaluator.evaluate("R")

        assert decision.allowed is True
        assert decision.data_classification is None

    def test_denied_operation(self, basic_2d_profile: Profile2D) -> None:
        """Test that denied operations return allowed=False."""
        evaluator = PolicyEvaluator(basic_2d_profile)
        decision = evaluator.evaluate("D")

        assert decision.allowed is False


class TestEmergencyEscalation:
    """Tests for emergency escalation logic."""

    def test_emergency_grants_permission(self) -> None:
        """Test that emergency escalation grants additional permissions."""
        profile = Profile3D(
            profile_id="rmacd-3d-emergency-v1",
            profile_name="Emergency Test",
            model="three-dimensional",
            version="1.0",
            permissions={
                DataClassification.PUBLIC: [Operation.READ],
            },
            emergency_escalation=EmergencyEscalation3D(
                enabled=True,
                trigger_conditions=[TriggerCondition.SOC_DECLARED_INCIDENT],
                escalated_permissions={
                    DataClassification.PUBLIC: [Operation.READ, Operation.CHANGE],
                },
                max_duration_minutes=60,
                notification_targets=["security@example.com"],
            ),
        )
        evaluator = PolicyEvaluator(profile)

        # Without emergency, Change is denied
        decision = evaluator.evaluate("C", "public")
        assert decision.allowed is False

        # With emergency, Change is allowed
        context = EvaluationContext(
            emergency_active=True,
            emergency_trigger=TriggerCondition.SOC_DECLARED_INCIDENT,
        )
        decision = evaluator.evaluate("C", "public", context)
        assert decision.allowed is True
        assert decision.emergency_mode is True


class TestConstraints:
    """Tests for operational constraint enforcement (time windows, environments)."""

    @staticmethod
    def _profile_with_hours(start: str, end: str) -> Profile3D:
        return Profile3D(
            profile_id="rmacd-3d-hours-v1",
            profile_name="Hours",
            model="three-dimensional",
            version="1.0",
            permissions={DataClassification.PUBLIC: [Operation.READ]},
            constraints=Constraints(
                time_windows=TimeWindows(
                    timezone="UTC",
                    allowed_hours=AllowedHours(start=start, end=end),
                )
            ),
        )

    def test_same_day_window_inside(self) -> None:
        evaluator = PolicyEvaluator(self._profile_with_hours("08:00", "18:00"))
        ctx = EvaluationContext(timestamp=datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc))
        assert evaluator.evaluate("R", "public", ctx).allowed is True

    def test_same_day_window_outside(self) -> None:
        evaluator = PolicyEvaluator(self._profile_with_hours("08:00", "18:00"))
        ctx = EvaluationContext(timestamp=datetime(2026, 6, 8, 22, 0, tzinfo=timezone.utc))
        assert evaluator.evaluate("R", "public", ctx).allowed is False

    def test_midnight_crossing_window_inside_after_start(self) -> None:
        # Window 22:00–06:00; 23:30 is inside.
        evaluator = PolicyEvaluator(self._profile_with_hours("22:00", "06:00"))
        ctx = EvaluationContext(timestamp=datetime(2026, 6, 8, 23, 30, tzinfo=timezone.utc))
        assert evaluator.evaluate("R", "public", ctx).allowed is True

    def test_midnight_crossing_window_inside_before_end(self) -> None:
        # Window 22:00–06:00; 02:00 is inside.
        evaluator = PolicyEvaluator(self._profile_with_hours("22:00", "06:00"))
        ctx = EvaluationContext(timestamp=datetime(2026, 6, 8, 2, 0, tzinfo=timezone.utc))
        assert evaluator.evaluate("R", "public", ctx).allowed is True

    def test_midnight_crossing_window_outside(self) -> None:
        # Window 22:00–06:00; 12:00 is outside.
        evaluator = PolicyEvaluator(self._profile_with_hours("22:00", "06:00"))
        ctx = EvaluationContext(timestamp=datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc))
        assert evaluator.evaluate("R", "public", ctx).allowed is False

    def test_environment_constraint_blocks_mismatch(self) -> None:
        profile = Profile3D(
            profile_id="rmacd-3d-env-v1",
            profile_name="Env",
            model="three-dimensional",
            version="1.0",
            permissions={DataClassification.PUBLIC: [Operation.READ]},
            constraints=Constraints(environments=[Environment.PRODUCTION]),
        )
        evaluator = PolicyEvaluator(profile)
        prod = EvaluationContext(environment=Environment.PRODUCTION)
        staging = EvaluationContext(environment=Environment.STAGING)
        assert evaluator.evaluate("R", "public", prod).allowed is True
        assert evaluator.evaluate("R", "public", staging).allowed is False


class TestPermissionMatrix:
    """Tests for permission matrix retrieval."""

    def test_get_all_permissions_3d(self, basic_3d_profile: Profile3D) -> None:
        """Test getting all permissions from 3D profile."""
        evaluator = PolicyEvaluator(basic_3d_profile)
        permissions = evaluator.get_all_permissions()

        assert "public" in permissions
        assert "R" in permissions["public"]
        assert "M" in permissions["public"]
        assert "A" in permissions["public"]

    def test_get_all_permissions_2d(self, basic_2d_profile: Profile2D) -> None:
        """Test getting all permissions from 2D profile."""
        evaluator = PolicyEvaluator(basic_2d_profile)
        permissions = evaluator.get_all_permissions()

        assert "default" in permissions
        assert "R" in permissions["default"]

    def test_get_effective_autonomy_matrix_3d(self, basic_3d_profile: Profile3D) -> None:
        """Test getting effective autonomy matrix for 3D profile."""
        evaluator = PolicyEvaluator(basic_3d_profile)
        matrix = evaluator.get_effective_autonomy_matrix()

        assert "public" in matrix
        assert "R" in matrix["public"]
        assert matrix["public"]["R"] == "autonomous"


# --- DC2D tests ---


@pytest.fixture
def basic_dc2d_profile() -> ProfileDC2D:
    """A DC2D profile mirroring the Appendix D recommended-default matrix."""
    return ProfileDC2D(
        profile_id="rmacd-dc2d-defaults-v1",
        profile_name="DC2D Defaults",
        model="data-classification-2d",
        version="1.0",
        data_access=DataAccess(
            public=TierPolicy(allowed=True, autonomy=AutonomyLevel.AUTONOMOUS),
            internal=TierPolicy(allowed=True, autonomy=AutonomyLevel.LOGGED),
            confidential=TierPolicy(allowed=True, autonomy=AutonomyLevel.APPROVAL),
            restricted=TierPolicy(
                allowed=False, autonomy=AutonomyLevel.PROHIBITED,
                justification="separately authorized profile",
            ),
        ),
    )


class TestPolicyEvaluatorDC2D:
    """Tests for DC2D profile evaluation."""

    def test_missing_classification_raises(self, basic_dc2d_profile: ProfileDC2D) -> None:
        evaluator = PolicyEvaluator(basic_dc2d_profile)
        with pytest.raises(ValueError, match="data_classification is required"):
            evaluator.evaluate("R")

    def test_public_autonomous(self, basic_dc2d_profile: ProfileDC2D) -> None:
        evaluator = PolicyEvaluator(basic_dc2d_profile)
        decision = evaluator.evaluate("R", "public")
        assert decision.allowed is True
        assert decision.autonomy_level == AutonomyLevel.AUTONOMOUS
        assert decision.requires_approval is False
        assert decision.requires_notification is False

    def test_internal_logged(self, basic_dc2d_profile: ProfileDC2D) -> None:
        evaluator = PolicyEvaluator(basic_dc2d_profile)
        decision = evaluator.evaluate("M", "internal")
        assert decision.allowed is True
        assert decision.autonomy_level == AutonomyLevel.LOGGED

    def test_confidential_requires_approval(self, basic_dc2d_profile: ProfileDC2D) -> None:
        evaluator = PolicyEvaluator(basic_dc2d_profile)
        decision = evaluator.evaluate("C", "confidential")
        assert decision.allowed is True
        assert decision.autonomy_level == AutonomyLevel.APPROVAL
        assert decision.requires_approval is True

    def test_restricted_denied(self, basic_dc2d_profile: ProfileDC2D) -> None:
        evaluator = PolicyEvaluator(basic_dc2d_profile)
        decision = evaluator.evaluate("R", "restricted")
        assert decision.allowed is False
        assert "restricted" in (decision.blocked_reason or "")

    def test_operation_is_metadata_only(self, basic_dc2d_profile: ProfileDC2D) -> None:
        """Operation does not affect the DC2D autonomy decision."""
        evaluator = PolicyEvaluator(basic_dc2d_profile)
        for op in ["R", "M", "A", "C", "D"]:
            decision = evaluator.evaluate(op, "internal")
            assert decision.autonomy_level == AutonomyLevel.LOGGED, (
                f"DC2D autonomy must be tier-driven; operation {op} should not change it"
            )
            assert decision.operation.value == op

    def test_emergency_escalates_tier(self) -> None:
        """Emergency escalation grants access to a previously denied tier."""
        profile = ProfileDC2D(
            profile_id="rmacd-dc2d-emergency-v1",
            profile_name="Emergency",
            model="data-classification-2d",
            version="1.0",
            data_access=DataAccess(
                public=TierPolicy(allowed=True, autonomy=AutonomyLevel.AUTONOMOUS),
                internal=TierPolicy(allowed=True, autonomy=AutonomyLevel.LOGGED),
                confidential=TierPolicy(allowed=False, autonomy=AutonomyLevel.PROHIBITED),
                restricted=TierPolicy(allowed=False, autonomy=AutonomyLevel.PROHIBITED),
            ),
            emergency_escalation=EmergencyEscalationDC2D(
                enabled=True,
                trigger_conditions=[TriggerCondition.SOC_DECLARED_INCIDENT],
                escalated_tiers=[DataClassification.CONFIDENTIAL],
                escalated_autonomy=AutonomyLevel.APPROVAL,
                max_duration_minutes=60,
                notification_targets=["soc@example.com"],
            ),
        )
        evaluator = PolicyEvaluator(profile)

        # Without emergency, confidential is denied
        assert evaluator.evaluate("R", "confidential").allowed is False

        # With emergency, confidential is allowed under approval
        ctx = EvaluationContext(
            emergency_active=True,
            emergency_trigger=TriggerCondition.SOC_DECLARED_INCIDENT,
        )
        decision = evaluator.evaluate("R", "confidential", ctx)
        assert decision.allowed is True
        assert decision.autonomy_level == AutonomyLevel.APPROVAL
        assert decision.emergency_mode is True

        # Restricted is not in escalated_tiers, stays denied
        assert evaluator.evaluate("R", "restricted", ctx).allowed is False

    def test_get_all_permissions_dc2d(self, basic_dc2d_profile: ProfileDC2D) -> None:
        evaluator = PolicyEvaluator(basic_dc2d_profile)
        perms = evaluator.get_all_permissions()
        assert perms["public"] == ["allowed"]
        assert perms["internal"] == ["allowed"]
        assert perms["confidential"] == ["allowed"]
        assert perms["restricted"] == []

    def test_get_effective_autonomy_matrix_dc2d(self, basic_dc2d_profile: ProfileDC2D) -> None:
        evaluator = PolicyEvaluator(basic_dc2d_profile)
        matrix = evaluator.get_effective_autonomy_matrix()
        assert matrix == {
            "public": "autonomous",
            "internal": "logged",
            "confidential": "approval",
            "restricted": "prohibited",
        }


class TestProfileDC2DLoaderAndValidator:
    """End-to-end: schema validation + loader for DC2D."""

    def test_loader_accepts_dc2d_dict(self) -> None:
        from rmacd.loader import ProfileLoader

        data = {
            "profile_id": "rmacd-dc2d-loader-test-v1",
            "profile_name": "Loader Test",
            "model": "data-classification-2d",
            "version": "1.0",
            "data_access": {
                "public": {"allowed": True, "autonomy": "autonomous"},
                "internal": {"allowed": True, "autonomy": "logged"},
                "confidential": {"allowed": True, "autonomy": "approval"},
                "restricted": {"allowed": False, "autonomy": "prohibited"},
            },
        }
        profile = ProfileLoader().load_dict(data)
        assert isinstance(profile, ProfileDC2D)
        assert profile.data_access.confidential.autonomy == AutonomyLevel.APPROVAL

    def test_validator_accepts_example_file(self) -> None:
        from pathlib import Path

        from rmacd.validator import ProfileValidator

        example = (
            Path(__file__).parent.parent.parent.parent
            / "schemas"
            / "examples"
            / "regulated-data-handler-dc2d.json"
        )
        if not example.exists():
            pytest.skip(f"Example file not found at {example}")
        validator = ProfileValidator()
        assert validator.is_valid(example)
