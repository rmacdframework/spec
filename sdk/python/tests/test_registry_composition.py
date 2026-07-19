"""Multi-pack composition on shared tool names (rmacd.packs.composition).

Covers the "last pack wins" fix: several governance packs overlaying the same
shell tool (git/docker/terraform on ``bash``) compose into an ordered chain —
per call, the pack whose rules match governs with *its own* capability ceiling,
falling through on no-match to the next pack and finally to any pre-pack
registration. Same-pack re-application stays idempotent, and the §12.5 floor
still applies end-to-end through a composed chain.
"""

from __future__ import annotations

from typing import Any

import pytest

from rmacd import (
    PolicyEnforcer,
    RMACDProhibitedError,
    RMACDToolCapabilityError,
)
from rmacd.approval import AutoApproveGateway
from rmacd.models import DataClassification as DC
from rmacd.models import Operation as Op
from rmacd.models import Profile3D
from rmacd.packs import (
    ComposedToolDefinition,
    apply_pack,
    load_pack,
    load_packs,
)
from rmacd.registry import ToolDefinition, ToolsRegistry


def _dev_profile() -> Profile3D:
    """Permissive 3D profile *without* Change/Delete on restricted."""
    return Profile3D(
        profile_id="rmacd-3d-devtools",
        profile_name="Dev Tools",
        model="three-dimensional",
        version="1.0",
        permissions={
            DC.PUBLIC: [Op.READ, Op.MOVE, Op.ADD, Op.CHANGE, Op.DELETE],
            DC.INTERNAL: [Op.READ, Op.MOVE, Op.ADD, Op.CHANGE, Op.DELETE],
            DC.CONFIDENTIAL: [Op.READ, Op.MOVE, Op.ADD, Op.CHANGE, Op.DELETE],
            DC.RESTRICTED: [Op.READ],
        },
    )


def _enforcer(registry: ToolsRegistry) -> PolicyEnforcer:
    return PolicyEnforcer(
        profile=_dev_profile(),
        agent_id="agent-1",
        registry=registry,
        approval_gateway=AutoApproveGateway(),
    )


# --- (a) each pack governs its own calls through the shared bash tool ----------
class TestChainedResolution:
    @pytest.fixture()
    def registry(self) -> ToolsRegistry:
        return load_packs(["git", "docker", "terraform"])

    def test_bash_is_composed_with_all_three_packs(self, registry: ToolsRegistry) -> None:
        bash = registry.get_tool("bash")
        assert isinstance(bash, ComposedToolDefinition)
        assert bash.metadata["packs"] == ["git", "docker", "terraform"]

    def test_git_force_push_resolves_to_git_pack(self, registry: ToolsRegistry) -> None:
        bash = registry.get_tool("bash")
        assert bash is not None
        resolved = bash.resolve_call({"command": "git push --force origin main"})
        assert resolved.source == "git"
        assert resolved.operation == Op.CHANGE
        assert resolved.tier == DC.RESTRICTED
        # ...and the floor blocks it end-to-end even though docker/terraform
        # are chained on the same tool name.
        with pytest.raises(RMACDProhibitedError):
            _enforcer(registry).enforce_tool_call(
                "bash", {"command": "git push --force origin main"}
            )

    def test_docker_rm_resolves_to_docker_pack(self, registry: ToolsRegistry) -> None:
        bash = registry.get_tool("bash")
        assert bash is not None
        resolved = bash.resolve_call({"command": "docker rm web"})
        assert resolved.source == "docker"
        assert resolved.operation == Op.DELETE
        assert resolved.tier == DC.CONFIDENTIAL
        decision = _enforcer(registry).enforce_tool_call("bash", {"command": "docker rm web"})
        assert decision.allowed is True
        assert decision.operation == Op.DELETE
        assert decision.data_classification == DC.CONFIDENTIAL

    def test_terraform_destroy_resolves_to_terraform_pack(
        self, registry: ToolsRegistry
    ) -> None:
        bash = registry.get_tool("bash")
        assert bash is not None
        resolved = bash.resolve_call({"command": "terraform destroy"})
        assert resolved.source == "terraform"
        assert resolved.operation == Op.DELETE
        assert resolved.tier == DC.RESTRICTED
        with pytest.raises(RMACDProhibitedError):
            _enforcer(registry).enforce_tool_call("bash", {"command": "terraform destroy"})

    def test_direct_cli_tools_stay_plain_single_pack(self, registry: ToolsRegistry) -> None:
        # Only the shared shell tool names compose; "git"/"docker"/"terraform"
        # each belong to exactly one pack and remain plain definitions.
        for name in ("git", "docker", "terraform"):
            tool = registry.get_tool(name)
            assert tool is not None
            assert not isinstance(tool, ComposedToolDefinition)


