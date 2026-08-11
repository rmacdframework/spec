# RMACD framework adapters

**Companion to:** `runtime-patterns.md` — this doc is the framework-specific
cookbook.

**Current release:** `rmacd-framework` 0.14.1
(`pip install "rmacd-framework>=0.14"`; the import name is `rmacd`).

### Version requirements

| Feature | Minimum SDK |
|---------|-------------|
| Registry-backed `enforce_tool_call` / `evaluate_tool_call`, `ToolCapability` | 0.8.0 |
| MCP tool auto-classification (`MCPRegistryBridge`, `llm_classifier=`) | 0.10.0 |
| Governance Packs (`rmacd.packs`, `load_packs`) | 0.11.0 |
| RMACD as an MCP policy server (`rmacd mcp-serve`, `[mcp]` extra) | 0.13.0 |

Everything else in this doc — `PolicyEnforcer`, `enforce`, `@guard`, and the
exception hierarchy — predates 0.8.0, except `RMACDToolCapabilityError`, which
arrived with the registry in 0.8.0.

### Runnable examples

Four reference integrations ship as full runnable examples:

| Example | What it demonstrates |
|---------|----------------------|
| `spec/examples/agent-integration-claude-sdk/` | Claude Agent SDK agent governed at the SDK's `PreToolUse` hook |
| `spec/examples/agent-integration-anthropic-sdk/` | Hand-rolled tool-use loop on the raw `anthropic` SDK — the most portable template |
| `spec/examples/governance-packs-quickstart/` | Building the enforcer's registry from built-in packs (`load_packs`), plus pack compile and sign/verify |
| `spec/examples/dc2d-customer-support/` | DC2D redaction and egress controls (no LLM, no network) |

This doc shows how to wire `PolicyEnforcer` into five other widely-used agent
frameworks (OpenAI Agents SDK, Microsoft Agent Framework, LangChain, AutoGen,
CrewAI) as concrete snippets you can drop into your codebase. The RMACD-side
wiring is identical across all of them — what changes is *where* the
enforcement call lands.

> **Use Governance Packs to skip the classifier code.** Every snippet below
> that hand-writes a classifier or `classifier=` lambda can instead get its
> tool classification from a **governance pack** (`rmacd.packs`, SDK ≥ 0.11.0).
> Build the enforcer's registry once with `load_packs([...])` and the
> per-framework wiring reduces to "call `enforce_tool_call` at the dispatch
> site" — no classification code at all:
>
> ```python
> from rmacd import PolicyEnforcer
> from rmacd.packs import load_packs
>
> enforcer = PolicyEnforcer(
>     profile, agent_id="agent-1",
>     registry=load_packs(["aws", "kubectl", "github", "sql", "jira"]),
> )
> # ...then in any framework's tool hook/middleware/callback:
> enforcer.enforce_tool_call(tool_name, tool_args)
> ```
>
> The same pack governs a LangChain, OpenAI, Claude, or AutoGen agent
> identically. See `docs/governance-packs/`. The classifier snippets below
> remain valid for bespoke tools not covered by a pack.

## Contents

