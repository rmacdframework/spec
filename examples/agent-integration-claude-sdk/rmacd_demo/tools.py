"""Custom tools exposed to Claude via the in-process MCP server.

Each tool corresponds to a row in ``classifier._TOOL_OP`` so the PreToolUse
hook can resolve the RMACD operation by name. The tool *implementations* here
are intentionally trivial — they only mutate the mock infra. The interesting
work happens earlier in the pipeline (the PreToolUse hook), which is the
point of the demo.
"""

from __future__ import annotations

from typing import Any

from claude_agent_sdk import tool

from rmacd_demo.infra import infra


@tool(
    "list_servers",
    "List all servers in the fleet with their role, environment, and data classification.",
    {},
)
async def list_servers(args: dict[str, Any]) -> dict[str, Any]:
    del args
    rows = [
        f"- {s.server_id} ({s.role}, {s.environment}, classification={s.classification})"
        for s in infra.list_servers()
    ]
    body = "Fleet inventory:\n" + ("\n".join(rows) if rows else "(empty)")
    return {"content": [{"type": "text", "text": body}]}


@tool(
    "read_server_config",
    "Read the current configuration for a specific server.",
    {"server_id": str},
)
async def read_server_config(args: dict[str, Any]) -> dict[str, Any]:
    server = infra.get(args["server_id"])
    if server is None:
        return _error(f"Unknown server: {args['server_id']}")
    return {
        "content": [
            {
                "type": "text",
                "text": f"{server.server_id} config: {server.config}",
            }
        ]
    }


@tool(
    "read_audit_log",
    "Read the in-memory audit ledger (confidential). Returns recent entries.",
    {"limit": int},
)
async def read_audit_log(args: dict[str, Any]) -> dict[str, Any]:
    limit = max(1, min(int(args.get("limit", 10)), 100))
    entries = infra.audit_ledger[-limit:]
    if not entries:
        return {"content": [{"type": "text", "text": "Audit ledger is empty."}]}
    lines = [
        f"- {e.when.isoformat()} | {e.actor} | {e.action} | {e.target} | {e.detail}"
        for e in entries
    ]
    return {"content": [{"type": "text", "text": "Recent audit entries:\n" + "\n".join(lines)}]}


@tool(
    "migrate_workload",
    "Move a workload from one server to another. Both servers must already exist.",
    {"source_id": str, "dest_id": str},
)
async def migrate_workload(args: dict[str, Any]) -> dict[str, Any]:
    source = infra.get(args["source_id"])
    dest = infra.get(args["dest_id"])
    if source is None or dest is None:
        return _error("Source or destination server not found.")
    infra.record(
        actor="devops-agent",
        action="migrate",
        target=f"{source.server_id}->{dest.server_id}",
        detail=f"role={source.role}",
    )
    return _ok(f"Migrated workload from {source.server_id} to {dest.server_id}.")


@tool(
    "provision_vm",
    "Provision a new server. ``classification`` controls which RMACD tier the new resource belongs to.",
    {"server_id": str, "role": str, "environment": str, "classification": str},
)
async def provision_vm(args: dict[str, Any]) -> dict[str, Any]:
    from rmacd_demo.infra import Server

    server_id = args["server_id"]
    if infra.get(server_id) is not None:
        return _error(f"Server {server_id} already exists.")
    infra.servers[server_id] = Server(
        server_id=server_id,
        role=args["role"],
        environment=args["environment"],
        classification=args["classification"],
    )
    infra.record(actor="devops-agent", action="provision", target=server_id, detail=args["role"])
    return _ok(f"Provisioned {server_id} ({args['role']}, {args['environment']}).")


@tool(
    "update_config",
    "Update a config key on an existing server.",
    {"server_id": str, "key": str, "value": str},
)
async def update_config(args: dict[str, Any]) -> dict[str, Any]:
    server = infra.get(args["server_id"])
    if server is None:
        return _error(f"Unknown server: {args['server_id']}")
    server.config[args["key"]] = args["value"]
    infra.record(
        actor="devops-agent",
        action="update_config",
        target=server.server_id,
        detail=f"{args['key']}={args['value']}",
    )
    return _ok(f"Updated {server.server_id}.{args['key']} = {args['value']}.")


@tool(
    "decommission_server",
    "Decommission (soft-delete) a server. Marks the server as decommissioned but does not purge state.",
    {"server_id": str},
)
async def decommission_server(args: dict[str, Any]) -> dict[str, Any]:
    server = infra.get(args["server_id"])
    if server is None:
        return _error(f"Unknown server: {args['server_id']}")
    server.decommissioned = True
    infra.record(actor="devops-agent", action="decommission", target=server.server_id)
    return _ok(f"Decommissioned {server.server_id}.")


def _ok(text: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}]}


def _error(text: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "is_error": True}


ALL_TOOLS = [
    list_servers,
    read_server_config,
    read_audit_log,
    migrate_workload,
    provision_vm,
    update_config,
    decommission_server,
]
