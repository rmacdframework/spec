"""Tests for the v0.9.0 registry upgrades: shell-keyword/process-substitution
bash classification, destructive-binary coverage, registry management methods,
denial auditing, MCP bridge provenance + capability ceilings, and the optional
LLM classifier (exercised against a fake client — no network)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from rmacd.models import Operation
from rmacd.registry import (
    LLMToolClassifier,
    MCPRegistryBridge,
    MCPTool,
    ToolClassification,
    ToolDefinition,
    ToolsRegistry,
    classify_bash_command,
)

R, M, A, C, D = (
    Operation.READ,
    Operation.MOVE,
    Operation.ADD,
    Operation.CHANGE,
    Operation.DELETE,
)


# ---------------------------------------------------------------------------
# bash classifier
# ---------------------------------------------------------------------------


class TestBashShellConstructs:
    @pytest.mark.parametrize(
        ("command", "expected"),
        [
            # control-keyword prefixes must not hide the real command
            ('for f in *.log; do rm "$f"; done', D),
            ("if grep -q error log.txt; then rm log.txt; fi", D),
            ("while true; do echo waiting; done", R),
            ("until test -f done.flag; do sleep 1; done", C),  # sleep unknown → fail-closed
            ("if [ -f /tmp/x ]; then cat /tmp/x; fi", R),
            # test expressions are read-only, their args are not binaries
            ("[ -f /etc/passwd ] && cat /etc/passwd", R),
            ("[[ -n $VAR ]] && echo ok", R),
            # process substitution runs inner commands
            ("diff <(ls dir-a) <(ls dir-b)", R),
            ("diff <(rm -rf scratch) report.txt", D),
            ("tee >(gzip -c > out.gz)", C),  # redirect inside substitution
        ],
    )
    def test_shell_constructs(self, command: str, expected: Operation) -> None:
        assert classify_bash_command(command).operation == expected


class TestBashDestructiveBinaries:
    @pytest.mark.parametrize(
        ("command", "expected"),
        [
            ("mkfs.ext4 /dev/sdb1", D),
            ("mkfs -t xfs /dev/sdb1", D),
            ("wipefs -a /dev/sdb", D),
            ("mkswap /dev/sdb2", D),
            ("userdel -r bob", D),
            ("useradd -m bob", A),
            ("groupdel staff", D),
            ("fdisk /dev/sda", D),
            ("fdisk -l", R),
            ("parted --list", R),
            ("parted /dev/sda mklabel gpt", D),
            ("reboot", C),
            ("shutdown -h now", C),
        ],
    )
    def test_destructive_binaries(self, command: str, expected: Operation) -> None:
        assert classify_bash_command(command).operation == expected


# ---------------------------------------------------------------------------
# registry management + denial auditing
# ---------------------------------------------------------------------------


def _tool(tool_id: str, level: str, **kwargs) -> ToolDefinition:
    return ToolDefinition(tool_id=tool_id, tool_name=tool_id, rmacd_level=level, **kwargs)


class TestRegistryManagement:
    def test_unregister_removes_tool_and_index(self) -> None:
        reg = ToolsRegistry("t")
        reg.register_tool(_tool("victim", "D"))
        assert reg.unregister_tool("victim") is True
        assert "victim" not in reg
        assert reg.get_tools_by_level("D") == []

    def test_unregister_missing_returns_false(self) -> None:
        assert ToolsRegistry("t").unregister_tool("ghost") is False

    def test_list_iter_and_tag_query(self) -> None:
        reg = ToolsRegistry("t")
        reg.register_tool(_tool("a", "R", tags={"mcp"}))
        reg.register_tool(_tool("b", "C", tags={"manual"}))
        assert {t.tool_id for t in reg.list_tools()} == {"a", "b"}
        assert {t.tool_id for t in reg} == {"a", "b"}
        assert [t.tool_id for t in reg.get_tools_by_tag("mcp")] == ["a"]

    def test_denials_are_audited(self) -> None:
        reg = ToolsRegistry("t")
        reg.register_tool(_tool("dropper", "D"))
        allowed, _ = reg.validate_tool_access("dropper", ["R"])
        assert allowed is False
        last = reg.get_audit_log(last_n=1)[0]
        assert last["action"] == "validate_access"
        assert last["details"]["allowed"] is False
        assert "reason" in last["details"]

    def test_unknown_tool_denial_is_audited(self) -> None:
        reg = ToolsRegistry("t")
        reg.validate_tool_access("ghost", ["D"])
        assert reg.get_audit_log(last_n=1)[0]["details"]["allowed"] is False

    def test_denial_reason_names_operation_not_rank(self) -> None:
        reg = ToolsRegistry("t")
        reg.register_tool(_tool("dropper", "D"))
        _, reason = reg.validate_tool_access("dropper", ["R", "M"])
        assert "highest allowed is M" in reason
        assert "rank" not in reason


# ---------------------------------------------------------------------------
# MCP bridge: provenance, ceilings, shared registry
# ---------------------------------------------------------------------------


class TestMCPBridge:
    def test_bridge_registers_into_provided_registry(self) -> None:
        reg = ToolsRegistry("enforcer-registry")
        bridge = MCPRegistryBridge(registry=reg)
        bridge.register_mcp_tool(
            MCPTool(name="file-search", description="Search files", inputSchema={})
        )
        assert reg.get_tool("file_search") is not None

    def test_capability_ceiling_caps_at_inferred_level(self) -> None:
        bridge = MCPRegistryBridge()
        tool = bridge.register_mcp_tool(
            MCPTool(name="log-viewer", description="View and search logs", inputSchema={})
        )
        assert tool.rmacd_level == R
        assert tool.permits(R, None) is True
        assert tool.permits(C, None) is False  # ceiling blocks escalation

    def test_keyword_match_records_high_confidence_provenance(self) -> None:
        bridge = MCPRegistryBridge()
        tool = bridge.register_mcp_tool(
            MCPTool(name="delete-bucket", description="", inputSchema={})
        )
        cls = tool.metadata["classification"]
        assert cls == {"engine": "keyword", "evidence": "delete", "confidence": "high"}
        assert tool.rmacd_level == D

    def test_no_keyword_match_flags_low_confidence(self) -> None:
        bridge = MCPRegistryBridge()
        bridge.register_mcp_tool(
            MCPTool(name="frobnicator", description="Frobnicates the doohickey", inputSchema={})
        )
        flagged = bridge.low_confidence_tools()
        assert [t.tool_id for t in flagged] == ["frobnicator"]

    def test_bulk_register_accepts_raw_mcp_dicts(self) -> None:
        bridge = MCPRegistryBridge()
        registered = bridge.register_mcp_tools([
            {"name": "get-weather", "description": "Get weather", "inputSchema": {}},
            MCPTool(name="purge-cache", description="", inputSchema={}),
        ])
        assert [t.rmacd_level for t in registered] == [R, D]
        assert len(bridge.registry) == 2

    def test_secret_bearing_schema_is_restricted(self) -> None:
        tool = MCPTool(
            name="vault-reader",
            description="Read entries",
            inputSchema={"properties": {"api_key": {"type": "string"}}},
        ).to_rmacd_tool()
        assert tool["data_access"] == "restricted"


# ---------------------------------------------------------------------------
# LLM classifier (fake client — no network)
# ---------------------------------------------------------------------------


class FakeAnthropicClient:
    """Stands in for anthropic.Anthropic — records parse() calls."""

    def __init__(self, result: ToolClassification | Exception) -> None:
        self._result = result
        self.calls: list[dict] = []
        self.messages = SimpleNamespace(parse=self._parse)

    def _parse(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self._result, Exception):
            raise self._result
        return SimpleNamespace(parsed_output=self._result)


def _llm(result: ToolClassification | Exception) -> tuple[LLMToolClassifier, FakeAnthropicClient]:
    fake = FakeAnthropicClient(result)
    return LLMToolClassifier(client=fake), fake


class TestLLMClassifier:
    def test_classify_returns_structured_result(self) -> None:
        expected = ToolClassification(
            rmacd_level="C", data_access="confidential",
            required_hitl="approval", rationale="Executes SQL.", confidence=0.9,
        )
        clf, fake = _llm(expected)
        result = clf.classify(name="run_query", input_schema={"properties": {"sql": {}}})
        assert result is expected
        assert fake.calls[0]["model"] == "claude-fable-5"
        assert "run_query" in fake.calls[0]["messages"][0]["content"]

    def test_fallback_mode_skips_llm_when_keywords_are_confident(self) -> None:
        clf, fake = _llm(Exception("must not be called"))
        bridge = MCPRegistryBridge(llm_classifier=clf, llm_mode="fallback")
        tool = bridge.register_mcp_tool(
            MCPTool(name="delete-file", description="", inputSchema={})
        )
        assert fake.calls == []
        assert tool.metadata["classification"]["engine"] == "keyword"

    def test_fallback_mode_uses_llm_for_ambiguous_tools(self) -> None:
        clf, fake = _llm(ToolClassification(
            rmacd_level="D", data_access="internal",
            required_hitl="elevated_approval",
            rationale="Frobnicating destroys the doohickey.", confidence=0.85,
        ))
        bridge = MCPRegistryBridge(llm_classifier=clf, llm_mode="fallback")
        tool = bridge.register_mcp_tool(
            MCPTool(name="frobnicator", description="Frobnicates the doohickey", inputSchema={})
        )
        assert len(fake.calls) == 1
        assert tool.rmacd_level == D
        assert tool.permits(D, None) is True  # ceiling raised with the level
        cls = tool.metadata["classification"]
        assert cls["engine"] == "llm"
        assert cls["confidence"] == "high"
        assert bridge.low_confidence_tools() == []

    def test_always_mode_classifies_everything(self) -> None:
        clf, fake = _llm(ToolClassification(
            rmacd_level="R", data_access="internal",
            required_hitl="logged", rationale="Read-only.", confidence=0.95,
        ))
        bridge = MCPRegistryBridge(llm_classifier=clf, llm_mode="always")
        bridge.register_mcp_tool(MCPTool(name="delete-file", description="", inputSchema={}))
        assert len(fake.calls) == 1

    def test_llm_failure_degrades_to_keyword_result(self) -> None:
        clf, _ = _llm(RuntimeError("api unreachable"))
        bridge = MCPRegistryBridge(llm_classifier=clf, llm_mode="always")
        tool = bridge.register_mcp_tool(
            MCPTool(name="delete-file", description="", inputSchema={})
        )
        assert tool.rmacd_level == D  # keyword result survives
        cls = tool.metadata["classification"]
        assert cls["engine"] == "keyword"
        assert "api unreachable" in cls["llm_error"]

    def test_low_llm_confidence_keeps_tool_in_review_queue(self) -> None:
        clf, _ = _llm(ToolClassification(
            rmacd_level="C", data_access="internal",
            required_hitl="approval", rationale="Unclear.", confidence=0.4,
        ))
        bridge = MCPRegistryBridge(llm_classifier=clf, llm_mode="always")
        bridge.register_mcp_tool(MCPTool(name="frobnicator", description="", inputSchema={}))
        assert [t.tool_id for t in bridge.low_confidence_tools()] == ["frobnicator"]