# --- (b) order independence ----------------------------------------------------
class TestOrderIndependence:
    COMMANDS = [
        "git push --force origin main",
        "git status",
        "docker rm web",
        "docker push registry/app:1.0",
        "terraform destroy",
        "terraform state rm aws_instance.web",
        "make clean",
    ]

    @pytest.mark.parametrize("command", COMMANDS)
    def test_disjoint_claims_resolve_identically_in_any_order(self, command: str) -> None:
        orders = [
            ["git", "docker", "terraform", "make"],
            ["make", "terraform", "docker", "git"],
            ["docker", "make", "git", "terraform"],
        ]
        outcomes = set()
        for order in orders:
            bash = load_packs(order).get_tool("bash")
            assert bash is not None
            resolved = bash.resolve_call({"command": command})
            outcomes.add((resolved.operation, resolved.tier, resolved.source))
        assert len(outcomes) == 1, f"{command!r}: order-dependent -> {outcomes}"

    def test_broad_shell_base_rule_does_not_shadow_later_specific_packs(self) -> None:
        # shell's coreutils rule matches *every* bash command (tool-name-only
        # selector) — it must not swallow git's claim even when loaded first.
        for order in (["shell", "git"], ["git", "shell"]):
            bash = load_packs(order).get_tool("bash")
            assert bash is not None
            forced = bash.resolve_call({"command": "git push --force origin main"})
            assert (forced.source, forced.tier) == ("git", DC.RESTRICTED), order
            # ...while plain coreutils calls still fall through to shell.
            ls = bash.resolve_call({"command": "ls -la"})
            assert (ls.source, ls.operation, ls.tier) == ("shell", Op.READ, DC.INTERNAL)


# --- (c) same-pack reapply is idempotent ----------------------------------------
class TestIdempotentReapply:
    def test_reapplying_a_chained_pack_replaces_its_entry_in_place(self) -> None:
        registry = load_packs(["git", "docker"])
        bash = registry.get_tool("bash")
        assert isinstance(bash, ComposedToolDefinition)
        before = [type(e).__name__ for e in bash.entries]
        assert bash.metadata["packs"] == ["git", "docker"]

        apply_pack(registry, load_pack("git"))  # reload git (e.g. config re-read)

        bash2 = registry.get_tool("bash")
        assert isinstance(bash2, ComposedToolDefinition)
        assert bash2.metadata["packs"] == ["git", "docker"]  # no duplicate, same slot
        assert len(bash2.entries) == len(before) == 2
        resolved = bash2.resolve_call({"command": "docker rm web"})
        assert resolved.source == "docker"  # docker still governs its calls

    def test_reapplying_a_single_pack_stays_plain(self) -> None:
        registry = load_packs(["git"])
        apply_pack(registry, load_pack("git"))
        bash = registry.get_tool("bash")
        assert bash is not None
        assert not isinstance(bash, ComposedToolDefinition)
        assert bash.metadata["pack"] == "git"


# --- (d) ceilings do not cross-contaminate --------------------------------------
def _mini_pack(
    name: str, marker: str, operation: str, capability: list[str]
) -> dict[str, Any]:
    """A tiny pack claiming tool 'runner' when *marker* appears in the command."""
    return {
        "pack": name,
        "version": "1.0.0",
        "default_operation": "C",
        "rules": [
            {
                "id": f"{name}-rule",
                "when": {
                    "tool": "runner",
                    "arg_regex": {"arg": "command", "pattern": marker},
                },
                "classify": {"operation": operation, "tier": "internal"},
                "capability": capability,
            }
        ],
    }


class TestCeilingIsolation:
    def test_matching_pack_ceiling_gates_not_a_union(self) -> None:
        # Pack A claims 'alpha' calls but (mis)classifies them as Delete while
        # its own ceiling only ever permits Read. Pack B claims 'beta' calls
        # with a full ceiling. If ceilings were unioned, A's Delete would slip
        # through under B's ceiling.
        read_only = _mini_pack("aa", "alpha", "D", ["R"])
        full = _mini_pack("bb", "beta", "D", ["R", "M", "A", "C", "D"])
        registry = load_packs([read_only, full])

        runner = registry.get_tool("runner")
        assert isinstance(runner, ComposedToolDefinition)

        alpha = runner.resolve_call({"command": "alpha"})
        assert (alpha.source, alpha.operation) == ("aa", Op.DELETE)
        assert alpha.capability is not None
        assert not alpha.capability.permits(Op.DELETE, alpha.tier)  # A's own ceiling

        beta = runner.resolve_call({"command": "beta"})
        assert (beta.source, beta.operation) == ("bb", Op.DELETE)
        assert beta.capability is not None
        assert beta.capability.permits(Op.DELETE, beta.tier)  # B's own ceiling

        # End-to-end: the capability gate fires for A's call, not B's.
        enforcer = _enforcer(registry)
        with pytest.raises(RMACDToolCapabilityError):
            enforcer.enforce_tool_call("runner", {"command": "alpha"})
        decision = enforcer.enforce_tool_call("runner", {"command": "beta"})
        assert decision.allowed is True

    def test_git_match_does_not_inherit_docker_ceiling(self) -> None:
        bash = load_packs(["git", "docker"]).get_tool("bash")
        assert bash is not None
        resolved = bash.resolve_call({"command": "git status"})
        assert resolved.source == "git"
        assert resolved.capability is not None
        # The attached ceiling is exactly git's declared ceiling for bash.
        git_only = load_packs(["git"]).get_tool("bash")
        assert git_only is not None
        assert git_only.capability is not None
        assert resolved.capability.to_dict() == git_only.capability.to_dict()


