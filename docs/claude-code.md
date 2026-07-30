# RMACD session governance for Claude Code

**Requires `rmacd-framework` ≥ 0.13.0** (`pip install "rmacd-framework>=0.13"`;
the import name is `rmacd`).

The `rmacd.claude_code` module makes RMACD govern a **Claude Code session
itself** — not an agent the user is building, but the session's own tool calls
(Bash, Write/Edit, Read/Glob/Grep, WebFetch, and any `mcp__<server>__<tool>`).
A `PreToolUse` command hook classifies every call into RMACD terms and
evaluates it against a bound profile before the tool runs:

```
Claude Code ──PreToolUse JSON on stdin──▶ python3 -m rmacd.claude_code.hook
                                              │  bind profile + packs
                                              │  map tool → (operation, tier, target)
                                              │  evaluate (profile ∩ ceiling, §12.5 floor)
Claude Code ◀──hook JSON on stdout────────────┘  allow / deny / ask
```

Enforcement is deterministic — no LLM, no network, no approval-gateway I/O in
the hook path — so a governed call adds only the Python process spawn plus a
few milliseconds of evaluation.

## Setup (developer)

1. Install the plugin (skills, `/rmacd:init`, `/rmacd:status`, and the hook
   configuration):

   ```
   /plugin marketplace add rmacdframework/spec
   /plugin install rmacd@rmacd-framework
   ```

2. Install the SDK into the Python environment the session's `python3`
   resolves to:

   ```bash
   pip install "rmacd-framework>=0.13"
   ```

3. Bind a profile (either mechanism; env var wins):

   ```bash
   export RMACD_PROFILE_PATH=/path/to/profile.json
   # or, per project:
   cp schemas/examples/devops-3d.json .claude/rmacd-profile.json
   ```

   `/rmacd:init` scaffolds and validates a profile interactively. Hooks load
   at session start — restart Claude Code after binding.

4. Verify with `/rmacd:status` (or `python3 -m rmacd.claude_code.status`).

Sessions without a bound profile are zero-friction: the hook emits no
decision, Claude Code's normal permission flow continues unchanged, and a
one-time notice ("RMACD installed but unbound") is written to stderr, which
Claude Code only surfaces in `--debug`.

## Enterprise rollout (managed settings)

