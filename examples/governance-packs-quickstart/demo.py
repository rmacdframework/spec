"""
Governance Packs quickstart (no LLM, no network).

Demonstrates the SDK 0.11.0 `rmacd.packs` workflow end to end:

1. Build a PolicyEnforcer registry from built-in packs with one line.
2. Enforce real tool calls — allowed, approval-gated, and §12.5-blocked.
3. AI-compile (keyword engine) a pack for a new MCP server and review it.
4. Sign + verify the pack if the optional [sign] extra is installed.

Run:  python demo.py
"""

from __future__ import annotations

from rmacd import PolicyEnforcer, RMACDError
from rmacd.approval import AutoApproveGateway
from rmacd.models import DataClassification as DC
from rmacd.models import Operation as Op
from rmacd.models import Profile3D
from rmacd.packs import (
    compile_pack,
    load_packs,
    register_resolver,
    review_items,
)


def build_enforcer() -> PolicyEnforcer:
    # A DevOps-ish profile: full ops on internal, read-only on restricted.
    profile = Profile3D(
        profile_id="rmacd-3d-devops",
        profile_name="DevOps Agent",
        model="three-dimensional",
        version="1.0",
        permissions={
            DC.PUBLIC: [Op.READ, Op.MOVE, Op.ADD, Op.CHANGE, Op.DELETE],
            DC.INTERNAL: [Op.READ, Op.MOVE, Op.ADD, Op.CHANGE, Op.DELETE],
            DC.CONFIDENTIAL: [Op.READ, Op.MOVE, Op.ADD],
            DC.RESTRICTED: [Op.READ],
        },
    )
    # One line: off-the-shelf classification for the whole tool surface.
    registry = load_packs(["shell", "aws", "kubectl", "github", "sql", "jira"])
    return PolicyEnforcer(
        profile=profile,
        agent_id="devops-agent-1",
        registry=registry,
        approval_gateway=AutoApproveGateway(),
    )


def try_call(enforcer: PolicyEnforcer, tool: str, args: dict) -> None:
    try:
        decision = enforcer.evaluate_tool_call(tool, args)
        verdict = "ALLOW" if decision.allowed else "DENY"
        tier = decision.data_classification.value if decision.data_classification else "-"
        print(f"  {verdict:5} {tool:9} {str(args):46} -> {decision.operation.value}/{tier}")
    except RMACDError as exc:
        print(f"  BLOCK {tool:9} {str(args):46} -> {type(exc).__name__}: {exc}")


def main() -> None:
    # The jira pack expects a project-tier resolver; register one (fail-closed otherwise).
    register_resolver(
        "jira_project_tier",
        lambda key, ctx: {"SEC": "restricted", "HR": "confidential"}.get(key, "internal"),
    )

    print("== Enforcing tool calls through built-in packs ==")
    enforcer = build_enforcer()
    try_call(enforcer, "kubectl", {"command": "get pods -n staging"})
    try_call(enforcer, "kubectl", {"command": "delete pod web -n prod"})
    try_call(enforcer, "aws", {"command": "s3 ls s3://logs"})
    try_call(enforcer, "sql", {"query": "SELECT email FROM customers"})
    # restricted delete -> §12.5 immutable floor blocks it
    try_call(enforcer, "jira_delete_issue", {"project_key": "SEC", "issue_key": "SEC-9"})

    print("\n== AI-compiling a pack for a new MCP server (keyword engine) ==")
    tools = [
        {"name": "crm_search_contacts", "description": "Search contacts", "inputSchema": {}},
        {"name": "crm_delete_contact", "description": "Delete a contact", "inputSchema": {}},
        {"name": "crm_do_sync", "description": "Sync stuff", "inputSchema": {}},  # vague
    ]
    pack = compile_pack(tools, pack_name="crm", version="0.1.0")
    print(f"  compiled '{pack.pack}' v{pack.version} with {len(pack.rules)} rules")
    for item in review_items(pack):
        print(f"  REVIEW {item['id']} [{item['operation']}] -> {item['reason']}")

    print("\n== Sign + verify (optional [sign] extra) ==")
    try:
        from rmacd.packs import generate_keypair, sign_pack, verify_pack

        priv, pub = generate_keypair()
        signed = sign_pack(pack, priv)
        print(f"  signed; content_hash={signed.content_hash[:23]}...")
        print(f"  verify -> {verify_pack(signed, pub)}")
    except ImportError:
        print("  (install rmacd-framework[sign] to enable signing)")


if __name__ == "__main__":
    main()
