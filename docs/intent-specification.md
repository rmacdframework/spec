# RMACD Intent Specification

**Version:** 2.0.0
**Status:** Normative
**Companion to:** `RMACD_Framework_v1.4.md` (§2.4, §3, §12)
**Narrative companion:** [`intents.md`](intents.md) — the model and its rationale
**Schemas:** `schemas/intent.schema.json`, `schemas/intent-decision.schema.json`
(published as `schema/v2/`; the field rename in 2.0.0 is not backward compatible)

This document specifies the intent envelope, the actor model, the adjudication
contract, the decision record, and the conformance requirements for an RMACD
Intent implementation. It is versioned independently of the framework
specification. It adds no autonomy levels, no governance matrix, and no
permission semantics; where it refers to those, the framework specification
governs.

The key words **MUST**, **MUST NOT** and **MAY** in this document are to be
interpreted as described in BCP 14 [RFC
2119](https://www.rfc-editor.org/rfc/rfc2119) and [RFC
8174](https://www.rfc-editor.org/rfc/rfc8174) when, and only when, they appear
in all capitals, as shown here. The same words in lower case carry their
ordinary English meaning and impose no requirement.

Per RFC 2119 §6, these imperatives appear only where they are needed for
interoperation or to limit behaviour that could cause harm. Explanatory
passages state their reasoning in plain words. Every capitalised keyword in
this document sits inside a numbered requirement, and `tools/check_spec.py`
enforces that.

**This specification uses no SHOULD and no SHOULD NOT.** RFC 2119 §4 permits
an implementation to disregard a **SHOULD** where it judges the reasons
sufficient. Adjudication is a grading function that **MUST** be reproducible
across implementations (N-21), so advice an implementer may decline would let
two conformant engines answer the same governance failure differently — and
the rules that would have been advisory are precisely the consequential ones:
demotion after a mismatch, demotion after divergence, marking revoked children
for review, carrying `intent_id` into the execution path. Each limits
behaviour with potential for harm, which is where RFC 2119 §6 directs an
author to use **MUST**. This specification therefore states obligations and
latitude, and nothing in between: what an implementation has to do is a
**MUST**, what it is free to choose is a **MAY**. The synonyms RFC 2119
permits — SHALL, REQUIRED, RECOMMENDED, OPTIONAL — are unused; the three
keywords above are the whole vocabulary.

## Contents

- [1. Scope and terminology](#1-scope-and-terminology)
- [2. The intent envelope](#2-the-intent-envelope)
- [3. The actor model](#3-the-actor-model)
- [4. Intent types](#4-intent-types)
- [5. The adjudication contract](#5-the-adjudication-contract)
- [6. Action patterns and precedent](#6-action-patterns-and-precedent)
- [7. Grants: campaigns and exceptions](#7-grants-campaigns-and-exceptions)
- [8. Budgets, demotion and emergencies](#8-budgets-demotion-and-emergencies)
- [9. The decision record](#9-the-decision-record)
- [10. Reconciliation with interception](#10-reconciliation-with-interception)
- [11. Conformance](#11-conformance)
- [Appendix A: Requirement Quick Reference](#appendix-a-requirement-quick-reference)

---

## 1. Scope and terminology

| Term | Definition |
|---|---|
| **Intent** | A structured declaration of an action an actor wants to take, submitted for adjudication before it is taken |
| **Adjudication** | The deterministic computation of a required autonomy level from a declared intent |
| **Base level** | The autonomy level the framework's effective matrix requires for the declared `(classification, operation)` |
| **Escalation** | Monotonic movement of a level toward greater oversight along the §2.4 ladder |
| **Action pattern** | The canonical equivalence class over which precedent is computed (§6) |
| **Grant** | A pre-recorded human disposition covering a bounded class of future intents (§7) |
| **Disposition** | A human decision recorded against an adjudicated intent |
| **Decision record** | The durable evidence artifact produced by every adjudication (§9) |
| **Reconciliation** | Comparison of a declared intent against the interception record of what was executed (§10) |

The **autonomy ladder** is the ordered list defined in framework §2.4:

```
0 autonomous  →  1 logged  →  2 notification  →  3 approval
              →  4 elevated_approval  →  5 prohibited
```

Escalation moves along this list toward higher indices only, and saturates
at index 4. Index 5 is not an escalation destination: `prohibited` is reached
only via the pinned or extended floor (N-14a, N-14b).

---

## 2. The intent envelope

Every intent, of every type, is a single JSON object conforming to
`schemas/intent.schema.json`.

### 2.1 Common fields

| Field | Required | Type | Notes |
|---|---|---|---|
| `$schema` | No | string | `https://rmacd-framework.org/schema/v2/intent.json` |
| `intent_id` | **Yes** | string | `^int-[a-z0-9][a-z0-9-]*$`; unique within the issuing organization |
| `intent_type` | **Yes** | string | A registered type (§4) |
| `submitted_at` | **Yes** | date-time | RFC 3339, UTC |
| `actor` | **Yes** | object | §3 |
| `declaration` | **Yes** | object | The declared facts (§2.2) |
| `justification` | No | string | Free text; never an adjudication input |
| `composes` | Conditional | array of `intent_id` | Required by composite types (§4) |
| `requires` | Conditional | array of `intent_id` | Required by dependent types (§4) |
| `grant_ref` | No | `intent_id` | A campaign or exception this intent claims coverage from (§7) |
| `compliance_tags` | No | array of string | Framework §10 vocabulary; a closed enum in the schema |
| `provenance` | No | object | `rationale_ref`, `produced_by`, `source_intent_id` |
| `valid_until` | Conditional | date-time | RFC 3339, UTC; **required** on production-plane types (N-52) |
| `metadata` | No | object | Organization-local; never an adjudication input |

**N-1 (Reject, Never Default).** <a id="n-1"></a>An implementation **MUST** reject an intent that fails schema
validation. It **MUST NOT** adjudicate a malformed intent, and **MUST NOT**
fall back to a default level.

**N-2 (Unlisted Fields Are Inert).** <a id="n-2"></a>Fields not listed in this specification or the schema **MUST NOT**
influence adjudication. `justification`, `metadata` and `provenance` are
recorded and surfaced to humans, but are never adjudication inputs.

### 2.2 The declaration block

The declaration carries the facts the engine grades.

| Field | Required | Type | Notes |
|---|---|---|---|
| `operation` | **Yes** | `R` \| `M` \| `A` \| `C` \| `D` | Framework §2.2 |
| `target` | **Yes** | string | The resource acted upon |
| `target_class` | No | string | Normalized target pattern; derived if absent (§6.2) |
| `data_classification` | Conditional | `public` \| `internal` \| `confidential` \| `restricted` | Required in 3D and DC2D deployments |
| `environment` | **Yes** | `development` \| `staging` \| `production` \| `disaster-recovery` \| `sandbox` | Framework environment vocabulary |
| `reversibility` | No | object | `rollback_declared`, `rollback_plan`, `attested_by` |
| `blast_radius` | No | object | `scope_percentage`, `affected_count` |

The declaration carries no impact axis of its own. Where an organization
substitutes one, it is declared in the bound profile and stamped into the
decision record, never supplied by the actor (N-8, N-16, §5.3).

**N-3 (Classification Required, Never Guessed).** <a id="n-3"></a>In a 3D or
DC2D deployment, `data_classification` **MUST** be present. Where a
classification is missing, an implementation **MUST** treat it as the most
sensitive tier the deployment recognizes.

**N-4 (Rollback Buys No Discount).** <a id="n-4"></a>
`reversibility.rollback_declared` **MUST NOT** lower a computed level. The base
level is the minimum in every case (§5.2). Where a rollback claim is attested by
a party other than the requesting actor, `attested_by` **MUST** identify that
party.

**N-52 (Every Intent Expires).** <a id="n-52"></a>A production-plane intent
**MUST** declare `valid_until`, an RFC 3339 timestamp after which its
adjudication authorizes nothing. An implementation **MUST NOT** permit execution
once `valid_until` has passed, and **MUST** record the reconciliation result
`unexecuted` where the intent was never executed. Where an intent cites a grant,
the earlier of `valid_until` and the grant's `expires_at` governs.

---

## 3. The actor model

```json
"actor": {
  "kind": "agent",
  "id": "devops-agent-007",
  "authorization": "spiffe://corp/ns/agents/devops-agent-007",
  "on_behalf_of": "platform-team@company.com"
}
```

| Field | Required | Notes |
|---|---|---|
| `kind` | **Yes** | `agent`, `pipeline`, or `human` |
| `id` | **Yes** | Stable identifier for the actor |
| `authorization` | **Yes** | A reference an implementation can resolve to verify the actor |
| `on_behalf_of` | Conditional | **Required** when `kind` is `agent` or `pipeline` |

**N-5 (Every Agent Has a Human).** <a id="n-5"></a>An implementation **MUST** reject an `agent` or `pipeline` intent whose
`on_behalf_of` is absent or does not resolve to an accountable human or team.

**N-6 (Fail Closed on Unknown Actors).** <a id="n-6"></a>Where `authorization`
cannot be resolved, the implementation **MUST** fail closed. Every operation
except `R` escalates to at least `approval`, whatever the matrix would
otherwise compute. `R` escalates the same way on `confidential` and
`restricted` data, and in any deployment that recognizes no classification
tier. The decision record **MUST** record `unresolved_authorization` as an
escalation factor.

**N-7 (Kind Routes, Never Grades).** <a id="n-7"></a>Adjudication **MUST** be actor-kind-agnostic. `kind` **MUST NOT**
influence the computed level. It **MAY** determine approval routing and
**MUST** be recorded for accountability.

**N-8 (No Self-Assigned Rating).** <a id="n-8"></a>An actor **MUST NOT** be able to assert its own rating. An
implementation **MUST** ignore any field in a submitted intent that names an
autonomy level, an impact grade, or a likelihood grade.

---

## 4. Intent types

Types are an open registry. A registered type declares its plane, its
composition obligations, and any additional required fields.

| Type | Plane | Maturity | Required beyond the envelope | Composition |
|---|---|---|---|---|
| `change` | Production | Stable | — | Lattice root |
| `release` | Production | Stable | `composes` (≥ 1 `change`) | Composite |
| `deployment` | Production | Stable | `requires` (exactly 1 `release`) | Dependent |
| `service_request` | Production | Stable | `catalogue_ref` | Grants over `change` |
| `decommission` | Production | Incubating | `composes` (≥ 1 `change`), `stages` | Composite |
| `maintenance_window` | Production | Incubating | `window.start`, `window.end`, `service_commitment` | Cited by `deployment` |
| `continuity_invocation` | Production | Incubating | `plan_ref`, `trigger` | Grant + trigger |
| `incident` | Record | Stable | `severity`, `dedup_key` | Produces `change` |
| `campaign` | Grant | Stable | `class_predicate`, `caps`, `expires_at` | Grants over `change` |
| `exception` | Grant | Stable | `base_profile_id`, `exception_category`, `escalated_permissions`, `expires_at` | Grants over `change` |

Only `campaign` and `exception` are grants in the sense of §7, and only they
carry the grant machinery — `class_predicate`, `caps`, `escalated_permissions`,
`expires_at`. `service_request` and `continuity_invocation` are described as
pre-authorized because their authorization is recorded outside the intent system
— in a service catalogue entry and in an approved continuity plan respectively —
and §7's requirements do not apply to them.

**N-9 (Maturity Is Not Rank).** <a id="n-9"></a>Maturity labels (`Stable`, `Incubating`) signal semantic stability
only. An implementation **MUST NOT** treat maturity as a rank, a trust level, or
an adjudication input.

**N-10 (One Envelope, One Contract).** <a id="n-10"></a>A new type **MUST** register against the common envelope and this
adjudication contract. A type that requires different adjudication semantics is
out of scope for this specification.

**N-11 (Composites Inherit the Worst).** <a id="n-11"></a>For any composite intent, the computed level
**MUST** be the most restrictive level among the composite itself and all
intents it composes or requires. Membership in a composite **MUST NOT** lower
any child's own computed level.

**N-53 (Same Incident, Same Key).** <a id="n-53"></a>`dedup_key` **MUST** be
computed the same way every time, from the field set the deployment declares in
its bound profile. An implementation **MUST** record which rule produced it.

**N-54 (The System's Key Wins).** <a id="n-54"></a>A `dedup_key` supplied by
the actor **MUST NOT** create a new incident identity; it **MAY** only join an
existing one. Where a supplied key and a computed key disagree, the computed key
governs and the discrepancy **MUST** be recorded.

---

## 5. The adjudication contract

### 5.1 The algorithm

Adjudication is the following sequence.

**N-50 (Steps Run In Order).** <a id="n-50"></a>An implementation **MUST**
apply these steps in the order given.

```
1. Validate the envelope.                        → reject if malformed        (N-1)
2. Resolve the actor.                            → unresolved ⇒ fail closed   (N-6)
3. Check the prohibited floor.                   → pinned/extended ⇒ stop     (N-12)
4. base  := effective_matrix[classification][operation]                       (N-13)
5. steps := Σ likelihood factors                 → each ≥ 0                   (N-17)
6. level := ladder[min(index(base) + steps, 4)]  → saturates below prohibited (N-14a)
7. Apply the composition floor for composite types.                           (N-11)
8. Apply grant coverage, if any.                 → discharges, never lowers   (N-27)
9. Emit the decision record.                     → durable, append-only       (N-43)
```

**N-12 (The Permanent No).** <a id="n-12"></a>Before any other computation, an implementation
**MUST** return `prohibited` for any intent whose declared
`(data_classification, operation)` falls in the framework's §12.5 set —
`(restricted, A)`, `(restricted, C)`, `(restricted, D)`. This result **MUST NOT**
be reachable by escalation configuration, grant coverage, emergency escalation,
or any organizational override.

The same step **MUST** also apply any prohibition the organization has extended
the floor with (N-14b). Extended prohibitions are checked here, alongside the
pinned set, so that both are evaluated before any permission, override or
escalation path is consulted — mirroring how the SDK evaluator applies
`IMMUTABLE_PROHIBITIONS`.

**N-13 (One Matrix, No Second).** <a id="n-13"></a>The base level **MUST** be derived from the framework's
effective matrix for the actor's bound profile — the §3.1 defaults as adjusted
by that profile's `autonomy_overrides`. An implementation **MUST NOT** define a
second matrix, and **MUST NOT** compute a base level from any other source.
In a 2D deployment the effective matrix is indexed by operation alone; in 3D and
DC2D deployments it is indexed by `(classification, operation)`.

**N-14 (The Monotonicity Rule).** <a id="n-14"></a>The computed level **MUST**
be at least as restrictive as the base level. A factor, grant, emergency,
attestation or configuration **MUST NOT** move a level toward lower oversight.

**N-14a (Escalation Stops Below Prohibited).** <a id="n-14a"></a>Escalation **MUST** saturate at `elevated_approval`.
Likelihood **MUST NOT** move an intent to `prohibited`.

`prohibited` means no human disposition can authorize the action for an
autonomous actor. That is a categorical statement about the action itself, not
a function of how novel or how poorly-attested a particular request is.
An unprecedented action can reasonably demand the CISO; it cannot be allowed to make an action
categorically impossible. An implementation that let escalation reach the end
of the ladder would turn routine production work on sensitive data — already
at `elevated_approval` in the §3.1 defaults — into a deterministic deny on its
first occurrence.

**N-14b (Two Sources of Prohibited).** <a id="n-14b"></a>An intent **MUST** compute to `prohibited` only
via one of exactly two sources:

| Source | Origin | Mutability |
|---|---|---|
| `pinned` | Framework §12.5 — A, C or D on Restricted | Immutable; never removable |
| `extended` | An organization's own declared prohibition | Extensible by the organization; **never** shrinkable below the pinned set |

An organization **MAY** extend the prohibited region by declaring additional
cells in its bound profile. It **MUST NOT** remove or narrow any pinned cell.

### 5.2 Why monotonicity is non-negotiable

The actor supplies the facts. Any mechanism capable of lowering a level would
therefore let an actor rate itself by choosing what to declare. Under monotonic
escalation, risk-reducing facts do not subtract oversight — they only fail to
add it — so the worst outcome of a false declaration is the framework's own
v1.4 baseline. Misdeclaration is then handled by reconciliation (§10) and
demotion (§8), not by the grading function.

### 5.3 Impact

**N-15 (Classification Is Impact).** <a id="n-15"></a>The impact dimension **MUST** be the deployment's data classification
tier, ordered `public < internal < confidential < restricted`.

**N-16 (Declare Any Impact Substitute).** <a id="n-16"></a>An organization
**MAY** substitute or supplement classification with another impact basis
(CMDB criticality, service tier). Where it does, the substitution **MUST** be
declared in the bound profile, **MUST** map onto the same four-tier ordering,
and **MUST** be stamped into every decision record via `impact_basis`. The
intent envelope carries no impact axis. An implementation **MUST NOT** accept
an impact basis supplied in the intent itself, and the schema provides no
field through which an actor could supply one (N-8).

### 5.4 Likelihood factors

**N-17 (The Five Likelihood Factors).** <a id="n-17"></a>An implementation **MUST** implement all five factors below. Each
contributes a non-negative number of escalation steps.

| # | Factor | Condition | Default steps |
|---|---|---|---|
| L1 | Unprecedented | No confirmed prior success of this action pattern (§6) | +1 |
| L2 | Reversibility | No attested rollback path | +1 |
| L3 | Environment | `production` or `disaster-recovery` | +1 |
| L4 | Budget standing | Actor at or over budget, or currently demoted | +2 |
| L5 | Blast radius | Declared scope exceeds the profile's cap | +2 |
| | | Declared scope within 80% of the cap | +1 |

**N-18 (Weights Adjustable, Never Negative).** <a id="n-18"></a>An organization **MAY** adjust these weights. Every weight **MUST**
remain ≥ 0; a negative weight **MUST** be rejected at configuration load. The
effective weight table **MUST** carry a version identifier, and that identifier
**MUST** be stamped into every decision record.

**N-19 (Factors Only Add).** <a id="n-19"></a>An implementation **MUST NOT**
introduce a factor that can contribute negative steps.

**N-51 (Declared Inputs Get Checked).** <a id="n-51"></a>An implementation
**MAY** compute a factor from a value the intent declares. Where it does, that
value **MUST** be attested by a party other than the requesting actor, or
compared against execution by reconciliation (§10).

### 5.5 The profile remains a ceiling

**N-20 (Approval Is Not Permission).** <a id="n-20"></a>Adjudication **MUST NOT** grant permission. A favourable
adjudication, an approved grant, and a recorded human disposition, singly or
together, **MUST NOT** authorize an operation the actor's bound profile or a
tool capability ceiling forbids. An intent that adjudicates successfully and is
subsequently refused by interception is conformant behaviour.

### 5.6 Determinism

**N-21 (Same Inputs, Same Level).** <a id="n-21"></a>Adjudication **MUST** be reproducible. Given the same intent, matrix
version, likelihood weight-table version, policy version, and decision-log
epoch, an implementation **MUST** produce the same level. The four version
inputs **MUST** be recorded in the decision record (§9), alongside the
`intent_id` that identifies the intent they were applied to.

Adjudication is deterministic but not stateless: precedent and budget standing
read organizational state. Reproducibility is therefore defined against a
recorded log epoch rather than against the intent alone.

---

## 6. Action patterns and precedent

Precedent is what lets a well-trodden action stop costing human
attention. The equivalence class it is computed over is consequently the most
security-sensitive definition in this specification: **whatever the action pattern
excludes becomes a gradient an actor can descend to erode its own scrutiny.**

### 6.1 The action pattern key

**N-22 (The Six-Field Pattern Key).** <a id="n-22"></a>The action pattern key **MUST** be a SHA-256 hash over the canonical JSON
serialization of exactly these fields, and **MUST NOT** include any other field:

| Field | Rationale for inclusion |
|---|---|
| `intent_type` | Standing earned as one type is not spendable as another |
| `declaration.operation` | Standing earned reading is not spendable deleting |
| `declaration.data_classification` | Standing earned on public data is not spendable on confidential |
| `declaration.environment` | Standing earned in staging is not spendable in production |
| `declaration.target_class` | The normalized target, never the literal target (§6.2) |
| `actor.kind` | Standing earned by a supervised pipeline is not spendable by an autonomous agent |

Literal target identifiers, timestamps, justification text, metadata, and the
actor's own `id` are excluded, so that the same governed action against a
hundred hosts converges on one action pattern rather than a hundred.

### 6.2 Target normalization

**N-23 (Same Target, Same Class).** <a id="n-23"></a>`target_class` **MUST**
be computed the same way every time. Where a Governance Pack rule or profile
constraint matched, it is the target pattern that rule declared. Otherwise it
is the target with its final identifier segment replaced by `*`. An
implementation **MUST** record which rule produced the normalization.

**N-24 (The System's Class Wins).** <a id="n-24"></a>An implementation **MUST NOT** accept a `target_class` supplied by the
actor in preference to a derived one. Where both exist and disagree, the derived
value governs and the discrepancy **MUST** be recorded.

### 6.3 What counts as a confirmed success

**N-25 (Only Checked Successes Count).** <a id="n-25"></a>A prior decision
**MUST NOT** count toward precedent unless all of the following hold:

1. The intent was adjudicated and received a disposition permitting execution.
2. Execution was **reconciled** (§10) — an interception record or an attested
   post-execution confirmation, joined on `intent_id`, reports success.
3. Reconciliation found no material discrepancy between declared and executed
   facts.

A declared-but-unreconciled outcome **MUST NOT** accrue standing. This closes
precedent farming by declaration: an actor cannot earn standing simply by
submitting intents.

**N-26 (A Mismatch Wipes Precedent).** <a id="n-26"></a>Where reconciliation
detects a material discrepancy, the implementation **MUST** clear that action
pattern's accrued precedent and demote the actor (§8).

---

## 7. Grants: campaigns and exceptions

A grant is a pre-recorded human disposition covering a bounded class of future
intents. Grants are the mechanism by which humans govern classes rather than
instances — and the mechanism most capable of laundering privilege if loosely
specified.

### 7.1 Coverage is discharge, not reduction

**N-27 (Grants Approve, Never Lower).** <a id="n-27"></a>A grant **MUST NOT** change a child intent's computed level. It
**MAY** discharge the child's approval requirement by supplying a recorded
human disposition in advance.

**N-28 (Coverage Is All or Nothing).** <a id="n-28"></a>A child is covered only when **all** of the following hold. If any
fails, the child **MUST** route for individual human disposition:

1. The child falls inside the bounds the grant declared — every field of a
   `campaign`'s `class_predicate` matches the child (§7.2), or the child's
   `(classification, operation)` falls inside an `exception`'s
   `escalated_permissions` grid.
2. Where the grant declares `caps.max_level`, the child's computed level is no
   more restrictive than that level — the level the human approved the grant at.
3. The grant is active: `expires_at` is in the future and it has not been
   revoked.
4. No declared cap is exhausted — `max_children`,
   `max_blast_radius_percentage`.
5. The child's computed level is not `prohibited`, whether pinned or extended
   (N-14b).

**N-29 (No Grant Covers Prohibited).** <a id="n-29"></a>A grant **MUST NOT** cover a `prohibited` child under any
circumstance, and **MUST NOT** be construed as an exception to framework §12.5.

### 7.2 Class predicates

**N-30 (The Closed Predicate Fields).** <a id="n-30"></a>A `class_predicate` **MUST** be evaluated deterministically and
**MUST** match only on this closed set of fields:

`intent_type`, `declaration.operation`, `declaration.data_classification`,
`declaration.environment`, `declaration.target_class`, `actor.id`,
`actor.on_behalf_of`.

The predicate names these flattened, as `intent_type`, `operation`,
`data_classification`, `environment`, `target_class`, `actor_id` and
`on_behalf_of`; the schema admits no other key.

**N-31 (Match All, Never Execute).** <a id="n-31"></a>All specified fields
**MUST** match conjunctively. Wildcards **MUST NOT** appear in any field
except `target_class`. A predicate **MUST NOT** match on `justification`,
`metadata`, or any free-text field, and **MUST NOT** be expressed as
executable code.

**N-32 (No Blanket Grants).** <a id="n-32"></a>A predicate that specifies no fields, or that would match every
intent of a type, **MUST** be rejected at grant submission. Blanket grants are
prohibited by framework §12.5.

### 7.3 Caps, expiry and revocation

**N-33 (Every Grant Expires and Caps).** <a id="n-33"></a>Every grant **MUST**
declare `expires_at`. Indefinite or open-ended grants **MUST** be rejected,
per framework §12.5. A `campaign` **MUST** additionally declare
`caps.max_children` and `caps.max_level`, because its bounds are otherwise
only a predicate. An `exception` is bounded instead by its
`escalated_permissions` grid and by the maximum duration its §12.2 category
fixes; it **MAY** declare `caps` in addition.

**N-34 (Revocation Is Immediate).** <a id="n-34"></a>Revocation **MUST** take effect immediately. Intents adjudicated after
revocation **MUST NOT** be covered.

**N-35 (Past Dispositions Stand).** <a id="n-35"></a>A child already
dispositioned when the grant is revoked stays validly dispositioned. The
implementation **MUST** record it as affected by the revocation and mark it
for human review.

**N-55 (Caps Count Once).** <a id="n-55"></a>Checking a grant's caps and
consuming capacity against them **MUST** be one atomic operation. A grant's
lifecycle transitions **MUST** be totally ordered with respect to coverage
decisions. Where an implementation cannot establish that order, the child
**MUST** route for individual human disposition.

### 7.4 The `exception` type

The `exception` type expresses framework §12.3's five-step process. Framework
§12.4's exception profile template *is* an `exception` intent: from framework
revision 1.4.1 the template is written in this envelope and points at
`schema/v2/intent.json`, so the framework carries one request path rather than
two. The `schema/v1/exception.json` URL that §12.4 advertised from v1.0 but
never published is retired rather than filled in.

| §12.3 step | Intent-model equivalent |
|---|---|
| 1. Request Submission | An `exception` intent is submitted |
| 2. Risk Assessment | Adjudication computes the required level |
| 3. Approval Decision | The §12.2 authority records a disposition |
| 4. Exception Activation | The grant becomes active; caps and expiry enforced |
| 5. Exception Closure | Expiry or revocation; the decision record closes |

Beyond the envelope, an `exception` carries the fields framework §12.3 Step 1
requires of a request:

| Field | Required | Notes |
|---|---|---|
| `base_profile_id` | **Yes** | The profile being temporarily widened |
| `exception_category` | **Yes** | `emergency`, `urgent`, `planned` or `extended` — framework §12.2, which fixes the maximum duration and the approval authority |
| `escalated_permissions` | **Yes** | Per-tier operation lists; `restricted` admits only `R` and `M` (N-36) |
| `expires_at` | **Yes** | The explicit expiration §12.5 requires (N-33) |
| `compensating_controls` | No | Monitoring or restriction applied for the life of the grant; `enhanced_logging` may only ever be `true` |
| `rollback_plan` | No | How the widening is undone if it causes issues |
| `caps` | No | Optional additional bounds (N-33) |
| `status` | No | Grant lifecycle state: `requested`, `active`, `expired`, `revoked`, `closed`. Shared with `campaign` |

Approval fields are deliberately absent from the request. Who approved, when,
and at what level are recorded as the *disposition* on the decision record (§9),
never asserted by the requester (N-8).

**N-36 (The Five Named Prohibitions).** <a id="n-36"></a>An `exception` intent **MUST** be rejected if it would escalate
`restricted` beyond `["R", "M"]`, omit `expires_at`, remove audit logging,
apply a profile across environments, or request a blanket grant. These are
framework §12.5's five named prohibitions. Two of the five are enforced by the
schema at authoring time — `escalated_permissions.restricted` admits only `R`
and `M`, and `expires_at` is required — and `compensating_controls`
`enhanced_logging`, where present, may only be `true`. The remaining
prohibitions are not expressible in a per-document schema and **MUST** be
enforced by the implementation at grant submission.

**N-37 (Scrutiny, Not the Decision).** <a id="n-37"></a>Adjudication of an `exception` computes the scrutiny the request
requires. It **MUST NOT** decide whether the exception is granted; that
disposition belongs to the authority named in framework §12.2.

---

## 8. Budgets, demotion and emergencies

### 8.1 Budgets

**N-38 (Budgets Come From the Profile).** <a id="n-38"></a>Budget standing **MUST** be derived from the actor's bound profile
constraints — `rate_limits`, `change_controls`, and
`max_blast_radius_percentage`. An implementation **MUST NOT** define a parallel
budget vocabulary.

**N-39 (Breach Escalates, Never Denies).** <a id="n-39"></a>Budget breach **MUST** produce escalation (factor L4), never a silent
denial and never a reduction.

### 8.2 Demotion

**N-40 (Demotion Is Escalation).** <a id="n-40"></a>Demotion **MUST** be expressed as escalation, not as a new state. A
demoted actor's intents escalate by the L4 weight until the demotion expires or
is lifted. The decision record **MUST** record demotion as an escalation factor
with its cause.

### 8.3 Emergencies

**N-41 (Emergencies Raise the Ceiling).** <a id="n-41"></a>An intent **MAY** cite an active emergency escalation defined by its
profile's `emergency_escalation` block. Citing an emergency raises the
*permission ceiling* only.

**N-42 (Emergencies Never Lower Grades).** <a id="n-42"></a>An emergency **MUST NOT** lower a computed level, **MUST NOT** waive
an escalation factor, and **MUST NOT** affect the §12.5 pinned cells. The
profile's `trigger_conditions`, `max_duration_minutes`, `cooldown_minutes` and
`require_post_incident_review` apply unchanged.

---

## 9. The decision record

Every adjudication produces exactly one decision record, conforming to
`schemas/intent-decision.schema.json`. The decision record is simultaneously the
evidence artifact and the precedent memory.

| Field | Required | Notes |
|---|---|---|
| `$schema` | No | `https://rmacd-framework.org/schema/v2/intent-decision.json` |
| `decision_id` | **Yes** | `^dec-[a-z0-9][a-z0-9-]*$` |
| `intent_id` | **Yes** | The adjudicated intent; the join key for reconciliation |
| `decided_at` | **Yes** | RFC 3339, UTC |
| `action_pattern_key` | **Yes** | §6.1 |
| `base_level` | **Yes** | Before escalation |
| `computed_level` | **Yes** | After escalation, composition and floor |
| `escalation_factors` | **Yes** | Array of `{factor, steps, cause}`, `factor` and `steps` required; the five §5.4 factors plus `unresolved_authorization` (N-6) and `composition_floor` (N-11). Empty if none fired |
| `impact_basis` | **Yes** | Classification, or the declared substitute (N-16) |
| `matrix_version` | **Yes** | Reproducibility input |
| `likelihood_weights_version` | **Yes** | Reproducibility input |
| `policy_version` | **Yes** | Reproducibility input |
| `log_epoch` | **Yes** | Reproducibility input |
| `profile_id` | **Yes** | The bound profile that supplied the ceiling |
| `grant_ref` | No | The grant that discharged approval, if any |
| `disposition` | No | `{outcome, approver, decided_at, note}`, `outcome` and `decided_at` required; `outcome` is one of framework §12.3 Step 3's four decisions |
| `prohibition_source` | Conditional | `pinned` or `extended`, when the level is `prohibited` (N-14b) |
| `reconciliation` | No | Populated after execution (§10) |

**N-43 (The Durable Decision Record).** <a id="n-43"></a>A decision record
**MUST** be durable and append-only. An implementation **MUST NOT** change a
decision record after emission. The only permitted additions are a
`disposition` and a `reconciliation` result.

**N-44 (Name the Prohibition Source).** <a id="n-44"></a>Where the computed level is `prohibited`, `prohibition_source`
**MUST** distinguish `pinned` (framework §12.5) from `extended` (an
organization's own declared prohibition), per N-14b. Escalation is never a
source: likelihood cannot reach `prohibited` (N-14a).

**N-45 (One Audit Trail).** <a id="n-45"></a>Decision records **MUST** join the same audit trail as interception
records, on `intent_id`.

---

## 10. Reconciliation with interception

Reconciliation is the mechanism that makes declaration trustworthy. It compares
what an actor declared against what interception observed it do.

**N-46 (Carry the Intent ID Through).** <a id="n-46"></a>Where both modes are
deployed, an implementation **MUST** propagate `intent_id` into the execution
path so interception records carry it.

**N-47 (The Four Reconciliation Results).** <a id="n-47"></a>A reconciliation result **MUST** classify each executed action as one
of:

| Result | Meaning |
|---|---|
| `matched` | Executed action's operation, target class, classification, environment and scope match the declared intent |
| `divergent` | An executed action carried a different operation, target class, classification, environment or scope |
| `undeclared` | An executed action carried no `intent_id` and matched no open intent |
| `unexecuted` | An adjudicated intent was never executed before expiry |

**N-48 (Divergence Is a Governance Event).** <a id="n-48"></a>A `divergent` or
`undeclared` result **MUST** be recorded as a governance event in its own
right. It **MUST** clear the affected action pattern's accrued precedent
(N-26) and trigger demotion.

**N-49 (Unreconciled Is Not Matched).** <a id="n-49"></a>Where interception
coverage is missing, an implementation **MUST NOT** treat the action as
reconciled. Where an action cannot be reconciled, the decision record's
`reconciliation.result` **MUST** remain unset rather than being recorded as
`matched`.

---

## 11. Conformance

An implementation conforms to this specification when all of the following
hold. The list is exhaustive over obligations: every **MUST** and **MUST NOT**
in this document rolls up into exactly one item below, and `requirements.json`
records the mapping. One requirement is deliberately excluded: N-41's **MAY**
grants latitude rather than imposing an obligation, so there is nothing for a
conformance run to assert.

| # | Name | Requirement |
|---|---|---|
| <a id="c-1"></a>C-1 | Malformed Intents Rejected | Intents are validated against `intent.schema.json`; malformed intents are rejected, never defaulted (N-1) |
| <a id="c-2"></a>C-2 | The Permanent No Comes First | The §12.5 immutable floor is checked before any other computation and is unreachable by any override (N-12) |
| <a id="c-3"></a>C-3 | Single Source Matrix | The base level comes from the framework's effective matrix; no second matrix exists (N-13) |
| <a id="c-4"></a>C-4 | Never Less Restrictive | No mechanism can produce a level less restrictive than the base level (N-14) |
| <a id="c-4a"></a>C-4a | Escalation Saturates | Escalation saturates at `elevated_approval`; likelihood never reaches `prohibited` (N-14a) |
| <a id="c-5"></a>C-5 | Five Factors, No Negatives | All five likelihood factors are implemented; no weight is negative (N-17, N-18) |
| <a id="c-6"></a>C-6 | Pattern Key Exactly Six | The action pattern key covers exactly the six fields in §6.1 (N-22) |
| <a id="c-7"></a>C-7 | Precedent Comes From Checks | Precedent accrues only from reconciled successes (N-25) |
| <a id="c-8"></a>C-8 | Accountable Human Required | Non-human actors without a resolvable `on_behalf_of` are rejected (N-5) |
| <a id="c-9"></a>C-9 | Unknown Actors Fail Closed | Unresolvable authorization escalates non-Read operations to at least `approval`, and Read too on `confidential` and `restricted` (N-6) |
| <a id="c-10"></a>C-10 | Grants Never Change Levels | Grants discharge approval without changing computed levels, and never cover `prohibited` (N-27, N-29) |
| <a id="c-11"></a>C-11 | Predicates Closed and Declarative | Class predicates match only the closed field set, conjunctively, with no executable code (N-30, N-31) |
| <a id="c-12"></a>C-12 | Bounded and Expiring Grants | Every grant declares an expiry and a child cap; blanket and indefinite grants are rejected (N-32, N-33) |
| <a id="c-13"></a>C-13 | Profile Ceiling Holds | Adjudication never grants permission the bound profile withholds (N-20) |
| <a id="c-14"></a>C-14 | Reproducible Durable Records | Every adjudication emits a durable decision record carrying all four reproducibility inputs (N-21, N-43) |
| <a id="c-15"></a>C-15 | Prohibition Source Recorded | Prohibited decisions distinguish `pinned` from `extended` (N-44) |
| <a id="c-16"></a>C-16 | No False Matches | Unreconcilable executions are never recorded as `matched` (N-49) |
| <a id="c-17"></a>C-17 | The Envelope Is the Whole Input | Only fields this specification and the schema define may grade an intent; a missing classification resolves to the most sensitive tier; a rollback claim never lowers the level (N-2, N-3, N-4) |
| <a id="c-18"></a>C-18 | Actors Are Recorded, Not Trusted | Actor kind never changes the computed level, and no grade an actor asserts about itself is honoured (N-7, N-8) |
| <a id="c-19"></a>C-19 | The Type Registry Is Flat | Maturity is never a rank, and every registered type uses the common envelope and adjudication contract (N-9, N-10) |
| <a id="c-20"></a>C-20 | Composites Take the Worst | A composite computes to the most restrictive level among itself and its children, and never softens a child (N-11) |
| <a id="c-21"></a>C-21 | Prohibited Has Two Sources | `prohibited` is reachable only as `pinned` or `extended`, and the pinned set is never narrowed (N-14b) |
| <a id="c-22"></a>C-22 | Impact Is Declared, Not Supplied | Impact is the four-tier classification ordering, and any substitute is profile-declared and stamped into every record (N-15, N-16) |
| <a id="c-23"></a>C-23 | No Factor Subtracts | No likelihood factor contributes negative steps or takes its value from the intent without attestation (N-19) |
| <a id="c-24"></a>C-24 | One Target, One Class | `target_class` is computed the same way every time, and a value the actor supplies never wins (N-23, N-24) |
| <a id="c-25"></a>C-25 | A Mismatch Clears Precedent | A material mismatch found at reconciliation clears the affected action pattern's precedent and demotes the actor (N-26) |
| <a id="c-26"></a>C-26 | Coverage Needs Every Condition | A child is covered only when every one of the five coverage conditions holds (N-28) |
| <a id="c-27"></a>C-27 | Grants End Cleanly | Revocation takes effect immediately; children already dispositioned are recorded as affected and marked for human review (N-34, N-35) |
| <a id="c-28"></a>C-28 | Exceptions Stay Inside §12.5 | An exception tripping any of framework §12.5's five prohibitions is rejected, and adjudication never decides the grant (N-36, N-37) |
| <a id="c-29"></a>C-29 | Budgets and Demotion Escalate | Budget standing comes from the bound profile, and breach and demotion escalate rather than deny or reduce (N-38, N-39, N-40) |
| <a id="c-30"></a>C-30 | Emergencies Only Raise Ceilings | An emergency never lowers a level, waives a factor, or touches the pinned cells (N-42) |
| <a id="c-31"></a>C-31 | One Joined Audit Trail | Decision records join the interception audit trail on `intent_id` (N-45) |
| <a id="c-32"></a>C-32 | Reconciliation Classifies Everything | Every executed action is classed into one of the four results, including a scope comparison; divergence is recorded as a governance event, clears precedent and demotes (N-47, N-48) |
| <a id="c-33"></a>C-33 | The Sequence Is Honoured | The nine adjudication steps are applied in the order §5.1 gives them (N-50) |
| <a id="c-34"></a>C-34 | The Intent ID Travels | Where both modes are deployed, `intent_id` is propagated into the execution path so interception records carry it (N-46) |
| <a id="c-35"></a>C-35 | Intents Carry an Expiry | Production-plane intents declare `valid_until`; execution after it is refused and the intent reconciles as `unexecuted` (N-52) |
| <a id="c-36"></a>C-36 | No Unchecked Self-Declaration | Any factor computed from a value the intent declares is attested by another party or compared against execution (N-51) |
| <a id="c-37"></a>C-37 | Incident Keys Are Computed | `dedup_key` is computed deterministically and recorded; an actor-supplied key may only join an existing incident (N-53, N-54) |
| <a id="c-38"></a>C-38 | Cap Checks Are Atomic | Grant cap checks consume atomically and lifecycle transitions are ordered against coverage; unresolvable order routes to a human (N-55) |

---

## Appendix A: Requirement Quick Reference

Every normative requirement and conformance item carries a short plain-English
name. A name is a reading aid, not an identifier: `N-14` and `C-5` are the
stable references external documents cite, and they never change. A name can be
revised; a number cannot.

Anchors are keyed to the identifier rather than the name, for the same reason:
`#n-14` resolves to N-14 whatever it comes to be called.

This appendix is generated from `requirements.yaml` by `tools/check_spec.py`.
Edit the registry, not the tables.

### A.1 Normative requirements

| # | Name | What it says | Section | Rolls up to |
|---|---|---|---|---|
| [N-1](#n-1) | Reject, Never Default | A malformed intent is rejected outright, never adjudicated at a fallback level | §2.1 | [C-1](#c-1) |
| [N-2](#n-2) | Unlisted Fields Are Inert | Anything outside the spec and schema is recorded but cannot move the grade | §2.1 | [C-17](#c-17) |
| [N-3](#n-3) | Classification Required, Never Guessed | 3D and DC2D intents must carry a classification; absence resolves to the most sensitive tier | §2.2 | [C-17](#c-17) |
| [N-4](#n-4) | Rollback Buys No Discount | A declared rollback can never pull the level below base; a third-party attestation must name the party | §2.2 | [C-17](#c-17) |
| [N-5](#n-5) | Every Agent Has a Human | Agent and pipeline intents need an `on_behalf_of` that resolves to an accountable human or team | §3 | [C-8](#c-8) |
| [N-6](#n-6) | Fail Closed on Unknown Actors | Unresolvable authorization escalates every operation to at least approval, and Read too on confidential and restricted data | §3 | [C-9](#c-9) |
| [N-7](#n-7) | Kind Routes, Never Grades | Actor kind may steer approval routing and must be recorded, but cannot change the level | §3 | [C-18](#c-18) |
| [N-8](#n-8) | No Self-Assigned Rating | Any level, impact or likelihood grade an actor puts in its own intent is ignored | §3 | [C-18](#c-18) |
| [N-9](#n-9) | Maturity Is Not Rank | `Stable` and `Incubating` describe semantic stability, not trust, and never feed adjudication | §4 | [C-19](#c-19) |
| [N-10](#n-10) | One Envelope, One Contract | A new type registers against the common envelope and this adjudication contract, or stays out of scope | §4 | [C-19](#c-19) |
| [N-11](#n-11) | Composites Inherit the Worst | A composite takes the most restrictive level among itself and its children; membership never softens a child | §4 | [C-20](#c-20) |
| [N-12](#n-12) | The Permanent No | Add, Change and Delete on Restricted return `prohibited` before anything else runs, and no override reaches them | §5.1 | [C-2](#c-2) |
| [N-13](#n-13) | One Matrix, No Second | The base level comes from the bound profile's effective matrix and from nowhere else | §5.1 | [C-3](#c-3) |
| [N-14](#n-14) | The Monotonicity Rule | Nothing — factor, grant, emergency, attestation or configuration — may move a level toward less oversight | §5.1 | [C-4](#c-4) |
| [N-14a](#n-14a) | Escalation Stops Below Prohibited | Likelihood saturates at `elevated_approval` and can never reach the end of the ladder | §5.1 | [C-4a](#c-4a) |
| [N-14b](#n-14b) | Two Sources of Prohibited | `prohibited` arises only as `pinned` or `extended`; the pinned set may be grown, never shrunk | §5.1 | [C-21](#c-21) |
| [N-15](#n-15) | Classification Is Impact | The impact dimension is the four-tier classification ordering | §5.3 | [C-22](#c-22) |
| [N-16](#n-16) | Declare Any Impact Substitute | A substituted impact basis must be profile-declared, map onto the same four tiers, and be stamped into every record | §5.3 | [C-22](#c-22) |
| [N-17](#n-17) | The Five Likelihood Factors | All five factors must be implemented, each adding a non-negative number of steps | §5.4 | [C-5](#c-5) |
| [N-18](#n-18) | Weights Adjustable, Never Negative | Weights may be tuned but never below zero, and the weight table is versioned into every record | §5.4 | [C-5](#c-5) |
| [N-19](#n-19) | Factors Only Add | No likelihood factor may contribute a negative number of steps | §5.4 | [C-23](#c-23) |
| [N-20](#n-20) | Approval Is Not Permission | No adjudication, grant or disposition authorizes what the profile or capability ceiling forbids | §5.5 | [C-13](#c-13) |
| [N-21](#n-21) | Same Inputs, Same Level | The same intent under the same four recorded version inputs must reproduce the same level | §5.6 | [C-14](#c-14) |
| [N-22](#n-22) | The Six-Field Pattern Key | The action pattern key hashes exactly six named fields and nothing else | §6.1 | [C-6](#c-6) |
| [N-23](#n-23) | Same Target, Same Class | `target_class` is worked out the same way every time — the matching rule, else last-segment wildcarding — and the source is recorded | §6.2 | [C-24](#c-24) |
| [N-24](#n-24) | The System's Class Wins | A `target_class` supplied by the actor never beats the one the system works out; any disagreement is recorded | §6.2 | [C-24](#c-24) |
| [N-25](#n-25) | Only Checked Successes Count | Precedent needs a disposition permitting execution, a checked execution, and no material mismatch | §6.3 | [C-7](#c-7) |
| [N-26](#n-26) | A Mismatch Wipes Precedent | A material mismatch clears the action pattern's precedent and should demote the actor | §6.3 | [C-25](#c-25) |
| [N-27](#n-27) | Grants Approve, Never Lower | A grant supplies the human approval in advance; it never changes the child's computed level | §7.1 | [C-10](#c-10) |
| [N-28](#n-28) | Coverage Is All or Nothing | All five coverage conditions must hold, or the child routes for individual human disposition | §7.1 | [C-26](#c-26) |
| [N-29](#n-29) | No Grant Covers Prohibited | No grant reaches a prohibited child, and none is an exception to framework §12.5 | §7.1 | [C-10](#c-10) |
| [N-30](#n-30) | The Closed Predicate Fields | A class predicate matches only on the seven named fields; the schema admits no other key | §7.2 | [C-11](#c-11) |
| [N-31](#n-31) | Match All, Never Execute | Predicate fields match conjunctively, wildcards only in `target_class`, no free text and no code | §7.2 | [C-11](#c-11) |
| [N-32](#n-32) | No Blanket Grants | An empty or catch-all predicate is rejected at grant submission | §7.2 | [C-12](#c-12) |
| [N-33](#n-33) | Every Grant Expires and Caps | Every grant declares an expiry; a campaign additionally declares a child cap and a maximum level | §7.3 | [C-12](#c-12) |
| [N-34](#n-34) | Revocation Is Immediate | Nothing adjudicated after revocation is covered | §7.3 | [C-27](#c-27) |
| [N-35](#n-35) | Past Dispositions Stand | Children dispositioned before revocation stay valid, but are recorded as affected and surfaced for review | §7.3 | [C-27](#c-27) |
| [N-36](#n-36) | The Five Named Prohibitions | An exception is rejected if it trips any of framework §12.5's five prohibitions, whether the schema catches it or not | §7.4 | [C-28](#c-28) |
| [N-37](#n-37) | Scrutiny, Not the Decision | Adjudicating an exception sizes the scrutiny required; the §12.2 authority decides whether to grant it | §7.4 | [C-28](#c-28) |
| [N-38](#n-38) | Budgets Come From the Profile | Budget standing comes from bound-profile constraints; no parallel budget vocabulary exists | §8.1 | [C-29](#c-29) |
| [N-39](#n-39) | Breach Escalates, Never Denies | A budget breach fires L4 escalation rather than a silent denial or a reduction | §8.1 | [C-29](#c-29) |
| [N-40](#n-40) | Demotion Is Escalation | Demotion is the L4 weight applied until it lifts, recorded with its cause — not a new state | §8.2 | [C-29](#c-29) |
| [N-41](#n-41) | Emergencies Raise the Ceiling | Citing an active emergency escalation raises the permission ceiling and nothing else | §8.3 | — |
| [N-42](#n-42) | Emergencies Never Lower Grades | An emergency cannot lower a level, waive a factor, or touch the pinned cells | §8.3 | [C-30](#c-30) |
| [N-43](#n-43) | The Durable Decision Record | Decision records are append-only; only a disposition or a reconciliation result may be attached | §9 | [C-14](#c-14) |
| [N-44](#n-44) | Name the Prohibition Source | Every prohibited decision states `pinned` or `extended`; escalation is never a source | §9 | [C-15](#c-15) |
| [N-45](#n-45) | One Audit Trail | Decision records join the interception records' audit trail on `intent_id` | §9 | [C-31](#c-31) |
| [N-46](#n-46) | Carry the Intent ID Through | Where both modes run, `intent_id` should propagate into the execution path | §10 | [C-34](#c-34) |
| [N-47](#n-47) | The Four Reconciliation Results | Every executed action is classed as matched, divergent, undeclared or unexecuted | §10 | [C-32](#c-32) |
| [N-48](#n-48) | Divergence Is a Governance Event | Divergent and undeclared results are recorded as events, clear the action pattern's precedent, and should demote | §10 | [C-32](#c-32) |
| [N-49](#n-49) | Unreconciled Is Not Matched | Missing interception coverage leaves `reconciliation.result` unset — never recorded as success | §10 | [C-16](#c-16) |
| [N-50](#n-50) | Steps Run In Order | The nine adjudication steps are applied in the order §5.1 gives them | §5.1 | [C-33](#c-33) |
| [N-51](#n-51) | Declared Inputs Get Checked | A factor may read a declared value only if that value is attested or reconciled | §5.4 | [C-36](#c-36) |
| [N-52](#n-52) | Every Intent Expires | A production-plane intent declares a `valid_until` after which its adjudication authorizes nothing | §2.2 | [C-35](#c-35) |
| [N-53](#n-53) | Same Incident, Same Key | `dedup_key` is computed the same way every time, and the rule that produced it is recorded | §4 | [C-37](#c-37) |
| [N-54](#n-54) | The System's Key Wins | An actor-supplied `dedup_key` may join an existing incident but never mint a new identity | §4 | [C-37](#c-37) |
| [N-55](#n-55) | Caps Count Once | Cap checks and grant lifecycle transitions are atomic and ordered; unresolvable order routes to a human | §7.3 | [C-38](#c-38) |

Every **MUST** and **MUST NOT** above rolls up into a conformance item. The
entries showing — are permissive (N-41): they grant latitude
rather than impose an obligation, so §11 has nothing to assert about them.

### A.2 Conformance checklist

| # | Name | What it says | Bundles |
|---|---|---|---|
| [C-1](#c-1) | Malformed Intents Rejected | Schema validation gates adjudication, with no defaulting | [N-1](#n-1) |
| [C-2](#c-2) | The Permanent No Comes First | Framework §12.5's prohibition is checked before everything and survives every override | [N-12](#n-12) |
| [C-3](#c-3) | Single Source Matrix | One effective matrix supplies the base level; no second matrix exists | [N-13](#n-13) |
| [C-4](#c-4) | Never Less Restrictive | No mechanism produces a level below base | [N-14](#n-14) |
| [C-4a](#c-4a) | Escalation Saturates | Escalation stops at `elevated_approval`; likelihood never reaches `prohibited` | [N-14a](#n-14a) |
| [C-5](#c-5) | Five Factors, No Negatives | All five likelihood factors are implemented and every weight is non-negative | [N-17](#n-17), [N-18](#n-18) |
| [C-6](#c-6) | Pattern Key Exactly Six | The action pattern key covers the six §6.1 fields, no more and no fewer | [N-22](#n-22) |
| [C-7](#c-7) | Precedent Comes From Checks | Precedent comes only from executions that were checked and succeeded | [N-25](#n-25) |
| [C-8](#c-8) | Accountable Human Required | Non-human actors without a resolvable `on_behalf_of` are rejected | [N-5](#n-5) |
| [C-9](#c-9) | Unknown Actors Fail Closed | Unresolvable authorization escalates non-Read operations to at least approval | [N-6](#n-6) |
| [C-10](#c-10) | Grants Never Change Levels | Grants leave computed levels untouched and never cover `prohibited` | [N-27](#n-27), [N-29](#n-29) |
| [C-11](#c-11) | Predicates Closed and Declarative | Predicates match the closed field set, conjunctively, with no executable code | [N-30](#n-30), [N-31](#n-31) |
| [C-12](#c-12) | Bounded and Expiring Grants | Every grant carries an expiry and a child cap; blanket and indefinite grants are rejected | [N-32](#n-32), [N-33](#n-33) |
| [C-13](#c-13) | Profile Ceiling Holds | Adjudication never grants what the bound profile withholds | [N-20](#n-20) |
| [C-14](#c-14) | Reproducible Durable Records | Every adjudication emits a durable record carrying all four reproducibility inputs | [N-21](#n-21), [N-43](#n-43) |
| [C-15](#c-15) | Prohibition Source Recorded | Prohibited decisions distinguish `pinned` from `extended` | [N-44](#n-44) |
| [C-16](#c-16) | No False Matches | Unreconcilable executions are never recorded as `matched` | [N-49](#n-49) |
| [C-17](#c-17) | The Envelope Is the Whole Input | Only fields this specification and the schema define may grade an intent; a missing classification resolves to the most sensitive tier; a rollback claim never lowers the level (N-2, N-3, N-4) | [N-2](#n-2), [N-3](#n-3), [N-4](#n-4) |
| [C-18](#c-18) | Actors Are Recorded, Not Trusted | Actor kind never changes the computed level, and no grade an actor asserts about itself is honoured (N-7, N-8) | [N-7](#n-7), [N-8](#n-8) |
| [C-19](#c-19) | The Type Registry Is Flat | Maturity is never a rank, and every registered type uses the common envelope and adjudication contract (N-9, N-10) | [N-9](#n-9), [N-10](#n-10) |
| [C-20](#c-20) | Composites Take the Worst | A composite computes to the most restrictive level among itself and its children, and never softens a child (N-11) | [N-11](#n-11) |
| [C-21](#c-21) | Prohibited Has Two Sources | `prohibited` is reachable only as `pinned` or `extended`, and the pinned set is never narrowed (N-14b) | [N-14b](#n-14b) |
| [C-22](#c-22) | Impact Is Declared, Not Supplied | Impact is the four-tier classification ordering, and any substitute is profile-declared and stamped into every record (N-15, N-16) | [N-15](#n-15), [N-16](#n-16) |
| [C-23](#c-23) | No Factor Subtracts | No likelihood factor contributes negative steps or takes its value from the intent without attestation (N-19) | [N-19](#n-19) |
| [C-24](#c-24) | One Target, One Class | `target_class` is computed the same way every time, and a value the actor supplies never wins (N-23, N-24) | [N-23](#n-23), [N-24](#n-24) |
| [C-25](#c-25) | A Mismatch Clears Precedent | A material mismatch clears the action pattern's precedent and demotes the actor | [N-26](#n-26) |
| [C-26](#c-26) | Coverage Needs Every Condition | A child is covered only when every one of the five coverage conditions holds (N-28) | [N-28](#n-28) |
| [C-27](#c-27) | Grants End Cleanly | Revocation takes effect immediately, and children already dispositioned are recorded as affected (N-34, N-35) | [N-34](#n-34), [N-35](#n-35) |
| [C-28](#c-28) | Exceptions Stay Inside §12.5 | An exception tripping any of framework §12.5's five prohibitions is rejected, and adjudication never decides the grant (N-36, N-37) | [N-36](#n-36), [N-37](#n-37) |
| [C-29](#c-29) | Budgets and Demotion Escalate | Budget standing comes from the bound profile, and breach and demotion escalate rather than deny or reduce (N-38, N-39, N-40) | [N-38](#n-38), [N-39](#n-39), [N-40](#n-40) |
| [C-30](#c-30) | Emergencies Only Raise Ceilings | An emergency never lowers a level, waives a factor, or touches the pinned cells (N-42) | [N-42](#n-42) |
| [C-31](#c-31) | One Joined Audit Trail | Decision records join the interception audit trail on `intent_id` (N-45) | [N-45](#n-45) |
| [C-32](#c-32) | Reconciliation Classifies Everything | Every executed action is classed into one of the four results, and divergence is recorded as a governance event (N-47, N-48) | [N-47](#n-47), [N-48](#n-48) |
| [C-33](#c-33) | The Sequence Is Honoured | Adjudication applies the §5.1 steps in order (N-50) | [N-50](#n-50) |
| [C-34](#c-34) | The Intent ID Travels | Where both modes are deployed, `intent_id` reaches the interception record | [N-46](#n-46) |
| [C-35](#c-35) | Intents Carry an Expiry | Production-plane intents declare an expiry, and nothing executes after it | [N-52](#n-52) |
| [C-36](#c-36) | No Unchecked Self-Declaration | A factor reading a declared value is attested or reconciled | [N-51](#n-51) |
| [C-37](#c-37) | Incident Keys Are Computed | `dedup_key` is computed, and an actor-supplied key cannot mint a new incident | [N-53](#n-53), [N-54](#n-54) |
| [C-38](#c-38) | Cap Checks Are Atomic | Cap consumption and revocation are ordered, and unresolvable order fails closed | [N-55](#n-55) |

---

## See also

- [`intents.md`](intents.md) — the model, its rationale, and the two-mode
  argument.
- `RMACD_Framework_v1.4.md` §2.4 (autonomy levels), §3.1 (the matrix),
  §12.3–12.5 (exceptions, the immutable floor).
- `docs/audit-evidence.md` — the interception-side audit record this
  specification joins on `intent_id`.
