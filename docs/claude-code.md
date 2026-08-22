# RMACD session governance for Claude Code

**Requires `rmacd-framework` ≥ 0.14.0** (`pip install "rmacd-framework>=0.14"`;
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

The plugin wires three hooks, all invoked as `"${RMACD_PYTHON:-python3}"`:

| Hook | Script | Job |
|------|--------|-----|
| `SessionStart` | `hooks/rmacd_session_start.py` | States the governance posture once: active (with the profile source), unbound, or configured-but-broken |
| `PreToolUse` | `hooks/rmacd_guard.py` → `rmacd.claude_code.hook` | Classifies and decides: `allow` / `deny` / `ask`; records the decision |
| `PostToolUse` | `hooks/rmacd_post.py` → `rmacd.claude_code.post_hook` | Records the execution outcome; emits no permission decision |

Only `PreToolUse` can change what runs. The other two report.

## Setup (developer)

1. Install the plugin (skills, `/rmacd:init`, `/rmacd:status`, and the hook
   configuration):

   ```
   /plugin marketplace add rmacdframework/spec
   /plugin install rmacd@rmacd-framework
   ```

2. Install the SDK into the interpreter the hooks actually run. Every hook is
   invoked as `"${RMACD_PYTHON:-python3}"`, so that is either the `python3` on
   `PATH` or whatever `RMACD_PYTHON` names:

   ```bash
   pip install "rmacd-framework>=0.14"
   # or, when the SDK lives in a project venv:
   export RMACD_PYTHON=/path/to/.venv/bin/python3
   ```

3. Bind a profile (either mechanism; env var wins):

   ```bash
   export RMACD_PROFILE_PATH=/path/to/profile.json
   # or, per project:
   cp schemas/examples/devops-3d.json .claude/rmacd-profile.json
   ```

   `/rmacd:init` scaffolds and validates a profile interactively. Hooks load
   at session start — restart Claude Code after binding.

4. Verify with `/rmacd:status` (or
   `"${RMACD_PYTHON:-python3}" -m rmacd.claude_code.status` — the same
   expansion the hooks use, so the diagnostic reports the environment that
   actually governs the session rather than a different one).

Sessions without a bound profile are zero-friction: the hook emits no
decision, Claude Code's normal permission flow continues unchanged, a
one-time notice ("RMACD installed but unbound") goes to stderr, and neither
hook imports the SDK at all (see *Unbound sessions take a fast path*).

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
    ],
    "PostToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {"type": "command", "command": "python3 -m rmacd.claude_code.post_hook", "timeout": 30}
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

`PreToolUse` is the enforcement half and is sufficient on its own;
`PostToolUse` adds the execution half of the audit trail (see *Audit trail*).

Notes for managed deployments:

- **Distribute the SDK in the base image / bootstrap** (`pip install
  "rmacd-framework>=0.14"`) and pair the managed hook with configuration
  management that asserts the package is present. The module entry points above
  are the SDK itself: if it cannot be imported, the process exits non-zero,
  which Claude Code treats as a *non-blocking* error, and the call runs
  ungoverned. The fail-closed behaviour for a missing SDK lives in the plugin's
  stdlib-only shims, not in the module — so either install the plugin as well,
  or distribute `hooks/rmacd_guard.py` and `hooks/rmacd_post.py` (stdlib-only,
  and `rmacd_post.py` imports `rmacd_guard` from its own directory) and point
  the managed commands at those instead.
