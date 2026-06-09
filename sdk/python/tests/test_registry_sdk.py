"""Tests for the SDK registry (rmacd.registry.tools and rmacd.registry.mcp)."""

from __future__ import annotations

import pytest

from rmacd.models import AutonomyLevel, DataClassification, Operation
from rmacd.registry.mcp import MCPTool
from rmacd.registry.tools import ToolCapability, ToolDefinition, ToolsRegistry


class TestToolDefinition:
    def test_risk_score_autocomputed_when_omitted(self) -> None:
        tool = ToolDefinition(tool_id="t1", tool_name="T1", rmacd_level=Operation.DELETE)
        assert tool.risk_score is not None and tool.risk_score > 0

    def test_explicit_zero_risk_score_is_preserved(self) -> None:
        # Regression: the old 0.0 sentinel meant an explicit 0.0 was silently
        # recomputed. With a None sentinel, an explicit 0.0 must survive.
        tool = ToolDefinition(
            tool_id="t2", tool_name="T2", rmacd_level=Operation.DELETE, risk_score=0.0
        )
        assert tool.risk_score == 0.0

    def test_tool_id_normalized(self) -> None:
        tool = ToolDefinition(tool_id="  My Tool ", tool_name="X", rmacd_level="R")
        assert tool.tool_id == "my_tool"

    def test_created_at_is_timezone_aware(self) -> None:
        tool = ToolDefinition(tool_id="t3", tool_name="T3", rmacd_level="R")
        assert tool.created_at.tzinfo is not None


class TestValidateToolAccess:
    def _registry(self) -> ToolsRegistry:
        reg = ToolsRegistry()
        reg.register_tool(
            ToolDefinition(
                tool_id="reader",
                tool_name="Reader",
                rmacd_level=Operation.READ,
                data_access=DataClassification.CONFIDENTIAL,
            )
        )
        return reg

    def test_tier_ordering_blocks_insufficient_clearance(self) -> None:
        reg = self._registry()
        ok, _ = reg.validate_tool_access("reader", [Operation.READ], DataClassification.INTERNAL)
        assert ok is False  # tool needs confidential, only internal allowed

    def test_tier_ordering_allows_sufficient_clearance(self) -> None:
        reg = self._registry()
        ok, _ = reg.validate_tool_access(
            "reader", [Operation.READ], DataClassification.RESTRICTED
        )
        assert ok is True

    def test_prohibited_hitl_blocks(self) -> None:
        reg = ToolsRegistry()
        reg.register_tool(
            ToolDefinition(
                tool_id="danger",
                tool_name="Danger",
                rmacd_level=Operation.DELETE,
                required_hitl=AutonomyLevel.PROHIBITED,
            )
        )
        ok, reason = reg.validate_tool_access("danger", [Operation.DELETE])
        assert ok is False and "prohibited" in reason.lower()


class TestMCPClassification:
    @pytest.mark.parametrize(
        "name,expected",
        [
            ("delete_record", "D"),
            ("update_config", "C"),
            ("create_user", "A"),
            ("move_file", "M"),
            ("list_servers", "R"),
        ],
    )
    def test_keyword_classification(self, name: str, expected: str) -> None:
        tool = MCPTool(name=name, description="", inputSchema={})
        assert tool._infer_rmacd_level() == expected

    @pytest.mark.parametrize(
        "name",
        ["asset_list", "dropdown_render", "newsletter_get", "addendum_view"],
    )
    def test_word_boundary_prevents_substring_misclassification(self, name: str) -> None:
        # "set" in asset, "drop" in dropdown, "new" in newsletter, "add" in
        # addendum must NOT be classified as mutating ops.
        tool = MCPTool(name=name, description="", inputSchema={})
        assert tool._infer_rmacd_level() == "R"

    def test_data_classification_inference_from_schema(self) -> None:
        tool = MCPTool(
            name="login",
            description="",
            inputSchema={"properties": {"password": {"type": "string"}}},
        )
        assert tool._infer_data_classification() == "restricted"