- [Enforcement points at a glance](#enforcement-points-at-a-glance)
- [The pattern](#the-pattern)
- [Exceptions to handle](#exceptions-to-handle)
- [Registry-backed enforcement (recommended)](#registry-backed-enforcement-recommended)
- [OpenAI Agents SDK](#openai-agents-sdk)
- [Microsoft Agent Framework](#microsoft-agent-framework)
- [LangChain](#langchain)
- [AutoGen (v0.4+)](#autogen-v04)
- [CrewAI](#crewai)
- [Generic dispatch-site pattern](#generic-dispatch-site-pattern)
- [RMACD as an MCP server](#rmacd-as-an-mcp-server)

---

## Enforcement points at a glance

The RMACD-side wiring never changes; only the interception seam does. Pick the
row for your framework and jump to that section.

| Framework | Where the enforcement call lands | Mechanism for a denial |
|-----------|----------------------------------|------------------------|
| Claude Agent SDK | The SDK's `PreToolUse` hook | Hook returns a deny decision; the tool body never runs |
| Raw Anthropic SDK | Your own tool-use loop, between decoding a `tool_use` block and invoking the handler | Return a `tool_result` with `is_error=True` |
| OpenAI Agents SDK | Tool guardrail (`@tool_guardrail`), plus `needs_approval` for HITL routing | `ToolGuardrailFunctionOutput.reject_content(reason)`; approvals pause the run |
| Microsoft Agent Framework | `FunctionMiddleware` in the agent (or chat-client) pipeline | Short-circuit: set `context.result` and never call `next()` |
| LangChain (A) | `@enforcer.guard` on the tool function or `BaseTool._run` | The decorator raises an `RMACD*Error` |
| LangChain (B) | `BaseCallbackHandler.on_tool_start` | Raise; the executor surfaces it as a tool error |
| AutoGen (v0.4+) | Decorator wrapping the `FunctionTool` body | Raise; AutoGen surfaces it back to the model |
| CrewAI | `BaseTool._run` override | Return the denial string as the tool result |
| Anything else | The dispatch site — earliest point where name + args are known and the body has not run | Whatever error shape the framework expects |

Common to every row:

- One shared `PolicyEnforcer`, built once at agent startup.
- One classification source — a governance pack, the tools registry, or a
  hand-written `classify` function.
- One call: `enforce_tool_call(...)` (registry-backed) or `enforce(...)`.

---

## The pattern

Every framework integration follows the same four steps:

1. **Build a shared `PolicyEnforcer`** at agent startup (with the profile,
   approval gateway, audit logger).
2. **Define a classifier** that turns the framework's "we're about to
   call tool X with arguments Y" event into `(operation, target, classification)`.
3. **Call `enforcer.enforce()`** at the framework's tool-dispatch site —
   the earliest point at which both the tool name and arguments are
   known and the underlying tool body has *not yet* run.
4. **Translate exceptions** into the framework's expected error shape
   (a returned error result, an exception type the framework recognizes,
   or a callback rejection).

```python
# Imports common to every adapter
from rmacd import (
    PolicyEnforcer,
    ProfileLoader,
    RMACDApprovalDeniedError,
    RMACDApprovalRequiredError,
    RMACDApprovalTimeoutError,
    RMACDConstraintError,
    RMACDPermissionDeniedError,
    RMACDPolicyError,
    RMACDProhibitedError,
)

# Shared classifier (lives in your code, not the SDK)
def classify(tool_name: str, tool_args: dict) -> tuple[str, str, str | None]:
    """Return (operation, target, classification) for a tool call."""
    ...


def enforce_or_explain(enforcer: PolicyEnforcer, tool_name: str, tool_args: dict) -> str | None:
    """Return None if allowed, or a user-facing denial message if blocked."""
    op, target, tier = classify(tool_name, tool_args)
    try:
        enforcer.enforce(operation=op, target=target, classification=tier)
        return None
    except RMACDProhibitedError as exc:
        return f"RMACD: {op} on {tier} is prohibited by the autonomy matrix. {exc}"
    except RMACDPermissionDeniedError as exc:
        return f"RMACD: profile does not grant {op} on {tier}. {exc}"
    except RMACDApprovalDeniedError as exc:
        return f"RMACD: approver denied {op} on {target}. {exc}"
    except RMACDApprovalTimeoutError:
        return f"RMACD: approval for {op} on {target} timed out."
    except RMACDApprovalRequiredError as exc:
        # Approval-gated but no ApprovalGateway wired up — a deployment bug,
        # not an agent decision. Fail closed and make it loud.
        return f"RMACD: approval required but no gateway is configured. {exc}"
    except RMACDConstraintError as exc:
        return f"RMACD: constraint blocked operation: {exc}"
    except RMACDPolicyError as exc:  # any future policy failure: fail closed
        return f"RMACD: blocked. {exc}"
```

Every adapter below uses `enforce_or_explain(enforcer, tool_name, tool_args)`
as its enforcement primitive — same signature everywhere. The differences are
purely in *how* each framework lets you intercept the tool-dispatch point.

---

## Exceptions to handle

All of these derive from `RMACDPolicyError` (itself an `RMACDError`), and all
carry the underlying `PolicyDecision` on `.decision`, so a single
`except RMACDPolicyError` is a safe fail-closed catch-all — the individual
types exist so a call site can render *why*.

| Exception | Raised when | What it means for the caller |
|-----------|-------------|------------------------------|
| `RMACDPermissionDeniedError` | The agent's profile does not grant this (operation, tier). Also raised by `enforce_tool_call` / `evaluate_tool_call` for an **unregistered tool** (fail-closed) | Profile-scoped: a broader profile could do this |
| `RMACDProhibitedError` | The autonomy matrix marks the combination Prohibited — including the §12.5 immutable floor (no Add/Change/Delete on Restricted) | No agent may do this autonomously; a human must |
| `RMACDToolCapabilityError` | The *tool's own* capability ceiling forbids the resolved (operation, tier). `enforce_tool_call` only, independent of the profile | This tool may never represent that operation |
| `RMACDConstraintError` | An environment, time-window, or quota/rate constraint blocked the call | Possibly retryable later or in another environment |
| `RMACDApprovalRequiredError` | Approval is required but no `ApprovalGateway` was configured — or the gateway itself raised | Deployment bug: wire a gateway. Never a silent allow |
| `RMACDApprovalDeniedError` | The human approver said no. Extra attributes: `approver`, `note` | Final denial for this call |
| `RMACDApprovalTimeoutError` | The approval request went unanswered. Extra attribute: `timeout_seconds` | Treat as a denial; optionally re-request |
| `RMACDEgressBlockedError` | A DC2D `egress_controls` rule blocked the destination (raised by callers of `check_egress`) | The **data flow** was blocked, not the tool call; inspect `destination`, `tier`, `matched_rule` (`.decision` is `None` here) |

`RMACDToolCapabilityError` is not in the `enforce_or_explain` above because
that version calls `enforce()`; the registry-backed version below can raise it,
which is one more reason its handler is a catch-all.

---

## Registry-backed enforcement (recommended)

Hand-writing a `classify` lambda per integration is the drift-prone part. The
**tools registry** is the first-class home for that mapping. Register each tool
once with:

- its RMACD **operation** (the static default, `rmacd_level`);
- an optional **dynamic classifier** — `args → (operation, tier, target)`, any
  element of which may be `None` to fall back to the static value;
- an optional **capability ceiling** (`ToolCapability`) — what this tool may
  *ever* do, regardless of who calls it.

Then call the single method `enforcer.enforce_tool_call(tool_name, args)`. It
resolves the call through the registry and enforces **profile ∩ tool
capability** with the §12.5 safety floor — no per-site `classify`/`enforce`
glue.

```python
from rmacd import PolicyEnforcer, ProfileLoader
from rmacd.registry import ToolsRegistry, ToolDefinition, ToolCapability
from rmacd.models import Operation

registry = ToolsRegistry("my-agent")
registry.register_tool(ToolDefinition(
    "update_config", "Update Config", Operation.CHANGE,
    # dynamic: prod resources resolve to Confidential, others Internal
    classifier=lambda args: (
        "C",
        "confidential" if str(args.get("server_id", "")).startswith("prod-") else "internal",
        f"server://{args.get('server_id')}",
    ),
    capability=ToolCapability(operations={Operation.CHANGE}),  # may never delete
))

enforcer = PolicyEnforcer(
    profile=ProfileLoader().load_file("profiles/agent.json"),
    agent_id="agent-1",
    registry=registry,
)

def enforce_or_explain(enforcer: PolicyEnforcer, tool_name: str, tool_args: dict) -> str | None:
    """Return None if allowed, or a denial message if blocked.

    Drop-in replacement for the classifier-based version above: same
    signature, so every adapter below is unchanged.
    """
    try:
        enforcer.enforce_tool_call(tool_name, tool_args)
        return None
    except Exception as exc:  # RMACD*Error subclasses; fail closed on anything else
        return f"RMACD: {exc}"
```

Two related surfaces:

- `enforcer.enforce_tool_call(tool_name, args)` — the enforcing call: audits,
  routes approvals, raises on denial, returns the `PolicyDecision` on allow.
- `enforcer.evaluate_tool_call(tool_name, args)` — the side-effect-free dry run
  (no audit, no approval, no raise except for an unregistered tool). Returns
  the `PolicyDecision` the call *would* get; used by the OpenAI
  `needs_approval` callback below.

### Classifying `bash` commands

`bash` is the hard case: one tool, any command. `make_bash_classifier()` parses
the command line and returns the **maximum** RMACD operation across everything
it finds, failing closed (`default=Operation.CHANGE`) on an unrecognised binary.

What it parses:

- binary and subcommand (`git log` vs `git push`);
- flags, scoped **per binary** — `pico -v` (view) is not treated like
  `cp -v` / `rm -v` (verbose);
- composition: pipes, `&&`, `;`, `sudo`, `$(...)`, process substitution `<(...)`;
- redirects — a `>` makes any command at least a Change;
- shell control keywords, so `for f in *; do rm "$f"; done` classifies as the
  Delete it is, rather than as an unknown `do`.

Switch-level distinctions it honours:

| Command | Operation | Why |
|---------|-----------|-----|
| `sed -n …` / `sed -i …` | Read / Change | `-i` edits in place |
| `pico` `nano` `vim` | Change | An editor invocation mutates by default |
| `pico -v` / `vim -R` | Read | Explicit view / read-only mode |
| `nslookup` / `nsupdate` | Read / Change | Query vs. DNS record update |
| any `--help`, `--version`, `--dry-run` | Read | Print-and-exit or simulate |

```python
from rmacd.registry import ToolsRegistry, ToolDefinition, make_bash_classifier
from rmacd.models import Operation

registry.register_tool(ToolDefinition(
    "Bash", "Shell", Operation.CHANGE,          # nominal level (for indexing)
    classifier=make_bash_classifier(),          # default=Change for unknowns
))
enforcer.enforce_tool_call("Bash", {"command": "rm -rf build/"})   # → Delete
enforcer.enforce_tool_call("Bash", {"command": "git log"})         # → Read
```

The classifier resolves an **operation** only — a shell command has no inherent
data tier, so it returns `tier=None` and pairs naturally with a **2D profile**
(operations × autonomy). For 3D governance, layer a path→resource resolver to
supply the tier. The classifier is a governance/audit heuristic, **not** a
sandbox — pair it with OS-level controls.

### Auto-classifying MCP tools (SDK ≥ 0.10.0)

When the agent's tools come from an MCP server, you don't hand-register them —
`MCPRegistryBridge` classifies each `tools/list` entry and registers it into
the same registry the enforcer consults, with a capability ceiling at the
inferred operation and provenance recorded in `metadata["classification"]`:

```python
from rmacd.registry import MCPRegistryBridge
from rmacd.registry.llm import LLMToolClassifier   # optional: rmacd-framework[llm]

bridge = MCPRegistryBridge(
    registry=registry,                  # the enforcer's registry
    llm_classifier=LLMToolClassifier(), # optional; reads ANTHROPIC_API_KEY
    llm_mode="fallback",                # LLM only when the keyword heuristic is unsure
)
bridge.register_mcp_tools(tools_list_response["tools"])   # raw MCP dicts OK

# Human-review queue: tools neither engine classified with confidence
for tool in bridge.low_confidence_tools():
    print(tool.tool_id, tool.metadata["classification"])
```

After this, `enforcer.enforce_tool_call(name, args)` governs MCP tool calls
exactly like hand-registered ones. The LLM classification is advisory input —
enforcement stays deterministic (§12.5 floor, profile, capability ceiling).

---

## OpenAI Agents SDK

Two complementary hooks:

- **Tool guardrail** — the synchronous deny gate, and the authoritative
  allow/deny.
- **`needs_approval`** — maps an RMACD `approval` / `elevated_approval`
  decision onto the SDK's built-in human-in-the-loop pause
  (`RunState.approve()` / `RunState.reject()`).

```python
from agents import function_tool
from agents.guardrail import tool_guardrail, ToolGuardrailFunctionOutput

# 1) Deny gate — reject the call before the tool body runs.
@tool_guardrail
def rmacd_guardrail(context, tool, args) -> ToolGuardrailFunctionOutput:
    reason = enforce_or_explain(enforcer, tool.name, args)
    if reason is not None:
        return ToolGuardrailFunctionOutput.reject_content(reason)   # model sees the denial
    return ToolGuardrailFunctionOutput.allow()

# 2) Approval routing — pause the run for HITL when RMACD says approval-gated.
#    The callback signature is (run_context, tool_parameters, call_id) with no
#    tool name, so bind the registered name per tool.
def rmacd_needs_approval(tool_name: str):
    def _needs_approval(run_context, tool_parameters, call_id) -> bool:
        try:
            return enforcer.evaluate_tool_call(tool_name, tool_parameters).requires_approval
        except Exception:
            return True  # fail safe: unknown/blocked → require a human
    return _needs_approval

@function_tool(needs_approval=rmacd_needs_approval("update_config"), tool_guardrails=[rmacd_guardrail])
def update_config(server_id: str, key: str, value: str) -> str:
    ...
```

The guardrail is the authoritative allow/deny; `needs_approval` only governs
*how* an approval-gated allow is surfaced (the SDK interrupts the run and you
resolve it with `RunState.approve()` / `RunState.reject()`).

---

## Microsoft Agent Framework

Gate every function invocation with a `FunctionMiddleware` in the agent's
middleware pipeline — the same seam the Agent Governance Toolkit's
`.UseGovernance()` uses, so RMACD can be the policy it evaluates.

```python
from agent_framework import FunctionInvocationContext  # MAF function middleware context

async def rmacd_middleware(context: FunctionInvocationContext, next):
    reason = enforce_or_explain(enforcer, context.function.name, dict(context.arguments))
    if reason is not None:
        # Short-circuit: don't call next() — the tool body never runs.
        context.result = f"BLOCKED by RMACD: {reason}"
        return
    await next(context)  # allowed → proceed to the function invocation

# Register on the agent (or the chat client) pipeline:
agent = chat_client.create_agent(
    instructions=system_prompt,
    tools=[update_config, decommission_server],
    middleware=[rmacd_middleware],
)
```

For human-in-the-loop, MAF's Tool Approval pauses the invocation for a decision
— wire it to fire when `enforcer.evaluate_tool_call(...).requires_approval` is
true, mirroring the OpenAI `needs_approval` pattern above.

---

## LangChain

LangChain offers two viable hook surfaces:

- **Option A — per-tool decorator.** Enforcement at the tool boundary. Cleanest;
  declared where the tool is defined, so it runs no matter who invokes it.
- **Option B — `BaseCallbackHandler`.** Enforcement at the agent-executor
  boundary. Broader visibility; the way to retrofit enforcement onto a
  third-party tool library you don't own.

### Option A: per-tool decorator (recommended)

The `@enforcer.guard` decorator wraps any callable. For LangChain tools
defined as plain functions or `BaseTool` subclasses, the wrap site is the
function or the `_run` method:

```python
from langchain_core.tools import tool

@enforcer.guard(
    operation="C",
    classifier=lambda *, server_id, **_: (f"server://{server_id}", "internal"),
)
def _update_config_impl(*, server_id: str, key: str, value: str) -> str:
    # actual work here
    ...

# Expose to LangChain
update_config_tool = tool(_update_config_impl)
```

For class-based tools, decorate `_run`:

```python
from langchain_core.tools import BaseTool

class UpdateConfigTool(BaseTool):
    name = "update_config"
    description = "..."

    @enforcer.guard(
        operation="C",
        classifier=lambda *, server_id, **_: (f"server://{server_id}", "internal"),
    )
    def _run(self, *, server_id: str, key: str, value: str) -> str:
        ...
```

### Option B: `BaseCallbackHandler` (cross-cutting)

For a centralized intercept site that covers every tool in the agent:

```python
from typing import Any
from langchain_core.callbacks.base import BaseCallbackHandler


class RMACDCallbackHandler(BaseCallbackHandler):
    def __init__(self, enforcer: PolicyEnforcer):
        self.enforcer = enforcer

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        **kwargs: Any,
    ) -> None:
        tool_name = serialized.get("name", "")
        # input_str is JSON for most tool kinds; parse if needed:
        import json
        try:
            tool_args = json.loads(input_str)
        except (json.JSONDecodeError, TypeError):
            tool_args = {"_raw": input_str}

        denial = enforce_or_explain(self.enforcer, tool_name, tool_args)
        if denial is not None:
            # Raise a plain exception — LangChain's executor will surface
            # it back to the LLM as a tool error on the next turn.
            raise RuntimeError(denial)


# Wire into the agent executor:
agent_executor.callbacks = [RMACDCallbackHandler(enforcer)]
```

**Trade-off**: the decorator declares policy at the tool and cannot be bypassed
by another call path; the callback handler covers tools you cannot edit, at the
cost of being wired on the executor (and therefore skippable if someone builds
a second executor without it).

---

## AutoGen (v0.4+)

AutoGen 0.4 reorganized around `BaseChatAgent` and tool-calling
middlewares. The natural integration is a **function-call interceptor**:

```python
import functools
import inspect
from typing import Any, Callable

from autogen_core.tools import FunctionTool


def rmacd_guarded(enforcer: PolicyEnforcer):
    """Decorator that wraps an AutoGen function-tool body with RMACD.

    Classification comes from the registry/pack (or the shared ``classify``),
    keyed on the tool name — so the decorator needs no per-tool arguments.
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            denial = enforce_or_explain(enforcer, fn.__name__, kwargs)
            if denial is not None:
                # AutoGen surfaces raised exceptions back to the model.
                raise RuntimeError(denial)
            return await fn(*args, **kwargs)

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            denial = enforce_or_explain(enforcer, fn.__name__, kwargs)
            if denial is not None:
                raise RuntimeError(denial)
            return fn(*args, **kwargs)

        return async_wrapper if inspect.iscoroutinefunction(fn) else sync_wrapper

    return decorator


# Usage:
@rmacd_guarded(enforcer)
async def update_config(*, server_id: str, key: str, value: str) -> str:
    ...


update_config_tool = FunctionTool(update_config, description="Update a config key.")
```

Notes:

- An `async def` tool needs an `async def` wrapper. A plain `def` wrapper only
  returns the coroutine, so enforcement would still run before the body — but
  any wrapper that also *records* the outcome would record it before the tool
  had run. `enforcer.guard` makes the same split internally.
- For AssistantAgent-style classes with `register_for_llm` /
  `register_for_execution`, register the **wrapped** function rather than the
  raw one. The interceptor runs at execution time, before the tool body.

---

## CrewAI

CrewAI tools subclass `BaseTool`. The integration point is the `_run`
method:

```python
from typing import Any
from crewai.tools import BaseTool


class RMACDGuardedTool(BaseTool):
    """Mix-in base that enforces RMACD before the tool body runs.

    Subclasses implement ``_run_impl`` instead of ``_run``; this base
    interposes the enforcement check. Classification is resolved from the
    tool name by the registry/pack (or the shared ``classify``), so
    subclasses declare no policy of their own.
    """

    enforcer: PolicyEnforcer  # set on the class or instance

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        denial = enforce_or_explain(self.enforcer, self.name, kwargs)
        if denial is not None:
            # CrewAI surfaces the return value to the LLM as the tool
            # result; an explicit string is friendlier than a raise.
            return denial
        return self._run_impl(*args, **kwargs)

    # Subclasses implement this:
    def _run_impl(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError


class UpdateConfigTool(RMACDGuardedTool):
    name: str = "update_config"
    description: str = "..."
    enforcer: PolicyEnforcer = enforcer

    def _run_impl(self, server_id: str, key: str, value: str) -> str:
        ...
```

Why `_run` is the right seam: it is the single execution path every CrewAI
invocation goes through — agent-initiated calls, task-driven calls, and direct
calls alike — so there is no route to the tool body that skips the enforcer.

One binding rule: `self.name` must match the tool's registry/pack `tool_id`
(which the registry normalizes to lower case with spaces as underscores). That
string is the join between the CrewAI tool and its RMACD classification; an
unregistered name fails closed with `RMACDPermissionDeniedError`, whose message
is returned to the model as the tool result.

---

## Generic dispatch-site pattern

For any framework not listed above, the integration follows the same
shape:

```python
# 1) Identify the dispatch site.
#    This is the function the framework calls when it has decoded a
#    tool_use block from the LLM and is about to invoke the local
#    handler. Examples:
#    - Anthropic SDK direct: between receiving content[i].type == "tool_use"
#      and calling the local function
#    - OpenAI SDK with function-calling: between parsing the function_call
#      block and dispatching to the local function
#    - Any custom agent loop: before the line that runs the tool body

# 2) At that site, call enforce_or_explain:
denial = enforce_or_explain(enforcer, tool_name, tool_args)
if denial is not None:
    # Return the denial as if it were the tool's output, with whatever
    # error indicator the framework expects (is_error=True content, raised
    # exception, error return code, etc.).
    return _make_tool_error(denial)

# 3) Otherwise dispatch as usual:
return run_local_handler(tool_name, tool_args)
```

If the framework's dispatch site is asynchronous, the same pattern applies
inside an `async def` wrapper — `enforcer.enforce()` is synchronous but
fast (it only becomes slow when an approval gateway is doing real I/O,
in which case wrap that gateway in a thread or replace it with an async
one).

---

## RMACD as an MCP server

Every adapter above runs the SDK in-process. When the agent is not Python —
or you want policy queries available to any MCP client (Claude Code, Claude
Desktop, a TypeScript agent) — run RMACD as a standard MCP server instead
(SDK ≥ 0.13.0, `[mcp]` extra):

```bash
pip install 'rmacd-framework[mcp]'
rmacd mcp-serve                          # clients pass profile_path per call
rmacd mcp-serve --profile ops-3d.json    # enterprise mode: profile pinned
```

Client configuration (`.mcp.json` for Claude Code, or the equivalent
`mcpServers` block in Claude Desktop):

```json
{"mcpServers": {"rmacd": {"command": "rmacd", "args": ["mcp-serve"]}}}
```

The server (name `rmacd`, stdio transport) exposes six **read-only** tools:

| Tool | Purpose |
|------|---------|
| `rmacd_evaluate` | Policy decision for (operation, target, classification, environment) — the same `PolicyEvaluator.evaluate` code path that `PolicyEnforcer.evaluate_only` wraps |
| `rmacd_validate_profile` | Schema-validate a profile file or JSON string → `{valid, errors[]}` |
| `rmacd_matrix` | Effective autonomy matrix (same data as `rmacd matrix`) |
| `rmacd_list_packs` | Built-in governance packs: names, versions, rule counts |
| `rmacd_pack_info` | One pack's metadata, rule count, and signature status |
| `rmacd_classify_bash` | Advisory RMACD classification of a shell command line |

Design notes:

- **Read-only by construction.** The server never mutates state, never runs
  approval gateways, and never writes audit records — enforcement (approvals,
  audit sinks) stays an in-process pattern per the adapters above. The §12.5
  immutable floor applies to every decision it returns.
- **Pinning is authoritative.** With `--profile`, per-call `profile_path`
  arguments to the decision-bearing tools (`rmacd_evaluate`, `rmacd_matrix`)
  are **rejected with a clear error** (not silently ignored), so a client can
  neither swap profiles nor believe it did. `rmacd_validate_profile` still
  lints arbitrary documents — validation confers no policy authority.
- **Advisory classification.** `rmacd_classify_bash` is the deterministic
  keyword heuristic from `rmacd.registry.bash`; like all classification it is
  advisory input — the bound profile and the §12.5 floor decide.
- **The extra is optional and lazily imported.** Without it, `rmacd mcp-serve`
  prints the `pip install 'rmacd-framework[mcp]'` hint and the rest of the
  SDK/CLI is unaffected. The extra resolves `mcp>=1.0,<2`: the server targets
  the 1.x FastMCP API, and `mcp` 2.0.0 removed `mcp.server.fastmcp`.

Other optional extras, for reference:

| Extra | Enables |
|-------|---------|
| `[llm]` | `LLMToolClassifier` (`anthropic`) — advisory classification at registration time |
| `[mcp]` | `rmacd mcp-serve`, the read-only MCP policy server |
| `[sign]` | Governance-pack signing and verification (`sign_pack` / `verify_pack`) |
| `[yaml]` | Reading and writing governance packs authored as YAML |
| `[dev]` | Test/lint toolchain for working on the SDK itself |

---

## See also

- Governing a **Claude Code session itself** (PreToolUse hook, `/rmacd:status`,
  managed-settings rollout): `claude-code.md`
- Governance packs — authoring, composition, signing: `docs/governance-packs/`
- Full runnable references: `spec/examples/agent-integration-claude-sdk/`,
  `spec/examples/agent-integration-anthropic-sdk/`, and
  `spec/examples/governance-packs-quickstart/`
- DC2D runtime: `runtime-patterns.md` §8 and `spec/examples/dc2d-customer-support/`
- Audit evidence produced by these integrations: `audit-evidence.md`
- SDK source: `spec/sdk/python/rmacd/`
