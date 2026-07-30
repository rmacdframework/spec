# Changelog

All notable changes to the RMACD Framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

#### Fixed — fail-closed coverage

- **A missing or broken SDK ran the entire session ungoverned.** The plugin
  invoked `python3 -m rmacd.claude_code.hook` directly, so an unimportable
  `rmacd` exited non-zero — and Claude Code treats a non-zero hook exit as a
  **non-blocking** error. Reproduced: with a valid profile bound, `rm -rf /etc`
  produced no decision at all and would have proceeded. The plugin now runs a
  stdlib-only wrapper, `plugins/rmacd/hooks/rmacd_guard.py`, which denies every
  tool call when `import rmacd` fails *and* a profile source exists, naming the
  profile source, the interpreter that failed, and the install command. With no
  profile bound it stays silent — an unbound session is an explicit
  zero-friction passthrough. Bound-detection mirrors `resolve_profile_path`,
  including the upward walk, so it cannot re-introduce the 0.14.0 cwd bug.
- **Added a `SessionStart` hook.** Binding failures previously surfaced only as
  per-tool-call stderr visible under `--debug`. The session now reports its
  governance state once, up front — most importantly the
  profile-bound-but-SDK-missing case.
- **The hook interpreter is overridable.** `hooks.json` hardcoded `python3`, so
  a venv/system mismatch produced an ungoverned session; it now honours
  `${RMACD_PYTHON:-python3}`.
- **Hook timeout reduced from 30 s to 10 s**, against a measured ~380 ms hook
  wall time. A 30 s budget only elapses when something is badly wrong, which is
  exactly when a timeout should not be generous.

#### Fixed — evidence integrity

- **`@guard` on an async tool recorded a false `EXECUTED`/`SUCCESS` audit
  record.** The decorator's wrapper was a plain `def`, so calling an `async def`
  tool returned an un-awaited coroutine: the success record fired immediately
  with `duration_ms≈0`, and the `except` arm could never observe a failure
  raised inside the coroutine. A guarded async tool that raised was still
  audited as having succeeded — forged evidence in a product whose headline
  claim is audit evidence. `guard` now emits an `async def` wrapper for
  coroutine functions, awaits the tool before auditing, and preserves
  `inspect.iscoroutinefunction` so adapters that branch on it still work.
  The execution clock now also starts *after* enforcement, so a recorded
  duration measures the tool rather than any approval round-trip.
- **Evaluation and audit timestamps were timezone-naive.**
  `EvaluationContext.timestamp` defaulted to `datetime.utcnow()`, a naive
  datetime holding UTC wall-clock. `_check_time_windows` then called
  `.astimezone()`, which interprets naive datetimes as **system local time** —
  so every `allowed_hours`, `allowed_days` and `blackout_dates` check was wrong
  by the host's UTC offset, both admitting and denying incorrectly (reproduced:
  a 4-hour error under `TZ=America/New_York`). It also left audit records naive
  while `registry/tools.py` emitted timezone-aware ones, so the two halves of
  the same product disagreed. The default is now `datetime.now(timezone.utc)`,
  and `_check_time_windows` defensively treats a caller-supplied naive
  timestamp as UTC.

#### Changed

- **The `shell` pack is now documented as advisory, not a `bash.py` parity port.**
  The parity claim in `design.md` §8/§9, `governance-packs/README.md` and the
  pack's own description was false, and the golden fixture certified it only on
  the subset where the two engines already agree — it contained no redirect, no
  `-c`, no `eval` and no flag-elevated command. Measured divergences, all of
  them *under*-classifications by the pack: `echo x > /etc/passwd` R vs C,
  `bash -c "rm -rf /"` and `eval "rm -rf /"` C vs D, `find . -delete` R vs D,
  `curl -X DELETE` C vs D, `mkfs.ext4` C vs D, `rsync --delete` C vs D.
  `bash.py` remains the enforcing shell classifier. The seven divergences are
  now pinned by tests that fail if either engine changes *or* if a gap is closed
  without the case being promoted, so the shortfall stays visible. Closing it
  needs four engine primitives: redirect detection, `-c`/`eval` recursion, flag
  elevation, and prefix binary matching.
- The test suite is now warning-clean and runs with `filterwarnings = ["error"]`.
  All 262 prior warnings had the single `datetime.utcnow()` root cause above; a
  naive datetime creeping back in is a correctness bug, not noise, so it now
  fails the build.

## [0.14.0] — 2026-07-29

Consolidated security release. Closes **nine** ways a governed operation could
be silently under-enforced: the three enforcement-floor bypasses from the
2026-07-19 code review (fixed at the time but never released), plus six found
by the 2026-07-29 audit — three in Claude Code session governance, two in pack
classification, one in emergency escalation, one in egress control. Every fix
ships with a regression test that reproduces the original behaviour.

#### Fixed — enforcement floor

- **The §12.5 immutable floor did not apply on the DC2D evaluation path.**
  `_evaluate_dc2d` checked tier policy only, so a DC2D profile granting the
  restricted tier permitted **autonomous Add/Change/Delete on Restricted**. The
  floor now short-circuits at the top of the DC2D path, matching 3D and 2D.
- **The bare `&` background operator hid a command's destructive tail.**
  `ls & rm -rf /` classified as **Read**, because everything after `&` was
  invisible to both the bash classifier and the pack engine. Both now split on
  `&` via a `(?<!>)&(?![&>])` guard that spares `&&`, `&>` and `2>&1`.
- **Compound commands resolved to the wrong segment.**
  `git log; shred /etc/secret` resolved to git's Read, hiding the shell pack's
  Delete. Composed-tool resolution is now per-segment — each segment resolves
  independently, and the **most severe** result wins.

**Upgrade note:** these fixes make enforcement *stricter*. A deployment that
was unknowingly relying on one of the gaps below will start seeing denials
where it previously saw allows or approval prompts. That is the point, but it
is a behaviour change, hence the minor bump rather than a patch.

