"""Map (tool_name, tool_input) → (RMACD operation, target, data classification).

This is the runtime bridge that closes the resource-classification gap (spec
§C.7 says "tag your data sources" but never specifies the lookup mechanism).
For the demo we look the classification up from the mock infra. A real
integration would consult its own data catalog, a tag registry, a DLP product,
or a sidecar lookup service.

Each entry in ``TOOL_CLASSIFICATION`` declares the static RMACD operation for
the tool. The ``target`` and ``classification`` are derived dynamically from
the tool call's arguments — this is what makes the classifier handle tools
whose tier depends on which resource the agent picked (gap #3, dynamic
classification: ``decommission_server`` on ``web-stage-01`` is Internal, but
on ``db-prod-01`` it would be Confidential).
"""

from __future__ import annotations

from dataclasses import dataclass

from rmacd_demo.infra import infra


@dataclass(frozen=True)
class ToolClassification:
    """RMACD attributes for one tool call.

    ``operation`` is the RMACD verb (R/M/A/C/D).
    ``target`` is a URI-like identifier of what was acted on, e.g.
    ``server://web-stage-01``. Logged verbatim in audit records.
    ``classification`` is the PICR tier; ``None`` means the operation is
    classification-agnostic (which the enforcer treats as a 2D-style check).
    """

    operation: str  # "R" | "M" | "A" | "C" | "D"
    target: str
    classification: str | None  # "public" | "internal" | "confidential" | "restricted"


# Static mapping: tool name → RMACD operation verb.
# We deliberately keep this separate from the dynamic target/classification
# lookup. The operation is a property of the *tool*; the classification is a
# property of the *resource* the tool happens to be acting on.
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
    """Derive (operation, target, classification) for a tool call.

    Raises ``UnknownToolError`` if the tool was not registered with a
    classification — a real integration should never see this because the
    enforcer's allowlist and this mapping are kept in sync.
    """
    op = _TOOL_OP.get(tool_name)
    if op is None:
        raise UnknownToolError(f"No RMACD classification registered for tool: {tool_name}")

    # Fleet-wide read: no single target, no per-server tier. Treated as
    # Internal because the fleet listing reveals which hosts exist (an
    # Internal-tier artifact).
    if tool_name == "list_servers":
        return ToolClassification(operation=op, target="fleet://servers", classification="internal")

    if tool_name == "read_audit_log":
        # The audit log itself is Confidential — it records who did what.
        return ToolClassification(operation=op, target="ledger://audit", classification="confidential")

    # All other tools act on a specific server. Look up the server to find
    # its classification; this is the "dynamic classification" pattern from
    # gap #3 — the RMACD tier of the operation depends on which resource
    # the LLM picked, not on the tool itself.
    server_id = tool_input.get("server_id")
    if not server_id:
        raise UnknownToolError(
            f"Tool '{tool_name}' requires a 'server_id' argument to classify the target."
        )
    server = infra.get(server_id)
    if server is None:
        # Unknown target — treat as Confidential by default. Failing to a
        # more restrictive tier when the lookup is ambiguous is the safer
        # default; an attacker who can rename targets shouldn't be able to
        # downgrade classification.
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
