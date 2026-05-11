"""Map (tool_name, tool_input) → (RMACD operation, target, data classification).

Same pattern as the Claude Agent SDK example's classifier — see
``../agent-integration-claude-sdk/rmacd_demo/classifier.py`` for the
extended commentary on why this lives at the call site rather than as a
static tag on the tool definition (gap #3 / dynamic classification).
"""

from __future__ import annotations

from dataclasses import dataclass

from infra import infra


@dataclass(frozen=True)
class ToolClassification:
    operation: str
    target: str
    classification: str | None


# Static mapping: tool name → RMACD operation verb.
_TOOL_OP: dict[str, str] = {
    "list_servers": "R",
    "read_server_config": "R",
    "read_audit_log": "R",
    "migrate_workload": "M",
    "provision_vm": "A",
    "update_config": "C",
    "decommission_server": "D",
}


def classify_tool_call(tool_name: str, tool_input: dict) -> ToolClassification:
    op = _TOOL_OP.get(tool_name)
    if op is None:
        raise UnknownToolError(f"No RMACD classification registered for tool: {tool_name}")

    if tool_name == "list_servers":
        return ToolClassification(operation=op, target="fleet://servers", classification="internal")

    if tool_name == "read_audit_log":
        return ToolClassification(operation=op, target="ledger://audit", classification="confidential")

    # provision_vm: the new resource's tier comes from the LLM's argument,
    # not from any pre-existing resource. Trust the argument here; in a
    # real integration you'd validate it against an allow-list of tiers
    # the agent is permitted to create.
    if tool_name == "provision_vm":
        tier = tool_input.get("classification", "internal")
        target = f"server://{tool_input.get('server_id', '<unknown>')}"
        return ToolClassification(operation=op, target=target, classification=tier)

    # migrate_workload acts on the source; the destination is derived.
    if tool_name == "migrate_workload":
        source_id = tool_input.get("source_id")
        if not source_id:
            raise UnknownToolError("migrate_workload requires source_id")
        server = infra.get(source_id)
        tier = server.classification if server else "confidential"
        target = f"server://{source_id}"
        return ToolClassification(operation=op, target=target, classification=tier)

    # Default path: tools acting on a single server_id resolve the tier
    # from the server's current classification. Unknown servers default
    # to Confidential as a safe-restrictive fallback — see the
    # commentary in the Claude Agent SDK example's classifier.
    server_id = tool_input.get("server_id")
    if not server_id:
        raise UnknownToolError(
            f"Tool '{tool_name}' requires a 'server_id' argument to classify the target."
        )
    server = infra.get(server_id)
    if server is None:
        return ToolClassification(
            operation=op,
            target=f"server://{server_id}",
            classification="confidential",
        )
    return ToolClassification(
        operation=op,
        target=f"server://{server.server_id}",
        classification=server.classification,
    )


class UnknownToolError(Exception):
    """Raised when a tool has no RMACD mapping. Treated as a hard deny upstream."""
