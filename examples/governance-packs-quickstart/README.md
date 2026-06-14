# Governance Packs quickstart

A self-contained, no-network demo of the SDK 0.11.0 `rmacd.packs` workflow:

1. **Build an enforcer's registry from built-in packs in one line**
   (`load_packs(["shell", "aws", "kubectl", "github", "sql", "jira"])`) — no
   hand-written classifier code.
2. **Enforce real tool calls** — allowed, denied, and a restricted-delete that
   the §12.5 immutable floor blocks.
3. **AI-compile a pack** for a new MCP server (keyword engine, no API key) and
   list the rules that warrant human review.
4. **Sign + verify** the pack (if the optional `[sign]` extra is installed).

## Run

```bash
pip install rmacd-framework          # core
pip install rmacd-framework[sign]    # optional: enables the sign/verify step
python demo.py
```

## What it shows

- The *same* packs govern any agent framework — the enforcement call
  (`enforce_tool_call`) is the only integration point.
- Classification is **data**: built-in packs load by name; you author new ones
  with `rmacd classify` / `rmacd pack sign`.
- Runtime stays deterministic — packs only produce `(operation, tier, target)`;
  the §12.5 floor, the agent profile, and the tool capability ceiling still gate.

See [`docs/governance-packs/`](../../docs/governance-packs/) for the full design,
roadmap, and authoring guide.

> Built-in packs are **AI-drafted starting points** — review and sign them
> before relying on them in production.