#### Fixed — governance bypasses

- **Claude Code: a subdirectory cwd silently unbound the session.**
  `resolve_profile_path` probed only `<cwd>/.claude/rmacd-profile.json`, so
  once the agent worked from a subdirectory the hook emitted *no decision at
  all* and every subsequent tool call ran ungoverned. It now walks `cwd`
  upward (nearest profile wins, so a subproject may bind a stricter one) and
  falls back to `$CLAUDE_PROJECT_DIR` for a cwd outside the project tree.
- **Claude Code: `..`, `./` and `~` evaded the classification map.**
  Rules were matched against raw tool arguments, so `rm -rf /data/../data/secret`
  and `rm -rf ./secret` classified as the session default tier while
  `rm -rf /data/secret` correctly hit the restricted rule — downgrading a §12.5
  hard deny to an approvable prompt. Targets are now matched in every
  normalized form (expanded, cwd-anchored, `..`-collapsed, and with leading
  `//` collapsed, which Linux resolves to `/` but `normpath` preserves).
- **Claude Code: `sh -c "…"` hid path arguments from the map.** A nested shell
  script arrives as one quoted token, so no path reached the classifier.
  Path extraction now recurses into `-c` payloads of `bash`/`sh`/`zsh`/`dash`/
  `ksh`/`ash`/`busybox`, to a depth of 4.
- **Packs: loading a second pack could *lower* an operation.** With `shell` and
  `docker` both loaded, `rm -rf` classified as **Change** instead of Delete,
  in either load order. A tier-only overlay rule asserts no operation but still
  carried its pack's wide `default_operation`, and outranked the shell pack's
  Delete on selector specificity. Two changes: `ClassificationResult` now
  reports `operation_asserted`, and composition takes the most severe asserted
  operation as a floor before ranking by specificity, applying the most
  sensitive tier any claim assigned. Adding a pack can no longer make a call
  look safer than it is.
- **Packs: shell overlays claimed commands belonging to other binaries.**
  Rules written as `when: {tool: [docker, bash, sh, …], arg_regex: '(^|\s)push\b'}`
  are correct for `tool: docker` but match *any* command line for `tool: bash` —
  `docker-push` was claiming `git push origin main`, and `terraform-apply` was
  claiming `kubectl apply` (wrong tier *and* a wrong audit trail). The engine
  now supplies the anchor the author meant: when a shell call is matched by a
  rule that also names real binaries, one of those binaries must appear as a
  token of the command. Rules that anchor themselves (`argv_contains`, or the
  `helm` pack's `\bhelm\b[^|;&]*\s…` form) are unaffected. This fixes 12 rules
  across `docker`, `npm`, `terraform`, `git`, `gh`, `pip-uv` and `ssh-transfer`
  without touching any pack data.
- **Emergency escalation ignored `trigger_conditions` when no trigger was given.**
  Both the 3D and DC2D paths treated an absent `emergency_trigger` as
  satisfying the gate, so a caller could take the escalated grant by simply
  omitting the field — a *wrong* trigger was rejected, no trigger was not. A
  profile that declares `trigger_conditions` now requires a matching one.
- **`block_external_models` was case- and trailing-dot-sensitive.**
  `API.OpenAI.com/v1` and `api.openai.com.` reached the same host as
  `api.openai.com` but bypassed the block, and allow-list entries were
  likewise case-sensitive. Hostnames are now normalized (lower-cased, trailing
  root dot stripped) on both sides of every comparison, including
  `external_model_hosts` at construction.

#### Fixed — packaging and documentation

- **The `[mcp]` extra is capped at `mcp>=1.0,<2`.** `mcp` 2.0.0 removed
  `mcp.server.fastmcp`, which `rmacd.mcp_server` is built on, so
  `pip install "rmacd-framework[mcp]"` was resolving to a version where
  `rmacd mcp-serve` raised `ModuleNotFoundError` on startup. The cap comes off
  when the server is ported to the 2.x API.
- **The wheel now ships `py.typed`** (PEP 561). It was absent from every
  release despite `Typing :: Typed` in the classifiers, so consumers' mypy and
  pyright silently treated all of `rmacd` as `Any`. A new test asserts the
  build's data files — `py.typed`, the 4 schemas, all 34 packs.
- **`Add` on `Restricted` is documented as Prohibited**, matching
  `IMMUTABLE_PROHIBITIONS` and `profile-3d.schema.json`. Spec §3.1 and the
  README both showed "Elevated Approval", so a profile built from the
  "definitive governance reference" was rejected at schema validation *and*
  runtime. §3.2 prose and the webapp's `/framework` matrix are corrected to
  match, and a webapp test now pins all 20 cells to the SDK.

#### Tests

Suite: 830 → 866, coverage 89% → 90%. New coverage for every bypass above,
including an order-independent sweep asserting that no built-in pack can
downgrade a shell Delete, a parametrized set of path spellings that must all
hit the §12.5 floor, and a build test pinning the wheel's data files.

### SDK 0.13.1 — Session-governance fix: introspection carve-out

Found by live end-to-end testing of the plugin: with a read-only profile bound,
the fail-closed bash default (unrecognized binary → Change) denied
`/rmacd:status` itself — a governed session could not inspect its own
governance state.

#### Fixed

- `rmacd.claude_code` bash mapping now classifies the governance layer's own
  deterministic read surfaces as Read (`rmacd:introspection`): the status
  renderer (`python3 -m rmacd.claude_code.status`) and the read-only rmacd CLI
  subcommands (`--version`, `--help`, `validate`, `info`, `matrix`, `evaluate`,
  `pack validate|verify|diff|review`, `audit summarize`). The carve-out applies
  only when the entire command is a single simple invocation — any shell
  metacharacter (compound commands, substitution, redirection) falls through to
  the normal classifier, and write/network/server surfaces (`pack sign`,
  `classify`, `mcp-serve`) are excluded. 17 new tests (suite: 813 → 830).

### SDK 0.13.0 — Claude Code governance, MCP server, 12 new packs, audit evidence

The "first-class citizen for Claude Code" release. Additive; no runtime or API
breaks; determinism and the §12.5 floor are unchanged.

#### Added

- **`rmacd.claude_code`** — session governance for Claude Code: a PreToolUse
  hook (`python3 -m rmacd.claude_code.hook`) that enforces a bound profile on
  the session's own Bash/Edit/Write/MCP tool calls (Bash via the bash
  classifier, files via filesystem-pack semantics, MCP tools via the registry).
  Unbound sessions pass through untouched; bound sessions fail closed;
  approval-level autonomy maps to Claude Code's own permission prompt
  (`permissionDecision: "ask"`). Deny reasons cite operation, tier, rule, and
  profile. Plus a status renderer (`python3 -m rmacd.claude_code.status`).
  Configuration via `RMACD_PROFILE_PATH` / `.claude/rmacd-profile.json`,
  `RMACD_PACKS`, `RMACD_CLASSIFICATION_MAP`, `RMACD_DEFAULT_TIER`,
  `RMACD_UNKNOWN_TOOL`. See `docs/claude-code.md`.
