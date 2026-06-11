"""
RMACD Tools Registry - MCP Integration
=======================================

Integration with Model Context Protocol (MCP) for AI agent governance.

An MCP server advertises tools as ``(name, description, inputSchema)``. This
module classifies each one into RMACD terms and registers it with governance
controls. Two classification engines are available:

1. **Keyword heuristic** (default, zero-dependency) — word-boundary matching on
   the tool's operations/name/description. Fast and deterministic, but blind to
   semantics ("archive_user" reads as harmless; "purge_cache" reads as Delete).
2. **LLM classifier** (optional, ``rmacd.registry.llm``) — asks a Claude model
   to classify the tool definition. Used in ``fallback`` mode (only when the
   heuristic has low confidence) or ``always`` mode.

Every auto-classified tool gets:

- a **capability ceiling** capped at its inferred operation (defence in depth —
  a tool classified Read can never represent a Delete, even if a later dynamic
  classifier or an over-broad profile would allow it), and
- **provenance metadata** (``metadata["classification"]``) recording which
  engine decided, on what evidence, and with what confidence — so a human can
  review the low-confidence tail (``bridge.low_confidence_tools()``).

Author: Kash Kashyap
License: CC BY 4.0
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from rmacd.registry.tools import (
    _OP_ORDER,
    ToolDefinition,
    ToolsRegistry,
    create_registry,
    parse_operation,
)

if TYPE_CHECKING:
    from rmacd.registry.llm import LLMToolClassifier

logger = logging.getLogger(__name__)


@dataclass
class MCPTool:
    """Represents an MCP tool definition."""

    name: str
    description: str
    inputSchema: dict[str, Any]
    operations: list[str] = field(default_factory=list)

    @classmethod
    def from_mcp(cls, tool: dict[str, Any]) -> MCPTool:
        """Build from a raw MCP ``tools/list`` entry (dict with name/description/inputSchema)."""
        return cls(
            name=tool["name"],
            description=tool.get("description", ""),
            inputSchema=tool.get("inputSchema", {}),
            operations=tool.get("operations", []),
        )

    def to_rmacd_tool(self) -> dict[str, Any]:
        """
        Convert MCP tool to RMACD tool definition (keyword-heuristic engine).

        The returned dict includes a ``capability`` ceiling capped at the
        inferred operation and ``metadata["classification"]`` provenance.
        """
        rmacd_level, evidence = self._infer_rmacd_level()
        data_access = self._infer_data_classification()
        hitl_level = self._infer_hitl_requirement(rmacd_level)
        confidence: str = "high" if evidence else "low"

        op = parse_operation(rmacd_level)
        # Capability ceiling: this tool may represent its inferred operation
        # and anything weaker, never anything stronger.
        ceiling = {o.value for o, rank in _OP_ORDER.items() if rank <= _OP_ORDER[op]}

        return {
            "tool_id": self.name.lower().replace(" ", "_").replace("-", "_"),
            "tool_name": self.name,
            "rmacd_level": rmacd_level,
            "description": self.description,
            "operations": self.operations or [],
            "data_access": data_access,
            "required_hitl": hitl_level,
            "capability": {"operations": sorted(ceiling)},
            "tags": {"mcp", "auto-classified"},
            "metadata": {
                "source": "mcp",
                "input_schema": self.inputSchema,
                "classification": {
                    "engine": "keyword",
                    "evidence": evidence,
                    "confidence": confidence,
                },
            },
        }

    def _infer_rmacd_level(self) -> tuple[str, str | None]:
        """
        Infer RMACD level from tool operations.

        Uses keyword matching to determine risk level:
        - READ: query, search, get, list, view, read, fetch, retrieve
        - MOVE: move, transfer, copy, relocate, migrate
        - ADD: create, add, post, upload, insert, provision
        - CHANGE: update, modify, edit, patch, configure, set, commit, push
        - DELETE: delete, remove, destroy, purge, drop

        Returns ``(level, matched_keyword)`` — keyword is None when nothing
        matched and the level fell back to the Read default (low confidence).
        """
        if not self.operations:
            text = f"{self.name} {self.description}".lower()
        else:
            text = " ".join(self.operations).lower()

        def find_keyword(keywords: list[str]) -> str | None:
            # Match on whole-word boundaries so e.g. "drop" does not fire on
            # "dropdown" and "set" does not fire on "asset". Treats common
            # identifier separators (_ - .) as word boundaries too.
            for k in keywords:
                if re.search(rf"(?<![a-z0-9]){re.escape(k)}(?![a-z0-9])", text):
                    return k
            return None

        # Check in order of decreasing risk
        delete_keywords = ["delete", "remove", "destroy", "purge", "drop", "erase"]
        if (kw := find_keyword(delete_keywords)) is not None:
            return "D", kw

        change_keywords = [
            "update", "modify", "edit", "patch", "configure",
            "set", "change", "alter", "commit", "push",
        ]
        if (kw := find_keyword(change_keywords)) is not None:
            return "C", kw

        add_keywords = ["create", "add", "post", "upload", "insert", "provision", "deploy", "new"]
        if (kw := find_keyword(add_keywords)) is not None:
            return "A", kw

        move_keywords = ["move", "transfer", "copy", "relocate", "migrate", "forward", "rename"]
        if (kw := find_keyword(move_keywords)) is not None:
            return "M", kw

        read_keywords = [
            "query", "search", "get", "list", "view", "read", "fetch", "retrieve",
            "describe", "show", "watch", "check",
        ]
        if (kw := find_keyword(read_keywords)) is not None:
            return "R", kw

        # No evidence at all: still Read, but flagged low-confidence so a
        # human (or the LLM classifier) reviews it.
        return "R", None

    def _infer_data_classification(self) -> str:
        """Infer data classification from input schema."""
        schema_str = json.dumps(self.inputSchema).lower()

        secret_terms = [
            "password", "secret", "credential", "ssn", "credit_card",
            "private_key", "api_key", "access_token", "auth_token",
        ]
        if any(term in schema_str for term in secret_terms):
            return "restricted"

        if any(term in schema_str for term in ["confidential", "private", "sensitive"]):
            return "confidential"

        if any(term in schema_str for term in ["internal", "company"]):
            return "internal"

        return "internal"

    def _infer_hitl_requirement(self, rmacd_level: str) -> str:
        """Infer HITL requirement based on RMACD level."""
        hitl_map = {
            "R": "logged",
            "M": "notification",
            "A": "approval",
            "C": "approval",
            "D": "elevated_approval",
        }
        return hitl_map.get(rmacd_level, "approval")


class MCPRegistryBridge:
    """
    Bridge between MCP tools and the RMACD registry.

    Automatically classifies MCP tools and registers them with governance
    controls. Pass an existing ``registry=`` (e.g. the one a ``PolicyEnforcer``
    enforces against) so MCP tools land in the same policy surface as your
    hand-registered tools; otherwise the bridge creates its own.

    ``llm_classifier`` (an ``rmacd.registry.llm.LLMToolClassifier``) upgrades
    classification quality:

    - ``llm_mode="fallback"`` (default when a classifier is given): the LLM is
      consulted only for tools the keyword heuristic could not classify with
      confidence — the cheap deterministic path handles the obvious cases.
    - ``llm_mode="always"``: every tool is classified by the LLM.

    LLM failures (missing API key, network, refusal) fall back to the keyword
    result and are recorded in the tool's classification provenance — the
    bridge never refuses to register a tool because the LLM was unavailable.
    """

    def __init__(
        self,
        registry_id: str = "mcp-registry",
        *,
        registry: ToolsRegistry | None = None,
        llm_classifier: LLMToolClassifier | None = None,
        llm_mode: Literal["fallback", "always"] = "fallback",
    ) -> None:
        """Initialize MCP bridge with (or around) an RMACD registry."""
        self.registry = registry if registry is not None else create_registry(registry_id)
        self.mcp_tools: dict[str, MCPTool] = {}
        self.llm_classifier = llm_classifier
        self.llm_mode = llm_mode
        logger.info("MCP Registry Bridge initialized: %s", self.registry.registry_id)

    def register_mcp_tool(self, mcp_tool: MCPTool | dict[str, Any]) -> ToolDefinition:
        """
        Register an MCP tool with automatic RMACD classification.

        Accepts an ``MCPTool`` or a raw MCP ``tools/list`` entry dict.
        Returns the registered ``ToolDefinition``.
        """
        if isinstance(mcp_tool, dict):
            mcp_tool = MCPTool.from_mcp(mcp_tool)

        rmacd_tool = mcp_tool.to_rmacd_tool()

        keyword_confidence = rmacd_tool["metadata"]["classification"]["confidence"]
        use_llm = self.llm_classifier is not None and (
            self.llm_mode == "always" or keyword_confidence == "low"
        )
        if use_llm:
            rmacd_tool = self._apply_llm_classification(mcp_tool, rmacd_tool)

        registered = self.registry.register_tool(rmacd_tool)

        self.mcp_tools[mcp_tool.name] = mcp_tool
        logger.info(
            "Registered MCP tool: %s (RMACD: %s, engine: %s)",
            mcp_tool.name,
            registered.rmacd_level.value,
            registered.metadata["classification"]["engine"],
        )
        return registered

    def register_mcp_tools(
        self, mcp_tools: list[MCPTool | dict[str, Any]]
    ) -> list[ToolDefinition]:
        """Register a batch of MCP tools (e.g. a whole ``tools/list`` response)."""
        return [self.register_mcp_tool(t) for t in mcp_tools]

    def _apply_llm_classification(
        self, mcp_tool: MCPTool, rmacd_tool: dict[str, Any]
    ) -> dict[str, Any]:
        """Overlay an LLM classification onto the keyword baseline (fail-soft)."""
        assert self.llm_classifier is not None
        try:
            result = self.llm_classifier.classify(
                name=mcp_tool.name,
                description=mcp_tool.description,
                input_schema=mcp_tool.inputSchema,
                operations=mcp_tool.operations,
            )
        except Exception as exc:  # noqa: BLE001 — any LLM failure degrades to keyword
            logger.warning(
                "LLM classification failed for '%s' (%s); keeping keyword result",
                mcp_tool.name, exc,
            )
            rmacd_tool["metadata"]["classification"]["llm_error"] = str(exc)
            return rmacd_tool

        op = parse_operation(result.rmacd_level)
        ceiling = {o.value for o, rank in _OP_ORDER.items() if rank <= _OP_ORDER[op]}
        rmacd_tool.update(
            rmacd_level=result.rmacd_level,
            data_access=result.data_access,
            required_hitl=result.required_hitl,
            capability={"operations": sorted(ceiling)},
        )
        rmacd_tool["metadata"]["classification"] = {
            "engine": "llm",
            "model": self.llm_classifier.model,
            "rationale": result.rationale,
            "confidence": "high" if result.confidence >= 0.7 else "low",
            "llm_confidence": result.confidence,
        }
        return rmacd_tool

    def low_confidence_tools(self) -> list[ToolDefinition]:
        """Auto-classified tools whose classification needs human review."""
        return [
            t
            for t in self.registry.get_tools_by_tag("auto-classified")
            if t.metadata.get("classification", {}).get("confidence") == "low"
        ]

    def can_agent_use_tool(
        self,
        tool_name: str,
        agent_permissions: list[str],
        agent_data_tier: str | None = None,
    ) -> tuple[bool, str]:
        """
        Check if an agent can use a specific MCP tool.

        Args:
            tool_name: Name of MCP tool
            agent_permissions: Agent's allowed RMACD levels
            agent_data_tier: Agent's allowed data classification

        Returns:
            Tuple of (is_allowed, reason)
        """
        tool_id = tool_name.lower().replace(" ", "_").replace("-", "_")
        return self.registry.validate_tool_access(
            tool_id,
            agent_permissions,
            agent_data_tier,
        )

    def get_allowed_tools_for_agent(
        self,
        agent_permissions: list[str],
        agent_data_tier: str | None = None,
    ) -> list[str]:
        """
        Get all MCP tools an agent is allowed to use.

        Args:
            agent_permissions: Agent's allowed RMACD levels
            agent_data_tier: Agent's allowed data classification

        Returns:
            List of allowed tool names
        """
        allowed_tools = []

        for tool_name in self.mcp_tools:
            is_allowed, _ = self.can_agent_use_tool(
                tool_name,
                agent_permissions,
                agent_data_tier,
            )
            if is_allowed:
                allowed_tools.append(tool_name)

        return allowed_tools

    def export_catalog(self, filepath: str) -> bool:
        """Export MCP tools catalog with RMACD classifications."""
        return self.registry.export_to_json(filepath)