class TestClassificationAndCapability:
    def test_static_resolve_with_target_template(self) -> None:
        tool = ToolDefinition(
            "read_cfg", "Read Config", Operation.READ,
            data_access="internal", target_template="server://{server_id}",
        )
        r = tool.resolve_call({"server_id": "web-01"})
        assert (r.operation, r.tier, r.target) == (
            Operation.READ, DataClassification.INTERNAL, "server://web-01",
        )

    def test_resolve_falls_back_to_tool_uri(self) -> None:
        tool = ToolDefinition("noop", "Noop", Operation.READ)
        assert tool.resolve_call({}).target == "tool://noop"

    def test_dynamic_classifier_overrides_static(self) -> None:
        def classify(args):
            tier = "confidential" if args.get("prod") else "internal"
            return ("D", tier, f"db://{args.get('id')}")

        tool = ToolDefinition("del_row", "Delete Row", Operation.READ, classifier=classify)
        r = tool.resolve_call({"prod": True, "id": "x"})
        assert (r.operation, r.tier, r.target) == (
            Operation.DELETE, DataClassification.CONFIDENTIAL, "db://x",
        )

    def test_classifier_none_fields_fall_back(self) -> None:
        # classifier returns None tier -> falls back to the static data_access
        tool = ToolDefinition(
            "t", "T", Operation.MOVE, data_access="internal",
            classifier=lambda args: (None, None, "tgt"),
        )
        r = tool.resolve_call({})
        assert (r.operation, r.tier, r.target) == (Operation.MOVE, DataClassification.INTERNAL, "tgt")

    def test_capability_2d_membership(self) -> None:
        cap = ToolCapability(operations={Operation.READ, Operation.MOVE})
        assert cap.permits(Operation.READ, None) is True
        assert cap.permits(Operation.DELETE, None) is False

    def test_capability_3d_per_tier(self) -> None:
        cap = ToolCapability(per_tier={DataClassification.INTERNAL: {Operation.DELETE}})
        assert cap.permits(Operation.DELETE, DataClassification.INTERNAL) is True
        assert cap.permits(Operation.DELETE, DataClassification.CONFIDENTIAL) is False
        # tier-agnostic call against a per-tier ceiling defers (no block here)
        assert cap.permits(Operation.DELETE, None) is True

    def test_unset_capability_is_unconstrained(self) -> None:
        tool = ToolDefinition("t", "T", Operation.DELETE)
        assert tool.permits(Operation.DELETE, DataClassification.RESTRICTED) is True

    def test_capability_roundtrips_through_dict(self) -> None:
        tool = ToolDefinition(
            "t", "T", Operation.CHANGE,
            capability=ToolCapability(per_tier={DataClassification.PUBLIC: {Operation.CHANGE}}),
        )
        restored = ToolDefinition.from_dict(tool.to_dict())
        assert restored.permits(Operation.CHANGE, DataClassification.PUBLIC) is True
        assert restored.permits(Operation.CHANGE, DataClassification.RESTRICTED) is False


class TestRegistryIndexing:
    def test_reregister_at_new_level_clears_stale_index(self) -> None:
        reg = ToolsRegistry()
        reg.register_tool(ToolDefinition("x", "X", Operation.READ))
        reg.register_tool(ToolDefinition("x", "X", Operation.DELETE))
        assert [t.tool_id for t in reg.get_tools_by_level("R")] == []
        assert [t.tool_id for t in reg.get_tools_by_level("D")] == ["x"]
        assert reg.get_stats()["by_level"] == {"R": 0, "M": 0, "A": 0, "C": 0, "D": 1}
        assert reg.get_stats()["total_tools"] == 1

    def test_validate_tool_access_is_cumulative(self) -> None:
        reg = ToolsRegistry()
        reg.register_tool(ToolDefinition("reader", "Reader", Operation.READ))
        # An agent granted Delete implicitly satisfies a Read tool (D ⊃ R).
        ok, _ = reg.validate_tool_access("reader", [Operation.DELETE])
        assert ok is True

    def test_import_from_json_reports_partial_failure(self, tmp_path) -> None:
        reg = ToolsRegistry()
        bad = tmp_path / "reg.json"
        bad.write_text('{"tools": [{"tool_id": "ok", "tool_name": "OK", "rmacd_level": "R"}, {"tool_id": "bad"}]}')
        # one tool missing required fields -> overall False, but the good one lands
        assert reg.import_from_json(bad) is False
        assert "ok" in reg
