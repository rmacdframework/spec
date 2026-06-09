"""Runnable demo: RMACD-governed DevOps agent on top of the Claude Agent SDK.

Usage::

    export ANTHROPIC_API_KEY=sk-ant-...
    cd spec/examples/agent-integration-claude-sdk
    python -m rmacd_demo.main "list the fleet, then update workers on web-stage-01 to 8"

Or with no argument for the built-in scripted task that exercises all five
RMACD verbs.

The wiring closes the spec gaps as follows:

- **Profile binding (gap #1)** — ``PolicyEnforcer.from_env()`` or explicit
  ``profile=`` constructor argument. We use the explicit form so the demo
  works without env setup; switch to ``from_env()`` for a 12-factor deploy.
- **Resource classification lookup (gap #2)** — ``classify_tool_call()``
  derives the tier from the mock infra. A real integration would consult a
  data catalog, IAM tag registry, or DLP product.
- **Dynamic operation classification (gap #3)** — the classifier resolves
  the tier from the *resource the LLM picked at call time*, not from a
  static tag on the tool definition.
- **Approval-wait semantics (gap #4)** — ``CLIApprovalGateway`` prompts the
  operator and blocks the tool call until they answer. For a real deployment
  swap in a webhook/Slack gateway that returns within the configured timeout.
- **Framework integration (gap #5)** — this whole file. The integration
  surface is the ``PreToolUse`` hook in ``hook.py``.
- **Agent-side prompt (gap #6)** — ``system_prompt.md`` tells the model what
  its profile permits so it can self-restrict and not waste turns proposing
  Prohibited operations.
- **Error contract (gap #8)** — the hook translates each exception subclass
  into a distinct ``permissionDecisionReason`` so the LLM can react
  appropriately.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path


def _load_dotenv() -> Path | None:
    """Load the nearest ``.env`` while walking up from this file.

    Minimal parser, no dependency on python-dotenv. Values already set in
    the shell win — the .env is a fallback, not an override.
    """
    here = Path(__file__).resolve().parent
    for candidate in (here, *here.parents):
        env = candidate / ".env"
        if env.is_file():
            for raw in env.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
            return env
    return None


_load_dotenv()

from claude_agent_sdk import (  # noqa: E402
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    HookMatcher,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    create_sdk_mcp_server,
)

from rmacd import PolicyEnforcer, ProfileLoader
from rmacd.audit import JSONLAuditLogger

from rmacd_demo.cli_gateway import CLIApprovalGateway
from rmacd_demo.hook import make_pretool_hook
from rmacd_demo.registry import build_registry
from rmacd_demo.tools import ALL_TOOLS


HERE = Path(__file__).resolve().parent.parent
PROFILE_PATH = HERE / "profiles" / "devops-demo-3d.json"
SYSTEM_PROMPT_PATH = HERE / "rmacd_demo" / "system_prompt.md"
AUDIT_LOG_PATH = HERE / "audit.jsonl"

DEFAULT_TASK = (
    "List the fleet first. Then: update the workers count on web-stage-01 to 8, "
    "and finally tell me whether you could decommission vault-prod-01."
)


def build_enforcer() -> PolicyEnforcer:
    """Wire up the enforcer with the demo profile, CLI gateway, JSONL audit."""
    profile = ProfileLoader().load_file(PROFILE_PATH)
    return PolicyEnforcer(
        profile=profile,
        agent_id="devops-agent-demo",
        approval_gateway=CLIApprovalGateway(approver_name="local-operator"),
        audit_logger=JSONLAuditLogger(AUDIT_LOG_PATH),
        registry=build_registry(),
    )


def build_options(enforcer: PolicyEnforcer) -> ClaudeAgentOptions:
    """Build Claude Agent SDK options: in-process tools + RMACD PreToolUse hook."""
    rmacd_server = create_sdk_mcp_server(
        name="rmacd_demo",
        version="1.0.0",
        tools=ALL_TOOLS,
    )

    pretool_hook = make_pretool_hook(enforcer)

    return ClaudeAgentOptions(
        mcp_servers={"rmacd_demo": rmacd_server},
        # Pre-approve our MCP tools so the SDK doesn't double-prompt the user;
        # the RMACD hook is the authoritative gate.
        allowed_tools=[
            "mcp__rmacd_demo__list_servers",
            "mcp__rmacd_demo__read_server_config",
            "mcp__rmacd_demo__read_audit_log",
            "mcp__rmacd_demo__migrate_workload",
            "mcp__rmacd_demo__provision_vm",
            "mcp__rmacd_demo__update_config",
            "mcp__rmacd_demo__decommission_server",
        ],
        system_prompt=SYSTEM_PROMPT_PATH.read_text(encoding="utf-8"),
        hooks={
            "PreToolUse": [HookMatcher(matcher="*", hooks=[pretool_hook])],
        },
    )


async def run_agent(task: str) -> None:
    enforcer = build_enforcer()
    options = build_options(enforcer)

    print(f"\n>>> Task: {task}\n", file=sys.stderr)

    async with ClaudeSDKClient(options=options) as client:
        await client.query(task)
        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        print(block.text)
                    elif isinstance(block, ToolUseBlock):
                        print(f"  [tool call] {block.name}({block.input})", file=sys.stderr)
            elif isinstance(msg, ResultMessage):
                if hasattr(msg, "total_cost_usd") and msg.total_cost_usd is not None:
                    print(
                        f"\n  [session] cost=${msg.total_cost_usd:.4f}",
                        file=sys.stderr,
                    )

    print(f"\n  [audit] wrote records to {AUDIT_LOG_PATH}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="RMACD ↔ Claude Agent SDK demo.")
    parser.add_argument(
        "task",
        nargs="?",
        default=DEFAULT_TASK,
        help="Free-text task for the agent (uses a scripted task if omitted).",
    )
    args = parser.parse_args()
    asyncio.run(run_agent(args.task))


if __name__ == "__main__":
    main()
