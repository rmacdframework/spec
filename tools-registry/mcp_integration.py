"""
RMACD Tools Registry - MCP Integration Example
===============================================

Demonstrates integration with Model Context Protocol (MCP) for AI agent governance.

This shows how the RMACD registry can automatically classify and govern MCP tools
based on their operations and risk levels.

Author: Kash Kashyap
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
import json
from rmacd_tools_registry import (
    ToolsRegistry,
    ToolDefinition,
    RMACDLevel,
    HITLLevel,
    DataClassification,
    create_registry
)


@dataclass
class MCPTool:
    """Represents an MCP tool definition."""
    name: str
    description: str
    inputSchema: Dict
    operations: List[str] = None
    
    def to_rmacd_tool(self) -> Dict:
        """
        Convert MCP tool to RMACD tool definition.
        
        Automatically infers RMACD level based on operations.
        """
        try:
            # Infer RMACD level from operations
            rmacd_level = self._infer_rmacd_level()
            
            # Infer data classification from schema
            data_access = self._infer_data_classification()
            
            # Infer HITL requirement from risk
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
                    "input_schema": self.inputSchema
                }
            }
        except Exception as e:
            print(f"Error converting MCP tool {self.name}: {e}")
            raise
    
    def _infer_rmacd_level(self) -> str:
        """
        Infer RMACD level from tool operations.
        
        Uses keyword matching to determine risk level:
        - READ: query, search, get, list, view, read, fetch, retrieve
        - MOVE: move, transfer, copy, relocate, migrate
        - ADD: create, add, post, upload, insert, provision
        - CHANGE: update, modify, edit, patch, configure, set
        - DELETE: delete, remove, destroy, purge, drop
        """
        if not self.operations:
            # Analyze tool name and description
            text = f"{self.name} {self.description}".lower()
        else:
            text = " ".join(self.operations).lower()
        
        # Check in order of decreasing risk
        delete_keywords = ["delete", "remove", "destroy", "purge", "drop", "erase"]
        if any(keyword in text for keyword in delete_keywords):
            return "D"
        
        change_keywords = ["update", "modify", "edit", "patch", "configure", "set", "change", "alter", "commit", "push"]
        if any(keyword in text for keyword in change_keywords):
            return "C"
        
        add_keywords = ["create", "add", "post", "upload", "insert", "provision", "deploy", "new"]
        if any(keyword in text for keyword in add_keywords):
            return "A"
        
        move_keywords = ["move", "transfer", "copy", "relocate", "migrate", "forward", "rename"]
        if any(keyword in text for keyword in move_keywords):
            return "M"
        
        # Default to READ if no destructive operations detected
        return "R"
    
    def _infer_data_classification(self) -> Optional[str]:
        """Infer data classification from input schema."""
        schema_str = json.dumps(self.inputSchema).lower()
        
        # Check for sensitive data indicators
        if any(term in schema_str for term in ["password", "secret", "credential", "ssn", "credit_card"]):
            return "restricted"
        
        if any(term in schema_str for term in ["confidential", "private", "sensitive"]):
            return "confidential"
        
        if any(term in schema_str for term in ["internal", "company"]):
            return "internal"
        
        # Default to internal for safety
        return "internal"
    
    def _infer_hitl_requirement(self, rmacd_level: str) -> str:
        """Infer HITL requirement based on RMACD level."""
        hitl_map = {
            "R": "logged",      # Read operations: log for audit
            "M": "notify",      # Move operations: notify user
            "A": "approve",     # Add operations: require approval
            "C": "approve",     # Change operations: require approval
            "D": "elevated"     # Delete operations: elevated approval
        }
        return hitl_map.get(rmacd_level, "approve")


class MCPRegistryBridge:
    """
    Bridge between MCP tools and RMACD registry.
    
    Automatically classifies MCP tools and registers them with governance controls.
    """
    
    def __init__(self, registry_id: str = "mcp-registry"):
        """Initialize MCP bridge with RMACD registry."""
        try:
            self.registry = create_registry(registry_id)
            self.mcp_tools: Dict[str, MCPTool] = {}
            print(f"[OK] MCP Registry Bridge initialized: {registry_id}")
        except Exception as e:
            print(f"[ERROR] Error initializing MCP bridge: {e}")
            raise
    
    def register_mcp_tool(self, mcp_tool: MCPTool) -> bool:
        """
        Register an MCP tool with automatic RMACD classification.
        
        Args:
            mcp_tool: MCP tool to register
            
        Returns:
            bool: True if successful
        """
        try:
            # Convert to RMACD tool
            rmacd_tool = mcp_tool.to_rmacd_tool()
            
            # Register with registry
            success = self.registry.register_tool(rmacd_tool)
            
            if success:
                # Store MCP tool for reference
                self.mcp_tools[mcp_tool.name] = mcp_tool
                print(f"[OK] Registered MCP tool: {mcp_tool.name} (RMACD: {rmacd_tool['rmacd_level']})")
            
            return success
            
        except Exception as e:
            print(f"[ERROR] Error registering MCP tool {mcp_tool.name}: {e}")
            return False
    
    def can_agent_use_tool(
        self,
        tool_name: str,
        agent_permissions: List[str],
        agent_data_tier: Optional[str] = None
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
        try:
            tool_id = tool_name.lower().replace(" ", "_").replace("-", "_")
            return self.registry.validate_tool_access(
                tool_id,
                agent_permissions,
                agent_data_tier
            )
        except Exception as e:
            return False, f"Error validating access: {e}"
    
    def get_allowed_tools_for_agent(
        self,
        agent_permissions: List[str],
        agent_data_tier: Optional[str] = None
    ) -> List[str]:
        """
        Get list of MCP tools an agent is allowed to use.
        
        Args:
            agent_permissions: Agent's allowed RMACD levels
            agent_data_tier: Agent's allowed data classification
            
        Returns:
            List of allowed tool names
        """
        try:
            allowed_tools = []
            
            for tool_name in self.mcp_tools.keys():
                is_allowed, _ = self.can_agent_use_tool(
                    tool_name,
                    agent_permissions,
                    agent_data_tier
                )
                if is_allowed:
                    allowed_tools.append(tool_name)
            
            return allowed_tools
            
        except Exception as e:
            print(f"[ERROR] Error getting allowed tools: {e}")
            return []
    
    def export_mcp_catalog(self, filepath: str) -> bool:
        """Export MCP tools catalog with RMACD classifications."""
        try:
            return self.registry.export_to_json(filepath)
        except Exception as e:
            print(f"[ERROR] Error exporting MCP catalog: {e}")
            return False


def create_example_mcp_tools() -> List[MCPTool]:
    """Create example MCP tools for demonstration."""
    
    return [
        # Read-level tools
        MCPTool(
            name="filesystem-read",
            description="Read file contents from the filesystem",
            inputSchema={"type": "object", "properties": {"path": {"type": "string"}}},
            operations=["read", "get"]
        ),
        MCPTool(
            name="database-query",
            description="Execute SELECT queries on database",
            inputSchema={"type": "object", "properties": {"query": {"type": "string"}}},
            operations=["query", "select"]
        ),
        
        # Move-level tools
        MCPTool(
            name="filesystem-move",
            description="Move or rename files",
            inputSchema={"type": "object", "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"}
            }},
            operations=["move", "rename"]
        ),
        
        # Add-level tools
        MCPTool(
            name="filesystem-create",
            description="Create new files",
            inputSchema={"type": "object", "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"}
            }},
            operations=["create", "write"]
        ),
        MCPTool(
            name="slack-post-message",
            description="Post messages to Slack channels",
            inputSchema={"type": "object", "properties": {
                "channel": {"type": "string"},
                "message": {"type": "string"}
            }},
            operations=["post", "send"]
        ),
        
        # Change-level tools
        MCPTool(
            name="filesystem-edit",
            description="Modify existing file contents",
            inputSchema={"type": "object", "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"}
            }},
            operations=["edit", "modify", "update"]
        ),
        MCPTool(
            name="github-commit",
            description="Commit changes to GitHub repository",
            inputSchema={"type": "object", "properties": {
                "repo": {"type": "string"},
                "message": {"type": "string"}
            }},
            operations=["commit", "push"]
        ),
        
        # Delete-level tools
        MCPTool(
            name="filesystem-delete",
            description="Delete files from filesystem",
            inputSchema={"type": "object", "properties": {"path": {"type": "string"}}},
            operations=["delete", "remove"]
        ),
        MCPTool(
            name="database-drop-table",
            description="Drop database tables",
            inputSchema={"type": "object", "properties": {
                "table": {"type": "string"},
                "password": {"type": "string"}  # Triggers restricted classification
            }},
            operations=["drop", "delete"]
        ),
    ]


def demonstrate_mcp_integration():
    """Demonstrate MCP integration with RMACD governance."""
    
    print("\n" + "="*70)
    print("RMACD + MCP INTEGRATION DEMONSTRATION")
    print("="*70)
    print("\nAutomatic MCP Tool Classification and Governance\n")
    
    try:
        # Create MCP bridge
        bridge = MCPRegistryBridge("mcp-demo")
        
        # Register example MCP tools
        print("[LOG] Registering MCP tools with auto-classification...")
        print("-" * 70)
        
        mcp_tools = create_example_mcp_tools()
        for tool in mcp_tools:
            bridge.register_mcp_tool(tool)
        
        # Define agent profiles
        print("\n" + "="*70)
        print("AGENT PERMISSION PROFILES")
        print("="*70)
        
        agent_profiles = {
            "observer": {
                "permissions": ["R"],
                "data_tier": "internal",
                "description": "Read-only observer agent"
            },
            "contributor": {
                "permissions": ["R", "M", "A"],
                "data_tier": "internal",
                "description": "Can read, move, and add"
            },
            "developer": {
                "permissions": ["R", "M", "A", "C"],
                "data_tier": "confidential",
                "description": "Full development access (no delete)"
            },
            "admin": {
                "permissions": ["R", "M", "A", "C", "D"],
                "data_tier": "restricted",
                "description": "Full administrative access"
            }
        }
        
        # Show allowed tools for each agent
        print("\n[INFO] Agent Tool Access Matrix")
        print("-" * 70)
        
        for agent_name, profile in agent_profiles.items():
            print(f"\n{agent_name.upper()} ({profile['description']})")
            print(f"  Permissions: {', '.join(profile['permissions'])}")
            print(f"  Data Tier: {profile['data_tier']}")
            
            allowed_tools = bridge.get_allowed_tools_for_agent(
                profile['permissions'],
                profile['data_tier']
            )
            
            print(f"  Allowed Tools ({len(allowed_tools)}):")
            for tool in allowed_tools:
                print(f"    + {tool}")
        
        # Demonstrate permission checks
        print("\n" + "="*70)
        print("PERMISSION VALIDATION EXAMPLES")
        print("="*70)
        
        test_cases = [
            ("observer", "filesystem-read", "Should be allowed"),
            ("observer", "filesystem-create", "Should be denied - requires ADD"),
            ("contributor", "slack-post-message", "Should be allowed"),
            ("contributor", "github-commit", "Should be denied - requires CHANGE"),
            ("developer", "filesystem-edit", "Should be allowed"),
            ("developer", "filesystem-delete", "Should be denied - requires DELETE"),
            ("admin", "database-drop-table", "Should be allowed"),
        ]
        
        for agent, tool, expected in test_cases:
            profile = agent_profiles[agent]
            is_allowed, reason = bridge.can_agent_use_tool(
                tool,
                profile['permissions'],
                profile['data_tier']
            )
            
            status = "[OK]" if is_allowed else "[ERROR]"
            print(f"\n{status} {agent.upper()} using '{tool}'")
            print(f"   Expected: {expected}")
            print(f"   Result: {reason}")
        
        # Export catalog
        print("\n" + "="*70)
        print("EXPORTING MCP CATALOG")
        print("="*70)
        
        catalog_path = "mcp_tools_catalog.json"
        success = bridge.export_mcp_catalog(catalog_path)
        
        if success:
            print(f"[OK] MCP catalog exported to: {catalog_path}")
            
            # Show stats
            stats = bridge.registry.get_stats()
            print(f"\nCatalog Statistics:")
            print(f"  Total MCP Tools: {stats['total_tools']}")
            print(f"  Distribution by RMACD Level:")
            for level, count in stats['by_level'].items():
                if count > 0:
                    print(f"    {level}: {count} tools")
        
        print("\n" + "="*70)
        print("[OK] MCP INTEGRATION DEMONSTRATION COMPLETE")
        print("="*70)
        
        print("\nKey Takeaways:")
        print("  1. MCP tools are automatically classified into RMACD levels")
        print("  2. Governance controls are applied based on risk")
        print("  3. Agent access is validated against permission profiles")
        print("  4. All operations are logged for audit")
        print("  5. Catalog can be exported for review and compliance")
        
    except Exception as e:
        print(f"\n[ERROR] Error in MCP demonstration: {e}")
        raise


if __name__ == "__main__":
    demonstrate_mcp_integration()
