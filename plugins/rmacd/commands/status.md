---
description: Show the RMACD governance status of this Claude Code session
allowed-tools: Bash("${RMACD_PYTHON:-python3}" -m rmacd.claude_code.status:*), Bash(python3 -m rmacd.claude_code.status:*)
---

Report the RMACD governance status of the current session.

## 1. Run the status renderer

```bash
"${RMACD_PYTHON:-python3}" -m rmacd.claude_code.status
```

Run it with exactly that expansion — **not** a bare `python3`. The plugin's hooks are
invoked as `"${RMACD_PYTHON:-python3}"`, so this is the only spelling that reports the
state of the interpreter actually governing the session. A bare `python3` will report a
different environment whenever `RMACD_PYTHON` is set (the usual case when the SDK lives
in a project venv), and can claim the session is ungoverned while it is governed, or
clean while the hook is denying every call.

Show the user its output verbatim (profile id, shape, effective autonomy matrix, bound
packs, classification map, audit sink, and how approvals/unknown tools are routed).

## 2. If the command fails

- **`ModuleNotFoundError: No module named 'rmacd'`** — the `rmacd-framework` SDK is not
  importable by this interpreter. Explain that the plugin ships stdlib-only hook shims
  and that all governance logic lives in the SDK ("thin plugin, fat SDK"):

  ```bash
  pip install "rmacd-framework>=0.14"
  ```

  The PyPI distribution is `rmacd-framework`; the import name is `rmacd` (never
  `pip install rmacd`). What happens meanwhile depends on whether a profile is bound:

  - **A profile is bound** (`RMACD_PROFILE_PATH` or `.claude/rmacd-profile.json`) — the
    PreToolUse shim fails **closed**: every tool call in the session is DENIED with a
    reason naming the interpreter that could not import the SDK. SessionStart says so
    once at the top of the session. This is the intended behaviour — a bound session
    never runs ungoverned. Fix it by installing the SDK, or by setting `RMACD_PYTHON`
    to the interpreter that already has it (e.g. a project venv's `python3`).
  - **No profile is bound** — the session passes through untouched and silently. An
    unconfigured session is a deliberate zero-friction passthrough; someone who
    installed the plugin without opting into governance is not blocked by it.
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
  what will prompt for approval via "ask", and that Add/Change/Delete on restricted is
  prohibited by the §12.5 immutable floor — no exception process can grant it).
- **BOUND BUT BROKEN** — the hook is denying all tool calls (fail-closed). Help the
  user fix the reported cause, or unbind and restart the session.