- **Claude Code plugin** (`plugins/rmacd/`, marketplace manifest at
  the repo root): the `rmacd-integrate` and `rmacd-bug-automation` skills,
  `/rmacd:init`, `/rmacd:status`, and `/rmacd:bug-setup` commands, and the
  PreToolUse hook wiring. Install:
  `/plugin marketplace add rmacdframework/spec`.
- **12 new built-in governance packs** (catalog: 22 → **34**). Developer
  toolchain: `git`, `gh`, `docker`, `terraform`, `npm`, `pip-uv`, `make`.
  Enterprise operations: `helm`, `vault`, `ssh-transfer`, `stripe`,
  `servicenow`. Destructive, credential, publish, and CAB-approval operations
  sit on the `restricted` tier as Change/Delete, so the §12.5 floor blocks them
  for autonomous agents.
- **Pack composition** (`rmacd.packs.composition`) — multiple packs can now
  govern the same tool name (e.g. shell overlays from `git` + `docker` +
  `terraform` together): ordered chain, most-specific claim wins, severity
  breaks ties fail-closed, and each match carries its own pack's capability
  ceiling. Previously last-applied pack won.
- **MCP server** (`rmacd.mcp_server`, optional `[mcp]` extra; CLI
  `rmacd mcp-serve [--profile]`) — read-only policy tools for any MCP client:
  `rmacd_evaluate`, `rmacd_validate_profile`, `rmacd_matrix`,
  `rmacd_list_packs`, `rmacd_pack_info`, `rmacd_classify_bash`. Pinned-profile
  mode for enterprise deployments.
- **Audit evidence** — `rmacd audit summarize <audit.jsonl>`
  (text/json/markdown; time/agent/denial filters; operation×tier matrix;
  §12.5-floor hits called out) backed by `rmacd.audit_report`, and
  `docs/audit-evidence.md` (SIEM shipping recipes + SOC 2 / ISO 27001 /
  GDPR mapping via §10).
- **Profiles-as-code CI assets** — a composite GitHub Action
  (`integrations/github-action/`) wrapping `rmacd validate` / `pack validate`
  / `pack verify`, a `pre-commit` hook (`rmacd-validate`), and a dogfood job in
  this repo's CI.
- **Bug-report automation** — issue form + label-gated Claude triage/fix/review
  workflows (`.github/workflows/claude-bug-triage.yml`, `claude-pr-review.yml`);
  reusable templates ship in the plugin's `rmacd-bug-automation` skill.

#### Docs

- New: `docs/claude-code.md`, `docs/audit-evidence.md`; framework-adapters
  gained "RMACD as an MCP server" and Claude Code cross-links;
  implementation guide gained "Profiles as code"; governance-packs catalog
  regenerated with two new families; pack counts swept 22 → 34 (including both
  architecture diagrams and the layers overview).

#### Tests

- Suite grows 543 → **813** (packs golden rows, composition, Claude Code hook
  subprocess tests, MCP server, audit report).

### SDK 0.12.0 — Cloud IAM packs + CLI approval gateway

Additive release on top of 0.11.0. No runtime or API breaks; determinism and the
§12.5 floor are unchanged.

#### Added

- **3 cloud-identity built-in packs** (wheel data) — `aws-iam`, `az-identity`,
  `gcp-iam` — bringing the built-in catalog to **22 packs**. These govern IAM /
  directory / secrets surfaces and map their most-sensitive operations to the
  `restricted` tier. (AI-drafted starting points; review + sign before
  production trust.)
- **`CLIApprovalGateway`** promoted into the SDK (`rmacd.approval`, exported from
  `rmacd`) — a ready-to-use interactive stdin/stderr approval surface, so an
  approval-gated agent is testable straight from `pip install` with no extra
  glue. Joins the existing `RejectAllApprovalGateway` (default) and
  `AutoApproveGateway`; fails closed on EOF. The agent examples now import it
  from the SDK instead of carrying a local copy.

#### Docs

- Corrected the built-in pack count (19 → 22) across the README, SDK README,
  implementation guide, governance-packs docs, spec v1.4 SDK-updates note, and
  both architecture diagrams.

### SDK 0.11.0 — Governance Packs

Onboarding an agent becomes *configuration, not code*: classification is now a
declarative, reusable, signable artifact (a **governance pack**) instead of a
hand-written per-integration classifier. New top-level package `rmacd.packs`.
Runtime stays 100% deterministic — packs only produce the
`(operation, data tier, target)` input to the evaluator; the §12.5 floor, agent
profile, and tool capability ceiling remain the authoritative gates, and the LLM
never runs at enforcement time. Fully backward compatible; existing classifiers
and `enforce_tool_call` are unchanged.

