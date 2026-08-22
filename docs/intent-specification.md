# RMACD Intent Specification

**Version:** 1.0.0
**Status:** Normative
**Companion to:** `RMACD_Framework_v1.4.md` (§2.4, §3, §12)
**Narrative companion:** [`intents.md`](intents.md) — the model and its rationale
**Schemas:** `schemas/intent.schema.json`, `schemas/intent-decision.schema.json`

This document specifies the intent envelope, the actor model, the adjudication
contract, the decision record, and the conformance requirements for an RMACD
Intent implementation. It is versioned independently of the framework
specification. It adds no autonomy levels, no governance matrix, and no
permission semantics; where it refers to those, the framework specification
governs.

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT** and **MAY** are
to be interpreted as described in RFC 2119.

## Contents

- [1. Scope and terminology](#1-scope-and-terminology)
- [2. The intent envelope](#2-the-intent-envelope)
- [3. The actor model](#3-the-actor-model)
- [4. Intent types](#4-intent-types)
- [5. The adjudication contract](#5-the-adjudication-contract)
- [6. Intent shape and novelty](#6-intent-shape-and-novelty)
- [7. Grants: campaigns and exceptions](#7-grants-campaigns-and-exceptions)
- [8. Budgets, demotion and emergencies](#8-budgets-demotion-and-emergencies)
- [9. The decision record](#9-the-decision-record)
- [10. Reconciliation with interception](#10-reconciliation-with-interception)
- [11. Conformance](#11-conformance)

---

## 1. Scope and terminology

| Term | Definition |
|---|---|
| **Intent** | A structured declaration of an action an actor wants to take, submitted for adjudication before it is taken |
| **Adjudication** | The deterministic computation of a required autonomy level from a declared intent |
| **Base level** | The autonomy level the framework's effective matrix requires for the declared `(classification, operation)` |
| **Escalation** | Monotonic movement of a level toward greater oversight along the §2.4 ladder |
| **Shape** | The canonical equivalence class over which novelty is computed (§6) |
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
| `$schema` | No | string | `https://rmacd-framework.org/schema/v1/intent.json` |
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
| `metadata` | No | object | Organization-local; never an adjudication input |

**N-1.** An implementation **MUST** reject an intent that fails schema
validation. It **MUST NOT** adjudicate a malformed intent, and **MUST NOT**
fall back to a default level.

**N-2.** Fields not listed in this specification or the schema **MUST NOT**
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

**N-3.** In a 3D or DC2D deployment, `data_classification` **MUST** be present.
An implementation **MUST NOT** infer a missing classification as anything other
than the most sensitive tier the deployment recognizes.

**N-4.** `reversibility.rollback_declared` **MUST NOT** reduce a computed level
below the base level under any circumstance (§5.2). Where a rollback claim is
attested by a party other than the requesting actor, `attested_by` **MUST**
identify that party.

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

**N-5.** An implementation **MUST** reject an `agent` or `pipeline` intent whose
`on_behalf_of` is absent or does not resolve to an accountable human or team.

**N-6.** Where `authorization` cannot be resolved, the implementation **MUST**
fail closed: every operation other than `R` is escalated to at least `approval`,
regardless of what the matrix would otherwise compute. The decision record
**MUST** record `unresolved_authorization` as an escalation factor.

**N-7.** Adjudication **MUST** be actor-kind-agnostic. `kind` **MUST NOT**
influence the computed level. It **MAY** determine approval routing and
**MUST** be recorded for accountability.

**N-8.** An actor **MUST NOT** be able to assert its own rating. An
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

**N-9.** Maturity labels (`Stable`, `Incubating`) signal semantic stability
only. An implementation **MUST NOT** treat maturity as a rank, a trust level, or
an adjudication input.

**N-10.** A new type **MUST** register against the common envelope and this
adjudication contract. A type that requires different adjudication semantics is
out of scope for this specification.

**N-11. Composition floor.** For any composite intent, the computed level
**MUST** be the most restrictive level among the composite itself and all
intents it composes or requires. Membership in a composite **MUST NOT** lower
any child's own computed level.

---

## 5. The adjudication contract

### 5.1 The algorithm

Adjudication is the following sequence. Steps **MUST** be applied in order.

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

**N-12. Immutable floor.** Before any other computation, an implementation
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

**N-13. Base level.** The base level **MUST** be derived from the framework's
effective matrix for the actor's bound profile — the §3.1 defaults as adjusted
by that profile's `autonomy_overrides`. An implementation **MUST NOT** define a
second matrix, and **MUST NOT** compute a base level from any other source.
In a 2D deployment the effective matrix is indexed by operation alone; in 3D and
DC2D deployments it is indexed by `(classification, operation)`.

**N-14. Monotonicity.** The computed level **MUST NOT** be less restrictive than
the base level. No factor, grant, emergency, attestation, or configuration
**MAY** move a level toward lower oversight.

**N-14a. Saturation.** Escalation **MUST** saturate at `elevated_approval`.
Likelihood **MUST NOT** move an intent to `prohibited`.

`prohibited` means no human disposition can authorize the action for an
autonomous actor. That is a categorical statement about the action itself, not a
function of how novel or how poorly-attested a particular request is. Novelty
**SHOULD** be able to demand the CISO; it **MUST NOT** be able to make an
action categorically impossible. An implementation that let escalation reach the
end of the ladder would turn routine production work on sensitive data —
already at `elevated_approval` in the §3.1 defaults — into a deterministic deny
on its first occurrence.

**N-14b. Reaching prohibited.** An intent **MUST** compute to `prohibited` only
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

**N-15.** The impact dimension **MUST** be the deployment's data classification
tier, ordered `public < internal < confidential < restricted`.

**N-16.** An organization **MAY** substitute or supplement classification with
another impact basis (CMDB criticality, service tier). Where it does, the
substitution **MUST** be declared in the bound profile, **MUST** map onto the
same four-tier ordering, and **MUST** be stamped into every decision record via
`impact_basis`. The intent envelope carries no impact axis: an implementation
**MUST NOT** accept an impact basis supplied in the intent itself, and the
schema provides no field through which an actor could supply one (N-8).

### 5.4 Likelihood factors

**N-17.** An implementation **MUST** implement all five factors below. Each
contributes a non-negative number of escalation steps.

| # | Factor | Condition | Default steps |
|---|---|---|---|
| L1 | Novelty | No confirmed prior success of this shape (§6) | +1 |
| L2 | Reversibility | No attested rollback path | +1 |
| L3 | Environment | `production` or `disaster-recovery` | +1 |
| L4 | Budget standing | Actor at or over budget, or currently demoted | +2 |
| L5 | Blast radius | Declared scope exceeds the profile's cap | +2 |
| | | Declared scope within 80% of the cap | +1 |

**N-18.** An organization **MAY** adjust these weights. Every weight **MUST**
remain ≥ 0; a negative weight **MUST** be rejected at configuration load. The
effective weight table **MUST** carry a version identifier, and that identifier
**MUST** be stamped into every decision record.

**N-19.** An implementation **MUST NOT** introduce a factor that can contribute
negative steps, and **MUST NOT** implement a factor whose value is taken
directly from the intent without attestation or reconciliation.

### 5.5 The profile remains a ceiling

**N-20.** Adjudication **MUST NOT** grant permission. A favourable
adjudication, an approved grant, and a recorded human disposition, singly or
together, **MUST NOT** authorize an operation the actor's bound profile or a
tool capability ceiling forbids. An intent that adjudicates successfully and is
subsequently refused by interception is conformant behaviour.

### 5.6 Determinism

**N-21.** Adjudication **MUST** be reproducible. Given the same intent, matrix
version, likelihood weight-table version, policy version, and decision-log
epoch, an implementation **MUST** produce the same level. The four version
inputs **MUST** be recorded in the decision record (§9), alongside the
`intent_id` that identifies the intent they were applied to.

Adjudication is deterministic but not stateless: novelty and budget standing
read organizational state. Reproducibility is therefore defined against a
recorded log epoch rather than against the intent alone.

---

## 6. Intent shape and novelty

Novelty is the factor that lets a well-trodden action stop costing human
attention. The equivalence class it is computed over is consequently the most
security-sensitive definition in this specification: **whatever the shape
excludes becomes a gradient an actor can descend to erode its own scrutiny.**

### 6.1 The shape key

**N-22.** The shape key **MUST** be a SHA-256 hash over the canonical JSON
serialization of exactly these fields, and **MUST NOT** include any other field:

| Field | Rationale for inclusion |
|---|---|
| `intent_type` | Credit earned as one type is not spendable as another |
| `declaration.operation` | Credit earned reading is not spendable deleting |
| `declaration.data_classification` | Credit earned on public data is not spendable on confidential |
| `declaration.environment` | Credit earned in staging is not spendable in production |
| `declaration.target_class` | The normalized target, never the literal target (§6.2) |
| `actor.kind` | Credit earned by a supervised pipeline is not spendable by an autonomous agent |

Literal target identifiers, timestamps, justification text, metadata, and the
actor's own `id` are excluded, so that the same governed action against a
hundred hosts converges on one shape rather than a hundred.

### 6.2 Target normalization

**N-23.** `target_class` **MUST** be derived deterministically: the target
pattern declared by the matching Governance Pack rule or profile constraint if
one matched, otherwise the target with its final identifier segment replaced by
`*`. An implementation **MUST** record which rule produced the normalization.

**N-24.** An implementation **MUST NOT** accept a `target_class` supplied by the
actor in preference to a derived one. Where both exist and disagree, the derived
value governs and the discrepancy **MUST** be recorded.

### 6.3 What counts as a confirmed success

**N-25.** A prior decision **MUST NOT** count toward novelty credit unless all
of the following hold:

1. The intent was adjudicated and received a disposition permitting execution.
2. Execution was **reconciled** (§10) — an interception record or an attested
   post-execution confirmation, joined on `intent_id`, reports success.
3. Reconciliation found no material discrepancy between declared and executed
   facts.

A declared-but-unreconciled outcome **MUST NOT** accrue credit. This closes
novelty farming by declaration: an actor cannot earn standing simply by
submitting intents.

**N-26.** Where reconciliation detects a material discrepancy, the
implementation **MUST** reset accrued novelty credit for that shape and
**SHOULD** demote the actor (§8).

---

## 7. Grants: campaigns and exceptions

A grant is a pre-recorded human disposition covering a bounded class of future
intents. Grants are the mechanism by which humans govern classes rather than
instances — and the mechanism most capable of laundering privilege if loosely
specified.

### 7.1 Coverage is discharge, not reduction

**N-27.** A grant **MUST NOT** change a child intent's computed level. It
**MAY** discharge the child's approval requirement by supplying a recorded
human disposition in advance.

**N-28.** A child is covered only when **all** of the following hold. If any
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

**N-29.** A grant **MUST NOT** cover a `prohibited` child under any
circumstance, and **MUST NOT** be construed as an exception to framework §12.5.

### 7.2 Class predicates

**N-30.** A `class_predicate` **MUST** be evaluated deterministically and
**MUST** match only on this closed set of fields:

`intent_type`, `declaration.operation`, `declaration.data_classification`,
`declaration.environment`, `declaration.target_class`, `actor.id`,
`actor.on_behalf_of`.

The predicate names these flattened, as `intent_type`, `operation`,
`data_classification`, `environment`, `target_class`, `actor_id` and
`on_behalf_of`; the schema admits no other key.

**N-31.** All specified fields **MUST** match conjunctively. Wildcards **MAY**
appear only in `target_class`. A predicate **MUST NOT** match on
`justification`, `metadata`, or any free-text field, and **MUST NOT** be
expressed as executable code.

**N-32.** A predicate that specifies no fields, or that would match every
intent of a type, **MUST** be rejected at grant submission. Blanket grants are
prohibited by framework §12.5.

### 7.3 Caps, expiry and revocation

**N-33.** Every grant **MUST** declare `expires_at`. Indefinite or open-ended
grants **MUST** be rejected, per framework §12.5. A `campaign` **MUST**
additionally declare `caps.max_children` and `caps.max_level`, because its
bounds are otherwise only a predicate; an `exception` is bounded instead by its
`escalated_permissions` grid and by the maximum duration its §12.2 category
fixes, and **MAY** declare `caps` in addition.

**N-34.** Revocation **MUST** take effect immediately. Intents adjudicated after
revocation **MUST NOT** be covered.

**N-35.** Children already dispositioned under a grant at the moment of
revocation remain validly dispositioned, but the implementation **MUST** record
them as affected by the revocation and **SHOULD** surface them for review.

### 7.4 The `exception` type

The `exception` type expresses framework §12.3's five-step process. Framework
§12.4's exception profile template *is* an `exception` intent: from framework
revision 1.4.1 the template is written in this envelope and points at
`schema/v1/intent.json`, so the framework carries one request path rather than
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

**N-36.** An `exception` intent **MUST** be rejected if it would escalate
`restricted` beyond `["R", "M"]`, omit `expires_at`, remove audit logging,
apply a profile across environments, or request a blanket grant. These are
framework §12.5's five named prohibitions. Two of the five are enforced by the
schema at authoring time — `escalated_permissions.restricted` admits only `R`
and `M`, and `expires_at` is required — and `compensating_controls`
`enhanced_logging`, where present, may only be `true`. The remaining
prohibitions are not expressible in a per-document schema and **MUST** be
enforced by the implementation at grant submission.

**N-37.** Adjudication of an `exception` computes the scrutiny the request
requires. It **MUST NOT** decide whether the exception is granted; that
disposition belongs to the authority named in framework §12.2.

---

## 8. Budgets, demotion and emergencies

### 8.1 Budgets

**N-38.** Budget standing **MUST** be derived from the actor's bound profile
constraints — `rate_limits`, `change_controls`, and
`max_blast_radius_percentage`. An implementation **MUST NOT** define a parallel
budget vocabulary.

**N-39.** Budget breach **MUST** produce escalation (factor L4), never a silent
denial and never a reduction.

### 8.2 Demotion

**N-40.** Demotion **MUST** be expressed as escalation, not as a new state. A
demoted actor's intents escalate by the L4 weight until the demotion expires or
is lifted. The decision record **MUST** record demotion as an escalation factor
with its cause.

### 8.3 Emergencies

**N-41.** An intent **MAY** cite an active emergency escalation defined by its
profile's `emergency_escalation` block. Citing an emergency raises the
*permission ceiling* only.

**N-42.** An emergency **MUST NOT** lower a computed level, **MUST NOT** waive
an escalation factor, and **MUST NOT** affect the §12.5 pinned cells. The
profile's `trigger_conditions`, `max_duration_minutes`, `cooldown_minutes` and
`require_post_incident_review` apply unchanged.

---

## 9. The decision record

Every adjudication produces exactly one decision record, conforming to
`schemas/intent-decision.schema.json`. The decision record is simultaneously the
evidence artifact and the novelty memory.

| Field | Required | Notes |
|---|---|---|
| `$schema` | No | `https://rmacd-framework.org/schema/v1/intent-decision.json` |
| `decision_id` | **Yes** | `^dec-[a-z0-9][a-z0-9-]*$` |
| `intent_id` | **Yes** | The adjudicated intent; the join key for reconciliation |
| `decided_at` | **Yes** | RFC 3339, UTC |
| `shape_key` | **Yes** | §6.1 |
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

**N-43.** A decision record **MUST** be durable and append-only. An
implementation **MUST NOT** mutate a decision record after emission, other than
by attaching a `disposition` or a `reconciliation` result.

**N-44.** Where the computed level is `prohibited`, `prohibition_source`
**MUST** distinguish `pinned` (framework §12.5) from `extended` (an
organization's own declared prohibition), per N-14b. Escalation is never a
source: likelihood cannot reach `prohibited` (N-14a).

**N-45.** Decision records **MUST** join the same audit trail as interception
records, on `intent_id`.

---

## 10. Reconciliation with interception

Reconciliation is the mechanism that makes declaration trustworthy. It compares
what an actor declared against what interception observed it do.

**N-46.** Where both modes are deployed, an implementation **SHOULD** propagate
`intent_id` into the execution path so interception records carry it.

**N-47.** A reconciliation result **MUST** classify each executed action as one
of:

| Result | Meaning |
|---|---|
| `matched` | Executed action's operation, target class, classification and environment match the declared intent |
| `divergent` | An executed action carried a different operation, target class, classification or environment |
| `undeclared` | An executed action carried no `intent_id` and matched no open intent |
| `unexecuted` | An adjudicated intent was never executed before expiry |

**N-48.** A `divergent` or `undeclared` result **MUST** be recorded as a
governance event in its own right, **MUST** reset novelty credit for the
affected shape (N-26), and **SHOULD** trigger demotion.

**N-49.** An implementation **MUST NOT** treat the absence of interception
coverage as reconciliation success. Where an action cannot be reconciled, the
decision record's `reconciliation.result` **MUST** remain unset rather than
being recorded as `matched`.

---

## 11. Conformance

An implementation conforms to this specification when all of the following hold.

| # | Requirement |
|---|---|
| C-1 | Intents are validated against `intent.schema.json`; malformed intents are rejected, never defaulted (N-1) |
| C-2 | The §12.5 immutable floor is checked before any other computation and is unreachable by any override (N-12) |
| C-3 | The base level comes from the framework's effective matrix; no second matrix exists (N-13) |
| C-4 | No mechanism can produce a level less restrictive than the base level (N-14) |
| C-4a | Escalation saturates at `elevated_approval`; likelihood never reaches `prohibited` (N-14a) |
| C-5 | All five likelihood factors are implemented; no weight is negative (N-17, N-18) |
| C-6 | The shape key covers exactly the six fields in §6.1 (N-22) |
| C-7 | Novelty credit accrues only from reconciled successes (N-25) |
| C-8 | Non-human actors without a resolvable `on_behalf_of` are rejected (N-5) |
| C-9 | Unresolvable authorization fails closed to at least `approval` for non-Read operations (N-6) |
| C-10 | Grants discharge approval without changing computed levels, and never cover `prohibited` (N-27, N-29) |
| C-11 | Class predicates match only the closed field set, conjunctively, with no executable code (N-30, N-31) |
| C-12 | Every grant declares an expiry and a child cap; blanket and indefinite grants are rejected (N-32, N-33) |
| C-13 | Adjudication never grants permission the bound profile withholds (N-20) |
| C-14 | Every adjudication emits a durable decision record carrying all four reproducibility inputs (N-21, N-43) |
| C-15 | Prohibited decisions distinguish `pinned` from `extended` (N-44) |
| C-16 | Unreconcilable executions are never recorded as `matched` (N-49) |

---

## See also

- [`intents.md`](intents.md) — the model, its rationale, and the two-mode
  argument.
- `RMACD_Framework_v1.4.md` §2.4 (autonomy levels), §3.1 (the matrix),
  §12.3–12.5 (exceptions, the immutable floor).
- `docs/audit-evidence.md` — the interception-side audit record this
  specification joins on `intent_id`.
