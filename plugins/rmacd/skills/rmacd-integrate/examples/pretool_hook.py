"""RMACD PreToolUse hook for the Claude Agent SDK.

Adapted from the reference integration in the spec repo
(``examples/agent-integration-claude-sdk/rmacd_demo/hook.py`` + ``main.py``).
Copy ``make_pretool_hook`` into your agent and wire it via ``ClaudeAgentOptions``:

    from claude_agent_sdk import ClaudeAgentOptions, HookMatcher

    options = ClaudeAgentOptions(
        ...,
        hooks={"PreToolUse": [HookMatcher(matcher="*", hooks=[
            make_pretool_hook(enforcer, mcp_prefix="mcp__myserver__"),
        ])]},
    )

Requires ``pip install "rmacd-framework>=0.14"`` (import name: ``rmacd``).
Run this file directly for an offline demo (no Claude SDK, no API key needed):

    python3 pretool_hook.py
"""

from __future__ import annotations

from typing import Any

from rmacd import (
    PolicyEnforcer,
    RMACDApprovalDeniedError,
    RMACDApprovalTimeoutError,
    RMACDConstraintError,
    RMACDPermissionDeniedError,
    RMACDProhibitedError,
    RMACDToolCapabilityError,
)


def make_pretool_hook(enforcer: PolicyEnforcer, *, mcp_prefix: str = "") -> Any:
    """Return an async PreToolUse hook bound to ``enforcer``.

    The Claude Agent SDK exposes MCP-server tools as ``mcp__<server-key>__<tool>``
    where ``<server-key>`` matches the key passed to
    ``ClaudeAgentOptions.mcp_servers``. Pass that namespace as ``mcp_prefix``
    (e.g. ``"mcp__myserver__"``) and the hook strips it before consulting the
    registry. With ``mcp_prefix=""`` tool names are used as-is (built-in tools
    such as ``Bash`` — register them in the registry, e.g. via the ``shell``
    pack or ``make_bash_classifier``).

    Decision translation (fail-closed throughout):

    - enforcer allows            -> ``permissionDecision: "allow"``
    - any ``RMACD*Error``        -> ``"deny"`` with a distinct, model-readable reason
    - anything else (bug, unknown tool, classifier fault) -> ``"deny"``
    """

    async def pretool_hook(
        input_data: dict[str, Any],
        tool_use_id: str | None,
        context: Any,
    ) -> dict[str, Any]:
        del tool_use_id, context  # not needed for the policy decision

        full_tool_name: str = input_data.get("tool_name", "")
        tool_input: dict[str, Any] = input_data.get("tool_input", {}) or {}

        if mcp_prefix:
            if not full_tool_name.startswith(mcp_prefix):
                # Default-deny anything outside the governed namespace rather
                # than silently allowing it.
                return _deny(
                    f"Tool '{full_tool_name}' is not governed by this RMACD profile."
                )
            tool_name = full_tool_name[len(mcp_prefix):]
        else:
            tool_name = full_tool_name

        # Single integration call: the registry classifies the call into RMACD
        # terms; the enforcer applies profile ∩ tool capability plus the §12.5
        # floor, routes approvals, and emits audit records.
        try:
            enforcer.enforce_tool_call(tool_name, tool_input)
        except RMACDToolCapabilityError as exc:
            return _deny(
                f"RMACD: tool '{tool_name}' is not permitted to perform that "
                f"operation (capability ceiling). Detail: {exc}"
            )
        except RMACDProhibitedError as exc:
            return _deny(
                f"RMACD: that operation is prohibited by the autonomy matrix for "
                f"any agent (human execution only). Detail: {exc}"
            )
        except RMACDPermissionDeniedError as exc:
            return _deny(
                f"RMACD: your profile does not grant this operation. Detail: {exc}"
            )
        except RMACDApprovalDeniedError as exc:
            note = f" Approver note: {exc.note}" if exc.note else ""
            return _deny(f"RMACD: human approver denied the operation.{note}")
        except RMACDApprovalTimeoutError as exc:
            return _deny(f"RMACD: approval timed out after {exc.timeout_seconds}s.")
        except RMACDConstraintError as exc:
            return _deny(f"RMACD: constraint blocked operation: {exc}")
        except Exception as exc:  # defensive: classifier/SDK errors fail closed
            return _deny(f"RMACD enforcer raised unexpectedly: {exc}")

        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
            }
        }

    return pretool_hook


def _deny(reason: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


# ---------------------------------------------------------------------------
# Offline demo: exercises the hook with fake PreToolUse payloads. Safe to
# delete when copying this file into your agent.
# ---------------------------------------------------------------------------

def _build_demo_enforcer() -> PolicyEnforcer:
    from rmacd import AutoApproveGateway, ProfileLoader
    from rmacd.models import Operation
    from rmacd.registry import ToolDefinition, ToolsRegistry

    profile = ProfileLoader().load_dict(
        {
            "profile_id": "rmacd-3d-hook-demo-v1",
            "profile_name": "Hook Demo Agent",
            "model": "three-dimensional",
            "version": "1.0",
            "permissions": {
                "public": ["R", "M", "A", "C"],
                "internal": ["R", "M"],
                "confidential": ["R"],
                "restricted": [],
            },
        }
    )

    registry = ToolsRegistry("hook-demo")
    registry.register_tool(
        ToolDefinition(
            "read_config", "Read Config", Operation.READ,
            # classifier: args -> (operation, tier, target)
            classifier=lambda args: (
                "R",
                "confidential" if str(args.get("name", "")).startswith("prod-")
                else "internal",
                f"config://{args.get('name')}",
            ),
        )
    )
    registry.register_tool(
        ToolDefinition(
            "delete_config", "Delete Config", Operation.DELETE,
            data_access="internal",
            target_template="config://{name}",
        )
    )

    return PolicyEnforcer(
        profile=profile,
        agent_id="hook-demo-agent",
        approval_gateway=AutoApproveGateway(),  # demo only — never in production
        registry=registry,
    )


def _demo() -> None:
    import asyncio
    import json

    enforcer = _build_demo_enforcer()
    hook = make_pretool_hook(enforcer, mcp_prefix="mcp__demo__")

    payloads = [
        # Allowed: Read on internal.
        {"tool_name": "mcp__demo__read_config", "tool_input": {"name": "web-01"}},
        # Denied: profile does not grant Delete on internal.
        {"tool_name": "mcp__demo__delete_config", "tool_input": {"name": "web-01"}},
        # Denied: tool not registered (fail-closed).
        {"tool_name": "mcp__demo__format_disk", "tool_input": {}},
        # Denied: outside the governed MCP namespace.
        {"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}},
    ]
    for payload in payloads:
        result = asyncio.run(hook(payload, None, None))
        print(f"{payload['tool_name']}:")
        print(f"  {json.dumps(result['hookSpecificOutput'], indent=2)}")


if __name__ == "__main__":
    _demo()