#### Added

- **Pack model & schema** — `GovernancePack` (+ `schemas/pack.schema.json`,
  bundled), canonical JSON serialization, `content_hash`, `freeze()`/`verify_hash()`.
- **Declarative engine** (`rmacd.packs.engine`) — tool-name selectors
  (exact/glob/`/regex/`) + argument predicates; shell tokenization with wrapper
  stripping and `$(...)` recursion; `verb_table` with MAX-operation combination;
  `pattern_map`/`resolver` tier resolution (most-sensitive wins, fail-closed);
  cross-rule combination (tier overlays); `verb_prefix_delimiters` for verb-noun
  CLIs; case-insensitive verbs. `DeclarativeClassifier` plugs into the existing
  `ToolClassifier` protocol.
- **Loading & registration** — `load_pack` / `load_packs` / `apply_pack`; a
  declarative classifier now round-trips through `ToolDefinition` export/import
  (closes the prior "dynamic classifier dropped on serialization" gap). Resolver
  registry (`register_resolver`) for live tier lookups, fail-closed + audit-logged.
- **19 built-in packs** (wheel data) — `shell`, `aws`, `gcloud`, `az`, `kubectl`,
  `github`, `gitlab`, `sql`, `filesystem`, `jira`, `confluence`, `slack`,
  `google-drive`, `postgres`, `boto3`, `aws-api-mcp`, `azure-mcp`, `gcp-toolbox`,
  `ms365`. (AI-drafted starting points; review + sign before production trust.)
- **AI-compile authoring** — `compile_pack()` turns an MCP `tools/list` into a
  proposal pack with per-rule confidence + provenance; `review_items()` surfaces
  the uncertain/destructive tail. CLI: `rmacd classify`, `rmacd pack review`.
- **Signing & integrity** — Ed25519 `sign_pack`/`verify_pack` (optional `[sign]`
  extra), drift detection (`pack_drift`), and a ReDoS guard (`find_redos_risks`
  + engine input cap). CLI: `rmacd pack sign|verify|diff|validate`.
- **Trust enforcement** — `load_pack`/`load_packs` accept
  `require_signed=True` + `trusted_keys=` to refuse unsigned/untrusted packs
  (recommended production posture, since built-in packs ship unsigned).
- **Hardening** — `rmacd pack validate` now runs the ReDoS/lint check (not just
  schema); `apply_pack` warns when a glob/regex pack registers nothing without a
  tool list; added a `[yaml]` extra for YAML-authored packs; PR CI now runs
  bandit + a coverage gate (was release-only).

## [1.4.0] - 2026-06-09

### SDK 0.10.0 (2026-06-11)

#### Added — LLM-assisted classification + registry governance hardening

- **LLM tool classifier** (`rmacd.registry.llm`, optional extra
  `pip install rmacd-framework[llm]`) — `LLMToolClassifier` asks a Claude model
  (default `claude-fable-5`) to classify a tool definition into
  `(rmacd_level, data_access, required_hitl)` with a rationale and confidence
  score, via structured outputs (Pydantic `ToolClassification`). Importing the
  module needs no `anthropic` package; only use does. The LLM output is
  advisory input to governance — the §12.5 floor, agent profile, and capability
  ceiling remain deterministically enforced.
- **MCP bridge upgrades** (`MCPRegistryBridge`):
  - accepts an existing `registry=` so MCP tools land in the same registry a
    `PolicyEnforcer` enforces against (previously the bridge always created an
    isolated one);
  - `llm_classifier=` + `llm_mode="fallback"|"always"` — keyword heuristic
    handles the obvious cases, the LLM handles the ambiguous tail (fallback) or
    everything (always); LLM failures degrade to the keyword result and are
    recorded, never blocking registration;
  - every auto-classified tool now gets a **capability ceiling** capped at its
    inferred operation (a tool classified Read can never represent a Delete);
  - **classification provenance** in `metadata["classification"]` (engine,
    evidence/rationale, confidence) and `bridge.low_confidence_tools()` to
    surface the human-review queue;
  - `register_mcp_tool` accepts raw MCP `tools/list` dicts and returns the
    registered `ToolDefinition`; new bulk `register_mcp_tools`;
  - keyword inference gains an explicit Read keyword list and secret detection
    for `private_key`/`api_key`/`access_token`/`auth_token` (→ restricted).
- **Registry management**: `unregister_tool`, `list_tools`,
  `get_tools_by_tag`, and iteration over a `ToolsRegistry`.
- **Bash classifier hardening**:
  - shell control keywords are now understood — `for f in *; do rm "$f"; done`
    previously read `do` as an unknown binary and fail-closed to Change,
    *hiding* the Delete; `if`/`then`/`else`/`while`/`until`/`do`/`!` are
    stripped like wrappers, `for`/`case`/`[`/`[[` headers classify as Read;
  - process substitution `<(...)` / `>(...)` inner commands are classified;
  - destructive-binary coverage: `mkfs`/`mkfs.*` (prefix-matched), `wipefs`,
    `mkswap`, `userdel`/`groupdel` (Delete), `useradd`/`groupadd` (Add),
    `fdisk`/`sfdisk`/`gdisk`/`parted` (Delete, with `-l`/`--list` → Read),
    `shutdown`/`reboot`/`swapon`/`swapoff` (Change).

#### Fixed

- `validate_tool_access` now audits **denials** (previously only successful
  checks were logged — backwards for a governance layer), and denial reasons
  name the operation (`highest allowed is M`) instead of an internal rank
  number.

### SDK 0.9.1 (2026-06-11)

#### Fixed

- `rmacd --version` and `rmacd.__version__` reported a stale hardcoded version.
  Both now read the installed distribution version via
  `importlib.metadata.version("rmacd-framework")`, making `pyproject.toml` the
  single source of truth.
