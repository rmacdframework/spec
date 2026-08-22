---
name: rmacd-integrate
description: This skill should be used when the user asks to "add RMACD to my agent", "govern agent tool calls", "enforce a policy profile", "integrate rmacd-framework", "create an RMACD profile", or wants governance, guardrails, or human-in-the-loop approval for an AI agent's tool use. Also trigger on mentions of RMACD operations (Read/Move/Add/Change/Delete), governance packs, PolicyEnforcer, enforce_tool_call, PICR data tiers (Public/Internal/Confidential/Restricted), autonomy levels, or approval gateways.
---

# Integrating RMACD governance into an agent

RMACD governs autonomous agents along three axes: **operations** (Read, Move, Add,
Change, Delete), **data classification** (Public, Internal, Confidential, Restricted —
"PICR"), and **autonomy** (autonomous → logged → notification → approval →
elevated_approval → prohibited). The `rmacd-framework` Python SDK enforces a JSON
**profile** at the agent's tool-call boundary: every call is classified into
`(operation, tier, target)` and checked before the tool body runs.

Follow the workflow below in order. Load a `references/` file only when its step
applies.

## Non-negotiable facts

Carry these into every integration; getting them wrong breaks governance:

- **Install name ≠ import name.** `pip install "rmacd-framework>=0.15"` but
  `import rmacd`. There is an unrelated `rmacd` distribution namespace — never
  `pip install rmacd`.
- **§12.5 immutable floor.** Add, Change and Delete on Restricted data are **prohibited for
  any autonomous agent**. This cannot be granted through the exception process, a
  profile, or an override — it is enforced twice: the profile-3d schema rejects it and
  the evaluator applies an immutable runtime floor even if a profile sneaks it in. Never
  attempt to work around it; tell the user those actions are human-execution-only.
- **Cumulative permissions: D ⊃ C ⊃ A ⊃ M ⊃ R.** Granting an operation grants everything
  below it. Grant the lowest verb that does the job.
- **Enforcement is deterministic.** LLM-assisted tool classification (the `[llm]` extra)
  is advisory input at registration/authoring time only. At runtime the decision is
  always the profile ∩ the tool's capability ceiling, with the §12.5 floor on top — no
  model in the loop.
- **The default approval gateway fails closed.** A `PolicyEnforcer` with no
  `approval_gateway=` uses `RejectAllApprovalGateway`: every approval-gated operation is
  denied. **On a first run, expect denials for anything above the autonomous/logged
  tiers — this is correct behaviour, not a bug.** Wire `CLIApprovalGateway()` for
  interactive runs or a custom `ApprovalGateway` for production.
- **Unregistered tools are denied.** `enforce_tool_call` fails closed on any tool the
  registry does not know. The registry must cover the agent's whole tool surface.
- **Profile IDs are validated** against `^rmacd-3d-[a-z0-9-]+$`, `^rmacd-2d-[a-z0-9-]+$`,
  or `^rmacd-dc2d-[a-z0-9-]+$`.

## Core workflow

### 1. Install

Install into the project's virtual environment:

```bash
pip install "rmacd-framework>=0.15"
python3 -c "import rmacd; print(rmacd.__version__)"
```

Optional extras: `[llm]` (Claude-assisted tool classification), `[yaml]` (YAML packs).

### 2. Create a profile

Pick a shape — **3D** by default; **2D** when the org has no data classification
program; **DC2D** when operational permissions are governed upstream by IAM/DLP and only
data-tier autonomy matters. Copy the nearest example from the spec repo's
`schemas/examples/`, set a compliant `profile_id`, trim permissions to need, then:

```bash
rmacd validate profiles/agent.json   # schema check — must print VALID
rmacd matrix profiles/agent.json     # show the effective autonomy matrix
```