# --- fallback to the pre-pack registration --------------------------------------
class TestPrePackFallback:
    def test_user_registered_tool_survives_as_chain_fallback(self) -> None:
        registry = ToolsRegistry()
        registry.register_tool(
            ToolDefinition("bash", "Bash (user default)", Op.CHANGE, data_access=DC.INTERNAL)
        )
        for name in ("git", "docker"):
            apply_pack(registry, load_pack(name))

        bash = registry.get_tool("bash")
        assert isinstance(bash, ComposedToolDefinition)
        assert bash.fallback is not None

        # Unclaimed by either pack -> the pre-pack definition classifies it.
        resolved = bash.resolve_call({"command": "ls -la"})
        assert resolved.source == "fallback:bash"
        assert resolved.operation == Op.CHANGE
        assert resolved.tier == DC.INTERNAL
        # Claimed calls still route to the packs.
        assert bash.resolve_call({"command": "git status"}).source == "git"

    def test_no_claim_no_fallback_uses_first_pack_default(self) -> None:
        bash = load_packs(["git", "docker"]).get_tool("bash")
        assert bash is not None
        resolved = bash.resolve_call({"command": "ls -la"})
        assert resolved.source == "git"  # first-applied pack's fail-closed default
        assert resolved.operation == Op.CHANGE  # git's default_operation

    def test_direct_register_tool_keeps_replace_semantics(self) -> None:
        registry = load_packs(["git", "docker"])
        assert isinstance(registry.get_tool("bash"), ComposedToolDefinition)
        # A direct user registration replaces the composed chain outright —
        # composition is a pack-layer behaviour only.
        registry.register_tool(ToolDefinition("bash", "Mine", Op.READ))
        bash = registry.get_tool("bash")
        assert bash is not None
        assert not isinstance(bash, ComposedToolDefinition)
        assert bash.rmacd_level == Op.READ


# --- (e) §12.5 floor end-to-end through a composed chain ------------------------
@pytest.mark.parametrize(
    "command",
    [
        "git push --force origin main",
        "docker login registry.example.com",
        "terraform apply -auto-approve",
        "terraform state rm aws_instance.web",
    ],
)
def test_floor_blocks_restricted_ops_through_composed_bash(command: str) -> None:
    enforcer = _enforcer(load_packs(["git", "docker", "terraform"]))
    with pytest.raises(RMACDProhibitedError):
        enforcer.enforce_tool_call("bash", {"command": command})


def test_ordinary_calls_still_flow_through_composed_bash() -> None:
    enforcer = _enforcer(load_packs(["git", "docker", "terraform"]))
    decision = enforcer.enforce_tool_call("bash", {"command": "git push origin main"})
    assert decision.allowed is True
    assert decision.operation == Op.CHANGE
    assert decision.data_classification == DC.CONFIDENTIAL


# --- serialization round-trip ---------------------------------------------------
def test_composed_tool_survives_registry_export_import(tmp_path: Any) -> None:
    registry = load_packs(["git", "docker"])
    path = tmp_path / "registry.json"
    assert registry.export_to_json(path) is True

    restored = ToolsRegistry("restored")
    assert restored.import_from_json(path) is True
    bash = restored.get_tool("bash")
    assert isinstance(bash, ComposedToolDefinition)
    assert bash.metadata["packs"] == ["git", "docker"]

    for command, source, op, tier in [
        ("git push --force origin main", "git", Op.CHANGE, DC.RESTRICTED),
        ("docker rm web", "docker", Op.DELETE, DC.CONFIDENTIAL),
    ]:
        resolved = bash.resolve_call({"command": command})
        assert (resolved.source, resolved.operation, resolved.tier) == (source, op, tier)
