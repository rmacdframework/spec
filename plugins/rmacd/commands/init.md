---
description: Scaffold RMACD governance for this project's AI agent
---

Scaffold RMACD governance for the agent in this project. Work through the steps below in
order. Consult the `rmacd-integrate` skill (and its `references/` files) for API details;
do not invent APIs that are not documented there.

## 1. Detect the agent stack

Grep the project's imports to identify which framework the agent uses:

- `claude_agent_sdk` → Claude Agent SDK (integrate via a `PreToolUse` hook)
- `anthropic` (without `claude_agent_sdk`) → raw Anthropic SDK (manual tool-use loop)
- `langchain` / `langchain_core` → LangChain (`@enforcer.guard` or callback handler)
- `autogen` / `crewai` / `agents` (OpenAI) → see the skill's `references/adapters.md`
- None of the above → generic dispatch-site pattern (`references/adapters.md`)

Also note which MCP servers the project configures (`.mcp.json`, `mcp_servers=` in code)
— they will need governance in step 5.

## 2. Install the SDK

Ensure the SDK is installed **into the project's virtual environment** (not globally):

```bash
pip install "rmacd-framework>=0.14"
```

The PyPI distribution is `rmacd-framework`; the import name is `rmacd`. Verify with
`python3 -c "import rmacd; print(rmacd.__version__)"`.

## 3. Ask the user for shape and role

Use AskUserQuestion to ask two questions:

1. **Deployment shape** — options: `3D` (default: operations × data classification ×
   autonomy), `2D` (operations × autonomy; no formal data classification program),
   `DC2D` (data classification × autonomy; operational permissions governed upstream
   by IAM/DLP).
2. **Role template** — options: `observer` (read-only), `devops`, `operations`,
   `administrator`, `regulated-data-handler` (DC2D only). Map the answer to the nearest
   example profile listed in the skill's `references/profiles.md`.

## 4. Create and validate the profile

Copy the nearest example profile from the spec repo's `schemas/examples/` (fetch from
https://github.com/rmacdframework/spec/tree/main/schemas/examples if not available
locally) to `./rmacd/profiles/<agent-name>.json`. Then:

- Set `profile_id` to match the shape's pattern: `^rmacd-3d-[a-z0-9-]+$`,
  `^rmacd-2d-[a-z0-9-]+$`, or `^rmacd-dc2d-[a-z0-9-]+$` (e.g. `rmacd-3d-myagent-v1`).
- Update `profile_name` and `description` to describe this agent.
- Trim `permissions` to what the agent actually needs — start narrow; permissions are
  cumulative (D ⊃ C ⊃ A ⊃ M ⊃ R), so granting Delete implies everything below it.
- Never grant `C` or `D` on `restricted` — the schema rejects it and the runtime floor
  (§12.5) blocks it regardless.
- Validate: `rmacd validate ./rmacd/profiles/<agent-name>.json` must print `VALID`.
- Show the effective matrix to the user: `rmacd matrix ./rmacd/profiles/<agent-name>.json`.

## 5. Build the tools registry and wire the enforcer

Build a registry that covers every tool the agent can call:

- For known tool families use built-in governance packs:
  `registry = load_packs(["shell", "github", ...])` (list built-ins with
  `python3 -c "from rmacd.packs import builtin_pack_names; print(builtin_pack_names())"`).
- For each MCP server the project uses, register its `tools/list` through
  `MCPRegistryBridge(registry=registry)` — see the skill's `references/packs.md` for the
  classify → review → sign flow for internal servers.
- For a Bash-style tool, register `make_bash_classifier()` (see `references/adapters.md`).

Then generate the enforcer wiring and the framework hook, adapting the skill's
`examples/pretool_hook.py` (Claude Agent SDK) or the matching adapter from
`references/adapters.md`. Unregistered tools are denied fail-closed, so make sure the
registry covers the full tool surface.

## 6. Smoke-test, then arm the real gateway

1. Dry-run decisions without side effects: `rmacd evaluate <profile> R -c internal`
   (repeat for the operations the agent needs), and/or `enforcer.evaluate_tool_call(...)`.
2. Run one scripted agent task with `approval_gateway=AutoApproveGateway()` to verify the
   enforcement path end-to-end (this auto-approves — never leave it in place).
3. Swap in `CLIApprovalGateway()` (interactive terminal approvals) or the team's own
   `ApprovalGateway` implementation. Warn the user: the enforcer's default gateway is
   `RejectAllApprovalGateway`, so approval-gated operations are denied until a real
   gateway is configured.
4. Print next steps for the user:
   - Bind the profile via environment for 12-factor deploys:
     `export RMACD_AGENT_ID=<agent-name>` and
     `export RMACD_PROFILE_PATH=./rmacd/profiles/<agent-name>.json`, then construct with
     `PolicyEnforcer.from_env()`.
   - Optionally set `RMACD_ENVIRONMENT` (e.g. `production`).
   - Add `build_system_prompt(profile)` output to the agent's system prompt so the model
     self-restricts.
   - Verify any time with the skill's `scripts/check_setup.sh`.
