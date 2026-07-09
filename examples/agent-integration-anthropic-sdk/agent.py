"""RMACD + raw Anthropic SDK reference integration.

Demonstrates the same RMACD enforcement pattern as the Claude Agent SDK
example, but without any framework — just the `anthropic` Python SDK and a
hand-rolled tool-use loop. The intent is to make the integration pattern
portable: any agent built directly on the Anthropic SDK (or any agent
framework that exposes a similar tool-dispatch site) can adapt this with
minimal changes.

Integration point: between receiving a ``ToolUseBlock`` from the API and
dispatching to the local handler, the loop calls ``PolicyEnforcer.enforce``.
On a denial, the tool result is returned to the LLM as a normal
``is_error=True`` content block — the same shape an executed-but-failed
tool call would produce. That lets the LLM react and adapt without
crashing the loop.

Run::

    export ANTHROPIC_API_KEY=sk-ant-...
    cd spec/examples/agent-integration-anthropic-sdk
    pip install -e ../../sdk/python
    pip install anthropic
    python agent.py "list the fleet, then update workers on web-stage-01 to 8"
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _load_dotenv() -> Path | None:
    """Load the nearest ``.env`` found while walking up from this file.

    Why this is here and not python-dotenv: keeping the demo dependency-free
    matters because the SDK itself doesn't require dotenv, and integrators
    who copy this pattern shouldn't have to take a new dependency just to
    read a local secret file. The parser is intentionally minimal — it
    handles ``KEY=value`` and ``# comment`` lines and nothing else.
    """
    here = Path(__file__).resolve().parent
    for candidate in (here, *here.parents):
        env = candidate / ".env"
        if env.is_file():
            for raw in env.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                # Don't clobber values the user has already exported in
                # their shell — the .env is a fallback, not an override.
                os.environ.setdefault(key, value)
            return env
    return None


_load_dotenv()

import anthropic  # noqa: E402

# Allow running without packaging.
SDK_PATH = Path(__file__).resolve().parent.parent.parent / "sdk" / "python"
if str(SDK_PATH) not in sys.path:
    sys.path.insert(0, str(SDK_PATH))

from rmacd import (  # noqa: E402
    CLIApprovalGateway,
    PolicyEnforcer,
    ProfileLoader,
    RMACDApprovalDeniedError,
    RMACDApprovalTimeoutError,
    RMACDConstraintError,
    RMACDPermissionDeniedError,
    RMACDProhibitedError,
)
from rmacd.audit import JSONLAuditLogger  # noqa: E402

# Mock infra and classifier live in this directory so the demo is
# self-contained. Patterns mirror the Claude Agent SDK example. The approval
# gateway (CLIApprovalGateway) now ships in the SDK — imported above.
from infra import infra, Server  # noqa: E402
from classifier import classify_tool_call, UnknownToolError  # noqa: E402


HERE = Path(__file__).resolve().parent
PROFILE_PATH = HERE / "profiles" / "devops-demo-3d.json"
AUDIT_LOG_PATH = HERE / "audit.jsonl"
SYSTEM_PROMPT_PATH = HERE / "system_prompt.md"

# Default to Haiku for cheaper / faster demo runs. Set RMACD_DEMO_MODEL to
# override (claude-sonnet-4-6 is a good upgrade when you want better
# reasoning about denials).
DEFAULT_MODEL = os.environ.get("RMACD_DEMO_MODEL", "claude-haiku-4-5")
MAX_TURNS = 8  # Hard cap so a runaway loop can't burn through budget.

DEFAULT_TASK = (
    "List the fleet first. Then: update the workers count on web-stage-01 to 8, "
    "and finally tell me whether you could decommission vault-prod-01."
)


# ---- Tool definitions in Anthropic-SDK format -------------------------------

TOOLS: list[dict[str, Any]] = [
    {
        "name": "list_servers",
        "description": "List all servers in the fleet with their role, environment, and data classification.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "read_server_config",
        "description": "Read the current configuration for a specific server.",
        "input_schema": {
            "type": "object",
            "properties": {"server_id": {"type": "string"}},
            "required": ["server_id"],
        },
    },
    {
        "name": "read_audit_log",
        "description": "Read the in-memory audit ledger (confidential). Returns recent entries.",
        "input_schema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 10}},
            "required": [],
        },
    },
    {
        "name": "migrate_workload",
        "description": "Move a workload from one server to another. Both servers must already exist.",
        "input_schema": {
            "type": "object",
            "properties": {
                "source_id": {"type": "string"},
                "dest_id": {"type": "string"},
            },
            "required": ["source_id", "dest_id"],
        },
    },
    {
        "name": "provision_vm",
        "description": "Provision a new server. classification controls which RMACD tier the new resource belongs to.",
        "input_schema": {
            "type": "object",
            "properties": {
                "server_id": {"type": "string"},
                "role": {"type": "string"},
                "environment": {"type": "string"},
                "classification": {
                    "type": "string",
                    "enum": ["public", "internal", "confidential", "restricted"],
                },
            },
            "required": ["server_id", "role", "environment", "classification"],
        },
    },
    {
        "name": "update_config",
        "description": "Update a config key on an existing server.",
        "input_schema": {
            "type": "object",
            "properties": {
                "server_id": {"type": "string"},
                "key": {"type": "string"},
                "value": {"type": "string"},
            },
            "required": ["server_id", "key", "value"],
        },
    },
    {
        "name": "decommission_server",
        "description": "Decommission (soft-delete) a server. Marks the server as decommissioned but does not purge state.",
        "input_schema": {
            "type": "object",
            "properties": {"server_id": {"type": "string"}},
            "required": ["server_id"],
        },
    },
]


# ---- Tool execution (post-enforcement) -------------------------------------


def _run_tool_body(name: str, args: dict[str, Any]) -> str:
    """Execute the underlying tool. Only reached after RMACD approves the call.

    Returns a plain string; the loop wraps it into a tool_result content
    block. Error messages are returned as strings (with is_error=True at
    the call site).
    """
    if name == "list_servers":
        rows = [
            f"- {s.server_id} ({s.role}, {s.environment}, classification={s.classification})"
            for s in infra.list_servers()
        ]
        return "Fleet inventory:\n" + ("\n".join(rows) if rows else "(empty)")

    if name == "read_server_config":
        server = infra.get(args["server_id"])
        if server is None:
            return f"Unknown server: {args['server_id']}"
        return f"{server.server_id} config: {server.config}"

    if name == "read_audit_log":
        limit = max(1, min(int(args.get("limit", 10)), 100))
        entries = infra.audit_ledger[-limit:]
        if not entries:
            return "Audit ledger is empty."
        return "Recent audit entries:\n" + "\n".join(
            f"- {e.when.isoformat()} | {e.actor} | {e.action} | {e.target} | {e.detail}"
            for e in entries
        )

    if name == "migrate_workload":
        src = infra.get(args["source_id"])
        dst = infra.get(args["dest_id"])
        if src is None or dst is None:
            return "Source or destination server not found."
        infra.record(
            actor="devops-agent",
            action="migrate",
            target=f"{src.server_id}->{dst.server_id}",
            detail=f"role={src.role}",
        )
        return f"Migrated workload from {src.server_id} to {dst.server_id}."

    if name == "provision_vm":
        if infra.get(args["server_id"]) is not None:
            return f"Server {args['server_id']} already exists."
        infra.servers[args["server_id"]] = Server(
            server_id=args["server_id"],
            role=args["role"],
            environment=args["environment"],
            classification=args["classification"],
        )
        infra.record(
            actor="devops-agent",
            action="provision",
            target=args["server_id"],
            detail=args["role"],
        )
        return f"Provisioned {args['server_id']} ({args['role']}, {args['environment']})."

    if name == "update_config":
        server = infra.get(args["server_id"])
        if server is None:
            return f"Unknown server: {args['server_id']}"
        server.config[args["key"]] = args["value"]
        infra.record(
            actor="devops-agent",
            action="update_config",
            target=server.server_id,
            detail=f"{args['key']}={args['value']}",
        )
        return f"Updated {server.server_id}.{args['key']} = {args['value']}."

    if name == "decommission_server":
        server = infra.get(args["server_id"])
        if server is None:
            return f"Unknown server: {args['server_id']}"
        server.decommissioned = True
        infra.record(actor="devops-agent", action="decommission", target=server.server_id)
        return f"Decommissioned {server.server_id}."

    return f"Unknown tool: {name}"


def dispatch_tool(
    enforcer: PolicyEnforcer,
    name: str,
    args: dict[str, Any],
) -> tuple[str, bool]:
    """Enforce RMACD, then execute. Returns (content, is_error).

    This is the integration point. Every framework's equivalent of "the
    code that receives a tool_use block and calls the local handler" needs
    one of these. The pattern is the same regardless of framework:
    classify the call, enforce, dispatch on allow, return an error
    content block on denial.
    """
    # 1) Classify the call: what RMACD operation is this, on what
    #    target, at what data tier?
    try:
        cls = classify_tool_call(name, args)
    except UnknownToolError as exc:
        return f"RMACD classifier error: {exc}", True

    # 2) Enforce. enforce() returns the decision on allow, raises on deny.
    try:
        enforcer.enforce(
            operation=cls.operation,
            target=cls.target,
            classification=cls.classification,
            justification=f"agent invoked {name}({_short_args(args)})",
        )
    except RMACDProhibitedError as exc:
        return (
            f"RMACD: {cls.operation} on tier {cls.classification} is "
            f"prohibited by the autonomy matrix for any agent. "
            f"Target={cls.target}. Detail: {exc}"
        ), True
    except RMACDPermissionDeniedError as exc:
        return (
            f"RMACD: your profile does not grant {cls.operation} on tier "
            f"{cls.classification}. Target={cls.target}. Detail: {exc}"
        ), True
    except RMACDApprovalDeniedError as exc:
        note = f" Approver note: {exc.note}" if exc.note else ""
        return (
            f"RMACD: human approver denied {cls.operation} on {cls.target}.{note}"
        ), True
    except RMACDApprovalTimeoutError as exc:
        return (
            f"RMACD: approval for {cls.operation} on {cls.target} timed out "
            f"after {exc.timeout_seconds}s."
        ), True
    except RMACDConstraintError as exc:
        return f"RMACD: constraint blocked operation: {exc}", True

    # 3) Allowed — run the tool body.
    try:
        return _run_tool_body(name, args), False
    except Exception as exc:  # pragma: no cover - defensive
        return f"Tool execution failed: {exc}", True


def _short_args(args: dict[str, Any]) -> str:
    if not args:
        return ""
    return ", ".join(f"{k}={v}" for k, v in list(args.items())[:4])


# ---- The agent loop --------------------------------------------------------


def run_agent(task: str, model: str = DEFAULT_MODEL) -> None:
    profile = ProfileLoader().load_file(PROFILE_PATH)
    enforcer = PolicyEnforcer(
        profile=profile,
        agent_id="devops-agent-anthropic-sdk",
        approval_gateway=CLIApprovalGateway(approver_name="local-operator"),
        audit_logger=JSONLAuditLogger(AUDIT_LOG_PATH),
    )

    client = anthropic.Anthropic()
    system_prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")

    print(f"\n>>> Task: {task}\n", file=sys.stderr)

    messages: list[dict[str, Any]] = [{"role": "user", "content": task}]

    for turn in range(MAX_TURNS):
        # Prompt-caching: cache the system prompt and tools so we don't
        # re-bill the input on every loop iteration. Both are stable for
        # the life of the agent process.
        response = client.messages.create(
            model=model,
            max_tokens=2048,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            tools=TOOLS,
            messages=messages,
        )

        # Echo any assistant text to stdout so the user can follow along.
        for block in response.content:
            if block.type == "text":
                print(block.text)
            elif block.type == "tool_use":
                print(f"  [tool call] {block.name}({block.input})", file=sys.stderr)

        if response.stop_reason != "tool_use":
            _print_session_summary(response, turn + 1)
            break

        # Append the assistant's response (containing tool_use blocks) to
        # the message history.
        messages.append({"role": "assistant", "content": response.content})

        # Dispatch every tool_use block through RMACD, build a single
        # user-role message containing all the tool_result blocks. The
        # Anthropic API requires tool_results to be batched per turn.
        tool_results: list[dict[str, Any]] = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            content, is_error = dispatch_tool(enforcer, block.name, dict(block.input))
            result: dict[str, Any] = {
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": content,
            }
            if is_error:
                result["is_error"] = True
            tool_results.append(result)

        messages.append({"role": "user", "content": tool_results})
    else:
        print(
            f"\n  [agent] hit MAX_TURNS={MAX_TURNS} without natural stop",
            file=sys.stderr,
        )

    print(f"\n  [audit] wrote records to {AUDIT_LOG_PATH}", file=sys.stderr)


def _print_session_summary(response: Any, turns: int) -> None:
    usage = getattr(response, "usage", None)
    if usage is None:
        print(f"\n  [session] turns={turns}", file=sys.stderr)
        return
    in_tokens = getattr(usage, "input_tokens", 0)
    out_tokens = getattr(usage, "output_tokens", 0)
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    cache_create = getattr(usage, "cache_creation_input_tokens", 0) or 0
    print(
        f"\n  [session] turns={turns} in={in_tokens} out={out_tokens} "
        f"cache_read={cache_read} cache_create={cache_create}",
        file=sys.stderr,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="RMACD + raw Anthropic SDK demo.")
    parser.add_argument(
        "task",
        nargs="?",
        default=DEFAULT_TASK,
        help="Free-text task for the agent (uses a scripted task if omitted).",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Model id (default: {DEFAULT_MODEL}; or set RMACD_DEMO_MODEL).",
    )
    args = parser.parse_args()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set.", file=sys.stderr)
        sys.exit(1)
    run_agent(args.task, model=args.model)


if __name__ == "__main__":
    main()


# Unused import silencer for strict linters.
_ = datetime, timezone
