# RMACD framework adapters

**Companion to:** `runtime-patterns.md` (this doc is the framework-specific
cookbook). Targets SDK ≥ 0.4.0.

Two reference integrations ship as full runnable examples:

- **Claude Agent SDK** — `spec/examples/agent-integration-claude-sdk/`
  — uses the SDK's `PreToolUse` hook as the enforcement point.
- **Raw Anthropic SDK** — `spec/examples/agent-integration-anthropic-sdk/`
  — uses a hand-rolled tool-use loop; the most portable template.

This doc shows how to wire `PolicyEnforcer` into three other widely-used
agent frameworks (LangChain, AutoGen, CrewAI) as concrete snippets you
can drop into your codebase. The RMACD-side wiring is identical across
all of them — what changes is *where* the enforcement call lands.

## Contents

- [The pattern](#the-pattern)
- [LangChain](#langchain)
- [AutoGen (v0.4+)](#autogen-v04)
- [CrewAI](#crewai)
- [Generic dispatch-site pattern](#generic-dispatch-site-pattern)

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
    RMACDApprovalTimeoutError,
    RMACDConstraintError,
    RMACDPermissionDeniedError,
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
    except RMACDApprovalTimeoutError as exc:
        return f"RMACD: approval for {op} on {target} timed out."
    except RMACDConstraintError as exc:
        return f"RMACD: constraint blocked operation: {exc}"
```

Every adapter below uses `enforce_or_explain` as its enforcement primitive.
The differences are purely in *how* each framework lets you intercept the
tool-dispatch point.

---

## LangChain

LangChain offers two viable hook surfaces. Pick based on whether you want
enforcement at the tool boundary (cleanest) or at the agent executor
boundary (broader visibility).

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

**Trade-off**: the decorator form is the cleaner integration (declared at
the tool, runs no matter who invokes it), while the callback handler is
better when you want to retrofit enforcement onto a third-party tool
library you don't own.

---

## AutoGen (v0.4+)

AutoGen 0.4 reorganized around `BaseChatAgent` and tool-calling
middlewares. The natural integration is a **function-call interceptor**:

```python
from typing import Any, Callable
from autogen_core.tools import FunctionTool


def rmacd_guarded(
    enforcer: PolicyEnforcer,
    operation: str,
    classifier: Callable[[dict[str, Any]], tuple[str, str | None]],
):
    """Decorator that wraps an AutoGen function-tool body with RMACD."""

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            target, tier = classifier(kwargs)
            denial = enforce_or_explain(
                enforcer,
                tool_name=fn.__name__,
                tool_args=kwargs,
            )
            if denial is not None:
                # AutoGen surfaces raised exceptions back to the model.
                raise RuntimeError(denial)
            return await fn(*args, **kwargs) if _is_async(fn) else fn(*args, **kwargs)

        return wrapper

    return decorator


import inspect

def _is_async(fn):
    return inspect.iscoroutinefunction(fn)


# Usage:
@rmacd_guarded(
    enforcer,
    operation="C",
    classifier=lambda kw: (f"server://{kw['server_id']}", "internal"),
)
async def update_config(*, server_id: str, key: str, value: str) -> str:
    ...


update_config_tool = FunctionTool(update_config, description="Update a config key.")
```

For AssistantAgent-style classes with `register_for_llm` /
`register_for_execution`, register the wrapped function rather than the
raw one. The interceptor runs at execution time, before the tool body.

---

## CrewAI

CrewAI tools subclass `BaseTool`. The integration point is the `_run`
method:

```python
from typing import Any
from crewai.tools import BaseTool


class RMACDGuardedTool(BaseTool):
    """Mix-in base that calls enforcer.enforce before the tool body runs.

    Subclasses provide ``_rmacd_classify`` (returns op/target/tier) and
    implement ``_run`` as usual; this base interposes the enforcement
    check.
    """

    enforcer: PolicyEnforcer  # set on the class or instance

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        op, target, tier = self._rmacd_classify(*args, **kwargs)
        denial = enforce_or_explain(self.enforcer, self.name, kwargs)
        if denial is not None:
            # CrewAI surfaces the return value to the LLM as the tool
            # result; an explicit string is friendlier than a raise.
            return denial
        return self._run_impl(*args, **kwargs)

    # Subclasses implement these:
    def _rmacd_classify(self, *args: Any, **kwargs: Any) -> tuple[str, str, str | None]:
        raise NotImplementedError

    def _run_impl(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError


class UpdateConfigTool(RMACDGuardedTool):
    name: str = "update_config"
    description: str = "..."
    enforcer: PolicyEnforcer = enforcer

    def _rmacd_classify(self, server_id: str, key: str, value: str):
        return ("C", f"server://{server_id}", "internal")

    def _run_impl(self, server_id: str, key: str, value: str) -> str:
        ...
```

The `_run` override ensures every CrewAI tool execution path
(including agent-initiated calls, task-driven calls, and direct calls)
goes through the enforcer.

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

## See also

- Full runnable references: `spec/examples/agent-integration-claude-sdk/`
  and `spec/examples/agent-integration-anthropic-sdk/`
- DC2D runtime: `runtime-patterns.md` §8 and `spec/examples/dc2d-customer-support/`
- SDK source: `spec/sdk/python/rmacd/`
