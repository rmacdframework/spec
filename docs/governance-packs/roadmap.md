# Governance Packs — Delivery Roadmap

**Status:** Delivered in `rmacd-framework` 0.11.0 (Phases 0–6); the catalog and
approval surface were extended in 0.12.0 (see [Post-0.11.0](#post-0110-follow-on-work)).
Companion documents: [README](README.md), [design](design.md),
[authoring guide](authoring-guide.md).

This roadmap sequenced the work into seven phases. Each phase was independently
reviewable and left the SDK in a shippable state; the ordering front-loaded the
foundation and validated the declarative language against the hardest known case
(`shell`) before investing in breadth. All seven phases are implemented and
tested (see `rmacd.packs` and the `tests/test_packs_*.py` suites).

### Status at a glance

| Phase | Scope | Status | Shipped in |
|-------|-------|--------|------------|
| 0 | Schema & models | ✅ Complete | 0.11.0 |
| 1 | Declarative engine | ✅ Complete | 0.11.0 |
| 2 | Loading, registration, serialization, resolvers | ✅ Complete | 0.11.0 |
| 3 | Built-in packs | ✅ Complete | 0.11.0 (+3 IAM packs in 0.12.0) |
| 4 | AI-compile authoring | ✅ Complete | 0.11.0 |
| 5 | Signing & drift | ✅ Complete | 0.11.0 |
| 6 | Docs, examples, adapters, release | ✅ Complete | 0.11.0 |
| — | Post-0.11.0 follow-on (0.12.0) | ✅ Complete | 0.12.0 |
| — | Normative spec · visual editor · control plane | ⏳ Deferred (not scheduled) | — |

**No phase is pending** — the roadmap is fully delivered. The only outstanding
items are the deliberately [out-of-scope](#out-of-scope-deliberately-deferred)
future initiatives at the bottom.

---

## Phase 0 — Schema & models

**Status:** ✅ Complete — shipped in 0.11.0.

**Goal:** a validated, hashable pack representation.

- `schemas/pack.schema.json` (pack, rule, selector, extractor, classifier).
- Pydantic/data models in `rmacd.packs`.
- Canonical JSON serialization and `content_hash`.
- Validation via the existing `ProfileValidator` pattern.

**Exit criteria:** packs round-trip losslessly; schema validation and canonical
hashing are stable and tested.

## Phase 1 — Declarative engine

**Status:** ✅ Complete — shipped in 0.11.0.

**Goal:** turn a pack rule into a working classifier.

- `DeclarativeClassifier` implementing the existing `ToolClassifier` protocol.
- Selectors (`tool` exact/glob/regex; argument predicates).
- Extraction/`parse` (wrapper stripping, tokenization, `$(...)` recursion).
- `verb_table` with MAX-operation combination and fail-closed default.
- `pattern_map` tier (most-sensitive wins) and target templating.
- Cross-rule combination: highest operation, most sensitive tier.

**Exit criteria:** behavior parity with a representative subset of `bash.py`,
driven entirely by a data pack.

## Phase 2 — Pack loading, registration, serialization, resolvers

**Status:** ✅ Complete — shipped in 0.11.0.

**Goal:** packs become usable end-to-end in the SDK.

- `load_pack`, `load_packs`, `apply_pack(registry, pack)`.
- Extend `ToolDefinition.to_dict/from_dict` to (de)serialize declarative
  classifiers — closing the round-trip gap.
- Resolver registry: `register_resolver(name)`, fail-closed default, audit
  recording of resolved values.
- `PolicyEnforcer`/registry convenience: `load_packs([...])` one-liner.

**Exit criteria:** an exported registry preserves its dynamic classification;
resolvers fire and are audited.

## Phase 3 — Built-in packs

**Status:** ✅ Complete — shipped in 0.11.0; 3 cloud-IAM packs added in 0.12.0 (22 total).

**Goal:** ship a catalog that covers the bulk of enterprise agent surface.
Largest phase; sequenced shell-first for parity validation. Each pack ships as
wheel data with golden classification fixtures.

| Group | Packs |
|-------|-------|
| Shell | `shell` (port `bash.py`; **build first**) |
| Cloud CLIs | `aws`, `gcloud`, `az`, `kubectl` |
| Cloud IAM / identity | `aws-iam`, `az-identity`, `gcp-iam` *(added in 0.12.0)* |
| Dev tools | `github`, `gitlab`, `sql`, `filesystem` |
| SaaS / collab MCPs | `slack`, `google-drive`, `jira`, `confluence`, `postgres` |
| Cloud-provider MCPs | AWS `awslabs/mcp` suite (incl. the GA AWS API MCP), Azure MCP Server, Google Cloud MCP Toolbox for Databases + Cloud Run MCP |
| Microsoft 365 MCPs | Microsoft Graph / Work IQ — Outlook, Teams, SharePoint, OneDrive, Word, Dataverse |

**Passthrough tools** (AWS API MCP, GCP DB toolbox, Azure CLI generation) follow
the `bash`/`sql` pattern: arg-aware classification, worst-case capability
ceiling, fail-closed default, mandatory human review at compile time.

**Exit criteria:** each pack passes its golden fixtures; `shell` matches
`bash.py`.

## Phase 4 — AI-compile authoring

**Status:** ✅ Complete — shipped in 0.11.0.

**Goal:** drafting a pack for a new tool source is a reviewable workflow.

- `compile_pack()` on `MCPRegistryBridge` / the LLM classifier — emits a proposal
  pack with rationale, confidence, and provenance.
- CLI: `rmacd classify <source> -o pack.yaml`.
- CLI: `rmacd pack review` (surfaces the low-confidence and passthrough tail
  first).

**Exit criteria:** compiling a mocked tool source produces a proposal pack with
provenance and correctly flagged low-confidence entries.

## Phase 5 — Signing & drift

**Status:** ✅ Complete — shipped in 0.11.0.

**Goal:** packs are trustworthy and maintainable over time.

- `rmacd pack sign` / `pack verify` (ed25519 over `content_hash`).
- `source_hash` capture and `rmacd pack diff` (flag changed tools for re-review).
- Regex complexity guard and per-match timeout (ReDoS protection).

**Exit criteria:** tampering and drift are both detected by tests.

## Phase 6 — Docs, examples, adapters, release

**Status:** ✅ Complete — shipped in 0.11.0.

**Goal:** the capability is documented, demonstrated, and released.

- Rewrite `docs/framework-adapters.md`: every adapter becomes "load packs, no
  classifier code".
- New example: onboard an MCP server (e.g. Jira/Confluence) via a compiled,
  signed pack.
- Update `docs/implementation.md`.
- Migrate existing examples from hand-written classifiers to `load_packs(...)`,
  demonstrating the LoC reduction.
- Version bump to SDK 0.11.0, CHANGELOG, tag `sdk-v0.11.0`, publish.

**Exit criteria:** 0.11.0 published; examples run on packs.

---

## Post-0.11.0 follow-on work

Incremental hardening delivered after the initial 0.11.0 cut. These are additive
— no runtime or API breaks, and the determinism/§12.5 invariants are unchanged.

### 0.12.0 — Cloud IAM packs + CLI approval gateway

- **3 cloud-identity built-in packs** — `aws-iam`, `az-identity`, `gcp-iam` —
  bringing the built-in catalog to **22 packs**. They overlay the corresponding
  cloud CLI (`aws` / `az` / `gcloud`) and map the most-sensitive
  IAM / directory / secrets / KMS operations to the `restricted` tier, so a
  Change/Delete on those surfaces meets the §12.5 floor. Golden fixtures cover
  every Delete/Change path; the reference catalog (`catalog.md`) is regenerated
  from the pack data.
- **`CLIApprovalGateway` promoted into the SDK** (`rmacd.approval`) — an
  interactive stdin/stderr approval surface, so an approval-gated agent is
  testable straight from `pip install` with no example glue. It fails closed on
  EOF and joins the existing `RejectAllApprovalGateway` (default) and
  `AutoApproveGateway`; the agent examples now import it from the SDK.

**Exit criteria:** identity packs pass their golden fixtures; the SDK ships a
ready-to-use interactive approval gateway; 0.12.0 published.

---

## Success metrics

- **Integration LoC for a new agent drops from ~60–105 to ~0** (pack references
  plus a small number of shared resolvers).
- **Classification is reusable**: the same pack governs LangChain, OpenAI, and
  Claude agents identically.
- **Runtime determinism preserved**: enforcement never invokes an LLM; the
  source of truth is a signed data file.
- **Round-trip fidelity**: an exported registry no longer loses dynamic
  classification.
- **Auditability**: every classification decision, including resolver lookups,
  is reconstructable from the pack version plus the audit record.

## Out of scope (deliberately deferred)

- A normative specification of the pack format (revisit after field validation).
- A visual pack editor or custom DSL beyond the fixed primitive set.
- Network-level / proxy enforcement and a central control plane (separate
  initiatives).
