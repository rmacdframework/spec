# RMACD plugin for Claude Code

Zero-to-governed in one session: this plugin teaches Claude Code how to integrate the
[RMACD Framework](https://rmacd-framework.org) into your AI agent, and scaffolds the
integration for you.

RMACD governs autonomous agents along three axes — **operations** (Read, Move, Add,
Change, Delete), **data classification** (Public / Internal / Confidential /
Restricted), and **autonomy** (autonomous through prohibited). The
[`rmacd-framework`](https://pypi.org/project/rmacd-framework/) Python SDK (import name:
`rmacd`) enforces a JSON policy profile at the agent's tool-call boundary.

## Install

```
/plugin marketplace add rmacdframework/spec
/plugin install rmacd@rmacd-framework
```

Or, for local development from a checkout of this repo:

```bash
claude --plugin-dir plugins/rmacd
```

The plugin ships markdown and reference material only; all executable logic lives in
the pip-installed SDK: `pip install "rmacd-framework>=0.13"`.

## What's inside

- **`/rmacd:init`** — scaffolds RMACD governance for the agent in the current project:
  detects the agent stack, installs the SDK, asks for a deployment shape (3D / 2D /
  DC2D) and role template, creates and validates a policy profile, builds the tools
  registry from governance packs, generates the enforcement hook, and smoke-tests the
  wiring.
- **`/rmacd:bug-setup`** — scaffolds label-gated GitHub bug automation into your repo:
  a bug-report issue form, a Claude triage + owner-gated auto-fix workflow, and an
  auto-review workflow for `fix/**` PRs — then walks you through the one-time token,
  app, and settings setup and a dummy-issue test run.
- **`rmacd-integrate` skill** — activates automatically when you ask Claude to "add
  RMACD to my agent", "govern agent tool calls", "enforce a policy profile", and the
  like. Carries the core workflow plus focused references:
  - `references/claude-hook.md` — Claude Agent SDK `PreToolUse` contract
  - `references/adapters.md` — OpenAI Agents, MS Agent Framework, LangChain, AutoGen,
    CrewAI, generic dispatch-site
  - `references/profiles.md` — profile authoring: shapes, examples, invariants
  - `references/packs.md` — governance packs and the classify → review → sign flow
  - `examples/pretool_hook.py` — runnable PreToolUse hook
  - `scripts/check_setup.sh` — verifies an integration end-to-end
- **`rmacd-bug-automation` skill** — activates when you ask to "set up bug automation",
  "auto-fix bugs from GitHub issues", or similar. Explains the label-gated flow (triage
  on `bug`, fix only on an owner-applied `claude-fix` label, human review as the RMACD
  Approval gate), carries the three workflow/form templates in `examples/`, and
  condenses the verified claude-code-action v1 facts in
  `references/claude-code-action.md`.

## Requirements

- Python 3.10+ with `rmacd-framework>=0.13` installed in the target project
  (`/rmacd:init` handles this).
- No API keys required by the plugin itself; the optional LLM-assisted pack authoring
  (`rmacd classify --llm`) reads `ANTHROPIC_API_KEY`.

## Links

- Specification and SDK source: https://github.com/rmacdframework/spec
- Website, profile generator and validator: https://rmacd-framework.org
- PyPI: https://pypi.org/project/rmacd-framework/

License: CC BY 4.0.