- A wheel-only install could not validate profiles
  (`SchemaValidationError: Schema directory not found`). The three profile
  schemas are now bundled as package data under `rmacd/schemas/` and
  `ProfileValidator` defaults to them via `importlib.resources`; the
  `schema_dir` constructor argument and `--schema-dir` CLI flag remain as
  overrides. A new `tests/test_schema_sync.py` fails if the bundled copies
  drift from the authoritative `schemas/` directory.
- SDK README: the validator example required a repo-relative `schema_dir` and
  used `SchemaValidationError` without importing it; `PolicyDecision` was shown
  as a dataclass (it is a Pydantic model); `ProfileDC2D` was missing from the
  profile-types list.

### SDK 0.8.0 (2026-06-09)

#### Added — first-class Tools Registry + registry-backed enforcement

- The **Tools Registry** (`rmacd.registry`) is now the authoritative tool→RMACD
  classifier and capability layer. `ToolDefinition` gains:
  - a **dynamic classifier** (`classifier=`) resolving a call's args to
    `(operation, tier, target)`, plus a static `target_template`, replacing the
    hand-written per-integration classifier lambdas;
  - a **capability ceiling** (`ToolCapability`, 2D op-set or 3D per-tier) bounding
    what a tool may *ever* do.
- **`PolicyEnforcer.enforce_tool_call(tool_name, args)`** (+ side-effect-free
  `evaluate_tool_call`) — classifies a call through the registry, applies the
  tool's capability gate, then evaluates against the agent profile. Enforcement
  is **profile ∩ tool capability** with the §12.5 immutable floor always on,
  returning an audited allow/deny/approve at the tool-call boundary. Unknown
  tools fail closed. `PolicyEnforcer` accepts a `registry=`.
- **`RMACDToolCapabilityError`** — new exception distinguishing "this tool may
  never do that" from a profile gap (`RMACDPermissionDeniedError`) or a matrix
  prohibition (`RMACDProhibitedError`).
- **Bash command classifier** (`rmacd.registry.classify_bash_command` /
  `make_bash_classifier`) — parses a shell command (binary, subcommand, flags,
  pipes/`&&`/`;`, redirects, `sudo`, `$(...)`) into the **maximum** RMACD
  operation, failing closed (Change) on unknown binaries. Honours switch-level
  distinctions (`sed -n`=Read vs `sed -i`=Change; `pico`/`nano`/`vim` edit=Change
  vs `-v`/`--view`/`-R` view=Read; `nslookup`=Read vs `nsupdate`=Change; any
  `--help`/`--version`=Read; `>` redirect ⇒ Change), with per-binary scoping so
  `pico -v` (view) ≠ `cp -v` (verbose). Curated table covering base commands
  (`cp`/`mv`/`rm`/`chmod`/`pico`/`nano`/`vim`/`sed`/`awk`/`find`/`tar`/…),
  subcommand-driven tools (`git`/`kubectl`/`docker`/`systemctl`/`apt`/`yum`/
  `dnf`/`brew`/`pip`/`npm`/`helm`/`terraform`), verb-mapped cloud CLIs
  (`aws`/`gcloud`/`az`), method-aware `curl` (`-X DELETE`→Delete), and
  conservative defaults for opaque clients (`psql`/`mysql`/`ansible`/`ssh`).
  Operation-level (tier `None`) — pairs with a 2D profile.
- **Framework adapters** (`docs/framework-adapters.md`): registry-backed
  `enforce_tool_call` wired into a Claude Agent SDK `PreToolUse` hook (the
  `agent-integration-claude-sdk` example now uses it), an **OpenAI Agents SDK**
  tool guardrail + `needs_approval` callback, and a **Microsoft Agent Framework**
  `FunctionMiddleware`. The integration point is identical across all of them:
  intercept at the tool-call boundary, return allow/deny/approve.

#### Fixed

- Registry: re-registering a tool at a different RMACD level no longer leaves a
  stale `_index_by_level` entry (corrupted `get_tools_by_level`/`get_stats`);
  `validate_tool_access` now honours the cumulative hierarchy (granting D implies
  R/M/A/C); `import_from_json` returns False on partial failure.

#### Removed

- The deprecated standalone `tools-registry/` directory (code + JSON catalogs)
  was folded into `rmacd.registry` and deleted. Imports move from
  `rmacd_tools_registry` to `from rmacd.registry import ...`.

#### Changed

- Specification document renamed `docs/RMACD_Framework_v1.3.{md,docx}` →
  `docs/RMACD_Framework_v1.4.{md,docx}` per the minor-release convention; §9.4
  reframed around the first-class registry and `enforce_tool_call`. References
  in `README.md`, `docs/runtime-patterns.md`, `docs/implementation.md`, and the
  DC2D example updated.

#### Tests

- New `tests/test_enforce_tool_call.py` (profile∩tool intersection, capability
  ceiling, dynamic classifier, approval routing, unknown-tool fail-closed, and
  the §12.5 floor through the tool path); expanded `tests/test_registry_sdk.py`
  (classification/capability model, re-register index fix, cumulative access).

---

## [1.3.2] - 2026-06-08

### SDK 0.7.0 (2026-06-08)

#### Security — the Restricted A/C/D safety boundary is now enforced

- The §12.5 invariant (**Add, Change, or Delete on Restricted data is
  prohibited for any agent and cannot be granted through the exception
  process**) was documented but not actually enforced. A profile that listed
  the operation in `permissions.restricted` and raised it via
  `autonomy_overrides` (e.g. `"restricted.C": "autonomous"`) previously
  evaluated to `allowed=true` at the `autonomous` level. Now closed with
  defense in depth:
  - **Evaluator runtime floor** — a new `IMMUTABLE_PROHIBITIONS` set in
    `evaluator.py` forces `PROHIBITED` for Restricted Add/Change/Delete
    *before* any override, permission, or emergency-escalation path is
    consulted. This is the authoritative, non-bypassable enforcement point.
  - **Schema tightening** — `schemas/profile-3d.schema.json` now restricts
    `permissions.restricted` to `["R", "M"]` and constrains
    `autonomy_overrides` for `restricted.(A|C|D)` to `prohibited` only.
  - Bypass-resistance tests in `tests/test_evaluator.py` and
    `tests/test_validator.py`. All eight shipped example profiles still
    validate against the tightened schema.

