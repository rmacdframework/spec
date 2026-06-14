"""
RMACD Governance Packs - AI-Compile Authoring
=============================================

Turn a tool source (an MCP ``tools/list`` response, or any list of
``(name, description, inputSchema)`` tool definitions) into a *proposal* pack:
each tool gets a rule with a keyword- (and optionally LLM-) inferred
classification, a confidence, and provenance.

This is a **build-time** step. The output is a data file a human reviews
(``rmacd pack review``), freezes, and signs (``rmacd pack sign``) — the LLM never
runs at enforcement time. It reuses the existing keyword + LLM classification
machinery in :mod:`rmacd.registry.mcp` / :mod:`rmacd.registry.llm`.

Author: Kash Kashyap
License: CC BY 4.0
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Literal

from rmacd.packs.models import GovernancePack
from rmacd.registry.mcp import MCPRegistryBridge, MCPTool
from rmacd.registry.tools import ToolsRegistry

if TYPE_CHECKING:
    from rmacd.registry.llm import LLMToolClassifier

_OP_RANK = {"R": 0, "M": 1, "A": 2, "C": 3, "D": 4}


def _source_hash(tools: list[dict[str, Any]]) -> str:
    """Stable hash of the tool definitions a pack was compiled from (for drift)."""
    normalized = sorted(
        (
            {
                "name": t.get("name", ""),
                "description": t.get("description", ""),
                "inputSchema": t.get("inputSchema", {}),
            }
            for t in tools
        ),
        key=lambda t: t["name"],
    )
    blob = json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


def compile_pack(
    tools: Sequence[dict[str, Any] | MCPTool],
    *,
    pack_name: str,
    version: str = "0.1.0",
    llm_classifier: LLMToolClassifier | None = None,
    llm_mode: Literal["fallback", "always"] = "fallback",
    default_operation: str = "C",
) -> GovernancePack:
    """Compile a proposal :class:`GovernancePack` from a list of tool definitions.

    Each tool becomes an MCP-style rule (matched by exact name) with the inferred
    operation/tier, a worst-case capability ceiling, and a per-rule ``confidence``
    so a reviewer can focus on the uncertain tail.
    """
    raw_tools = [t if isinstance(t, dict) else _mcp_to_dict(t) for t in tools]

    bridge = MCPRegistryBridge(
        registry=ToolsRegistry("compile"),
        llm_classifier=llm_classifier,
        llm_mode=llm_mode,
    )
    definitions = bridge.register_mcp_tools(list(tools))

    rules: list[dict[str, Any]] = []
    for definition in definitions:
        classification = definition.metadata.get("classification", {})
        confidence = "high" if classification.get("confidence") == "high" else "low"
        tier = definition.data_access.value if definition.data_access else "internal"
        capability = (
            sorted((op.value for op in definition.capability.operations), key=lambda v: _OP_RANK[v])
            if definition.capability and definition.capability.operations
            else None
        )
        rule: dict[str, Any] = {
            "id": definition.tool_id,
            "when": {"tool": definition.tool_name},
            "classify": {"operation": definition.rmacd_level.value, "tier": tier},
            "confidence": confidence,
        }
        if capability:
            rule["capability"] = capability
        rules.append(rule)

    pack_dict: dict[str, Any] = {
        "pack": pack_name,
        "version": version,
        "description": f"AI-compiled governance pack for {pack_name} (pending human review).",
        "default_operation": default_operation,
        "provenance": {
            "authored_by": "rmacd compile",
            "llm_assisted": llm_classifier is not None,
            "review_status": "ai-drafted",
            "source_hash": _source_hash(raw_tools),
        },
        "rules": rules,
    }
    return GovernancePack.from_dict(pack_dict)


def review_items(pack: GovernancePack) -> list[ReviewItem]:
    """Rules a human should review first: low-confidence or Delete-capable."""
    items: list[ReviewItem] = []
    for rule in pack.rules:
        op = rule.classify.operation if rule.classify else rule.operation
        is_delete = op == "D" or (rule.capability is not None and "D" in rule.capability)
        if rule.confidence == "low" or is_delete:
            items.append(
                {
                    "id": rule.id,
                    "operation": op,
                    "confidence": rule.confidence,
                    "reason": "low-confidence" if rule.confidence == "low" else "delete-capable",
                }
            )
    return items


# A small typed alias for review summaries.
ReviewItem = dict[str, Any]


def _mcp_to_dict(tool: MCPTool) -> dict[str, Any]:
    return {
        "name": tool.name,
        "description": tool.description,
        "inputSchema": tool.inputSchema,
        "operations": tool.operations,
    }


__all__ = ["compile_pack", "review_items", "ReviewItem"]
