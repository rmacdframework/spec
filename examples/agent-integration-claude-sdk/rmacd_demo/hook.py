"""PreToolUse hook that funnels every tool call through ``PolicyEnforcer``.

This is the single integration point between the Claude Agent SDK and RMACD.
The agent receives a ``tool_use`` block, the SDK fires the ``PreToolUse``
hook with the tool name and input, and we return a permission decision. The
hook is the spec's Policy Enforcement Point made concrete for this framework.

How the decision is translated:

- ``ALLOW`` (enforcer returns a decision) → ``permissionDecision: "allow"``.
- ``RMACDProhibitedError`` → ``"deny"`` with a reason that surfaces the spec's
  hard-stop wording. The LLM sees this and can adapt or escalate to the user.
- ``RMACDPermissionDeniedError`` → ``"deny"``. Returned to the model as a
  recoverable error so it can attempt a different approach (a lower-risk
  operation, or asking the user for permission to broaden the profile).
- ``RMACDApprovalDeniedError`` / ``RMACDApprovalTimeoutError`` → ``"deny"``.
  The human said no (or never answered); the agent must respect that.
- ``RMACDConstraintError`` → ``"deny"`` with the constraint name in the
  reason (e.g. "production change window closed").
- Anything else (unknown tool, classifier error, RMACD SDK bug) → ``"deny"``
  fail-closed. Better for the agent to see a denial it can react to than for
  enforcement to silently fall through.
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
)

from rmacd_demo.classifier import UnknownToolError, classify_tool_call


# The Claude Agent SDK exposes MCP-server tools under names of the form
# ``mcp__<server-key>__<tool-name>``. The ``server-key`` here matches the key
# we pass to ``ClaudeAgentOptions.mcp_servers`` in main.py.
_MCP_PREFIX = "mcp__rmacd_demo__"


def make_pretool_hook(enforcer: PolicyEnforcer) -> Any:
    """Return an async hook function bound to ``enforcer``.

    The Agent SDK's hook API expects a coroutine, so we close over the
    enforcer and return a callable with the correct signature.
    """

    async def pretool_hook(
        input_data: dict[str, Any],
        tool_use_id: str | None,
        context: Any,
    ) -> dict[str, Any]:
        del tool_use_id, context  # not needed for the policy decision

        full_tool_name: str = input_data.get("tool_name", "")
        tool_input: dict[str, Any] = input_data.get("tool_input", {}) or {}

        # Tools registered through our in-process MCP server are namespaced.
        # Built-in Claude tools (Bash, Read, Write, etc.) aren't part of this
        # demo's allow-list and shouldn't reach this hook, but if they do,
        # default-deny rather than silently allow.
        if not full_tool_name.startswith(_MCP_PREFIX):
            return _deny(f"Tool '{full_tool_name}' is not governed by this RMACD profile.")
        local_tool_name = full_tool_name[len(_MCP_PREFIX) :]

        try:
            cls = classify_tool_call(local_tool_name, tool_input)
        except UnknownToolError as exc:
            return _deny(f"RMACD classifier error: {exc}")
        except Exception as exc:  # pragma: no cover - defensive
            return _deny(f"RMACD classifier crashed: {exc}")

        try:
            enforcer.enforce(
                operation=cls.operation,
                target=cls.target,
                classification=cls.classification,
                justification=_summarise_args(local_tool_name, tool_input),
            )
        except RMACDProhibitedError as exc:
            return _deny(
                f"RMACD: {cls.operation} on tier {cls.classification} is "
                f"prohibited by the autonomy matrix for any agent. "
                f"Target={cls.target}. Detail: {exc}"
            )
        except RMACDPermissionDeniedError as exc:
            return _deny(
                f"RMACD: your profile does not grant {cls.operation} on tier "
                f"{cls.classification}. Target={cls.target}. Detail: {exc}"
            )
        except RMACDApprovalDeniedError as exc:
            note = f" Approver note: {exc.note}" if exc.note else ""
            return _deny(
                f"RMACD: human approver denied {cls.operation} on {cls.target}.{note}"
            )
        except RMACDApprovalTimeoutError as exc:
            return _deny(
                f"RMACD: approval for {cls.operation} on {cls.target} timed out "
                f"after {exc.timeout_seconds}s."
            )
        except RMACDConstraintError as exc:
            return _deny(f"RMACD: constraint blocked operation: {exc}")
        except Exception as exc:  # pragma: no cover - defensive
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


def _summarise_args(tool_name: str, tool_input: dict[str, Any]) -> str:
    if not tool_input:
        return f"agent invoked {tool_name}"
    args_preview = ", ".join(f"{k}={v}" for k, v in list(tool_input.items())[:4])
    return f"agent invoked {tool_name}({args_preview})"