Read `references/profiles.md` for the shape decision tree, the 8 example profiles, and
authoring invariants. The site Generator (https://rmacd-framework.org/generator) and
Validator (https://rmacd-framework.org/validator) do this interactively.

### 3. Build the tools registry

The registry maps each tool to RMACD terms and holds its capability ceiling. Prefer
governance packs over hand-registration:

```python
from rmacd.packs import load_packs
registry = load_packs(["shell", "github"])   # built-in packs → ready registry
```

For MCP servers, auto-classify their `tools/list` with `MCPRegistryBridge`; for Bash
tools, use `make_bash_classifier()`. Read `references/packs.md` for the built-in pack
list and the classify → review → sign flow for internal servers.

### 4. Wire the enforcer

```python
from rmacd import PolicyEnforcer, ProfileLoader, CLIApprovalGateway
from rmacd.audit import JSONLAuditLogger

enforcer = PolicyEnforcer(
    profile=ProfileLoader().load_file("profiles/agent.json"),
    agent_id="my-agent",
    approval_gateway=CLIApprovalGateway(),      # omit → RejectAll (fails closed)
    audit_logger=JSONLAuditLogger("audit.jsonl"),
    registry=registry,
)
```

For 12-factor deployments use `PolicyEnforcer.from_env()`, which reads
`RMACD_AGENT_ID`, `RMACD_PROFILE_PATH`, and optionally `RMACD_ENVIRONMENT`.

### 5. Gate the tool-dispatch site

Call `enforcer.enforce_tool_call(tool_name, args)` at the point where the framework has
the tool name and arguments but has not yet run the tool body. It classifies via the
registry, applies the capability ceiling and profile (plus §12.5 floor), routes
approvals through the gateway, writes audit records, and raises a typed
`RMACD*Error` on any non-allowed outcome. Map each exception to the framework's error
shape so the model can adapt instead of retrying blindly.

- Claude Agent SDK: a `PreToolUse` hook — copy `examples/pretool_hook.py` and read
  `references/claude-hook.md` for the payload contract and MCP name-prefix handling.
- OpenAI Agents, Microsoft Agent Framework, LangChain, AutoGen, CrewAI, or a custom
  loop: read `references/adapters.md`.

`enforcer.evaluate_tool_call(...)` is the side-effect-free dry run (no audit, no
approval) for "would this be allowed?" surfaces.

### 6. Tell the model its limits

Generate a self-restriction fragment from the live profile and prepend it to the
agent's system prompt, so the model does not waste turns proposing prohibited actions:

```python
from rmacd import build_system_prompt
fragment = build_system_prompt(profile)
```

### 7. Verify

Run `scripts/check_setup.sh` (in this skill) to confirm: `rmacd` imports, version
≥ 0.15, the profile validates, and env vars are bound. Then smoke-test with
`rmacd evaluate profiles/agent.json C -c internal` and one scripted agent task using
`AutoApproveGateway()` (test-only — swap it out immediately after).

## Quick reference: default 3D autonomy matrix

Autonomy applied when a granted `(operation, tier)` cell has no profile override:

| Tier \ Op | R | M | A | C | D |
|---|---|---|---|---|---|
| Public | autonomous | autonomous | notification | approval | approval |
| Internal | autonomous | notification | approval | approval | elevated |
| Confidential | logged | approval | elevated | elevated | elevated |
| Restricted | notification | elevated | **PROHIBITED** | **PROHIBITED** | **PROHIBITED** |

> **Warning (§12.5):** the Restricted-row prohibitions — Add, Change and Delete — are
> hard safety boundaries. No profile, override, emergency escalation, or exception
> request can lift Add/Change/Delete on Restricted for an autonomous agent. Surface
> `RMACDProhibitedError` to the user as "a human must do this directly".

Exception types to handle: `RMACDProhibitedError` (hard stop),
`RMACDPermissionDeniedError` (profile gap — an exception request is possible),
`RMACDToolCapabilityError` (tool ceiling), `RMACDApprovalDeniedError` /
`RMACDApprovalTimeoutError` (human said no / never answered), `RMACDConstraintError`
(env/time-window/quota).

## Claude Code session governance (requires rmacd-framework>=0.15)

To govern a Claude Code session itself (rather than an agent the user is building),
the SDK ships a session hook, `python3 -m rmacd.claude_code.hook`, and this plugin's
`/rmacd:status` command reports the bound profile. Both require `rmacd-framework>=0.15`;
do not reference them if an older SDK is installed.

## Resources

- `references/claude-hook.md` — Claude Agent SDK PreToolUse contract, MCP prefix
  stripping, exception→deny mapping.
- `references/adapters.md` — OpenAI Agents, MS Agent Framework, LangChain, AutoGen,
  CrewAI, generic dispatch-site pattern.
- `references/profiles.md` — shape decision tree, example profiles, authoring
  invariants, CLI checks.
- `references/packs.md` — built-in governance packs, `load_packs`, signing workflow.
- `examples/pretool_hook.py` — runnable PreToolUse hook adapted from the reference
  integration.
- `scripts/check_setup.sh` — setup verification with actionable failures.
- Canonical docs: https://github.com/rmacdframework/spec (`docs/RMACD_Framework_v1.4.md`,
  `docs/framework-adapters.md`, `docs/runtime-patterns.md`, `docs/implementation.md`).
