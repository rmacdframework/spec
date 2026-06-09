"""Tests for the SDK registry (rmacd.registry.tools and rmacd.registry.mcp)."""

from __future__ import annotations

import pytest

from rmacd.models import AutonomyLevel, DataClassification, Operation
from rmacd.registry.mcp import MCPTool
from rmacd.registry.tools import ToolDefinition, ToolsRegistry


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
