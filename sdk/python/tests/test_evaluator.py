"""Tests for the PolicyEvaluator."""

import pytest

from rmacd.evaluator import PolicyEvaluator
from rmacd.models import (
    AutonomyLevel,
    DataClassification,
    EmergencyEscalation3D,
    EvaluationContext,
    Operation,
    Profile2D,
    Profile3D,
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
