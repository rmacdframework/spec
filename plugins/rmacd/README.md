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

The plugin ships markdown, reference material, and three small stdlib-only hook shims;
all governance logic lives in the pip-installed SDK:
`pip install "rmacd-framework>=0.14"`. The shims are deliberately dependency-free so
they still work in the one case that matters — when the SDK itself cannot be imported.

## What's inside

### Session governance (hooks)

Once a profile is bound, the plugin governs **this Claude Code session's own** tool
calls, not just agents you build. Bind one with `RMACD_PROFILE_PATH` or
`.claude/rmacd-profile.json` in the project root, then restart the session.

- **`SessionStart`** — states the governance posture once, up front: active (with the
  profile source), unbound, or configured-but-broken.
- **`PreToolUse`** — classifies every call into `(operation, tier, target)` and
  evaluates it against the profile: `allow`, `deny`, or `ask` (Claude Code's own
  permission prompt is the human-in-the-loop step for approval-level autonomy).
  Records the decision — including denials, which never reach `PostToolUse`.
- **`PostToolUse`** — records the execution outcome, joined to its decision by
  `tool_use_id`, in `.claude/rmacd-audit.jsonl` beside the profile.

Fail modes: an **unbound** session is a zero-friction passthrough. A **bound** session
fails **closed** — if the profile is broken, the event is malformed, or the SDK cannot
be imported, tool calls are denied rather than run ungoverned. Set `RMACD_PYTHON` to
point the hooks at the interpreter that has the SDK (e.g. a project venv).

### Commands and skills

- **`/rmacd:status`** — reports the session's governance state: bound profile and
  shape, the effective autonomy matrix, bound packs, classification map, audit sink,
  and how approvals and unknown tools are routed.
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

- Python 3.10+ with `rmacd-framework>=0.14` installed in the interpreter the hooks run
  (`${RMACD_PYTHON:-python3}`) and in the target project (`/rmacd:init` handles the
  latter).
- No API keys required by the plugin itself; the optional LLM-assisted pack authoring
  (`rmacd classify --llm`) reads `ANTHROPIC_API_KEY`.

## Links

- Specification and SDK source: https://github.com/rmacdframework/spec
- Session governance reference (binding order, env vars, tool mapping, audit format):
  [`docs/claude-code.md`](https://github.com/rmacdframework/spec/blob/main/docs/claude-code.md)
- Website, profile generator and validator: https://rmacd-framework.org
- PyPI: https://pypi.org/project/rmacd-framework/

License: CC BY 4.0.