Platform teams can enforce the hook org-wide without the plugin by adding the
equivalent hook to managed settings
(`/etc/claude-code/managed-settings.json` on Linux,
`/Library/Application Support/ClaudeCode/managed-settings.json` on macOS),
which users cannot override:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {"type": "command", "command": "python3 -m rmacd.claude_code.hook", "timeout": 30}
        ]
      }
    ]
  },
  "env": {
    "RMACD_PROFILE_PATH": "/etc/rmacd/claude-code-profile.json",
    "RMACD_CLASSIFICATION_MAP": "/etc/rmacd/classification-map.json"
  }
}
```

Notes for managed deployments:

- Distribute the SDK in the base image / bootstrap (`pip install
  "rmacd-framework>=0.13"`). If the SDK is missing the hook command fails and
  Claude Code treats it as a **non-blocking** error — pair the managed hook
  with configuration management that asserts the package is present.
- The profile file itself should be root-owned/read-only; a bound-but-broken
  configuration fails closed (all tool calls denied), so broken rollouts are
  loud, not silent.
- Approval-level autonomy surfaces as Claude Code's own permission prompt
  (`permissionDecision: "ask"`); no separate approval gateway is needed for
  the interactive session case.

## Profile binding order

First hit wins:

1. `RMACD_PROFILE_PATH`.
2. `.claude/rmacd-profile.json` in the session's current working directory,
   then in each parent directory — **nearest wins**, so a subproject may bind
   a stricter profile than its repository root.
3. `$CLAUDE_PROJECT_DIR/.claude/rmacd-profile.json`, covering a session whose
   cwd has moved outside the project tree.
4. Otherwise the session is unbound (passthrough).

The upward walk matters. Claude Code reports the session's *current* directory
on every hook event, so before 0.14.0 — when only the cwd itself was probed —
a governed project became silently ungoverned the moment the agent worked from
a subdirectory. If you are pinning a profile for a fleet, prefer
`RMACD_PROFILE_PATH` via managed settings: it is unambiguous and independent of
where the session happens to be working.

## Environment variables

| Variable | Meaning | Default |
|----------|---------|---------|
| `RMACD_PROFILE_PATH` | Profile JSON to bind (overrides the project file) | unset → search for `.claude/rmacd-profile.json` (see *Profile binding order* below), else unbound |
| `RMACD_PACKS` | Extra governance packs, comma-separated built-in names or file paths, merged onto the defaults | unset |
| `RMACD_CLASSIFICATION_MAP` | Path-glob → tier map: inline JSON (`{"/data/secret/*": "restricted"}`) or a path to a JSON file of that shape | unset |
| `RMACD_DEFAULT_TIER` | Tier assumed for targets no map rule matches (3D/DC2D evaluation requires a tier) | `internal` |
| `RMACD_UNKNOWN_TOOL` | `deny` or `ask` for tools the registry cannot govern | `deny` |
| `RMACD_AGENT_ID` | Identity attached to the session's decisions | `claude-code` |
| `RMACD_ENVIRONMENT` | Deployment environment fed to profile constraints (`development`/`staging`/`production`/...) | unset |

The registry always contains the built-in `shell` and `filesystem` packs;
`RMACD_PACKS` adds more (list the available built-ins with
`python3 -c "from rmacd.packs import builtin_pack_names; print(builtin_pack_names())"`).

Classification-map semantics: `fnmatch` globs; a `/dir/*` pattern also covers
`/dir` itself (so `rm -rf /dir` is classified as strictly as its contents);
when several patterns match, the **most sensitive** tier wins.

Targets are matched in every normalized form as well as verbatim, so a rule
cannot be sidestepped by spelling the same path differently — `/data/secret`,
`/data/../data/secret`, `./secret` (against the session cwd), `~/…` and
`//data//secret` all match a `/data/secret/*` rule. Patterns themselves are
`~`-expanded at load, so `{"~/.ssh/*": "restricted"}` works. Path arguments
nested inside `sh -c "…"` / `bash -c "…"` payloads are extracted too (to a
depth of 4), so a wrapped command cannot hide its target from the map. Before
0.14.0 each of these evaded the map and fell back to `RMACD_DEFAULT_TIER`,
which downgraded §12.5 denials to approval prompts.

## How tool calls are mapped

| Claude Code tool | RMACD mapping |
|------------------|---------------|
| `Bash` | `classify_bash_command()` on the command line (max operation across pipelines/sub-shells; unknown binaries fail closed to Change); the classification map is applied to the command's path-like tokens |
| `Write` / `Edit` / `MultiEdit` / `NotebookEdit` | Add if the path does not exist yet, Change if it does; target = path |
| `Read` / `Glob` / `Grep` / `NotebookRead` | Read |
| `WebFetch` / `WebSearch` | Read; on DC2D profiles the destination is additionally checked against `egress_controls` |
| `mcp__<server>__<tool>` | Prefix stripped, resolved via the session registry (packs); the tool's capability ceiling gates first, then the profile |
| Session-internal tools (Task, TodoWrite, AskUserQuestion, ...) | Read on `public` (they orchestrate the session, not external data) |
| Anything else | Ungovernable → `RMACD_UNKNOWN_TOOL` fail mode |

## Decision output contract

- **allow** → `{"hookSpecificOutput": {"hookEventName": "PreToolUse",
  "permissionDecision": "allow"}}`
- **deny** → `permissionDecision: "deny"` with a `permissionDecisionReason`
  citing operation, tier, rule, and profile id, e.g.:

  > RMACD: Delete on restricted target '/etc/passwd' is prohibited (§12.5
  > immutable floor — cannot be granted by exception; human execution only).
  > Profile: rmacd-3d-devops-v1.

- **approval-level autonomy** (`approval` / `elevated_approval`) →
  `permissionDecision: "ask"` — Claude Code's own permission prompt is the
  human-in-the-loop step. The hook never invokes an `ApprovalGateway`: the
  hook process is short-lived and has no interactive stdin, so decisions are
  computed side-effect-free (`evaluate_only` semantics) and the approval is
  delegated to the Claude Code prompt.

The hook always exits 0; decisions travel in the stdout JSON. An *unbound*
session produces **no output at all** — deliberately not
`permissionDecision: "allow"`, which would suppress Claude Code's own
permission prompts and auto-approve everything. "Unbound" must mean
"ungoverned", never "wide open".

## Fail modes (normative)

| State | Behavior |
|-------|----------|
| No profile bound | Passthrough (no decision emitted; Claude Code's own permission flow unchanged); one-time stderr notice "RMACD installed but unbound" per session |
| Profile bound, hook errors | **Fail closed** — deny with a diagnostic reason (covers invalid profile/pack/map, malformed stdin, and unexpected exceptions) |
| Profile bound, unknown MCP tool | Deny by default; `RMACD_UNKNOWN_TOOL=ask` routes it to the user's approval instead |
| SDK missing (plugin without pip install), profile bound | **Fail closed** — the plugin's stdlib-only wrapper denies every tool call and names the profile source, the interpreter, and the install command. A `SessionStart` notice says so once, up front |
| SDK missing, no profile bound | Passthrough. An unbound session is an explicit zero-friction passthrough; installing the plugin without configuring it must not block anything |

Stderr is safe in all cases: with exit code 0 Claude Code reads only stdout
for the JSON decision and shows stderr only in `--debug` mode.

## Worked example

Bind the DevOps example profile and mark a path restricted:

```bash
export RMACD_PROFILE_PATH=$PWD/schemas/examples/devops-3d.json
export RMACD_CLASSIFICATION_MAP='{"/data/secret/*": "restricted"}'
```

| Session action | Decision |
|----------------|----------|
| `ls -la` | allow (Read on internal → autonomous) |
| `git push origin main` | **ask** (Change on internal → `approval` via the profile's `internal.C` override) |
| `rm -rf /data/secret` | **deny** — "Delete on restricted target '/data/secret' is prohibited (§12.5 immutable floor — cannot be granted by exception; human execution only)" |

Note that `devops-3d.json` also carries `time_windows` constraints
(Mon–Fri 06:00–22:00 America/New_York): outside that window *every* operation
is denied with a constraint reason — working as designed for a
change-controlled profile. Trim the `constraints` block if you don't want
that behaviour for interactive sessions.

## See also

- `docs/framework-adapters.md` — governing agents you *build* (Claude Agent
  SDK, OpenAI, LangChain, ...), as opposed to the session you work in.
- `plugins/rmacd/` — the plugin (skill, `/rmacd:init`,
  `/rmacd:status`, hook wiring).
- SDK sources: `sdk/python/rmacd/claude_code/` (`hook.py`, `mapping.py`,
  `session.py`, `status.py`).