- **The managed command names the interpreter.** `RMACD_PYTHON` only takes
  effect where the command expands it (`"${RMACD_PYTHON:-python3}" …`, as the
  plugin's `hooks.json` does); a literal `python3` above must itself be the
  interpreter that has the SDK.
- **Make the profile root-owned/read-only.** A bound-but-broken configuration
  fails closed (all tool calls denied), so broken rollouts are loud, not
  silent.
- **No approval gateway is needed for interactive sessions.** Approval-level
  autonomy surfaces as Claude Code's own permission prompt
  (`permissionDecision: "ask"`).

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
| `RMACD_PYTHON` | Interpreter the plugin's hooks run under — every hook in `hooks.json` is invoked as `"${RMACD_PYTHON:-python3}"`. Set it to the `python3` that has the SDK (typically a project venv) | `python3` from `PATH` |
| `RMACD_PROFILE_PATH` | Profile JSON to bind (overrides the project file) | unset → search for `.claude/rmacd-profile.json` (see *Profile binding order* above), else unbound |
| `RMACD_PACKS` | Extra governance packs, comma-separated built-in names or file paths, merged onto the defaults | unset |
| `RMACD_CLASSIFICATION_MAP` | Path-glob → tier map: inline JSON (`{"/data/secret/*": "restricted"}`) or a path to a JSON file of that shape | unset |
| `RMACD_DEFAULT_TIER` | Tier assumed for targets no map rule matches (3D/DC2D evaluation requires a tier). `restricted` is **refused at binding**: the value is asserted as the classification of unmapped targets, not used as a floor, so it would place every Add/Change/Delete on them under the §12.5 immutable floor — prohibited outright and not grantable by any approver or exception. Classify restricted targets explicitly instead. | `internal` |
| `RMACD_UNKNOWN_TOOL` | `deny` or `ask` for tools the registry cannot govern; any other value falls back to `deny` rather than erroring | `deny` |
| `RMACD_AGENT_ID` | Identity attached to the session's decisions | `claude-code` |
| `RMACD_ENVIRONMENT` | Deployment environment fed to profile constraints (`development`/`staging`/`production`/...) | unset |

`RMACD_PYTHON` is the odd one out: it is read by the **plugin**, not by the
SDK. It is a shell expansion in the plugin's `hooks.json` (and in
`/rmacd:status`, so the diagnostic reports the same environment the hooks run
in) — nothing inside `rmacd` ever looks at it. Every other variable in the
table is read by the SDK at bind time. Two more, `RMACD_AUDIT_PATH` and
`RMACD_AUDIT`, are covered under *Audit trail*.

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

A `file://` target is unwrapped and classified as the path it denotes — most
built-in pack target templates are URI-shaped, so without that the map would
never see them. Genuinely remote schemes are left alone: `s3://bucket/secret`
is not the local path `/bucket/secret`.

## How tool calls are mapped

