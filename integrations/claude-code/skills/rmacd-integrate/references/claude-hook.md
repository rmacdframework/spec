# Claude Agent SDK integration: the PreToolUse hook

The Claude Agent SDK fires a `PreToolUse` hook after the model emits a `tool_use` block
and before the tool body runs. That hook is RMACD's Policy Enforcement Point for this
framework: one hook, one `enforce_tool_call`, every tool governed.

Full runnable reference: `examples/agent-integration-claude-sdk/` in the spec repo
(https://github.com/rmacdframework/spec). A ready-to-adapt hook is in this skill at
`examples/pretool_hook.py`.

## Hook payload contract

The SDK calls the hook as an async function
`hook(input_data: dict, tool_use_id: str | None, context) -> dict`.

Input (`input_data`):

```json
{"tool_name": "mcp__myserver__update_config", "tool_input": {"server_id": "prod-01"}}
```

Return value — `hookSpecificOutput` with a permission decision:

```python
# allow
{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow"}}
# deny — reason is shown to the model so it can adapt
{"hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "RMACD: your profile does not grant this operation. ...",
}}
```

`hookEventName` must be exactly `"PreToolUse"`. `permissionDecisionReason` is required
for denials — it is the only channel through which the model learns *why* and can pick
a lower-risk alternative or ask the user.

## MCP name-prefix stripping

Tools served over MCP reach the hook as `mcp__<server-key>__<tool-name>`, where
`<server-key>` is the key used in `ClaudeAgentOptions.mcp_servers`. The registry knows
tools by their bare names, so strip the prefix before enforcing:

```python
_MCP_PREFIX = "mcp__myserver__"

if not full_tool_name.startswith(_MCP_PREFIX):
    return _deny(f"Tool '{full_tool_name}' is not governed by this RMACD profile.")
local_tool_name = full_tool_name[len(_MCP_PREFIX):]
```

Decide the stance for non-MCP built-ins (Bash, Read, Write, ...) explicitly: either
register them in the registry (e.g. `make_bash_classifier()` for Bash, or the `shell`
pack) and enforce them too, or default-deny them as above. Never silently allow a name
that misses the prefix check.

## Exception → deny mapping

Catch each RMACD exception and produce a distinct reason — the model reacts differently
to a hard stop than to a profile gap:

| Exception | Meaning | Reason wording |
|---|---|---|
| `RMACDToolCapabilityError` | tool's own ceiling forbids it | "tool not permitted to perform that operation (capability ceiling)" |
| `RMACDProhibitedError` | §12.5 / matrix prohibition | "prohibited by the autonomy matrix for any agent (human execution only)" |
| `RMACDPermissionDeniedError` | profile does not grant it | "your profile does not grant this operation" (a §12 exception request is possible) |
| `RMACDApprovalDeniedError` | human approver said no | "human approver denied the operation" (+ approver note, `exc.note`) |
| `RMACDApprovalTimeoutError` | approver never answered | "approval timed out after {exc.timeout_seconds}s" |
| `RMACDConstraintError` | env / time-window / quota | "constraint blocked operation: {exc}" |
| any other `Exception` | classifier bug, unknown tool, SDK fault | deny, fail-closed |

The final catch-all matters: a broken classifier must produce a denial the model can
see, not silent passthrough.

## Wiring into ClaudeAgentOptions

```python
from claude_agent_sdk import ClaudeAgentOptions, HookMatcher, create_sdk_mcp_server

options = ClaudeAgentOptions(
    mcp_servers={"myserver": create_sdk_mcp_server(name="myserver", version="1.0.0",
                                                   tools=ALL_TOOLS)},
    # Pre-approve the MCP tools so the SDK doesn't double-prompt the user;
    # the RMACD hook is the authoritative gate.
    allowed_tools=["mcp__myserver__update_config", ...],
    system_prompt=build_system_prompt(profile) + "\n\n" + task_prompt,
    hooks={"PreToolUse": [HookMatcher(matcher="*", hooks=[pretool_hook])]},
)
```

Notes:

- `matcher="*"` routes every tool call through the hook — keep it that way; narrowing
  the matcher creates ungoverned paths.
- `allowed_tools` pre-approval avoids the SDK's own permission prompt stacking on top of
  RMACD approvals; RMACD remains the gate.
- The `CLIApprovalGateway` blocks the hook coroutine while the operator answers on the
  terminal — acceptable for interactive runs; production gateways should respect
  `ApprovalRequest.timeout_seconds` and return `TIMEOUT` rather than hang.
