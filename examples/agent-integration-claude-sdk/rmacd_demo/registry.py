"""Build the RMACD tools registry for the demo.

The registry is the first-class classifier the enforcer consults at the
tool-call boundary. Each tool registers:

- its RMACD operation (``rmacd_level``);
- a **dynamic classifier** that derives ``(operation, tier, target)`` from the
  call's arguments — here it delegates to ``classify_tool_call``, which reads
  the mock infra so a Delete on a prod resource resolves to Confidential while
  the same tool on a staging resource resolves to Internal; and
- a **capability ceiling** bounding what the tool may *ever* do (defence in
  depth: a read tool can never represent a Change even if the profile would
  allow one).

``PolicyEnforcer.enforce_tool_call(tool, args)`` then enforces *profile ∩ tool*
with the §12.5 safety floor — replacing the bespoke classify-then-enforce
glue that the ``hook`` used to carry.
"""

from __future__ import annotations

from rmacd.models import Operation as Op
from rmacd.registry import ToolCapability, ToolDefinition, ToolsRegistry

from rmacd_demo.classifier import _TOOL_OP, classify_tool_call


def _make_classifier(tool_name: str):
    def classify(args: dict):
        c = classify_tool_call(tool_name, args)
        return (c.operation, c.classification, c.target)

    return classify


# The most each tool may ever do, regardless of which agent invokes it.
_CAPABILITY = {
    "list_servers": ToolCapability(operations={Op.READ}),
    "read_server_config": ToolCapability(operations={Op.READ}),
    "read_audit_log": ToolCapability(operations={Op.READ}),
    "migrate_workload": ToolCapability(operations={Op.MOVE}),
    "provision_vm": ToolCapability(operations={Op.ADD}),
    "update_config": ToolCapability(operations={Op.CHANGE}),
    "decommission_server": ToolCapability(operations={Op.DELETE}),
}


def build_registry() -> ToolsRegistry:
    """Register every demo tool with its classifier and capability ceiling."""
    reg = ToolsRegistry("rmacd-demo")
    for tool_name, op in _TOOL_OP.items():
        reg.register_tool(
            ToolDefinition(
                tool_id=tool_name,
                tool_name=tool_name,
                rmacd_level=op,
                classifier=_make_classifier(tool_name),
                capability=_CAPABILITY.get(tool_name),
            )
        )
    return reg
