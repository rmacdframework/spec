"""
RMACD Tools Registry - MCP Integration
=======================================

Integration with Model Context Protocol (MCP) for AI agent governance.

Author: Kash Kashyap
License: Apache-2.0
"""

from dataclasses import dataclass, field
from typing import Any
import json
import logging

from rmacd.registry.tools import ToolsRegistry, create_registry

logger = logging.getLogger(__name__)


@dataclass
class MCPTool:
    """Represents an MCP tool definition."""

    name: str
    description: str
    inputSchema: dict[str, Any]
    operations: list[str] = field(default_factory=list)

    def to_rmacd_tool(self) -> dict[str, Any]:
        """
        Convert MCP tool to RMACD tool definition.

        Automatically infers RMACD level based on operations.
        """
        rmacd_level = self._infer_rmacd_level()
        data_access = self._infer_data_classification()
        hitl_level = self._infer_hitl_requirement(rmacd_level)

        return {
            "tool_id": self.name.lower().replace(" ", "_").replace("-", "_"),
            "tool_name": self.name,
            "rmacd_level": rmacd_level,
            "description": self.description,
            "operations": self.operations or [],
            "data_access": data_access,
            "required_hitl": hitl_level,
            "tags": {"mcp", "auto-classified"},
            "metadata": {
                "source": "mcp",
                "input_schema": self.inputSchema,
            },
        }

    def _infer_rmacd_level(self) -> str:
        """
        Infer RMACD level from tool operations.

        Uses keyword matching to determine risk level:
        - READ: query, search, get, list, view, read, fetch, retrieve
        - MOVE: move, transfer, copy, relocate, migrate
        - ADD: create, add, post, upload, insert, provision
        - CHANGE: update, modify, edit, patch, configure, set, commit, push
        - DELETE: delete, remove, destroy, purge, drop
        """
        if not self.operations:
            text = f"{self.name} {self.description}".lower()
        else:
            text = " ".join(self.operations).lower()

        # Check in order of decreasing risk
        delete_keywords = ["delete", "remove", "destroy", "purge", "drop", "erase"]
        if any(keyword in text for keyword in delete_keywords):
            return "D"

        change_keywords = [
            "update", "modify", "edit", "patch", "configure",
            "set", "change", "alter", "commit", "push",
        ]
        if any(keyword in text for keyword in change_keywords):
            return "C"

        add_keywords = ["create", "add", "post", "upload", "insert", "provision", "deploy", "new"]
        if any(keyword in text for keyword in add_keywords):
            return "A"

        move_keywords = ["move", "transfer", "copy", "relocate", "migrate", "forward", "rename"]
        if any(keyword in text for keyword in move_keywords):
            return "M"

        return "R"

    def _infer_data_classification(self) -> str:
        """Infer data classification from input schema."""
        schema_str = json.dumps(self.inputSchema).lower()

        if any(term in schema_str for term in ["password", "secret", "credential", "ssn", "credit_card"]):
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
    Bridge between MCP tools and RMACD registry.

    Automatically classifies MCP tools and registers them with governance controls.
    """

    def __init__(self, registry_id: str = "mcp-registry") -> None:
        """Initialize MCP bridge with RMACD registry."""
        self.registry = create_registry(registry_id)
        self.mcp_tools: dict[str, MCPTool] = {}
        logger.info(f"MCP Registry Bridge initialized: {registry_id}")

    def register_mcp_tool(self, mcp_tool: MCPTool) -> bool:
        """
        Register an MCP tool with automatic RMACD classification.

        Args:
            mcp_tool: MCP tool to register

        Returns:
            True if successful
        """
        rmacd_tool = mcp_tool.to_rmacd_tool()
        success = self.registry.register_tool(rmacd_tool)

        if success:
            self.mcp_tools[mcp_tool.name] = mcp_tool
            logger.info(f"Registered MCP tool: {mcp_tool.name} (RMACD: {rmacd_tool['rmacd_level']})")

        return success

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
