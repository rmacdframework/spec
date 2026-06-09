"""
RMACD Tools Registry
====================

Tool governance system for managing and validating AI agent tool access.

Usage:
    from rmacd.registry import ToolsRegistry, ToolDefinition, quick_register

    # Create registry
    registry = ToolsRegistry("my-registry")

    # Register a tool
    quick_register(
        registry,
        tool_id="file_reader",
        tool_name="File Reader",
        rmacd_level="R",
        data_access="internal"
    )

    # Validate access
    allowed, reason = registry.validate_tool_access(
        "file_reader",
        allowed_levels=["R", "M"],
        data_tier="internal"
    )
"""

from rmacd.registry.tools import (
    ResolvedCall,
    ToolCapability,
    ToolClassifier,
    ToolDefinition,
    ToolsRegistry,
    create_registry,
    quick_register,
)
from rmacd.registry.mcp import MCPTool, MCPRegistryBridge
from rmacd.registry.bash import (
    BashClassification,
    classify_bash_command,
    make_bash_classifier,
)

__all__ = [
    "ToolCapability",
    "ToolClassifier",
    "ToolDefinition",
    "ToolsRegistry",
    "ResolvedCall",
    "create_registry",
    "quick_register",
    "MCPTool",
    "MCPRegistryBridge",
    "BashClassification",
    "classify_bash_command",
    "make_bash_classifier",
]
