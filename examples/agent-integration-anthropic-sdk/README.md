# RMACD ↔ raw Anthropic SDK reference integration

> **Note (SDK 0.11.0):** this example hand-writes a classifier to show the full
> mechanics. New integrations can skip that code and get classification from
> **Governance Packs** — `registry=load_packs([...])` — see
> [`docs/governance-packs/`](../../docs/governance-packs/) and
> [`examples/governance-packs-quickstart/`](../governance-packs-quickstart/).
> The enforcement wiring (the tool-use dispatch loop) is unchanged.

The same RMACD enforcement pattern as the Claude Agent SDK example, but
without any framework — just the `anthropic` Python SDK and a hand-rolled
tool-use loop. The integration point is between receiving a `tool_use`
block from the API and dispatching to the local handler.

Many production agents are built directly on the Anthropic SDK rather
than on a framework, and the pattern shown here is the lowest common
denominator for any framework integration (LangChain, AutoGen, CrewAI
all end in a tool-dispatch site). That site is where
`PolicyEnforcer.enforce()` goes.

## What you get

- A DevOps-style agent with the same seven tools as the Claude Agent SDK
  example, built directly on `anthropic.Anthropic().messages.create(...)`.
- A manual multi-turn tool-use loop (capped at 8 turns).
- Prompt caching of the system prompt so the loop doesn't re-bill input
  tokens on every iteration.
- The same JSONL audit log and CLI approval gateway as the other examples.

## Prerequisites

- Python 3.10+
- `pip install anthropic` and `pip install -e ../../sdk/python`
- `ANTHROPIC_API_KEY` — either exported in your shell, **or** placed in
  `spec/.env` (the demo auto-loads the nearest `.env` walking up from the
  script). Copy `spec/.env.example` to `spec/.env` and fill in the key.
  `.env` is gitignored.

## Run

```bash
cd spec/examples/agent-integration-anthropic-sdk
python agent.py
# or with a custom task:
python agent.py "Show me the fleet, then try to read the audit log."
```

Default model is `claude-haiku-4-5` (fast, cheap). Override with
`--model claude-sonnet-4-6` or set `RMACD_DEMO_MODEL` for better
reasoning about denials.

## The integration point

The whole RMACD integration fits in one function (`dispatch_tool` in
`agent.py`):

```python
def dispatch_tool(enforcer, name, args):
    # 1) Classify: what RMACD op is this, on what target, at what tier?
    cls = classify_tool_call(name, args)
    # 2) Enforce: returns on allow, raises on deny.
    try:
        enforcer.enforce(operation=cls.operation, target=cls.target, classification=cls.classification)
    except RMACDProhibitedError as exc:
        return f"RMACD: ... prohibited ...", True
    except RMACDPermissionDeniedError as exc:
        return f"RMACD: ... profile gap ...", True
    # ... other subclasses ...
    # 3) Allowed — run the tool body.
    return _run_tool_body(name, args), False
```

The loop wraps each `tool_use` block in this function, then turns the
return value into a `tool_result` content block with `is_error=True` on
denial. The LLM sees the denial as a normal failed-tool error and can
adapt.

## How this differs from the Claude Agent SDK example

| Concern | Claude Agent SDK example | This example |
|---|---|---|
| Tool definition | `@tool` decorator + `create_sdk_mcp_server` | Plain Python dicts in `TOOLS` list |
| Enforcement site | `PreToolUse` hook returning `permissionDecision` | `dispatch_tool` in the loop, returning `tool_result` content |
| Loop management | SDK handles `ClaudeSDKClient.receive_response()` | Hand-rolled `while response.stop_reason == "tool_use"` |
| Lines of agent code | ~80 | ~150 |
| Best for | Existing Claude Agent SDK deployments | Custom agents built directly on the Anthropic SDK |

The RMACD-side wiring (profile, enforcer, gateway, audit, classifier,
exception handling) is identical — only the dispatch surface differs.

## Layout

```
.
├── README.md
├── profiles/
│   └── devops-demo-3d.json    # Copy of the Claude Agent SDK example's profile
├── agent.py                   # Entry point: TOOLS list + dispatch_tool + run_agent loop
├── infra.py                   # Mock fleet (shared pattern with the Claude Agent SDK example)
├── classifier.py              # (tool_name, args) → (op, target, tier) — flat-layout variant
├── cli_gateway.py             # CLI ApprovalGateway (same as the other example)
├── system_prompt.md           # Self-restriction prompt
└── audit.jsonl                # Written on first run
```

## See also

- The Claude Agent SDK example: `../agent-integration-claude-sdk/`
- The DC2D runtime demo: `../dc2d-customer-support/`
- Runtime patterns reference: `../../docs/runtime-patterns.md`
- SDK source: `../../sdk/python/rmacd/`
