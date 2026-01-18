"""
RMACD Tools Registry - Core Implementation
==========================================

Tool registration, validation, and risk assessment for AI agent governance.

Author: Kash Kashyap
License: Apache-2.0
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
import json
import logging

from rmacd.models import Operation, DataClassification, AutonomyLevel

logger = logging.getLogger(__name__)


# Risk metadata for operations
OPERATION_RISK = {
    Operation.READ: {"level": 0.0, "name": "Near-Zero", "desc": "Observe, query, analyze"},
    Operation.MOVE: {"level": 0.25, "name": "Low-Medium", "desc": "Relocate, transfer"},
    Operation.ADD: {"level": 0.50, "name": "Medium", "desc": "Create, provision"},
    Operation.CHANGE: {"level": 0.75, "name": "High", "desc": "Modify, update"},
    Operation.DELETE: {"level": 1.0, "name": "Critical", "desc": "Remove, destroy"},
}

DATA_RISK = {
    DataClassification.PUBLIC: 0.0,
    DataClassification.INTERNAL: 0.33,
    DataClassification.CONFIDENTIAL: 0.67,
    DataClassification.RESTRICTED: 1.0,
}

HITL_MODIFIER = {
    AutonomyLevel.PROHIBITED: 0.0,
    AutonomyLevel.ELEVATED_APPROVAL: 0.2,
    AutonomyLevel.APPROVAL: 0.4,
    AutonomyLevel.NOTIFICATION: 0.6,
    AutonomyLevel.LOGGED: 0.8,
    AutonomyLevel.AUTONOMOUS: 1.0,
}


def parse_operation(value: str | Operation) -> Operation:
    """Parse operation from string or enum."""
    if isinstance(value, Operation):
        return value
    return Operation(value.upper().strip())


def parse_data_classification(value: str | DataClassification | None) -> DataClassification | None:
    """Parse data classification from string or enum."""
    if value is None:
        return None
    if isinstance(value, DataClassification):
        return value
    return DataClassification(value.lower().strip())


def parse_autonomy_level(value: str | AutonomyLevel | None) -> AutonomyLevel | None:
    """Parse autonomy level from string or enum."""
    if value is None:
        return None
    if isinstance(value, AutonomyLevel):
        return value
    return AutonomyLevel(value.lower().strip())


@dataclass
class ToolDefinition:
    """Tool definition with RMACD classification."""

    tool_id: str
    tool_name: str
    rmacd_level: Operation
    description: str = ""
    operations: list[str] = field(default_factory=list)
    data_access: DataClassification | None = None
    required_hitl: AutonomyLevel | None = None
    risk_score: float = 0.0
    tags: set[str] = field(default_factory=set)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        """Validate and normalize tool definition."""
        if not self.tool_id or not isinstance(self.tool_id, str):
            raise ValueError("tool_id must be a non-empty string")

        self.tool_id = self.tool_id.strip().lower().replace(" ", "_")

        if not self.tool_name or not isinstance(self.tool_name, str):
            raise ValueError("tool_name must be a non-empty string")

        # Parse enums from strings
        self.rmacd_level = parse_operation(self.rmacd_level)

        if self.data_access is not None:
            self.data_access = parse_data_classification(self.data_access)

        if self.required_hitl is not None:
            self.required_hitl = parse_autonomy_level(self.required_hitl)

        # Ensure tags is a set
        if not isinstance(self.tags, set):
            self.tags = set(self.tags) if self.tags else set()

        # Calculate risk score if not provided
        if self.risk_score == 0.0:
            self.risk_score = self._calculate_risk_score()

    def _calculate_risk_score(self) -> float:
        """
        Calculate risk score based on RMACD level, data classification, and HITL.

        Formula: (rmacd_risk * 0.6 + data_risk * 0.4) * hitl_modifier * 10
        """
        rmacd_risk = OPERATION_RISK.get(self.rmacd_level, {}).get("level", 0.5)

        data_risk = 0.0
        if self.data_access:
            data_risk = DATA_RISK.get(self.data_access, 0.5)

        hitl_modifier = 1.0
        if self.required_hitl:
            hitl_modifier = HITL_MODIFIER.get(self.required_hitl, 0.5)

        base_risk = (rmacd_risk * 0.6 + data_risk * 0.4) * hitl_modifier
        return round(base_risk * 10, 2)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "tool_id": self.tool_id,
            "tool_name": self.tool_name,
            "rmacd_level": self.rmacd_level.value,
            "description": self.description,
            "operations": self.operations,
            "data_access": self.data_access.value if self.data_access else None,
            "required_hitl": self.required_hitl.value if self.required_hitl else None,
            "risk_score": self.risk_score,
            "tags": list(self.tags),
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolDefinition":
        """Create tool from dictionary."""
        required_fields = ["tool_id", "tool_name", "rmacd_level"]
        missing = [f for f in required_fields if f not in data]
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")

        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now()

        return cls(
            tool_id=data["tool_id"],
            tool_name=data["tool_name"],
            rmacd_level=data["rmacd_level"],
            description=data.get("description", ""),
            operations=data.get("operations", []),
            data_access=data.get("data_access"),
            required_hitl=data.get("required_hitl"),
            risk_score=data.get("risk_score", 0.0),
            tags=set(data.get("tags", [])),
            metadata=data.get("metadata", {}),
            created_at=created_at,
        )


class ToolsRegistry:
    """
    Central registry for managing tools and their RMACD classifications.

    Provides:
    - Tool registration and lookup
    - Permission validation
    - Risk assessment
    - Audit logging
    - JSON import/export
    """

    def __init__(self, registry_id: str = "default") -> None:
        """Initialize the tools registry."""
        self.registry_id = registry_id
        self._tools: dict[str, ToolDefinition] = {}
        self._index_by_level: dict[Operation, set[str]] = {
            level: set() for level in Operation
        }
        self._audit_log: list[dict[str, Any]] = []
        self._version = "1.0.0"
        logger.info(f"Tools registry '{registry_id}' initialized")

    def register_tool(self, tool: ToolDefinition | dict[str, Any]) -> bool:
        """
        Register a new tool in the registry.

        Args:
            tool: ToolDefinition object or dictionary

        Returns:
            True if successful
        """
        if isinstance(tool, dict):
            tool = ToolDefinition.from_dict(tool)
        elif not isinstance(tool, ToolDefinition):
            raise TypeError(f"Tool must be ToolDefinition or dict, got {type(tool)}")

        if tool.tool_id in self._tools:
            logger.warning(f"Tool '{tool.tool_id}' already registered, updating...")

        self._tools[tool.tool_id] = tool
        self._index_by_level[tool.rmacd_level].add(tool.tool_id)

        self._log_audit("register", tool.tool_id, {
            "rmacd_level": tool.rmacd_level.value,
            "risk_score": tool.risk_score,
        })

        logger.info(f"Tool '{tool.tool_id}' registered with RMACD level {tool.rmacd_level.value}")
        return True

    def get_tool(self, tool_id: str) -> ToolDefinition | None:
        """Retrieve a tool by ID."""
        normalized_id = tool_id.strip().lower().replace(" ", "_")
        return self._tools.get(normalized_id)

    def get_tools_by_level(self, rmacd_level: Operation | str) -> list[ToolDefinition]:
        """Get all tools at a specific RMACD level."""
        if isinstance(rmacd_level, str):
            rmacd_level = parse_operation(rmacd_level)

        tool_ids = self._index_by_level.get(rmacd_level, set())
        return [self._tools[tid] for tid in tool_ids if tid in self._tools]

    def validate_tool_access(
        self,
        tool_id: str,
        allowed_levels: list[Operation | str],
        data_tier: DataClassification | str | None = None,
    ) -> tuple[bool, str]:
        """
        Validate if a tool can be accessed based on permission profile.

        Args:
            tool_id: Tool to validate
            allowed_levels: List of allowed RMACD levels
            data_tier: Optional data classification for 3D model

        Returns:
            Tuple of (is_allowed, reason)
        """
        tool = self.get_tool(tool_id)
        if tool is None:
            return False, f"Tool '{tool_id}' not found in registry"

        # Parse allowed levels
        allowed_ops = [parse_operation(lvl) for lvl in allowed_levels]

        # Check RMACD level permission
        if tool.rmacd_level not in allowed_ops:
            return False, (
                f"Tool requires {tool.rmacd_level.value} permission, "
                f"but only {[o.value for o in allowed_ops]} allowed"
            )

        # Check data classification if 3D model
        if data_tier is not None:
            data_tier = parse_data_classification(data_tier)
            if tool.data_access is not None:
                tier_order = list(DataClassification)
                if tier_order.index(tool.data_access) > tier_order.index(data_tier):
                    return False, (
                        f"Tool requires {tool.data_access.value} data access, "
                        f"but only {data_tier.value} allowed"
                    )

        # Check HITL requirements
        if tool.required_hitl == AutonomyLevel.PROHIBITED:
            return False, "Tool is explicitly prohibited"

        self._log_audit("validate_access", tool_id, {
            "allowed": True,
            "allowed_levels": [o.value for o in allowed_ops],
        })

        return True, f"Access granted for {tool.rmacd_level.value} operation"

    def calculate_workflow_risk(self, tool_ids: list[str]) -> dict[str, Any]:
        """Calculate aggregate risk for a workflow using multiple tools."""
        tools = []
        missing = []

        for tid in tool_ids:
            tool = self.get_tool(tid)
            if tool:
                tools.append(tool)
            else:
                missing.append(tid)

        if not tools:
            return {
                "total_risk": 0.0,
                "max_risk": 0.0,
                "avg_risk": 0.0,
                "tool_count": 0,
                "highest_rmacd": None,
                "missing_tools": missing,
                "error": "No valid tools found",
            }

        risk_scores = [t.risk_score for t in tools]
        rmacd_levels = [t.rmacd_level for t in tools]

        # Order for comparison
        level_order = list(Operation)
        highest_rmacd = max(rmacd_levels, key=lambda x: level_order.index(x))
        highest_risk_tool = max(tools, key=lambda t: t.risk_score)

        return {
            "total_risk": round(sum(risk_scores), 2),
            "max_risk": round(max(risk_scores), 2),
            "avg_risk": round(sum(risk_scores) / len(tools), 2),
            "tool_count": len(tools),
            "highest_rmacd": highest_rmacd.value,
            "highest_risk_tool": highest_risk_tool.tool_id,
            "missing_tools": missing,
            "risk_distribution": {
                level.value: len([t for t in tools if t.rmacd_level == level])
                for level in Operation
            },
        }

    def export_to_json(self, filepath: str | Path) -> bool:
        """Export registry to JSON file."""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        export_data = {
            "registry_id": self.registry_id,
            "version": self._version,
            "exported_at": datetime.now().isoformat(),
            "tool_count": len(self._tools),
            "tools": [tool.to_dict() for tool in self._tools.values()],
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Registry exported to {filepath}")
        return True

    def import_from_json(self, filepath: str | Path) -> bool:
        """Import tools from JSON file."""
        filepath = Path(filepath)

        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        if "tools" not in data:
            raise ValueError("Invalid registry file: missing 'tools' key")

        success_count = 0
        for tool_data in data["tools"]:
            try:
                self.register_tool(tool_data)
                success_count += 1
            except Exception as e:
                logger.error(f"Error importing tool {tool_data.get('tool_id', 'unknown')}: {e}")

        logger.info(f"Imported {success_count} tools from {filepath}")
        return True

    def _log_audit(self, action: str, tool_id: str, details: dict[str, Any]) -> None:
        """Log an audit event."""
        self._audit_log.append({
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "tool_id": tool_id,
            "details": details,
        })

    def get_audit_log(self, last_n: int | None = None) -> list[dict[str, Any]]:
        """Retrieve audit log entries."""
        if last_n is not None:
            return self._audit_log[-last_n:]
        return self._audit_log.copy()

    def get_stats(self) -> dict[str, Any]:
        """Get registry statistics."""
        total_risk = sum(t.risk_score for t in self._tools.values())
        return {
            "registry_id": self.registry_id,
            "total_tools": len(self._tools),
            "by_level": {
                level.value: len(tools)
                for level, tools in self._index_by_level.items()
            },
            "avg_risk_score": round(total_risk / max(len(self._tools), 1), 2),
            "audit_entries": len(self._audit_log),
        }

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, tool_id: str) -> bool:
        normalized_id = tool_id.strip().lower().replace(" ", "_")
        return normalized_id in self._tools

    def __repr__(self) -> str:
        return f"ToolsRegistry(id='{self.registry_id}', tools={len(self._tools)})"


def create_registry(registry_id: str = "default") -> ToolsRegistry:
    """Create a new tools registry."""
    return ToolsRegistry(registry_id)


def quick_register(
    registry: ToolsRegistry,
    tool_id: str,
    tool_name: str,
    rmacd_level: str,
    **kwargs: Any,
) -> bool:
    """Quick tool registration helper."""
    tool = ToolDefinition(
        tool_id=tool_id,
        tool_name=tool_name,
        rmacd_level=rmacd_level,
        **kwargs,
    )
    return registry.register_tool(tool)