| Claude Code tool | RMACD mapping |
|------------------|---------------|
| `Bash` | `classify_bash_command()` on the command line (max operation across pipelines/sub-shells; unknown binaries fail closed to Change); the classification map is applied to the command's path-like tokens |
| `Bash`, read-only RMACD introspection | Read on `rmacd:introspection` — a carve-out for `rmacd --version/--help/validate/info/matrix/evaluate`, `rmacd pack validate/verify/diff/review`, `rmacd audit summarize`, and `python3 -m rmacd.claude_code.status`. Voided by any shell metacharacter, so `rmacd info && rm -rf /` cannot ride it |
| `Monitor` | The `Bash` path, identically — it runs a shell command in the background, so filing it with the session-internal tools would let `Monitor({command: "rm -rf /data"})` walk past the classifier |
| `Write` / `Edit` / `MultiEdit` / `NotebookEdit` | Add if the path does not exist yet, Change if it does; target = path. A call with no path argument is Change (conservative) |
| `Read` / `Glob` / `Grep` / `NotebookRead` / `LS` / `ListMcpResourcesTool` / `ReadMcpResourceTool` / `ReadMcpResourceDirTool` | Read; target = the first of `file_path`, `notebook_path`, `path`, `pattern`, `uri` present, classified by the map. The trailing `Tool` is part of the real MCP-resource names — the suffixless `ListMcpResources` matched nothing, so those calls fell through to the fail mode in the last row |
| `WebFetch` / `WebSearch` | Read; on DC2D profiles the destination (`WebFetch`'s URL host, or `web-search`) is additionally checked against `egress_controls` |
| `mcp__<server>__<tool>` | Resolved via the session registry (packs) under the full namespaced name first, then the bare name; the tool's capability ceiling gates first, then the profile. Path-like arguments — nested up to depth 4 — and the resolved target are overlaid against the classification map, which can only raise the tier |
| `Artifact` | Classified by its `action` argument: `read` / `list` / `comments` / `status` / `watch` / `unwatch` / `resolve` / `list_assets` / `read_asset` → **Read**; `delete_asset` → **Delete**; `publish` / `reply` / `upload_asset` / `resume_replies` → **Add** carrying egress destination `claude.ai`. A missing or unrecognised action takes the **Add** branch — the most severe of the common cases, so a newly added action can never arrive as a Read. Tier = `file_path` classified by the map when one is present (the read-only actions name a `url` instead); publishing a local file as a hosted page is an outbound data flow, not a read, so DC2D `egress_controls` gate it and the tier of the file being published is what the profile evaluates |
| `PushNotification` | **Add** at the session default tier, target `session://PushNotification`, egress destination `user-device`. It delivers off this machine, and its body can carry arbitrary session content, so the session default is the right conservative basis and `egress_controls` do the real gating — the same shape `Artifact` is wired into |
| `EnterWorktree` / `ExitWorktree` / `CronCreate` / `CronDelete` / `CronList` | Add / (Read for `action: "keep"`, Delete for `action: "remove"`, Delete when the action is absent or unrecognised) / Add / Delete / Read, at an explicit `internal` tier; target = `session://<Tool>`. Their effects outlive the session, so they are not session-internal. The tier is pinned rather than inherited from `RMACD_DEFAULT_TIER` because the target is a session-local scratch resource, not the data that default describes: under a `restricted` default `ExitWorktree` evaluated as Delete on Restricted, which §12.5 makes unapprovable by anyone — a session could enter a worktree and never leave it. Only these three `Cron` names are mapped; any other (`CronUpdate`, `CronGet`) takes the last row |
| Session-internal tools (`Task`, `Agent`, `SendMessage`, `Workflow`, `TodoWrite`, `Task{Create,Get,List,Update}`, `AskUserQuestion`, `Skill`, `SlashCommand`, `ExitPlanMode`, `ToolSearch`, `BashOutput`, `KillShell`, ...) | Read on `public` (they orchestrate the session, not external data) — still governed, so a profile that denies Read denies them too |
| Anything else | Ungovernable → `RMACD_UNKNOWN_TOOL` fail mode. `RemoteTrigger` and `DesignSync` are left here **by choice, not by oversight**: each reaches outward to change something off this machine in a way that needs an explicit policy decision, and denying is the correct answer until one is made |

The introspection carve-out exists so a bound read-only session can inspect its
own governance state: without it the fail-closed Bash default would deny
`/rmacd:status` itself. It deliberately excludes everything that writes
(`rmacd pack sign`), reaches the network or an LLM (`rmacd classify`), or starts
a server (`rmacd mcp-serve`).

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

Every denial names why, so the reason is actionable without reading the
profile:

| Cause | Reason cites |
|-------|--------------|
| §12.5 immutable floor (Add/Change/Delete on `restricted`) | "prohibited (§12.5 immutable floor — cannot be granted by exception; human execution only)" + profile id. Checked first, even when a profile permission gap is the proximate cause |
| Profile constraint (environment / time window) | The constraint that failed + rule `profile constraints (env/time-window)` |
| Profile permission gap | The evaluator's blocked reason + the mapping rule that produced the call |
| Tool capability ceiling | Rule `tool capability ceiling` — the registered tool may never represent that operation/tier |
| DC2D `egress_controls` | The blocked destination + the matched egress rule |
| Unknown/unmapped tool | The tool name and `RMACD_UNKNOWN_TOOL` as the override |

The hook always exits 0; decisions travel in the stdout JSON. An *unbound*
session produces **no output at all** — deliberately not
`permissionDecision: "allow"`, which would suppress Claude Code's own
permission prompts and auto-approve everything. "Unbound" must mean
"ungoverned", never "wide open".

## Fail modes (normative)

| State | Behavior |
|-------|----------|
| No profile bound | **Passthrough** — no decision emitted, Claude Code's own permission flow unchanged; `SessionStart` says so once per session |
| Profile bound, configuration broken | **Fail closed** — deny, naming the binding error (invalid profile, unknown pack, malformed classification map, bad `RMACD_DEFAULT_TIER`/`RMACD_ENVIRONMENT`) |
| Profile bound, malformed event on stdin | **Fail closed** — deny; a bound session never passes through on a hook error |
| Profile bound, unexpected exception while deciding | **Fail closed** — deny, naming the tool and the exception |
| Profile bound, unknown/unmapped tool | Deny by default; `RMACD_UNKNOWN_TOOL=ask` routes it to the user's approval instead |
| SDK missing (plugin without `pip install`), profile bound | **Fail closed** — the plugin's stdlib-only `PreToolUse` shim denies every tool call and names the profile source, the interpreter (`sys.executable`), and the install command. A `SessionStart` notice says so once, up front |
| SDK missing, no profile bound | **Passthrough**, silently. An unbound session is an explicit zero-friction passthrough; installing the plugin without configuring it must not block anything |
| Anything wrong in `PostToolUse` | **Silent** — a note on stderr at most. The call already ran and its decision is already recorded; an audit problem must not disturb a session whose governance did its job |

The `PostToolUse` asymmetry is deliberate rather than an oversight: if the SDK
cannot be imported there, the `PreToolUse` guard has already denied every call
in the session, so there is no execution to record and a per-call error would be
noise on top of a problem the user was already told about once at
`SessionStart`.

Stderr is safe in all cases: with exit code 0 Claude Code reads only stdout for
the JSON decision, so a notice can never corrupt a decision. It is not hidden,
though — since 2026-07-31 Claude Code emits
`{"type": "system", "subtype": "hook_response", …}` events carrying hook
`stderr` verbatim under `--output-format stream-json`, where it was previously
visible only under `--debug`. Write notices that are safe to be read.

### Unbound sessions take a fast path

Both `PreToolUse` and `PostToolUse` shims answer "is a profile bound here?"
with a stdlib-only check — the same search order as
`session.resolve_profile_path`, testing only for the *presence* of a profile
source — **before** importing the SDK, and return immediately when the answer
is no.

That ordering is what makes "zero-friction" true rather than aspirational.
Importing `rmacd` costs roughly 0.3s of interpreter and pydantic startup, and
both hooks used to pay it on every tool call only to discover there was nothing
to govern: **~680ms per tool call, measured, down to 71ms** for the pair once
the check moved in front of the import. The people paying it were exactly those
who had installed the plugin and never configured anything.

The trade-off is that this check now gates enforcement, not just the wording of
a denial: if it ever disagreed with `resolve_profile_path`, a governed session
would run unenforced rather than merely warn oddly. `test_plugin_guard.py` pins
the two implementations to the same answer across the binding matrix, so drift
fails the build.

### The one gap: hook timeout

Fail-closed is enforced *inside* the hook, so it covers everything the hook can
observe. It cannot cover a hook that never returns an answer. If the process
exceeds the configured `timeout`, Claude Code treats it as a non-blocking error
and the tool call proceeds **ungoverned** — the same fail-open shape that the
0.14.1 wrapper closed for a missing SDK, reachable here through latency instead.

In practice the margin is wide: a governed decision is a Python start plus a
profile load and an in-memory evaluation, and the plugin ships a 10s timeout.
It is worth knowing about anyway on machines where that assumption can break —
cold NFS home directories, heavily oversubscribed CI runners, a profile or
classification map on a network mount. If that is your environment, raise the
`timeout` in the hook configuration rather than leaving it near the edge, and
keep the profile and map on local disk.

## Audit trail

A bound session records every governance decision to
`.claude/rmacd-audit.jsonl` — beside the profile that bound it — in the spec
Appendix C.6 format. Two hooks write it:

| Hook | Records | Result values |
|------|---------|---------------|
| `PreToolUse` | The decision, before the call runs | `ALLOW`, `DENY`, `QUEUED` (an `ask` awaiting the user) |
| `PostToolUse` | The outcome, for calls that ran | `EXECUTED`, with `execution.status` of `SUCCESS` or `FAILURE` (+ the tool's error text) |

**Decisions are recorded at `PreToolUse` on purpose.** A denied call never
runs, so it never reaches `PostToolUse`; a trail assembled only from executions
would omit every denial — precisely the evidence that shows the boundary held.
Every return path in the decision function records first, including the
unknown-tool and capability-ceiling denials that short-circuit before an
evaluation happens (those get a synthetic `prohibited` decision so they are
first-class rows rather than gaps).

Records carry an `extra` block outside the C.6 shape:

| Field | Present when |
|-------|--------------|
| `session_id`, `tool_use_id`, `tool_name`, `cwd` | Always (whenever the hook event carried them) |
| `agent_id`, `agent_type` | Only when the call came from a subagent |

The two record kinds join on `tool_use_id`. The absence of `agent_id` is itself
meaningful: the call came from the main conversation.

### Decision handoff (`PreToolUse` → `PostToolUse`)

The execution record is written *from* the decision, not recomputed.
`PreToolUse` hands its result forward in a single-use JSON sidecar under the
system temp directory, keyed by `(session_id, tool_use_id)`; `PostToolUse`
consumes it, unlinks it, and writes the execution record from its contents —
loading no profile and building no registry at all.

This is what makes the two rows consistent. The mapping is **not** a pure
function of the tool call: `Write` is **Add** when the path does not exist and
**Change** when it does. By the time `PostToolUse` runs, the file exists — so
re-deriving the mapping after the write filed every file creation as `Add` in
its decision and `Change` in its execution: two rows that join on
`tool_use_id` and contradict each other, in the half of the product whose whole
purpose is evidence. The sidecar also carries the autonomy level the decision
actually computed, so a call a human approved through the `ask` prompt is not
recorded as having run autonomously.

| Property | Behavior |
|----------|----------|
| Contents | Resolved audit path, `agent_id`, `profile_id`, operation, target, classification, `autonomy_level`, `requires_approval` |
| Written for | `ALLOW` and `QUEUED` decisions, and only while auditing is enabled — a denied call never runs, so it needs nothing handed forward |
| Location | `<tempdir>/rmacd-handoff-<session_id>/<tool_use_id>.json`, mode `0600` in a `0700` directory the hook refuses to use unless it is a real directory owned by the current user |
| Lifetime | Single-use: unlinked as soon as it is opened, even if its contents cannot be parsed, so it can never be replayed onto a later call |
| Orphans | Expected (an `ask` the user declines never reaches `PostToolUse`), swept after 24h on the next write |
| Missing | Costs one execution record, never a decision record |

Both ids are required: without them there is no join key, so an execution
record could not be correlated even if it were written. Sidecars are
best-effort throughout — denials, the evidence that matters most, are written
inline by `PreToolUse` and never depend on the handoff.

### Configuration

| Variable | Effect | Default |
|----------|--------|---------|
| `RMACD_AUDIT_PATH` | Write to this path instead of the default | unset → `rmacd-audit.jsonl` beside the bound profile |
| `RMACD_AUDIT` | Set false-y (`0`, `off`, `false`, `no`) to disable session audit entirely | enabled |

- Summarize a trail with `rmacd audit summarize .claude/rmacd-audit.jsonl`.
- `/rmacd:status` reports the resolved sink, `DISABLED` when `RMACD_AUDIT` is
  off, and a warning when the path is not writable.
- Add `.claude/rmacd-audit.jsonl` to `.gitignore` unless you intend to commit
  the evidence.

Auditing is **best-effort and never affects a decision**: an unwritable sink
produces a stderr note and the governance outcome stands. Making it a denial
would take a working session down over bookkeeping; making it an exception
would fail the hook closed for the same reason.

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
- `docs/audit-evidence.md` — the Appendix C.6 record format and what
  `rmacd audit summarize` reports.
- `plugins/rmacd/` — the plugin: skills, `/rmacd:init`, `/rmacd:status`,
  `/rmacd:bug-setup`, and the three stdlib-only hook shims in `hooks/`
  (`rmacd_session_start.py`, `rmacd_guard.py`, `rmacd_post.py`) wired by
  `hooks/hooks.json`.
- SDK sources: `sdk/python/rmacd/claude_code/` — `hook.py` (PreToolUse),
  `post_hook.py` (PostToolUse), `handoff.py` (decision sidecar), `audit.py`,
  `mapping.py`, `session.py`, `status.py`.
