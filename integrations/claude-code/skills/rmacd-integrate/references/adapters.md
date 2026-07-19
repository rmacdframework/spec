# Framework adapters

Condensed from the canonical `docs/framework-adapters.md` in the spec repo
(https://github.com/rmacdframework/spec/blob/main/docs/framework-adapters.md) — go
there for full, copy-pasteable versions.

## The universal pattern

Every integration is the same four steps:

1. Build one shared `PolicyEnforcer` at agent startup (profile, gateway, audit logger,
   registry).
2. Find the **dispatch site** — the earliest point where the framework has the tool
   name *and* arguments but has not yet run the tool body.
3. Call `enforcer.enforce_tool_call(tool_name, args)` there (registry-backed,
   recommended) or `enforcer.enforce(operation, target, classification)` with a
   hand-written classifier.
4. Translate `RMACD*Error` exceptions into the framework's error shape (returned error
   result, raised exception, or callback rejection) so the model sees the denial and
   can adapt.

A reusable primitive:

```python
def enforce_or_explain(enforcer, tool_name: str, tool_args: dict) -> str | None:
    """Return None if allowed, or a user-facing denial message if blocked."""
    try:
        enforcer.enforce_tool_call(tool_name, tool_args)
        return None
    except Exception as exc:   # RMACD*Error subclasses; fail closed on anything else
        return f"RMACD: {exc}"
```

`enforcer.evaluate_tool_call(name, args)` is the dry run (no audit/approval/raise
except for unregistered tools) — use it wherever a framework asks "does this need
approval?" separately from "is this allowed?".

## Claude Agent SDK

`PreToolUse` hook — see `claude-hook.md` and `examples/pretool_hook.py` in this skill.

## OpenAI Agents SDK

Two complementary hooks:

- **Deny gate** — a `@tool_guardrail` function that calls `enforce_or_explain` and
  returns `ToolGuardrailFunctionOutput.reject_content(reason)` on denial,
  `.allow()` otherwise. This is the authoritative allow/deny.
- **Approval routing** — a `needs_approval` callable per tool returning
  `enforcer.evaluate_tool_call(tool_name, tool_parameters).requires_approval`
  (return `True` on any exception — fail safe). The SDK pauses the run; resolve with
  `RunState.approve()` / `RunState.reject()`. The callback signature
  `(run_context, tool_parameters, call_id)` carries no tool name, so bind the
  registered name per tool via a closure.

## Microsoft Agent Framework

A `FunctionMiddleware` in the agent's middleware pipeline:

```python
async def rmacd_middleware(context, next):
    reason = enforce_or_explain(enforcer, context.function.name, dict(context.arguments))
    if reason is not None:
        context.result = f"BLOCKED by RMACD: {reason}"   # short-circuit: no next()
        return
    await next(context)
```

Wire MAF's Tool Approval to fire when `evaluate_tool_call(...).requires_approval` is
true, mirroring the OpenAI pattern.

## LangChain

- **Option A (recommended): per-tool decorator.** Wrap the tool function (or a
  `BaseTool` subclass's `_run`) with `@enforcer.guard(operation=..., classifier=...)`.
  The classifier receives the call kwargs and returns `(target, classification)`. Then
  expose via `langchain_core.tools.tool(...)`. Runs no matter who invokes the tool.
- **Option B: `BaseCallbackHandler`.** Implement `on_tool_start`, parse `input_str`
  as JSON, call `enforce_or_explain`, and `raise RuntimeError(denial)` — LangChain
  surfaces it to the LLM as a tool error. Better for retrofitting third-party tool
  libraries you don't own.

## AutoGen (v0.4+)

Wrap the function-tool body with a decorator that calls `enforce_or_explain` and raises
`RuntimeError(denial)` before invoking the real function; register the wrapped function
with `FunctionTool` (or `register_for_llm` / `register_for_execution`). Handle both sync
and async bodies (`inspect.iscoroutinefunction`).

## CrewAI

Override `_run` on a shared `BaseTool` base class: classify, call `enforce_or_explain`,
and **return** the denial string (CrewAI feeds the return value to the LLM — a string is
friendlier than a raise); otherwise delegate to the real implementation. The `_run`
override covers agent-initiated, task-driven, and direct calls.

## Bash / shell tools

One tool, any command — use the SDK's shell classifier instead of a static level:

```python
from rmacd.registry import ToolDefinition, make_bash_classifier
from rmacd.models import Operation

registry.register_tool(ToolDefinition(
    "Bash", "Shell", Operation.CHANGE,        # nominal level for indexing
    classifier=make_bash_classifier(),        # unknown binaries → Change (fail closed)
))
enforcer.enforce_tool_call("Bash", {"command": "rm -rf build/"})   # → Delete
```

`classify_bash_command` parses pipes/`&&`/`;`, sub-shells, redirects, `sudo`, and
per-binary flag semantics (`sed -n` Read vs `sed -i` Change), returning the **maximum**
operation found. It resolves operation only (tier `None`) — natural fit for a 2D
profile; add a path→tier resolver for 3D. It is a governance heuristic, not a sandbox:
pair with OS-level controls.

## MCP servers

Auto-classify a server's `tools/list` into the enforcer's registry:

```python
from rmacd.registry import MCPRegistryBridge

bridge = MCPRegistryBridge(registry=registry)     # + llm_classifier= optionally
bridge.register_mcp_tools(tools_list_response["tools"])
for tool in bridge.low_confidence_tools():        # human-review queue
    print(tool.tool_id, tool.metadata["classification"])
```

Each auto-classified tool gets a capability ceiling capped at its inferred operation
and provenance metadata. LLM classification is advisory at registration time only —
runtime enforcement stays deterministic. Prefer a reviewed, signed governance pack for
internal servers (see `packs.md`).

## Generic dispatch site

For anything else (raw Anthropic SDK tool-use loop, OpenAI function calling, custom
loops): at the point where the decoded `tool_use` block is about to be dispatched, call
`enforce_or_explain`; on denial return it as the tool's error output (`is_error=True`
content or the framework's equivalent), otherwise dispatch normally. `enforce()` is
synchronous and fast — it only blocks while an approval gateway does real I/O; wrap
that gateway in a thread for async loops.
