"""
RMACD Tools Registry - Core Implementation
==========================================

The registry is the first-class RMACD *classification + capability* layer for
tools. For each registered tool it answers two questions the enforcer needs at
the tool-call boundary:

1. **Classification** — what does calling this tool *mean* in RMACD terms? A
   call ``(tool_name, args)`` resolves to ``(operation, data tier, target)``.
   The operation is a property of the tool; the tier/target may be static or
   derived dynamically from the arguments (e.g. ``kubectl delete`` on a prod
   namespace is Delete on Confidential, on a staging namespace Internal).
2. **Capability ceiling** — what is this tool *ever* allowed to do, regardless
   of which agent invokes it? An optional second gate (defence in depth): a
   read-only search tool should never represent a Delete even if an
   over-broad profile would permit it.

``PolicyEnforcer.enforce_tool_call`` consults the registry to classify a call,
checks the capability ceiling, then evaluates the resolved ``(operation, tier)``
against the agent's profile. Permission is the *intersection*: the agent
profile must allow it AND the tool's capability must allow it, with the §12.5
safety floor always enforced by the evaluator.

Author: Kash Kashyap
License: CC BY 4.0
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rmacd.models import AutonomyLevel, DataClassification, Operation

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    """Timezone-aware UTC now (naive ``datetime.now()`` is ambiguous in logs)."""
    return datetime.now(timezone.utc)


# Explicit orderings so comparisons don't depend on enum declaration order.
# Sensitivity: public < internal < confidential < restricted.
_TIER_ORDER: dict[DataClassification, int] = {
    DataClassification.PUBLIC: 0,
    DataClassification.INTERNAL: 1,
    DataClassification.CONFIDENTIAL: 2,
    DataClassification.RESTRICTED: 3,
}
# Operation risk ordering: R < M < A < C < D. Permissions are cumulative
# (D ⊃ C ⊃ A ⊃ M ⊃ R) — granting a higher operation implies all lower ones.
_OP_ORDER: dict[Operation, int] = {
    Operation.READ: 0,
    Operation.MOVE: 1,
    Operation.ADD: 2,
    Operation.CHANGE: 3,
    Operation.DELETE: 4,
}


# Risk metadata for operations
OPERATION_RISK: dict[Operation, dict[str, Any]] = {
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


# A dynamic classifier maps a tool call's arguments to a partial RMACD
# classification: (operation, data tier, target). Any field returned as None
# falls back to the tool's static ``rmacd_level`` / ``data_access`` / target
# template. This is how a single tool handles calls whose tier/target depend on
# which resource the agent picked, replacing hand-written per-integration lambdas.
ToolClassifier = Callable[
    [dict[str, Any]],
    "tuple[Operation | str | None, DataClassification | str | None, str | None]",
]


@dataclass
class ToolCapability:
    """The set of RMACD operations a tool may *ever* perform — its ceiling.

    Two forms, mirroring the profile model:

    - ``operations`` (2D): operations allowed regardless of data tier.
    - ``per_tier`` (3D): operations allowed per data classification.

    A capability is an explicit allow-list of operations the tool is permitted
    to represent (membership, not cumulative) — a read-only tool declares
    ``operations={READ}`` and can never represent a Change even if the agent's
    profile would permit one. An empty/unset capability does not constrain
    (the agent profile remains the only gate).
    """

    operations: set[Operation] | None = None
    per_tier: dict[DataClassification, set[Operation]] | None = None

    def permits(self, operation: Operation, tier: DataClassification | None) -> bool:
        """Return True if this tool may perform ``operation`` on ``tier``."""
        if self.per_tier is not None:
            if tier is None:
                # Per-tier ceiling but a tier-agnostic call: fail safe by
                # capping at the *union* of operations allowed on any tier — a
                # read-only-per-tier ceiling must not become unbounded just
                # because the caller couldn't supply a tier.
                allowed: set[Operation] = set()
                for ops in self.per_tier.values():
                    allowed |= ops
                return operation in allowed
            return operation in self.per_tier.get(tier, set())
        if self.operations is not None:
            return operation in self.operations
        return True

    def to_dict(self) -> dict[str, Any]:
        if self.per_tier is not None:
            return {
                "per_tier": {
                    tier.value: sorted(o.value for o in ops)
                    for tier, ops in self.per_tier.items()
                }
            }
        if self.operations is not None:
            return {"operations": sorted(o.value for o in self.operations)}
        return {}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolCapability:
        if "per_tier" in data:
            per_tier: dict[DataClassification, set[Operation]] = {}
            for tier, ops in data["per_tier"].items():
                dc = parse_data_classification(tier)
                if dc is not None:
                    per_tier[dc] = {parse_operation(o) for o in ops}
            return cls(per_tier=per_tier)
        if "operations" in data:
            return cls(operations={parse_operation(o) for o in data["operations"]})
        return cls()


@dataclass
class ResolvedCall:
    """The RMACD classification of a concrete tool call."""

    operation: Operation
    tier: DataClassification | None
    target: str


@dataclass
class ToolDefinition:
    """A registered tool with its RMACD classification and capability ceiling."""

    tool_id: str
    tool_name: str
    rmacd_level: Operation  # the tool's RMACD operation (static default)
    description: str = ""
    operations: list[str] = field(default_factory=list)
    data_access: DataClassification | None = None  # static data tier (optional)
    required_hitl: AutonomyLevel | None = None
    risk_score: float | None = None
    tags: set[str] = field(default_factory=set)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utcnow)
    # --- classification + capability (the first-class policy surface) ---
    target_template: str | None = None  # e.g. "server://{server_id}"
    classifier: ToolClassifier | None = None  # dynamic (args) -> (op, tier, target)
    capability: ToolCapability | None = None  # operation ceiling (defence in depth)

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

        # Calculate risk score if not explicitly provided (None sentinel, so a
        # caller can still pin an explicit 0.0 without it being recomputed).
        if self.risk_score is None:
            self.risk_score = self._calculate_risk_score()

    # ----- runtime classification --------------------------------------------

    def resolve_call(self, args: dict[str, Any] | None = None) -> ResolvedCall:
        """Resolve a concrete call to ``(operation, tier, target)``.

        Uses the dynamic ``classifier`` if set (with static fields as the
        fallback for any value it returns as ``None``); otherwise the tool's
        static ``rmacd_level`` / ``data_access`` and a rendered target.
        """
        args = args or {}
        op: Operation = self.rmacd_level
        tier: DataClassification | None = self.data_access
        target: str | None = None

        if self.classifier is not None:
            c_op, c_tier, c_target = self.classifier(args)
            if c_op is not None:
                op = parse_operation(c_op)
            if c_tier is not None:
                tier = parse_data_classification(c_tier)
            if c_target is not None:
                target = c_target

        if target is None:
            target = self._render_target(args)
        return ResolvedCall(operation=op, tier=tier, target=target)

    def permits(self, operation: Operation, tier: DataClassification | None) -> bool:
        """Whether the tool's capability ceiling allows ``(operation, tier)``."""
        if self.capability is None:
            return True
        return self.capability.permits(operation, tier)

    def _render_target(self, args: dict[str, Any]) -> str:
        if self.target_template:
            try:
                return self.target_template.format(**args)
            except (KeyError, IndexError):
                return self.target_template
        return f"tool://{self.tool_id}"

    # ----- risk / serialization ----------------------------------------------

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

        base_risk = (float(rmacd_risk) * 0.6 + data_risk * 0.4) * hitl_modifier
        return round(base_risk * 10, 2)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Note: a dynamic ``classifier`` is code and is not serialized — it must
        be re-registered programmatically after loading from JSON.
        """
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
            "target_template": self.target_template,
            "capability": self.capability.to_dict() if self.capability else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolDefinition:
        """Create tool from dictionary."""
        required_fields = ["tool_id", "tool_name", "rmacd_level"]
        missing = [f for f in required_fields if f not in data]
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")

        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = _utcnow()

        capability_data = data.get("capability")
        capability = ToolCapability.from_dict(capability_data) if capability_data else None

        return cls(
            tool_id=data["tool_id"],
            tool_name=data["tool_name"],
            rmacd_level=data["rmacd_level"],
            description=data.get("description", ""),
            operations=data.get("operations", []),
            data_access=data.get("data_access"),
            required_hitl=data.get("required_hitl"),
            risk_score=data.get("risk_score"),
            tags=set(data.get("tags", [])),
            metadata=data.get("metadata", {}),
            created_at=created_at,
            target_template=data.get("target_template"),
            capability=capability,
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
        logger.info("Tools registry '%s' initialized", registry_id)

    def register_tool(self, tool: ToolDefinition | dict[str, Any]) -> ToolDefinition:
        """Register (or replace) a tool. Returns the registered ToolDefinition."""
        if isinstance(tool, dict):
            tool = ToolDefinition.from_dict(tool)
        elif not isinstance(tool, ToolDefinition):
            raise TypeError(f"Tool must be ToolDefinition or dict, got {type(tool)}")

        # If replacing an existing tool, drop its old level-index entry first so
        # a re-registration at a different rmacd_level doesn't leave a stale
        # entry behind (which would corrupt get_tools_by_level / get_stats).
        existing = self._tools.get(tool.tool_id)
        if existing is not None:
            logger.warning("Tool '%s' already registered, replacing", tool.tool_id)
            self._index_by_level[existing.rmacd_level].discard(tool.tool_id)

        self._tools[tool.tool_id] = tool
        self._index_by_level[tool.rmacd_level].add(tool.tool_id)

        self._log_audit("register", tool.tool_id, {
            "rmacd_level": tool.rmacd_level.value,
            "risk_score": tool.risk_score,
        })

        logger.info(
            "Tool '%s' registered with RMACD level %s", tool.tool_id, tool.rmacd_level.value
        )
        return tool

    def unregister_tool(self, tool_id: str) -> bool:
        """Remove a tool from the registry. Returns True if it was registered."""
        normalized_id = tool_id.strip().lower().replace(" ", "_")
        tool = self._tools.pop(normalized_id, None)
        if tool is None:
            return False
        self._index_by_level[tool.rmacd_level].discard(normalized_id)
        self._log_audit("unregister", normalized_id, {"rmacd_level": tool.rmacd_level.value})
        logger.info("Tool '%s' unregistered", normalized_id)
        return True

    def get_tool(self, tool_id: str) -> ToolDefinition | None:
        """Retrieve a tool by ID."""
        normalized_id = tool_id.strip().lower().replace(" ", "_")
        return self._tools.get(normalized_id)

    def list_tools(self) -> list[ToolDefinition]:
        """All registered tools, in registration order."""
        return list(self._tools.values())

    def get_tools_by_tag(self, tag: str) -> list[ToolDefinition]:
        """All tools carrying a given tag (e.g. 'mcp', 'auto-classified')."""
        return [t for t in self._tools.values() if tag in t.tags]

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
        Validate (advisory) whether an agent with ``allowed_levels`` may use a tool.

        Honours the cumulative RMACD hierarchy (D ⊃ C ⊃ A ⊃ M ⊃ R): an agent
        granted a higher operation implicitly satisfies all lower tool levels.
        For authoritative, profile-aware enforcement use
        ``PolicyEnforcer.enforce_tool_call``; this helper is for catalog/UX
        filtering of a tool list.

        Returns a tuple of (is_allowed, reason).
        """
        def deny(reason: str) -> tuple[bool, str]:
            # Denials are audited too — for a governance layer the refusals are
            # the interesting half of the log.
            self._log_audit("validate_access", tool_id, {"allowed": False, "reason": reason})
            return False, reason

        tool = self.get_tool(tool_id)
        if tool is None:
            return deny(f"Tool '{tool_id}' not found in registry")

        allowed_ops = [parse_operation(lvl) for lvl in allowed_levels]

        # Cumulative check: the agent's highest granted level must cover the
        # tool's required level.
        if allowed_ops:
            max_op = max(allowed_ops, key=lambda o: _OP_ORDER[o])
            if _OP_ORDER[tool.rmacd_level] > _OP_ORDER[max_op]:
                return deny(
                    f"Tool requires {tool.rmacd_level.value} permission, "
                    f"but highest allowed is {max_op.value}"
                )
        else:
            return deny("No allowed levels provided")

        # Check data classification if 3D model
        if data_tier is not None:
            dt = parse_data_classification(data_tier)
            if (
                dt is not None
                and tool.data_access is not None
                and _TIER_ORDER[tool.data_access] > _TIER_ORDER[dt]
            ):
                return deny(
                    f"Tool requires {tool.data_access.value} data access, "
                    f"but only {dt.value} allowed"
                )

        # Check HITL requirements
        if tool.required_hitl == AutonomyLevel.PROHIBITED:
            return deny("Tool is explicitly prohibited")

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

        risk_scores = [t.risk_score or 0.0 for t in tools]
        rmacd_levels = [t.rmacd_level for t in tools]

        highest_rmacd = max(rmacd_levels, key=lambda x: _OP_ORDER[x])
        highest_risk_tool = max(tools, key=lambda t: t.risk_score or 0.0)

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
            "exported_at": _utcnow().isoformat(),
            "tool_count": len(self._tools),
            "tools": [tool.to_dict() for tool in self._tools.values()],
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        logger.info("Registry exported to %s", filepath)
        return True

    def import_from_json(self, filepath: str | Path) -> bool:
        """Import tools from JSON file. Returns True only if every tool imported."""
        filepath = Path(filepath)

        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        if "tools" not in data:
            raise ValueError("Invalid registry file: missing 'tools' key")

        success_count = 0
        error_count = 0
        for tool_data in data["tools"]:
            try:
                self.register_tool(tool_data)
                success_count += 1
            except Exception as e:
                error_count += 1
                logger.error("Error importing tool %s: %s", tool_data.get("tool_id", "unknown"), e)

        logger.info("Imported %d tools from %s (%d errors)", success_count, filepath, error_count)
        return error_count == 0

    def _log_audit(self, action: str, tool_id: str, details: dict[str, Any]) -> None:
        """Log an audit event."""
        self._audit_log.append({
            "timestamp": _utcnow().isoformat(),
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
        total_risk = sum(t.risk_score or 0.0 for t in self._tools.values())
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

    def __iter__(self) -> Iterator[ToolDefinition]:
        return iter(self._tools.values())

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
) -> ToolDefinition:
    """Quick tool registration helper. Returns the registered ToolDefinition."""
    tool = ToolDefinition(
        tool_id=tool_id,
        tool_name=tool_name,
        rmacd_level=parse_operation(rmacd_level),
        **kwargs,
    )
    return registry.register_tool(tool)