#### Fixed

- **Time-window midnight crossing** (`evaluator.py`) — windows that wrap past
  midnight (e.g. `22:00`–`06:00`) previously always blocked; now evaluated
  correctly with wraparound logic.
- **Egress allow-list substring bypass** (`egress.py`) — an allow-list entry
  like `internal` previously admitted look-alike hosts such as
  `evil.internal-breach.com`. Matching is now exact or hostname-suffix.
- **Egress scheme-less destinations** (`egress.py`) — `block_external_models`
  silently failed to fire for hosts without a URL scheme (e.g.
  `api.openai.com/v1`); host extraction now handles bare hosts and ports.
- **MCP auto-classifier keyword matching** (`registry/mcp.py`) — substring
  matching misclassified tools (`set` in `asset`, `drop` in `dropdown`); now
  anchored on word boundaries.
- **Redaction patterns** (`redaction.py`) — the credit-card regex was rewritten
  to avoid catastrophic backtracking on long digit runs, and the IPv4 pattern
  now validates octet ranges (0–255) so version strings like `1.2.3.4` are no
  longer redacted as IP addresses.
- **CLI `--version`** corrected from a stale `0.3.1` string.
- `registry/tools.py`: timezone-aware timestamps, explicit tier/operation
  ordering maps (no longer dependent on enum declaration order), and a `None`
  `risk_score` sentinel so an explicit `0.0` is preserved. Dead code removed in
  `loader.py`; the no-op approver ternary fixed in both example CLI gateways.

#### Changed — observability

- `PolicyEnforcer` now logs a warning when an audit sink raises, instead of
  swallowing the error silently. Enforcement remains fail-open on audit failure
  by design (a broken sink must not turn into a global outage), but the failure
  is now observable.

#### Tests

- SDK suite expanded from 60 to 148 tests (line coverage 62% → 83%). New files:
  `test_validator.py`, `test_cli.py`, `test_models.py`, `test_registry_sdk.py`,
  `test_loader.py`; added time-window/environment constraint coverage and the
  safety-boundary bypass tests above.

---

## [1.3.1] - 2026-05-11

### SDK 0.6.0 (2026-05-11)

#### Added — programmatic agent prompt construction

- **`rmacd.prompts.build_system_prompt(profile)`** — generates a
  markdown prompt fragment derived mechanically from the profile's
  permissions, autonomy overrides, and tier policies. Closes the
  drift-prone gap between hand-written prompts and live profiles
  noted in `docs/runtime-patterns.md` §7. Supports all three profile
  shapes (2D, 3D, DC2D), renders an autonomy table for 3D, surfaces
  redaction and egress controls for DC2D, and lists hard prohibitions
  from the autonomy matrix.
- 13 new tests in `tests/test_prompts.py`.

#### Added — runtime architecture diagram + renderer

- **`docs/RMACD_Runtime_Architecture.drawio`** plus its rendered
  `.drawio.png`: PDP/PEP/Audit/Approval/Classifier topology with SDK
  class names overlaid, plus a DC2D-only band showing Redactor and
  Egress Gate. Referenced from spec §C.1 and README.
- **`docs/render_drawio_to_png.py`** — pragmatic matplotlib-based
  renderer for environments without draw.io desktop or a headless
  Chromium. Re-run after edits to refresh the PNG.

### SDK 0.5.0 (2026-05-11)

#### Added — DC2D runtime enforcement

- **`rmacd.redaction`** module: `Redactor` Protocol, `RedactionResult`,
  `NullRedactor`, `RegexRedactor` (email, US SSN, credit-card,
  US phone, IPv4 with stable per-process tokenization).
- **`rmacd.egress`** module: `EgressGate` Protocol, `EgressDecision`,
  `PolicyDrivenEgressGate` enforcing the profile's `allowed_destinations`
  allow-list and `block_external_models` flag.
- **`PolicyEnforcer.apply_redaction(content, tier)`** and
  **`PolicyEnforcer.check_egress(tier, destination)`** methods. Both
  no-op for non-DC2D profiles.
- **`RMACDEgressBlockedError`** exception subclass.
- 11 new tests in `tests/test_dc2d_runtime.py`.

### SDK 0.4.0 (2026-05-11)

#### Added — enforcement layer

- **`PolicyEnforcer`** — decision + side effects on top of
  `PolicyEvaluator`. Methods: `enforce()`, `evaluate_only()`,
  `guard()` decorator, `from_env()` class method (reads
  `RMACD_AGENT_ID` and `RMACD_PROFILE_PATH`).
- **`rmacd.approval`** module: `ApprovalGateway` Protocol,
  `ApprovalRequest`, `ApprovalDecision`, `ApprovalOutcome`
  (`APPROVED`/`DENIED`/`TIMEOUT`), `RejectAllApprovalGateway`
  (fail-closed default), `AutoApproveGateway` (scripted/test use).
- **`rmacd.audit`** module: `AuditLogger` Protocol,
  `AuditRecord` (matches spec Appendix C.6), `JSONLAuditLogger`,
  `NullAuditLogger`, helper `build_audit_record()`.
- **`rmacd.exceptions`** module: `RMACDError` hierarchy with
  `RMACDPolicyError` and six subclasses
  (`RMACDPermissionDeniedError`, `RMACDProhibitedError`,
  `RMACDConstraintError`, `RMACDApprovalRequiredError`,
  `RMACDApprovalDeniedError`, `RMACDApprovalTimeoutError`).
