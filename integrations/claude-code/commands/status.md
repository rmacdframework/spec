---
description: Show the RMACD governance status of this Claude Code session
allowed-tools: Bash(python3 -m rmacd.claude_code.status:*)
---

Report the RMACD governance status of the current session.

## 1. Run the status renderer

```bash
python3 -m rmacd.claude_code.status
```

Show the user its output verbatim (profile id, shape, effective autonomy matrix, bound
packs, classification map, and how approvals/unknown tools are routed).

## 2. If the command fails

- **`ModuleNotFoundError: No module named 'rmacd'`** — the `rmacd-framework` SDK is not
  installed in the Python environment this session uses. Explain that the plugin is
  markdown + a hook config only ("thin plugin, fat SDK") and the session hook cannot
  govern anything until the SDK is installed:

  ```bash
  pip install "rmacd-framework>=0.13"
  ```

  The PyPI distribution is `rmacd-framework`; the import name is `rmacd` (never
  `pip install rmacd`). While the SDK is missing, the PreToolUse hook command fails and
  Claude Code treats a failed hook as a non-blocking error — the session is
  **ungoverned**, not broken.
- **Any other error** — show the error and suggest re-running after fixing it; if a
  profile is configured (`RMACD_PROFILE_PATH` or `.claude/rmacd-profile.json`), warn
  that the session hook is failing closed (denying tool calls) until it is fixed.

## 3. Interpret the state for the user

- **UNBOUND** — RMACD is installed but no profile is bound; tool calls pass through to
  Claude Code's normal permission flow. Offer `/rmacd:init` to scaffold a profile, or
  binding an existing one via `RMACD_PROFILE_PATH=/path/to/profile.json` or
  `.claude/rmacd-profile.json` in the project root. Hooks load at session start, so a
  new binding takes effect after restarting Claude Code.
- **BOUND** — summarise the matrix in one or two sentences (what runs autonomously,
  what will prompt for approval via "ask", and that Change/Delete on restricted is
  prohibited by the §12.5 immutable floor — no exception process can grant it).
- **BOUND BUT BROKEN** — the hook is denying all tool calls (fail-closed). Help the
  user fix the reported cause, or unbind and restart the session.
