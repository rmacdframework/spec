# RMACD ↔ Claude Agent SDK reference integration

> **Note (SDK 0.11.0):** this example hand-writes a classifier to show the full
> mechanics. New integrations can skip that code and get classification from
> **Governance Packs** — `registry=load_packs([...])` — see
> [`docs/governance-packs/`](../../docs/governance-packs/) and
> [`examples/governance-packs-quickstart/`](../governance-packs-quickstart/).
> The enforcement wiring (the `PreToolUse` hook) is unchanged.

A runnable end-to-end example showing an RMACD-governed agent built on the
[Claude Agent SDK for Python](https://github.com/anthropics/claude-agent-sdk-python).
Every tool the agent calls is intercepted by a Policy Enforcement Point that
consults an RMACD profile, routes approval-gated operations through a human
operator, and writes audit records matching the spec's Appendix C.6 format.

The [walkthrough](docs/walkthrough.md) maps each piece of code to the
runtime concern it addresses (profile binding, resource classification,
dynamic operation classification, approval-wait, error contract,
agent self-restriction).

## What you get

- A DevOps-style agent with seven custom tools (Read, Move, Add, Change, Delete).
- A custom RMACD profile (`profiles/devops-demo-3d.json`) that exercises all
  four data tiers and overrides four cells of the default governance matrix.
- A `PreToolUse` hook that funnels every tool call through `PolicyEnforcer`.
- A CLI `ApprovalGateway` that prompts you on stdin for approval-gated
  operations.
- A JSONL audit log written next to the demo (`audit.jsonl`).
- An agent system prompt that tells the model its own profile so it
  self-restricts.

## Prerequisites

- Python 3.10+
- The [Claude Agent SDK for Python](https://pypi.org/project/claude-agent-sdk/)
  installed (`pip install claude-agent-sdk`)
- The [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code/overview)
  available on `PATH` — the Agent SDK uses it as the LLM transport. Verify
  with `claude --version`.
- `ANTHROPIC_API_KEY` — either exported in your shell, **or** placed in
  `spec/.env` (the demo auto-loads the nearest `.env` walking up from the
  script). Copy `spec/.env.example` to `spec/.env` and fill in the key.
  `.env` is gitignored.

## Install

```bash
cd spec/examples/agent-integration-claude-sdk

# Option A: install from local SDK source (this repo)
pip install -e ../../sdk/python
pip install claude-agent-sdk

# Option B: from PyPI
pip install "rmacd-framework>=0.12.0" claude-agent-sdk
```

## Run

Default scripted task (lists fleet, updates a config that requires approval,
asks about decommissioning a Restricted vault that is prohibited):

```bash
python -m rmacd_demo.main
```

Custom task:

```bash
python -m rmacd_demo.main "Show me the fleet, then provision a new staging web server called web-stage-99."
```

When the agent hits an approval-gated operation you'll see a prompt like:

```
────────────────────────────────────────────────────────────────────────
  APPROVAL REQUIRED  (approval)
────────────────────────────────────────────────────────────────────────
  Request:   apr-9c14e7a2b1d04f80
  Agent:     devops-agent-demo
  Profile:   rmacd-3d-devops-demo-v1
  Operation: C  (Change)
  Target:    server://web-stage-01
  Data tier: internal
  Reason:    agent invoked update_config(server_id=web-stage-01, key=workers, value=8)
────────────────────────────────────────────────────────────────────────
  Approve? [y/N] (optional note after a space):
```

Type `y` to approve, `n` (or just Enter) to deny. The agent will react to
your answer and continue.

## What the agent should and shouldn't be able to do

Given the demo profile (`rmacd-3d-devops-demo-v1`):

| Operation | Target server | Tier | Expected outcome |
|---|---|---|---|
| `list_servers` | fleet | internal | Allowed (R is autonomous) |
| `read_audit_log` | ledger | confidential | Allowed but logged enhanced |
| `update_config` | web-stage-01 | internal | **Approval prompt** (Change/Internal override) |
| `update_config` | db-prod-01 | confidential | Elevated approval prompt |
| `provision_vm` (confidential) | new server | confidential | Elevated approval prompt |
| `decommission_server` | vault-prod-01 | restricted | **Denied — Delete on Restricted is Prohibited** |
| `decommission_server` | db-prod-01 | confidential | Denied — profile does not grant D on Confidential |

## Layout

```
.
├── README.md
├── pyproject.toml
├── profiles/
│   └── devops-demo-3d.json       # The agent's RMACD profile
├── rmacd_demo/
│   ├── __init__.py
│   ├── main.py                   # Entry point — wires everything together
│   ├── tools.py                  # @tool functions exposed to Claude
│   ├── infra.py                  # In-memory mock fleet
│   ├── classifier.py             # Tool call → (RMACD op, target, tier)
│   ├── hook.py                   # PreToolUse hook → PolicyEnforcer
│   └── system_prompt.md          # Agent system prompt (self-restriction)
├── docs/
│   └── walkthrough.md            # Spec-gap → code mapping
└── audit.jsonl                   # Created on first run
```

## How this maps to the RMACD spec

| Spec concept | This demo |
|---|---|
| Policy Decision Point (§C.1) | `rmacd.PolicyEvaluator` (inside `PolicyEnforcer`) |
| Policy Enforcement Point (§C.1) | `rmacd_demo.hook.make_pretool_hook` — the Claude Agent SDK `PreToolUse` hook |
| Policy Store (§C.1) | `profiles/devops-demo-3d.json` loaded by `ProfileLoader` |
| Audit Engine (§C.1) | `rmacd.audit.JSONLAuditLogger` writing to `audit.jsonl` |
| Runtime evaluation flow (§C.2) | `PolicyEnforcer.enforce()` |
| `@enforcer.guard` (§C.4) | Available on `PolicyEnforcer.guard` but unused here — the Agent SDK hook is the integration site instead |
| Approval request schema (§C.5) | `rmacd.approval.ApprovalRequest` |
| Audit record schema (§C.6) | `rmacd.audit.AuditRecord` |

See [docs/walkthrough.md](docs/walkthrough.md) for the gap-by-gap mapping.

## Adapting this to other frameworks

The integration surface is the PreToolUse hook in `hook.py`. To adapt:

- **LangChain**: wrap each tool with `@enforcer.guard(operation=..., classifier=...)`
  or write a custom `BaseCallbackHandler` that runs the same enforce-then-call
  logic in `on_tool_start`.
- **AutoGen**: register a `register_for_execution` middleware that calls
  `PolicyEnforcer.enforce()` before dispatching.
- **Anthropic SDK direct tool use**: intercept between receiving a `tool_use`
  block and dispatching to the local function — same pattern, no framework.

The SDK pieces (`PolicyEnforcer`, `ApprovalGateway`, `AuditLogger`, exception
hierarchy) are framework-agnostic.