- Profile-denied vs matrix-prohibited disambiguation in
  `PolicyEnforcer._classify_denial`: when both apply, the matrix
  prohibition wins so callers see the hard safety boundary rather
  than an exception-eligible profile gap.
- 12 new tests in `tests/test_enforcer.py`.

### Added — reference integrations

- **`examples/agent-integration-claude-sdk/`** — Claude Agent SDK with
  `PreToolUse` hook → `PolicyEnforcer.enforce`. Includes seven DevOps
  tools, custom 3D profile, CLI approval gateway, JSONL audit, and
  walkthrough doc.
- **`examples/agent-integration-anthropic-sdk/`** — raw Anthropic SDK
  manual tool-use loop with prompt caching; `dispatch_tool()` is the
  single integration site. Live-tested end-to-end against the API.
- **`examples/dc2d-customer-support/`** — deterministic DC2D demo (no
  LLM) covering all four tiers and four destination types.

### Added — companion documentation

- **`docs/runtime-patterns.md`** — profile binding, resource
  classification lookup, dynamic operation classification, approval-wait
  semantics for LLM agents, SDK error contract, agent self-restriction
  prompts, DC2D runtime, and an end-to-end integration checklist with
  the SDK-provides-vs-integrator-provides boundary.
- **`docs/framework-adapters.md`** — LangChain
  (`BaseCallbackHandler` and per-tool decorator), AutoGen v0.4+
  (`rmacd_guarded` wrapper), CrewAI (`RMACDGuardedTool` mixin) plus
  a generic dispatch-site pattern.

### Changed

- **Spec document** (`docs/RMACD_Framework_v1.3.md`) gained a new
  section §9.5 covering the SDK enforcement layer and a new section
  C.8 cross-referencing the companion docs. Version header updated to
  include the 1.3.1 update line.
- **Implementation guide** (`docs/implementation.md`) replaced its
  Tools Registry-only section with a Python SDK section covering the
  enforcement layer; cross-references the reference integrations and
  companion docs.
- **`spec/.gitignore`** added `.env`, `.env.*` (with `!.env.example`
  whitelist), and `examples/**/audit.jsonl`. `spec/.env.example`
  shipped as a committable template.

---

## [1.3.0] - 2026-05-09

### SDK 0.3.1 amendment (2026-05-09, packaging only)

- **Distribution name renamed**: `rmacd` → `rmacd-framework` on PyPI. The import name is
  unchanged (`from rmacd import ...`), so existing code is unaffected. Aligns with the
  GitHub org (`rmacdframework`), the website (`rmacd-framework.org`), and the citation
  key. Done before first PyPI publish to avoid post-release deprecation shims.
- **SDK version** bumped `0.3.0` → `0.3.1` (no functional code changes).
- **`publish-sdk.yml` CVE audit step** fixed earlier the same day to audit declared
  dependencies via `uv export` rather than the live environment, which prevented
  first-publish on a never-yet-on-PyPI package.



### Added

- **Data-Classification Two-Dimensional variant (DC2D)** — A second 2D projection of the
  governance model that pairs Data Classification with HITL Autonomy, dropping the
  operations axis. Intended for organizations whose primary governance lever is data
  sensitivity and whose operational permissions are governed by an upstream IAM/RBAC or
  DLP layer (e.g., regulated industries, AI-DLP product deployments).
- **Specification Appendix D: The Data-Classification Two-Dimensional Variant (DC2D)** —
  Motivation, relationship to 2D and 3D models, governance matrix with recommended
  defaults, schema identifier, intentional omissions, and prior-art positioning
  (CSA capability-control matrix as nearest framework analogue, AI-DLP vendors as
  implementation analogue).
- **`schemas/profile-dc2d.schema.json`** — JSON Schema (Draft 2020-12) for DC2D profiles.
  Required `data_access` block with per-tier `allowed` + `autonomy` policy. Adds
  `redaction` and `egress_controls` constraint blocks; emergency escalation operates on
  data tiers (`escalated_tiers` + `escalated_autonomy`) rather than operations.
- **`schemas/examples/regulated-data-handler-dc2d.json`** — Worked example: customer-support
  agent with public→autonomous, internal→logged, confidential→approval (DPO),
  restricted→denied with justification.

### Changed

- **Python SDK to v0.3.0** — Adds `ProfileDC2D`, `DataAccess`, `TierPolicy`, and supporting
  models. `ProfileLoader`, `ProfileValidator`, `PolicyEvaluator`, and the `rmacd` CLI all
  recognize `model: "data-classification-2d"`. CLI `info` and `matrix` commands render
  per-tier output for DC2D profiles. Operation argument to `evaluator.evaluate()` is
  preserved as decision metadata for DC2D but does not affect the autonomy decision.
- **`DEFAULT_AUTONOMY_DC2D`** matrix added to evaluator: public→autonomous,
  internal→logged, confidential→approval, restricted→elevated_approval.
- **Specification document renamed** — `docs/RMACD_Framework_v1.2.{md,docx}` →
  `docs/RMACD_Framework_v1.3.{md,docx}`, following the existing convention of bumping
  the filename on every minor release. Internal version line bumped to v1.3.0
  (May 2026). All references in `README.md`, `tools-registry/README.md`, and
  `CITATION.cff` updated.

### Tests

- 11 new tests in `tests/test_evaluator.py` covering DC2D evaluation paths, the
  operation-is-metadata-only invariant, emergency tier escalation with selective
  coverage, and end-to-end loader + schema validator round-trip.

---

## [1.2.1] - 2026-04-27

### Fixed

- **Governance matrix bug** — `DEFAULT_AUTONOMY_3D` in Python SDK `evaluator.py` did not match the
  specification matrix; corrected six cells: `public.M`, `public.C`, `internal.R`,
  `confidential.R`, `confidential.D`, and `restricted.R`
- **Python SDK `DeleteControls` model** — Added missing `two_person_rule_for_confidential` field
  and corrected `retention_compliance_check` default (`false` → `true`) to match JSON schema
