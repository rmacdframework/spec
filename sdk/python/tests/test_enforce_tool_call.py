"""Tests for PolicyEnforcer.enforce_tool_call / evaluate_tool_call (profile ∩ tool)."""

from __future__ import annotations

import pytest

from rmacd import (
    PolicyEnforcer,
    RMACDPermissionDeniedError,
    RMACDProhibitedError,
    RMACDToolCapabilityError,
)
from rmacd.approval import AutoApproveGateway
from rmacd.models import AutonomyLevel, DataClassification as DC, Operation as Op, Profile3D
from rmacd.registry import ToolCapability, ToolDefinition, ToolsRegistry


@pytest.fixture
def profile() -> Profile3D:
    # Read everywhere; Move on public/internal; Add on public only.
    return Profile3D(
        profile_id="rmacd-3d-demo",
        profile_name="Demo",
        model="three-dimensional",
        version="1.0",
        permissions={
            DC.PUBLIC: [Op.READ, Op.MOVE, Op.ADD],
            DC.INTERNAL: [Op.READ, Op.MOVE],
            DC.CONFIDENTIAL: [Op.READ],
            DC.RESTRICTED: [Op.READ],
        },
    )


@pytest.fixture
def registry() -> ToolsRegistry:
    reg = ToolsRegistry()
    reg.register_tool(
        ToolDefinition("read_cfg", "Read Config", Op.READ, data_access="internal",
                       capability=ToolCapability(operations={Op.READ}))
    )
    reg.register_tool(
        ToolDefinition("edit_cfg", "Edit Config", Op.CHANGE, data_access="internal")
    )
    # mislabeled: claims Delete but capability ceiling is read-only
    reg.register_tool(
        ToolDefinition("safe_search", "Safe Search", Op.DELETE, data_access="internal",
                       capability=ToolCapability(operations={Op.READ}))
    )
    # restricted delete: profile + tool would both allow, but §12.5 floor must block
    reg.register_tool(
        ToolDefinition("purge", "Purge", Op.DELETE, data_access="restricted",
                       capability=ToolCapability(per_tier={DC.RESTRICTED: {Op.DELETE}}))
    )
    return reg


@pytest.fixture
def enforcer(profile, registry) -> PolicyEnforcer:
    return PolicyEnforcer(profile=profile, agent_id="agent-1", registry=registry)


class TestProfileIntersectTool:
    def test_allowed_when_both_gates_pass(self, enforcer):
        decision = enforcer.enforce_tool_call("read_cfg", {})
        assert decision.allowed is True
        assert decision.operation == Op.READ
        assert decision.data_classification == DC.INTERNAL

    def test_profile_gate_denies(self, enforcer):
        # Tool capability would allow C, but the agent profile lacks C@internal.
        with pytest.raises(RMACDPermissionDeniedError):
            enforcer.enforce_tool_call("edit_cfg", {})

    def test_capability_gate_denies_before_profile(self, enforcer):
        # The tool's own ceiling forbids Delete regardless of the agent.
        with pytest.raises(RMACDToolCapabilityError):
            enforcer.enforce_tool_call("safe_search", {})

    def test_safety_floor_blocks_even_when_both_would_allow(self, enforcer):
        # profile grants R@restricted, tool capability grants D@restricted, but
        # §12.5 makes Delete-on-Restricted prohibited for any agent.
        with pytest.raises(RMACDProhibitedError):
            enforcer.enforce_tool_call("purge", {})

    def test_unknown_tool_fails_closed(self, enforcer):
        with pytest.raises(RMACDPermissionDeniedError, match="not registered"):
            enforcer.enforce_tool_call("ghost_tool", {})

    def test_requires_registry(self, profile):
        enf = PolicyEnforcer(profile=profile, agent_id="a")
        with pytest.raises(ValueError, match="requires a ToolsRegistry"):
            enf.enforce_tool_call("read_cfg", {})


class TestDynamicClassifier:
    def test_tier_resolved_from_args(self, profile):
        reg = ToolsRegistry()

        def classify(args):
            tier = "confidential" if str(args.get("ns", "")).startswith("prod") else "internal"
            return ("M", tier, f"k8s://{args.get('ns')}")

        reg.register_tool(
            ToolDefinition("migrate", "Migrate", Op.MOVE, classifier=classify)
        )
        enf = PolicyEnforcer(profile=profile, agent_id="a", registry=reg)

        # staging → Move@internal → profile allows
        d = enf.enforce_tool_call("migrate", {"ns": "staging"})
        assert d.allowed and d.data_classification == DC.INTERNAL

        # prod → Move@confidential → profile only grants Read on confidential
        with pytest.raises(RMACDPermissionDeniedError):
            enf.enforce_tool_call("migrate", {"ns": "prod-db"})


class TestApprovalRouting:
    def test_approval_required_routes_through_gateway(self):
        # Profile grants Change@internal, which the default matrix scores APPROVAL.
        profile = Profile3D(
            profile_id="rmacd-3d-cab", profile_name="CAB", model="three-dimensional",
            version="1.0",
            permissions={
                DC.PUBLIC: [Op.READ], DC.INTERNAL: [Op.READ, Op.CHANGE],
                DC.CONFIDENTIAL: [Op.READ], DC.RESTRICTED: [Op.READ],
            },
        )
        reg = ToolsRegistry()
        reg.register_tool(ToolDefinition("edit_cfg", "Edit Config", Op.CHANGE, data_access="internal"))
        enf = PolicyEnforcer(
            profile=profile, agent_id="a", registry=reg,
            approval_gateway=AutoApproveGateway(),
        )
        d = enf.enforce_tool_call("edit_cfg", {})
        assert d.allowed is True
        assert d.autonomy_level == AutonomyLevel.APPROVAL


class TestEvaluateToolCall:
    def test_dry_run_reflects_capability(self, enforcer):
        d = enforcer.evaluate_tool_call("safe_search", {})
        assert d.allowed is False
        assert d.autonomy_level == AutonomyLevel.PROHIBITED

    def test_dry_run_allowed(self, enforcer):
        assert enforcer.evaluate_tool_call("read_cfg", {}).allowed is True