- **CLI version string** — Hardcoded `0.1.0` in `cli.py` updated to `0.2.1`
- **Appendix B profile schemas** — Fixed wrong domain (`rmacd.io` → `rmacd-framework.org`),
  missing `"model": "three-dimensional"` field, and missing `rmacd-3d-` ID prefix across all
  six example profiles; runtime example records in Appendix C updated to match
- **Test coverage** — Added `test_default_autonomy_matrix_matches_spec` covering all 20 cells
  of the governance matrix

---

## [1.2.0] - 2026-01-18

### Added

- **Python Tools Registry** — Reference implementation for automated tool governance
  - Core registry with tool registration and RMACD classification
  - Permission validation against agent profiles
  - Risk scoring algorithm combining all three RMACD dimensions
  - Audit logging for compliance tracking
  - MCP (Model Context Protocol) auto-classification bridge
  - 27 pre-configured tools across all RMACD levels
  - 5 standard permission profiles (Observer, Coordinator, Contributor, Developer, Administrator)
  - Comprehensive test suite (43 tests)
  - JSON export/import for tool catalogs

### Changed

- Added Section 9.4 "Python Tools Registry Implementation" to framework specification
- Updated implementation guide with tools-registry reference
- Documentation links updated to reference tools-registry directory

---

## [1.1.0] - 2026-01-13

### Added

- All 15 governance tables now present in Markdown specification
- Tables 1-5: RMACD Hierarchy, Data Classification Tiers, Autonomy Levels, Governance Matrix (3D), Governance Matrix (2D)
- Tables 11-13: GDPR Alignment, HIPAA Alignment, PCI-DSS Alignment
- Table 15: Adoption Roadmap

### Changed

- Updated Tables 6-10 and Table 14 to match DOCX 4-column format with full content
- Renamed specification files from v1.0 to v1.1
- Version updated to 1.1 in both DOCX and Markdown documents

### Fixed

- Markdown formatting: proper code fences for pseudocode, Python, and JSON blocks
- Markdown formatting: blank lines before bullet lists
- Full parity between DOCX and Markdown versions (15 tables, 16 H1, 64 H2 headings)

---

## [1.0.2] - 2026-01-11

### Added

- Framework diagram (`docs/RMACD_Framework_Diagram.drawio.png`)
- Editable draw.io source file (`docs/RMACD_Framework_Diagram.drawio`)
- Embedded diagram in README for visual overview

### Changed

- Updated Documentation section with diagram links

---

## [1.0.1] - 2026-01-11

### Added

- Markdown version of full specification (`docs/RMACD_Framework_v1.0.md`)
- Improved documentation section in README with better organization

### Changed

- Updated README to prioritize markdown documentation for GitHub readability

---

## [1.0.0] - 2026-01-11

### Added

- **RMACD Operational Hierarchy**: Five graduated permission tiers
  - Read (R): Observe, query, analyze — no state change
  - Move (M): Relocate, transfer — reversible operations
  - Add (A): Create, provision — additive impact
  - Change (C): Modify, update — state mutation
  - Delete (D): Remove, destroy — potentially irreversible

- **Human-in-the-Loop (HITL) Autonomy Levels**
  - Autonomous: No human oversight required
  - Logged: Autonomous with enhanced audit trail
  - Notification: Human notified, no approval required
  - Approval: Human approval required before execution
  - Elevated Approval: Senior/CAB approval required
  - Prohibited: Operation not permitted for agents

- **Two Implementation Models**
  - Two-Dimensional Model: RMACD × HITL (no data classification required)
  - Three-Dimensional Model: RMACD × HITL × Data Classification

- **Data Classification Integration (PICR)**
  - Public: Freely shareable
  - Internal: Business use only
  - Confidential: Sensitive information
  - Restricted: Maximum protection required

- **Permission Profile Templates**
  - Observer (Read-only)
  - Logistics (Read + Move)
  - Provisioning (Read + Move + Add)
  - Operations (Read + Move + Add + Change)
  - Administrator (Full RMACD)

- **JSON Schema Definitions**
  - Two-dimensional profile schema
  - Three-dimensional profile schema
  - Example profiles for common agent types

- **Compliance Mappings**
  - GDPR alignment
  - HIPAA alignment
  - PCI-DSS alignment
  - SOX alignment
  - ISO 27001 alignment

- **Implementation Guidance**
  - Environment-based differentiation
  - Approval authority mapping
  - ITIL change management integration
  - Adoption roadmap

### Notes

- Initial public release
- Created by Kash Kashyap
- Licensed under CC BY 4.0

---

## Future Roadmap

### Planned for v1.4

- Platform-specific integration guides (Kubernetes, AWS/Azure/GCP)
- LangChain / AutoGen / CrewAI integration modules
- GraphQL API for registry management

### Planned for v2.0

- Multi-agent coordination patterns
- Delegation and escalation workflows
- Web UI for registry management

---

[1.4.0]: https://github.com/rmacdframework/spec/releases/tag/v1.4.0
[1.3.2]: https://github.com/rmacdframework/spec/releases/tag/v1.3.2
[1.3.1]: https://github.com/rmacdframework/spec/releases/tag/v1.3.1
[1.3.0]: https://github.com/rmacdframework/spec/releases/tag/v1.3.0
[1.2.1]: https://github.com/rmacdframework/spec/releases/tag/v1.2.1
[1.2.0]: https://github.com/rmacdframework/spec/releases/tag/v1.2.0
[1.1.0]: https://github.com/rmacdframework/spec/releases/tag/v1.1.0
[1.0.2]: https://github.com/rmacdframework/spec/releases/tag/v1.0.2
[1.0.1]: https://github.com/rmacdframework/spec/releases/tag/v1.0.1
[1.0.0]: https://github.com/rmacdframework/spec/releases/tag/v1.0.0
