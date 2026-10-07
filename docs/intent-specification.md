# RMACD Intent Specification

**Version:** 2.4.0
**Status:** Binding — these are the rules an implementation has to follow
**Companion to:** `RMACD_Framework_v1.4.md` (§2.4, §3, §12)
**Plain-words companion:** [`intents.md`](intents.md) — the model and why it is built this way
**Schemas:** `schemas/intent.schema.json`, `schemas/intent-decision.schema.json`,
`schemas/intent-log-entry.schema.json`, `schemas/adjudication-log-entry.schema.json`
(published as `schema/v2/`; the field rename in 2.0.0 is not backward compatible)

This document specifies the intent envelope, the actor model, the adjudication
contract, the decision record, and the checklist an implementation has to
meet. It is versioned independently of the framework specification. It adds no
autonomy levels, no governance matrix, and no permission semantics; where it
refers to those, the framework specification governs.

The key words **MUST**, **MUST NOT** and **MAY** in this document are to be
interpreted as described in BCP 14 [RFC
2119](https://www.rfc-editor.org/rfc/rfc2119) and [RFC
8174](https://www.rfc-editor.org/rfc/rfc8174) when, and only when, they appear
in all capitals, as shown here. The same words in lower case carry their
ordinary English meaning and impose no requirement.

Per RFC 2119 §6, these imperatives appear only where they are needed for
interoperation or to limit behaviour that could cause harm. Explanatory
passages state their reasoning in plain words. Every capitalised keyword in
this document sits inside a numbered rule, and `tools/check_spec.py` enforces
that.

**This specification uses no SHOULD and no SHOULD NOT.** RFC 2119 §4 permits
an implementation to disregard a **SHOULD** where it judges the reasons
sufficient. Adjudication is a grading function that **MUST** be reproducible
across implementations (N-21), so advice an implementer may decline would let
two well-built engines answer the same governance failure differently — and
the rules that would have been advisory are precisely the consequential ones:
demotion after a mismatch, demotion after divergence, marking revoked children
for review, carrying `intent_id` into the execution path. Each limits
behaviour with potential for harm, which is where RFC 2119 §6 directs an
author to use **MUST**. This specification therefore states obligations and
latitude, and nothing in between: what an implementation has to do is a
**MUST**, what it is free to choose is a **MAY**. The synonyms RFC 2119
permits — SHALL, REQUIRED, RECOMMENDED, OPTIONAL — are unused; the three
keywords above are the whole vocabulary.

## Revision history

This specification carries its own version, separate from the framework's. A
revision that invalidates an existing intent document or a well-built
implementation is a major version; new rules, new fields and new checklist
items are a minor version; wording alone is a patch. Identifiers are
permanent: an N-x rule, a C-x checklist item and an L implementation level
are added, never renumbered, because external documents cite them. Names and
headings may change at any revision; citations use the identifier.

| Revision | Date | Change |
|---|---|---|
| 2.4.0 | 2026-10-07 | The two logs named and given schemas (§9.1: N-72, N-73, N-74, N-76). The epoch pinned to a shared sequence number (§9.3: N-75). The three-stream join stated |
| 2.3.0 | 2026-10-07 | Grants are graded by their reach, never below their cap, and always by a human (§7.5: N-66, N-67, N-68). Exception coverage checks the profile and actor it names (N-28). An L1 register keeps the six pattern fields in place of the hash (N-69). The first-report invariant is a rule (N-70). Grant lifecycle changes are traced (N-71). `window` joins the reconciliation comparison set |
| 2.2.0 | 2026-09-05 | Plain-language pass (jargon retired in favour of common words). The intent lifecycle (§2.3: N-57, N-58, N-59). One agreed byte form for the pattern key (N-56). The log epoch defined (N-60). Precedent aging (N-61). Deployments cite their window (N-62). Bundles decided children-first (N-63). Three implementation levels (§11.1: N-64, N-65). Security considerations (§12) |
| 2.1.1 | 2026-08-31 | §1.1 and §1.2 define the vocabulary the type registry assumes; the `service_request` plane contradiction between the two documents resolved |
| 2.1.0 | 2026-08-31 | Five design gaps closed together: N-51 to N-55, C-35 to C-38 |
| 2.0.0 | 2026-08-30 | Named rules, full checklist coverage, RFC 2119 alignment; the equivalence-class key renamed `action_pattern_key` (breaking) |

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
- [11. The checklist](#11-the-checklist)
- [12. Security considerations](#12-security-considerations)
- [Appendix A: Requirement Quick Reference](#appendix-a-requirement-quick-reference)

---

## 1. Scope and terminology

| Term | Definition |
|---|---|
| **Intent** | A structured declaration of an action an actor wants to take, submitted for adjudication before it is taken |
| **Adjudication** | Grading a declared intent by fixed rules: computing the oversight level it needs before the action runs. This document also calls it *grading* |
| **Base level** | The autonomy level the framework's effective matrix requires for the declared `(classification, operation)` |
| **Escalation** | One-way movement of a level toward greater oversight along the §2.4 ladder |
| **Action pattern** | The class of like-for-like actions over which precedent is counted (§6) |
| **Grant** | A human approval recorded in advance, covering a bounded class of future intents (§7) |
| **Human decision** | A human ruling — approve, deny, defer or escalate — recorded against a graded intent, in the record's `disposition` field |
| **Decision record** | The permanent evidence artifact produced by every adjudication (§9) |
| **Reconciliation** | Comparison of a declared intent against the interception record of what was executed (§10) |

The **autonomy ladder** is the ordered list defined in framework §2.4:

```
0 autonomous  →  1 logged  →  2 notification  →  3 approval
              →  4 elevated_approval  →  5 prohibited
```

Escalation moves along this list toward higher indices only, and stops
at index 4. Index 5 is not an escalation destination: `prohibited` is reached
only via the pinned or extended floor (N-14a, N-14b).

### 1.1 Planes, maturity and how types combine

The type registry in §4 classifies every type along three axes. This is the
vocabulary it uses.

| Term | Definition |
|---|---|
| **Plane** | Which part of the estate a type acts on. It determines what obligations attach to that type — expiry, deduplication, caps — but never how much oversight a given action receives. That comes from the matrix and the likelihood factors. |
| **Production plane** | Acts on infrastructure, applications or data. These types carry an expiry, because an approved-but-unexecuted change is otherwise a standing authorization (N-52). |
| **Record plane** | Creates or updates ITSM records themselves — raising an incident, opening a problem. Adjudicated because a fleet raising fifty thousand incidents is a denial of service on human attention. Bounded by the first-report invariant: throttling may limit repeats, never the first report of a distinct condition (N-70). |
| **Grant plane** | Pre-authorizes a bounded class of future work rather than performing any. `campaign` and `exception` only. Always carries caps and an expiry (§7). |
| **Maturity** | How settled a type's required-field contract is. Deliberately not a trust signal — an `Incubating` type is enforced exactly as strictly as a `Stable` one (N-9). |
| **Stable** | The required-field set is fixed. Changes need a major revision, so it is safe to build an integration against. |
| **Incubating** | The required-field set may still change between minor revisions. Usable in production, but pin the integration and expect to revisit it. |
| **Building block** | The atomic unit of production work. Every other production type either bundles it, depends on something that does, or authorizes it. `change` only. |
| **Bundle** | Gathers one or more child intents and inherits the most restrictive level among them. A release carrying one risky migration is adjudicated at that migration's level, not at an average of its contents (N-11). |
| **Dependent** | Cites exactly one upstream intent it cannot proceed without. A deployment names the release it deploys. |
| **Grants over `change`** | Pre-authorizes future `change` intents within declared bounds instead of performing work. The human approval is recorded once, up front; covered children do not queue for individual sign-off (N-27). |
| **Cited by `deployment`** | Referenced by a deployment as context it must fall inside. It does not become part of the deployment and is adjudicated separately. |
| **Produces `change`** | Resolving one of these normally results in a separate `change` intent. The type records a condition; it does not remediate it. |
| **Grant + trigger** | Pre-authorized outside this system, and activated by a declared condition rather than by a request. `continuity_invocation` only. |

### 1.2 The intent types

Each type carries its familiar service-management meaning. What changes when
the actor is an agent is that the declaration is graded before the work runs,
and the type fixes which facts have to be declared.

| Type | Definition |
|---|---|
| **`change`** | A single unit of production work against one target: add, modify or remove. The atomic unit — every other production type either bundles changes, depends on something that does, or authorizes them. Where an existing change record maps. |
| **`release`** | A set of changes packaged to ship together. Bundles one or more `change` intents and inherits the most restrictive level among them, so one risky migration sets the level for the whole release. |
| **`deployment`** | Moving one release into one environment. Cites exactly one `release`. Kept separate from release precisely so the same release deploys to staging and production under different adjudications — environment is a likelihood factor, so production costs a step that staging does not. |
| **`service_request`** | Fulfilment of a catalogue item, which is production work. Cites the `catalogue_ref` it came from. Raising the request is a record-plane act; fulfilling it is what this type governs. Pre-authorized in the sense that the approval already lives in the catalogue entry, so §7's grant rules do not apply. |
| **`decommission`** | Retiring a service or asset. Bundles the changes that make it up, plus `stages`, because decommissioning is ordered and largely one-way: the staging is the point, not an optional extra. |
| **`maintenance_window`** | An agreed period during which disruption is permitted. Declares `window.start`, `window.end` and the `service_commitment` that holds during it. A deployment names the window it must fall inside (N-62); the window is adjudicated on its own. |
| **`continuity_invocation`** | Invoking an approved continuity or disaster-recovery plan. Cites the `plan_ref` and the `trigger` that fired. Pre-authorized because the approval lives in the plan itself. Citing an emergency raises the permission ceiling only: it never lowers a computed level and never reaches the pinned cells (N-41, N-42). |
| **`incident`** | An unplanned interruption or degradation. Declares `severity` and a `dedup_key`. Lives on the record plane and produces work rather than doing it: raising an incident fixes nothing, and the remediation is its own adjudicated `change`. |
| **`campaign`** | A standing approval for a bounded class of future changes — the fleet equivalent of a pre-approved standard change. Declares which children it covers (`class_predicate`), how far it goes (`caps`, including a child cap and a maximum level), and when it lapses (`expires_at`). It never lowers a child's level; it supplies the human approval in advance so covered children skip individual sign-off. |
| **`exception`** | A time-boxed widening of a profile — framework §12.3's exception process expressed as an intent. Declares the profile being widened, the category that fixes its maximum duration and approving authority, the permissions being escalated, and an expiry. Restricted data still admits only Read and Move: the permanent prohibitions cannot be reached through an exception. |

---

## 2. The intent envelope

Every intent, of every type, is a single JSON object conforming to
`schemas/intent.schema.json`.

### 2.1 Common fields

| Field | Required | Type | Notes |
|---|---|---|---|
| `$schema` | No | string | `https://rmacd-framework.org/schema/v2/intent.json` |
| `intent_id` | **Yes** | string | `^int-[a-z0-9][a-z0-9-]*$`; unique within the issuing organization (N-57) |
| `intent_type` | **Yes** | string | A registered type (§4) |
| `submitted_at` | **Yes** | date-time | RFC 3339, UTC |
| `actor` | **Yes** | object | §3 |
| `declaration` | **Yes** | object | The declared facts (§2.2) |
| `justification` | No | string | Free text; never an adjudication input |
| `composes` | Conditional | array of `intent_id` | Required by bundle types (§4) |
| `requires` | Conditional | array of `intent_id` | Required by dependent types (§4) |
| `window_ref` | No | `intent_id` | A `maintenance_window` intent a deployment commits to fall inside (N-62) |
| `grant_ref` | No | `intent_id` | A campaign or exception this intent claims coverage from (§7) |
| `compliance_tags` | No | array of string | Framework §10 vocabulary; a closed enum in the schema |
| `provenance` | No | object | Where the intent came from: `rationale_ref`, `produced_by`, `source_intent_id` |
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
the earlier of `valid_until` and the grant's `expires_at` governs. `valid_until`
**MUST** be later than `submitted_at`.

### 2.3 The intent lifecycle

An intent moves through a fixed set of states, and no others. Submission
either fails validation and ends as **rejected**, or is accepted and graded
exactly once, producing one decision record. A graded intent is **awaiting
decision** until a human, or a grant claimed at grading time, records the
decision; a decided intent is then **executed** before `valid_until`, or ends
as **expired**. Reconciliation (§10) closes the loop on executed intents.

```
submitted ──▶ rejected                        (schema fails; recorded, N-59)
    │
    ▼ graded once (one decision record, N-58)
awaiting decision ──▶ decided ──▶ executed ──▶ reconciled
    │                    │
    └────────────────────┴──▶ expired         (valid_until passes; reconciles
                                               as unexecuted, N-52)
```

The states are evidence, not workflow: an implementation is free to run any
approval workflow it likes between grading and decision, but the record of
what happened admits only these outcomes.

**N-57 (One Id, One Intent).** <a id="n-57"></a>An implementation **MUST**
refuse a second intent bearing an `intent_id` it has already accepted.
Changed facts arrive as a new intent, with a new id, graded on its own.

**N-58 (No Second Grading).** <a id="n-58"></a>An accepted intent **MUST** be
graded exactly once. An implementation **MUST NOT** replace an emitted
decision record with a recomputed one. Re-running the computation to verify a
past decision is always fine — N-21 exists to make that possible. What it can
never do is displace the record.

**N-59 (Rejections Leave a Trace).** <a id="n-59"></a>An implementation
**MUST** record every rejection in the audit trail, with the submitted
document, the failure, and the time. A rejection **MUST NOT** produce a
decision record. A decision record asserts that grading ran; a rejection
asserts that it never did. Keeping the two artifacts distinct is what lets an
auditor count both.

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
obligations when combined with other intents, and any additional required
fields.

| Type | Plane | Maturity | Required beyond the envelope | Combines as |
|---|---|---|---|---|
| `change` | Production | Stable | — | Building block |
| `release` | Production | Stable | `composes` (≥ 1 `change`) | Bundle |
| `deployment` | Production | Stable | `requires` (exactly 1 `release`) | Dependent |
| `service_request` | Production | Stable | `catalogue_ref` | Grants over `change` |
| `decommission` | Production | Incubating | `composes` (≥ 1 `change`), `stages` | Bundle |
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

**N-11 (Bundles Inherit the Worst).** <a id="n-11"></a>For any bundle intent, the computed level
**MUST** be the most restrictive level among the bundle itself and all
intents it composes or requires. Membership in a bundle **MUST NOT** lower
any child's own computed level.

**N-63 (Children Are Graded First).** <a id="n-63"></a>A bundle **MUST NOT**
receive a human decision before every intent it composes or requires has been
graded. Until every child is graded, the bundle's own level is provisional —
N-11's floor cannot be computed over children that have no level yet.

**N-62 (A Deployment Names Its Window).** <a id="n-62"></a>A `deployment`
**MAY** cite one maintenance-window intent through `window_ref`. Where a
window is cited, execution outside it **MUST** reconcile as `divergent` (§10).
The citation is a commitment, not a bound on grading: the window changes what
counts as executing the declared intent, never the computed level.

**N-53 (Same Incident, Same Key).** <a id="n-53"></a>`dedup_key` **MUST** be
computed the same way every time, from the field set the deployment declares in
its bound profile. An implementation **MUST** record which rule produced it.
Where the bound profile declares no field set, the key **MUST** be computed
from `target_class` and `environment`.

**N-54 (The System's Key Wins).** <a id="n-54"></a>A `dedup_key` supplied by
the actor **MUST NOT** create a new incident identity; it **MAY** only join an
existing one. Where a supplied key and a computed key disagree, the computed key
governs and the discrepancy **MUST** be recorded.

**N-70 (First Reports Are Never Gated).** <a id="n-70"></a>Record-plane
budgets and deduplication **MAY** throttle repeats of a `dedup_key`. They
**MUST NOT** delay, gate or suppress the first report of a distinct `dedup_key`
within its deduplication window. Governing the record plane is a control on
fleets, not a checkpoint on first responders.

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
6. level := ladder[min(index(base) + steps, 4)]  → stops below prohibited     (N-14a)
7. Apply the bundle floor for bundle types.                                   (N-11)
8. Apply grant coverage, if any.                 → approves, never lowers     (N-27)
9. Emit the decision record.                     → permanent, append-only     (N-43)
```

For a grant, step 4 reads the cells the grant can cover rather than the grant's
own declaration (N-66, §7.5).

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

**N-14 (The One-Way Rule).** <a id="n-14"></a>The computed level **MUST**
be at least as restrictive as the base level. A factor, grant, emergency,
attestation or configuration **MUST NOT** move a level toward lower oversight.

**N-14a (Escalation Stops Below Prohibited).** <a id="n-14a"></a>Escalation **MUST** stop at `elevated_approval`.
Likelihood **MUST NOT** move an intent to `prohibited`.

`prohibited` means no human decision can authorize the action for an
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

### 5.2 Why the rule only goes one way

The actor supplies the facts. Any mechanism capable of lowering a level would
therefore let an actor rate itself by choosing what to declare. Under one-way
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
adjudication, an approved grant, and a recorded human decision, singly or
together, **MUST NOT** authorize an operation the actor's bound profile or a
tool capability ceiling forbids. An intent that adjudicates successfully and is
subsequently refused by interception is correct behaviour, not a defect.

### 5.6 Determinism

**N-21 (Same Inputs, Same Level).** <a id="n-21"></a>Adjudication **MUST** be reproducible. Given the same intent, matrix
version, likelihood weight-table version, policy version, and decision-log
epoch, an implementation **MUST** produce the same level. The four version
inputs **MUST** be recorded in the decision record (§9), alongside the
`intent_id` that identifies the intent they were applied to.

Adjudication is deterministic but not stateless: precedent and budget standing
read organizational state. Reproducibility is therefore defined against a
recorded log epoch rather than against the intent alone.

**N-60 (The Epoch Names the State).** <a id="n-60"></a>`log_epoch` **MUST**
identify the decision-log state the grading read. An implementation **MUST**
advance the epoch whenever precedent, budget standing, demotion, or grant
state changes. Two gradings that read the same epoch read the same facts, so
any past decision replays by pinning its four recorded version inputs — the
epoch among them.

---

## 6. Action patterns and precedent

Precedent is what lets a well-trodden action stop costing human
attention. The class of like-for-like actions it is counted over is
consequently the most security-sensitive definition in this specification:
**whatever the action pattern excludes becomes a gradient an actor can descend
to erode its own scrutiny.**

### 6.1 The action pattern key

**N-22 (The Six-Field Pattern Key).** <a id="n-22"></a>The action pattern key **MUST** be a SHA-256 hash over the agreed
byte form (N-56) of exactly these fields, and **MUST NOT** include any other field:

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

**N-56 (One Byte Stream, One Hash).** <a id="n-56"></a>The agreed byte form
**MUST** be the JSON Canonicalization Scheme, RFC 8785. Given the same six
fields, every implementation **MUST** produce the same bytes, and so the same
key. Without one pinned byte form, two honest engines hash the same intent to
different keys, precedent stops transferring between them, and the key silently
loses its meaning across implementations.

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

1. The intent was adjudicated and received a human decision permitting
   execution.
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

**N-61 (Precedent Ages Only by Policy).** <a id="n-61"></a>An organization
**MAY** expire precedent after an age it chooses. Where it does, the age bound
**MUST** live in the versioned weight table (N-18). One reconciled success is
enough to retire the unprecedented factor, and it stays retired until a
mismatch wipes it (N-26) or a declared age bound expires it — never by an
undocumented rule inside the engine.

---

## 7. Grants: campaigns and exceptions

A grant is a human approval recorded in advance, covering a bounded class of
future intents. Grants are the mechanism by which humans govern classes rather
than instances — and the mechanism most capable of laundering privilege if
loosely specified.

### 7.1 Coverage is approval in advance, not a discount

**N-27 (Grants Approve, Never Lower).** <a id="n-27"></a>A grant **MUST NOT** change a child intent's computed level. It
**MAY** satisfy the child's approval requirement in advance, by supplying a
recorded human decision.

**N-28 (Coverage Is All or Nothing).** <a id="n-28"></a>A child is covered only when **all** of the following hold. If any
fails, the child **MUST** route to a human for an individual decision:

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
6. For an `exception`, the child's bound profile is the exception's
   `base_profile_id`, and the child's `actor.id` or `on_behalf_of` equals the
   exception's. A widening of one profile is not claimable from another.

**N-29 (No Grant Covers Prohibited).** <a id="n-29"></a>A grant **MUST NOT** cover a `prohibited` child under any
circumstance, and **MUST NOT** be construed as an exception to framework §12.5.

### 7.2 Class match rules

**N-30 (The Closed Match-Rule Fields).** <a id="n-30"></a>A `class_predicate` **MUST** be evaluated deterministically and
**MUST** match only on this closed set of fields:

`intent_type`, `declaration.operation`, `declaration.data_classification`,
`declaration.environment`, `declaration.target_class`, `actor.id`,
`actor.on_behalf_of`.

The match rule names these flattened, as `intent_type`, `operation`,
`data_classification`, `environment`, `target_class`, `actor_id` and
`on_behalf_of`; the schema admits no other key.

**N-31 (Match All, Never Execute).** <a id="n-31"></a>All specified fields
**MUST** match together, every one of them. Wildcards **MUST NOT** appear in
any field except `target_class`. A match rule **MUST NOT** match on
`justification`, `metadata`, or any free-text field, and **MUST NOT** be
expressed as executable code.

**N-32 (No Blanket Grants).** <a id="n-32"></a>A match rule that specifies no fields, or that would match every
intent of a type, **MUST** be rejected at grant submission. Blanket grants are
prohibited by framework §12.5.

### 7.3 Caps, expiry and revocation

**N-33 (Every Grant Expires and Caps).** <a id="n-33"></a>Every grant **MUST**
declare `expires_at`. Indefinite or open-ended grants **MUST** be rejected,
per framework §12.5. A `campaign` **MUST** additionally declare
`caps.max_children` and `caps.max_level`, because its bounds are otherwise
only a match rule. An `exception` is bounded instead by its
`escalated_permissions` grid and by the maximum duration its §12.2 category
fixes; it **MAY** declare `caps` in addition.

**N-34 (Revocation Is Immediate).** <a id="n-34"></a>Revocation **MUST** take effect immediately. Intents adjudicated after
revocation **MUST NOT** be covered.

**N-35 (Past Dispositions Stand).** <a id="n-35"></a>A child already decided
when the grant is revoked stays validly decided. The implementation **MUST**
record it as affected by the revocation and mark it for human review.

**N-55 (Caps Count Once).** <a id="n-55"></a>Checking a grant's caps and
consuming capacity against them **MUST** be one atomic operation. A grant's
lifecycle transitions **MUST** be totally ordered with respect to coverage
decisions. Where an implementation cannot establish that order, the child
**MUST** route to a human for an individual decision.

A grant carries one field beyond the envelope that records where it is in its
life:

| Field | Required | Notes |
|---|---|---|
| `status` | No | `requested`, `active`, `expired`, `revoked` or `closed`. Set by the implementation as the grant moves through framework §12.3's steps; an actor submits `requested` or nothing |

**N-71 (Lifecycle Changes Leave a Trace).** <a id="n-71"></a>An actor **MAY**
submit a grant only as `requested`. Every later `status` transition **MUST** be
made by the implementation and recorded in the audit trail with who made it and
when. A transition changes no declared fact, so it is not a second intent under
N-57 and does not touch the decision record under N-43.

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
| 3. Approval Decision | The §12.2 authority records its decision |
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
decision belongs to the authority named in framework §12.2.

### 7.5 Grading the grant itself

A grant is an intent and is graded like one, with one difference: the facts
that matter are the ones about what it can cover, not the ones the requester
chose to write in its own declaration. Without that difference a requester
could declare a harmless `declaration` on a campaign whose match rule reaches
production, and have the grant itself land at a level no human looks at —
self-rating one level up.

**N-66 (A Grant Is Graded by Its Reach).** <a id="n-66"></a>A grant's base
level **MUST** be the most restrictive effective-matrix cell among those its
`class_predicate` or `escalated_permissions` grid can cover. It **MUST NOT** be
read from the grant's own `declaration`. The likelihood factors then apply as
they do to any other intent. A match rule that leaves `operation` or
`data_classification` open covers every value of it and is graded accordingly;
one that reaches a pinned cell computes to `prohibited` and is refused (N-29).

**N-67 (A Grant Is Never Graded Below Its Cap).** <a id="n-67"></a>A grant's
computed level **MUST** be at least as restrictive as its `caps.max_level`.
Where the computation lands lower, the implementation **MUST** raise it to
`caps.max_level` and record `grant_cap` as the escalation factor. The human
who approves a grant at a level is the human the grant's own grading has to
reach.

**N-68 (Every Grant Gets a Human Decision).** <a id="n-68"></a>A grant
**MUST NOT** become `active` without a recorded `disposition` whose outcome
permits it, whatever level it computed to. A campaign that computes to `autonomous`
still waits for a human: a grant is approval recorded in advance, and there is
no approval to record if nobody gave one.

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
| `action_pattern_key` | Conditional | §6.1; required unless `implementation_level` is `L1` (N-69) |
| `action_pattern_fields` | Conditional | The six §6.1 fields verbatim; required when `implementation_level` is `L1` (N-69) |
| `base_level` | **Yes** | Before escalation |
| `computed_level` | **Yes** | After escalation, the bundle floor, and the prohibited floor |
| `escalation_factors` | **Yes** | Array of `{factor, steps, cause}`, `factor` and `steps` required; the five §5.4 factors plus `unresolved_authorization` (N-6) and `composition_floor` (N-11). Empty if none fired |
| `impact_basis` | **Yes** | Classification, or the declared substitute (N-16) |
| `matrix_version` | **Yes** | Reproducibility input |
| `likelihood_weights_version` | **Yes** | Reproducibility input |
| `policy_version` | **Yes** | Reproducibility input |
| `log_epoch` | **Yes** | Reproducibility input (N-60); `seq-` and the shared sequence number the grading read (N-75) |
| `profile_id` | **Yes** | The bound profile that supplied the ceiling |
| `implementation_level` | Conditional | `L1`, `L2` or `L3` — required where the implementation claims a level (N-65, §11.1) |
| `grant_ref` | No | The grant that satisfied approval in advance, if any |
| `disposition` | No | The recorded human decision: `{outcome, approver, decided_at, note}`, `outcome` and `decided_at` required; `outcome` is one of framework §12.3 Step 3's four decisions |
| `prohibition_source` | Conditional | `pinned` or `extended`, when the level is `prohibited` (N-14b) |
| `reconciliation` | No | Populated after execution (§10) |

**N-43 (The Permanent Decision Record).** <a id="n-43"></a>A decision record
**MUST** be permanent and append-only. An implementation **MUST NOT** change a
decision record after emission. The only permitted additions are a
`disposition` and a `reconciliation` result.

**N-44 (Name the Prohibition Source).** <a id="n-44"></a>Where the computed level is `prohibited`, `prohibition_source`
**MUST** distinguish `pinned` (framework §12.5) from `extended` (an
organization's own declared prohibition), per N-14b. Escalation is never a
source: likelihood cannot reach `prohibited` (N-14a).

**N-45 (One Audit Trail).** <a id="n-45"></a>Decision records **MUST** join the same audit trail as interception
records, on `intent_id`.

### 9.1 The two logs

An implementation keeps two append-only streams of its own, and joins both to
a third it does not own. The **intent log** holds everything that was
submitted, as it was submitted, whether it was accepted or not, and every
later change to a grant's standing. The **adjudication log** holds decision
records and the two attachments N-43 permits, and nothing else. The
**interception audit trail** is the framework's Appendix C.6 record stream,
written by the enforcement side; its records carry `intent_id` where both
modes run (N-46). The three join on one key:

| Stream | Entry key | Holds | Joins to |
|---|---|---|---|
| Intent log | `intent_id` | Submissions, rejections, grant status transitions | The adjudication log, on `intent_id` |
| Adjudication log | `decision_id` | Decision records, `disposition` and `reconciliation` attachments | The intent log and the audit trail, on `intent_id` |
| Interception audit trail | record id | Appendix C.6 records, with `extra.intent_id` | The adjudication log, on `intent_id` |

Each question an auditor asks is then one join. What was asked and refused at
the door is the intent log alone. What was graded, and how, is the
adjudication log. Whether what ran matched what was declared is the
adjudication log against the audit trail, which is reconciliation (§10).
Precedent is a count over the adjudication log restricted to reconciled
successes (N-25).

An intent-log entry conforms to `schemas/intent-log-entry.schema.json`:

| Field | Required | Notes |
|---|---|---|
| `seq` | **Yes** | From the counter both logs share (N-76) |
| `logged_at` | **Yes** | RFC 3339, UTC |
| `kind` | **Yes** | `submission`, `rejection` or `transition` |
| `intent_id` | Conditional | Required for `submission` and `transition`; a rejection records it where the document carried one |
| `document` | Conditional | The intent exactly as received; required for `submission`, and for `rejection` where the submission parsed as JSON |
| `raw` | Conditional | The submission as text, for a `rejection` of something that was not JSON |
| `failure` | Conditional | Why validation failed; required for `rejection` |
| `from_status` | No | The grant's `status` before a `transition` |
| `to_status` | Conditional | The grant's `status` after a `transition`; required for `transition` |
| `changed_by` | Conditional | Who made the `transition` (N-71); required for `transition` |

**N-72 (Two Logs, Never One).** <a id="n-72"></a>An implementation **MUST**
keep the intent log and the adjudication log as distinct append-only streams.
A rejection **MUST** be written to the intent log and **MUST NOT** be written
to the adjudication log. Keeping the streams apart is what makes N-59's
distinction impossible to blur: nothing in the adjudication log can be
mistaken for a refusal, and nothing in the intent log for a grade.

**N-73 (Logged as Received).** <a id="n-73"></a>Every submission **MUST** be
written to the intent log as an entry carrying the document exactly as
received. Where the submission was not valid JSON, the implementation **MUST**
keep it as text in `raw`. A replay under N-21 starts from the bytes the actor
sent, never from a parsed and re-serialized copy.

### 9.2 The adjudication log

An adjudication-log entry conforms to
`schemas/adjudication-log-entry.schema.json`:

| Field | Required | Notes |
|---|---|---|
| `seq` | **Yes** | From the counter both logs share (N-76) |
| `logged_at` | **Yes** | RFC 3339, UTC |
| `kind` | **Yes** | `decision`, `disposition` or `reconciliation` |
| `decision_id` | **Yes** | The decision record this entry is, or attaches to |
| `record` | Conditional | The decision record as emitted (§9); required for `decision` |
| `disposition` | Conditional | The human decision; required for a `disposition` attachment |
| `reconciliation` | Conditional | The reconciliation result (§10); required for a `reconciliation` attachment |

**N-74 (The Adjudication Log Holds Only Decisions).** <a id="n-74"></a>Every
entry in the adjudication log **MUST** be a decision record, a `disposition`
attachment or a `reconciliation` attachment. An attachment **MUST** cite the
`decision_id` it attaches to, and an implementation **MUST NOT** attach a
second `disposition` or a second `reconciliation` to one decision. The
attachments are how N-43's two permitted additions reach an append-only
stream: the record itself is never rewritten.

### 9.3 The epoch

**N-75 (The Epoch Is a Sequence Number).** <a id="n-75"></a>`log_epoch`
**MUST** be the string `seq-` followed by the `seq` of the latest entry, in
either log, that the grading read. Two engines that agree on the logs then
agree on the epoch, and a recorded epoch names an exact prefix of both logs.

**N-76 (One Counter Orders Both Logs).** <a id="n-76"></a>Every entry in
either log **MUST** carry a `seq` drawn from one counter shared by both logs,
assigned at write and strictly increasing. One counter is what gives N-55 its
total order and N-75 its meaning: a grant's transition and the coverage
decision that raced it are ordered by their sequence numbers, whichever log
each landed in.

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
| `divergent` | An executed action carried a different operation, target class, classification, environment or scope — or fell outside a cited maintenance window (N-62) |
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

## 11. The checklist

An implementation meets this specification when every checklist item at its
claimed level holds. The list is exhaustive over obligations: every **MUST**
and **MUST NOT** in this document rolls up into exactly one item below, and
`requirements.json` records the mapping. One rule is deliberately excluded:
N-41's **MAY** leaves a choice open rather than imposing an obligation, so
there is nothing for a checklist run to assert.

| # | Level | Name | Requirement |
|---|---|---|---|
| <a id="c-1"></a>C-1 | L1 | Malformed Intents Rejected | Intents are validated against `intent.schema.json`; malformed intents are rejected, never defaulted (N-1) |
| <a id="c-2"></a>C-2 | L1 | The Permanent No Comes First | The §12.5 immutable floor is checked before any other computation and is unreachable by any override (N-12) |
| <a id="c-3"></a>C-3 | L1 | Single Source Matrix | The base level comes from the framework's effective matrix; no second matrix exists (N-13) |
| <a id="c-4"></a>C-4 | L1 | Never Less Restrictive | No mechanism can produce a level less restrictive than the base level (N-14) |
| <a id="c-4a"></a>C-4a | L1 | Escalation Stops Early | Escalation stops at `elevated_approval`; likelihood never reaches `prohibited` (N-14a) |
| <a id="c-5"></a>C-5 | L1 | Five Factors, No Negatives | All five likelihood factors are implemented, no weight is negative, and any precedent age bound lives in the versioned weight table (N-17, N-18, N-61) |
| <a id="c-6"></a>C-6 | L2 | Pattern Key Exactly Six | The action pattern key covers exactly the six fields in §6.1, serialized per RFC 8785, so every implementation computes the same key (N-22, N-56) |
| <a id="c-7"></a>C-7 | L2 | Precedent Comes From Checks | Precedent accrues only from reconciled successes (N-25) |
| <a id="c-8"></a>C-8 | L1 | Accountable Human Required | Non-human actors without a resolvable `on_behalf_of` are rejected (N-5) |
| <a id="c-9"></a>C-9 | L1 | Unknown Actors Fail Closed | Unresolvable authorization escalates non-Read operations to at least `approval`, and Read too on `confidential` and `restricted` (N-6) |
| <a id="c-10"></a>C-10 | L3 | Grants Never Change Levels | Grants satisfy approval in advance without changing computed levels, and never cover prohibited children (N-27, N-29) |
| <a id="c-11"></a>C-11 | L3 | Match Rules Closed and Declarative | Class match rules match only the closed field set, all fields at once, with no executable code (N-30, N-31) |
| <a id="c-12"></a>C-12 | L3 | Bounded and Expiring Grants | Every grant declares an expiry and a child cap; blanket and indefinite grants are rejected (N-32, N-33) |
| <a id="c-13"></a>C-13 | L1 | Profile Ceiling Holds | Adjudication never grants permission the bound profile withholds (N-20) |
| <a id="c-14"></a>C-14 | L1 | Reproducible Permanent Records | Every adjudication emits a permanent decision record carrying all four reproducibility inputs, the log epoch is the shared sequence number the grading read, and the record keeps `action_pattern_key` or, at L1, the six fields verbatim (N-21, N-43, N-60, N-69, N-75) |
| <a id="c-15"></a>C-15 | L1 | Prohibition Source Recorded | Prohibited decisions distinguish `pinned` from `extended` (N-44) |
| <a id="c-16"></a>C-16 | L2 | No False Matches | Unreconcilable executions are never recorded as `matched` (N-49) |
| <a id="c-17"></a>C-17 | L1 | The Envelope Is the Whole Input | Only fields this specification and the schema define may grade an intent; a missing classification resolves to the most sensitive tier; a rollback claim never lowers the level (N-2, N-3, N-4) |
| <a id="c-18"></a>C-18 | L1 | Actors Are Recorded, Not Trusted | Actor kind never changes the computed level, and no grade an actor asserts about itself is honoured (N-7, N-8) |
| <a id="c-19"></a>C-19 | L1 | The Type Registry Is Flat | Maturity is never a rank, and every registered type uses the common envelope and adjudication contract (N-9, N-10) |
| <a id="c-20"></a>C-20 | L1 | Bundles Take the Worst | A bundle computes to the most restrictive level among itself and its children, never softens a child, and is decided only after every child is graded (N-11, N-63) |
| <a id="c-21"></a>C-21 | L1 | Prohibited Has Two Sources | `prohibited` is reachable only as `pinned` or `extended`, and the pinned set is never narrowed (N-14b) |
| <a id="c-22"></a>C-22 | L1 | Impact Is Declared, Not Supplied | Impact is the four-tier classification ordering, and any substitute is profile-declared and stamped into every record (N-15, N-16) |
| <a id="c-23"></a>C-23 | L1 | No Factor Subtracts | No likelihood factor contributes negative steps (N-19) |
| <a id="c-24"></a>C-24 | L1 | One Target, One Class | `target_class` is computed the same way every time, and a value the actor supplies never wins (N-23, N-24) |
| <a id="c-25"></a>C-25 | L2 | A Mismatch Clears Precedent | A material mismatch found at reconciliation clears the affected action pattern's precedent and demotes the actor (N-26) |
| <a id="c-26"></a>C-26 | L3 | Coverage Needs Every Condition | A child is covered only when every one of the six coverage conditions holds, including that an exception covers only the profile and actor it names; otherwise it routes to a human individually (N-28) |
| <a id="c-27"></a>C-27 | L3 | Grants End Cleanly | Revocation takes effect immediately; children already decided are recorded as affected and marked for human review; every grant status transition is made by the implementation and recorded (N-34, N-35, N-71) |
| <a id="c-28"></a>C-28 | L3 | Exceptions Stay Inside §12.5 | An exception tripping any of framework §12.5's five prohibitions is rejected, and adjudication never decides the grant (N-36, N-37) |
| <a id="c-29"></a>C-29 | L2 | Budgets and Demotion Escalate | Budget standing comes from the bound profile, and breach and demotion escalate rather than deny or reduce (N-38, N-39, N-40) |
| <a id="c-30"></a>C-30 | L1 | Emergencies Only Raise Ceilings | An emergency never lowers a level, waives a factor, or touches the pinned cells (N-42) |
| <a id="c-31"></a>C-31 | L2 | One Joined Audit Trail | Decision records join the interception audit trail on `intent_id` (N-45) |
| <a id="c-32"></a>C-32 | L2 | Reconciliation Classifies Everything | Every executed action is classed into one of the four results, including a scope comparison; divergence is recorded as a governance event, clears precedent and demotes (N-47, N-48) |
| <a id="c-33"></a>C-33 | L1 | The Sequence Is Honoured | The nine adjudication steps are applied in the order §5.1 gives them (N-50) |
| <a id="c-34"></a>C-34 | L2 | The Intent ID Travels | Where both modes are deployed, `intent_id` is propagated into the execution path so interception records carry it (N-46) |
| <a id="c-35"></a>C-35 | L2 | Intents Carry an Expiry | Production-plane intents declare `valid_until`; execution after it is refused and the intent reconciles as `unexecuted` (N-52) |
| <a id="c-36"></a>C-36 | L2 | No Unchecked Self-Declaration | Any factor computed from a value the intent declares is attested by another party or compared against execution (N-51) |
| <a id="c-37"></a>C-37 | L1 | Incident Keys Are Computed | `dedup_key` is computed deterministically and recorded; an actor-supplied key may only join an existing incident; the first report of a distinct key is never delayed or suppressed (N-53, N-54, N-70) |
| <a id="c-38"></a>C-38 | L3 | Cap Checks Are Atomic | Grant cap checks consume atomically and lifecycle transitions are ordered against coverage; unresolvable order routes to a human (N-55) |
| <a id="c-39"></a>C-39 | L1 | The Lifecycle Is Enforced | A duplicate intent_id is refused, and an emitted decision record is never replaced by a recomputed one (N-57, N-58) |
| <a id="c-40"></a>C-40 | L1 | Rejections Are Recorded | Every rejection is recorded in the audit trail with its reason, and no rejection produces a decision record (N-59) |
| <a id="c-41"></a>C-41 | L2 | Windows Bind Deployments | A deployment executed outside the maintenance window it cited reconciles as divergent (N-62) |
| <a id="c-42"></a>C-42 | L1 | Graders Are Not Requesters | Where grading is done by hand, the grader is never the requesting actor or its accountable human (N-64) |
| <a id="c-43"></a>C-43 | L1 | Claimed Levels Are Stamped | An implementation claiming a level stamps implementation_level into every decision record it emits (N-65) |
| <a id="c-44"></a>C-44 | L3 | Grants Are Graded by Their Reach | A grant's base level comes from the most restrictive cell its match rule or permission grid can cover, its computed level is never below `caps.max_level`, and no grant becomes active without a recorded human decision (N-66, N-67, N-68) |
| <a id="c-45"></a>C-45 | L1 | The Logs Are Kept | The intent log and the adjudication log are distinct append-only streams sharing one sequence counter; every submission is logged as received, rejections never enter the adjudication log, and it holds only decision records and their single attachments (N-72, N-73, N-74, N-76) |

### 11.1 The three levels

Not every deployment starts with execution feedback, and not every deployment
offers grants. The checklist is therefore split into three cumulative levels,
so that an organization can adopt the discipline in stages and say honestly
which stage it is at.

| Level | Name | What it takes |
|---|---|---|
| **L1** | Adjudicating | Grade every intent and keep permanent records. Every L1 item can be met with paper — a form, a register, a filing discipline — which is deliberate: the practice is adoptable before any software exists. |
| **L2** | Reconciling | Everything in L1, plus execution feedback: interception records join the decision log, declarations are checked against what actually ran, and precedent becomes trustworthy. |
| **L3** | Delegating | Everything in L2, plus the grant machinery: campaigns and exceptions let humans govern classes of work instead of instances. |

A level is a claim about which items hold, not a partial pass on any one item:
an implementation claims the highest level at which *every* item holds, and
items above the claimed level are simply not claimed. An implementation that
offers no grants can honestly claim L2; one that cannot see execution stops at
L1. The levels are cumulative by construction — there is no path to L3 that
skips reconciliation, because grants without reconciliation are approvals
nobody ever checks up on.

Two boundaries are worth naming. The pattern-key hash sits at L2, not L1,
because a SHA-256 over a canonical byte stream cannot be produced by hand: an
L1 register records the six §6.1 fields verbatim in place of the hash, and
computing the key from them is part of moving to L2 (N-69). And the incident
deduplication key stays at L1 because its default inputs (N-53) are two fields
a person can copy into a ledger.

Level numbers are pinned identifiers, like rule and checklist numbers: a
future revision adds a level, and never renumbers one, because a published
claim of "L2" has to keep meaning the same thing.

**N-64 (No One Grades Their Own Ask).** <a id="n-64"></a>Where grading is
performed by hand, the person grading **MUST NOT** be the requesting actor or
the human it acts on behalf of. Automated grading carries this guarantee
structurally — the engine is not a party to the request. Hand grading
relocates the guarantee to the org chart, and it has to survive the move.

**N-65 (Say the Level You Claim).** <a id="n-65"></a>An implementation
claiming a level **MUST** stamp `implementation_level` into every decision
record it emits. A claim that appears nowhere in the evidence cannot be
audited; one stamped into every record can be checked record by record.

**N-69 (The Register Keeps the Six Fields).** <a id="n-69"></a>An
implementation at L1 **MUST** record the six §6.1 fields verbatim in
`action_pattern_fields` in place of `action_pattern_key`. An implementation at
L2 or L3 **MUST** record `action_pattern_key`. Either way the record carries
what the hash is computed from, so moving from L1 to L2 is a computation over
existing records, not a migration.

---

## 12. Security considerations

Every mechanism in this specification assumes a capable adversary who submits
well-formed intents. The threats below are the ones the design answers, each
with the rules that answer it. None of these defences is optional: each is a
binding rule elsewhere in this document, and this section only gathers them.

| Threat | The move | The answer |
|---|---|---|
| Self-rating | The actor words its declaration to earn a lower grade | Facts can only fail to add oversight, never subtract it (N-14, N-19); asserted grades are ignored (N-8); declared inputs are attested or checked (N-4, N-51) |
| Scrutiny erosion | Small variations walk an action out of its pattern, or into a well-trodden one | The pattern key is closed over six fields and one byte form (N-22, N-56); the system derives `target_class`, and its derivation wins (N-23, N-24) |
| Precedent farming | Submit many intents to manufacture standing | Only reconciled successes count (N-25); a mismatch wipes the pattern's standing and demotes (N-26, N-48) |
| Privilege laundering | A loose grant turns one approval into standing permission | Match rules are closed, conjunctive and declarative (N-30, N-31); blanket and indefinite grants are refused (N-32, N-33); no grant reaches `prohibited` (N-29); the grant itself is graded by its reach, never below its cap, and always by a human (N-66, N-67, N-68); an exception covers only the profile and actor it names (N-28) |
| Incident flooding | A fleet mints identities or buries humans in records | The system computes the deduplication key and its key wins (N-53, N-54); record-plane budgets bite at volume while the first-report invariant protects first reports (N-70) |
| Race conditions | Concurrent children spend a cap twice, or slip through a revocation | Cap checks consume atomically and lifecycle transitions are ordered (N-55); a duplicate id is refused (N-57); unresolvable order routes to a human |
| Evidence tampering | A record is rewritten after the fact to match what happened | Records are append-only (N-43); rejections leave their own trace (N-59); the epoch pins what the grading read (N-60) and names a prefix of two logs that share one counter (N-75, N-76); rejections and grades live in separate streams, logged as received (N-72, N-73, N-74); one audit trail joins both modes (N-45); grant lifecycle changes are made by the implementation and traced (N-71) |
| Floor probing | Escalation, emergency or grant paths are tried against the §12.5 cells | The floor is checked before anything else and is unreachable from every path (N-12, N-14b, N-29, N-42) |

Three limits are equally worth naming, because the specification does not
defend against them and an adopter has to. A colluding approver defeats
grants exactly as it defeats any approval process; separation of duties
(N-64) narrows this, and organizational controls have to do the rest. A
compromised bound profile moves the base matrix itself; profile integrity is
the framework's concern (§9 of the framework specification), not this
document's. And an actor that never declares is invisible to adjudication by
definition — that gap belongs to interception, which is why a mature
deployment runs both modes (§10).

---

## Appendix A: Requirement Quick Reference

Every rule and checklist item carries a short plain-English name. A name is a
reading aid, not an identifier: `N-14` and `C-5` are the stable references
external documents cite, and they never change. A name can be revised; a
number cannot. The three implementation levels are pinned the same way: L1, L2
and L3 keep their numbers and their meaning — add a level, never renumber one.

Anchors are keyed to the identifier rather than the name, for the same reason:
`#n-14` resolves to N-14 whatever it comes to be called.

This appendix is generated from `requirements.yaml` by `tools/check_spec.py`.
Edit the registry, not the tables.

### A.1 The rules

| # | Name | What it says | Section | Checked by |
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
| [N-11](#n-11) | Bundles Inherit the Worst | A bundle takes the most restrictive level among itself and its children; membership never softens a child | §4 | [C-20](#c-20) |
| [N-12](#n-12) | The Permanent No | Add, Change and Delete on Restricted return `prohibited` before anything else runs, and no override reaches them | §5.1 | [C-2](#c-2) |
| [N-13](#n-13) | One Matrix, No Second | The base level comes from the bound profile's effective matrix and from nowhere else | §5.1 | [C-3](#c-3) |
| [N-14](#n-14) | The One-Way Rule | Nothing — factor, grant, emergency, attestation or configuration — may move a level toward less oversight | §5.1 | [C-4](#c-4) |
| [N-14a](#n-14a) | Escalation Stops Below Prohibited | Likelihood stops at elevated_approval and can never reach the end of the ladder | §5.1 | [C-4a](#c-4a) |
| [N-14b](#n-14b) | Two Sources of Prohibited | `prohibited` arises only as `pinned` or `extended`; the pinned set may be grown, never shrunk | §5.1 | [C-21](#c-21) |
| [N-15](#n-15) | Classification Is Impact | The impact dimension is the four-tier classification ordering | §5.3 | [C-22](#c-22) |
| [N-16](#n-16) | Declare Any Impact Substitute | A substituted impact basis must be profile-declared, map onto the same four tiers, and be stamped into every record | §5.3 | [C-22](#c-22) |
| [N-17](#n-17) | The Five Likelihood Factors | All five factors must be implemented, each adding a non-negative number of steps | §5.4 | [C-5](#c-5) |
| [N-18](#n-18) | Weights Adjustable, Never Negative | Weights may be tuned but never below zero, and the weight table is versioned into every record | §5.4 | [C-5](#c-5) |
| [N-19](#n-19) | Factors Only Add | No likelihood factor may contribute a negative number of steps | §5.4 | [C-23](#c-23) |
| [N-20](#n-20) | Approval Is Not Permission | No adjudication, grant or human decision authorizes what the profile or capability ceiling forbids | §5.5 | [C-13](#c-13) |
| [N-21](#n-21) | Same Inputs, Same Level | The same intent under the same four recorded version inputs must reproduce the same level | §5.6 | [C-14](#c-14) |
| [N-22](#n-22) | The Six-Field Pattern Key | The action pattern key hashes exactly six named fields and nothing else | §6.1 | [C-6](#c-6) |
| [N-23](#n-23) | Same Target, Same Class | `target_class` is worked out the same way every time — the matching rule, else last-segment wildcarding — and the source is recorded | §6.2 | [C-24](#c-24) |
| [N-24](#n-24) | The System's Class Wins | A `target_class` supplied by the actor never beats the one the system works out; any disagreement is recorded | §6.2 | [C-24](#c-24) |
| [N-25](#n-25) | Only Checked Successes Count | Precedent needs a recorded human decision permitting execution, a checked execution, and no material mismatch | §6.3 | [C-7](#c-7) |
| [N-26](#n-26) | A Mismatch Wipes Precedent | A material mismatch clears the action pattern’s precedent and demotes the actor | §6.3 | [C-25](#c-25) |
| [N-27](#n-27) | Grants Approve, Never Lower | A grant supplies the human approval in advance; it never changes the child's computed level | §7.1 | [C-10](#c-10) |
| [N-28](#n-28) | Coverage Is All or Nothing | All six coverage conditions must hold, or the child routes to a human individually | §7.1 | [C-26](#c-26) |
| [N-29](#n-29) | No Grant Covers Prohibited | No grant reaches a prohibited child, and none is an exception to framework §12.5 | §7.1 | [C-10](#c-10) |
| [N-30](#n-30) | The Closed Match-Rule Fields | A class match rule matches only on the seven named fields; the schema admits no other key | §7.2 | [C-11](#c-11) |
| [N-31](#n-31) | Match All, Never Execute | Every named field must match; wildcards only in target_class, no free text and no code | §7.2 | [C-11](#c-11) |
| [N-32](#n-32) | No Blanket Grants | An empty or catch-all match rule is rejected at grant submission | §7.2 | [C-12](#c-12) |
| [N-33](#n-33) | Every Grant Expires and Caps | Every grant declares an expiry; a campaign additionally declares a child cap and a maximum level | §7.3 | [C-12](#c-12) |
| [N-34](#n-34) | Revocation Is Immediate | Nothing adjudicated after revocation is covered | §7.3 | [C-27](#c-27) |
| [N-35](#n-35) | Past Dispositions Stand | Children decided before revocation stay valid, but are recorded as affected and surfaced for review | §7.3 | [C-27](#c-27) |
| [N-36](#n-36) | The Five Named Prohibitions | An exception is rejected if it trips any of framework §12.5's five prohibitions, whether the schema catches it or not | §7.4 | [C-28](#c-28) |
| [N-37](#n-37) | Scrutiny, Not the Decision | Adjudicating an exception sizes the scrutiny required; the §12.2 authority decides whether to grant it | §7.4 | [C-28](#c-28) |
| [N-38](#n-38) | Budgets Come From the Profile | Budget standing comes from bound-profile constraints; no parallel budget vocabulary exists | §8.1 | [C-29](#c-29) |
| [N-39](#n-39) | Breach Escalates, Never Denies | A budget breach fires L4 escalation rather than a silent denial or a reduction | §8.1 | [C-29](#c-29) |
| [N-40](#n-40) | Demotion Is Escalation | Demotion is the L4 weight applied until it lifts, recorded with its cause — not a new state | §8.2 | [C-29](#c-29) |
| [N-41](#n-41) | Emergencies Raise the Ceiling | Citing an active emergency escalation raises the permission ceiling and nothing else | §8.3 | — |
| [N-42](#n-42) | Emergencies Never Lower Grades | An emergency cannot lower a level, waive a factor, or touch the pinned cells | §8.3 | [C-30](#c-30) |
| [N-43](#n-43) | The Permanent Decision Record | Decision records are append-only; only a human decision or a reconciliation result may be attached | §9 | [C-14](#c-14) |
| [N-44](#n-44) | Name the Prohibition Source | Every prohibited decision states `pinned` or `extended`; escalation is never a source | §9 | [C-15](#c-15) |
| [N-45](#n-45) | One Audit Trail | Decision records join the interception records' audit trail on `intent_id` | §9 | [C-31](#c-31) |
| [N-46](#n-46) | Carry the Intent ID Through | Where both modes run, intent_id propagates into the execution path | §10 | [C-34](#c-34) |
| [N-47](#n-47) | The Four Reconciliation Results | Every executed action is classed as matched, divergent, undeclared or unexecuted | §10 | [C-32](#c-32) |
| [N-48](#n-48) | Divergence Is a Governance Event | Divergent and undeclared results are recorded as events, clear the action pattern’s precedent, and demote | §10 | [C-32](#c-32) |
| [N-49](#n-49) | Unreconciled Is Not Matched | Missing interception coverage leaves `reconciliation.result` unset — never recorded as success | §10 | [C-16](#c-16) |
| [N-50](#n-50) | Steps Run In Order | The nine adjudication steps are applied in the order §5.1 gives them | §5.1 | [C-33](#c-33) |
| [N-51](#n-51) | Declared Inputs Get Checked | A factor may read a declared value only if that value is attested or reconciled | §5.4 | [C-36](#c-36) |
| [N-52](#n-52) | Every Intent Expires | A production-plane intent declares a `valid_until` after which its adjudication authorizes nothing | §2.2 | [C-35](#c-35) |
| [N-53](#n-53) | Same Incident, Same Key | `dedup_key` is computed the same way every time, and the rule that produced it is recorded | §4 | [C-37](#c-37) |
| [N-54](#n-54) | The System's Key Wins | An actor-supplied `dedup_key` may join an existing incident but never mint a new identity | §4 | [C-37](#c-37) |
| [N-55](#n-55) | Caps Count Once | Cap checks and grant lifecycle transitions are atomic and ordered; unresolvable order routes to a human | §7.3 | [C-38](#c-38) |
| [N-56](#n-56) | One Byte Stream, One Hash | The pattern key hashes RFC 8785 canonical bytes, so every implementation computes the same key | §6.1 | [C-6](#c-6) |
| [N-57](#n-57) | One Id, One Intent | A second intent bearing an already-accepted id is refused; changed facts arrive as a new intent | §2.3 | [C-39](#c-39) |
| [N-58](#n-58) | No Second Grading | An accepted intent is graded once; an emitted decision record is never replaced by a recomputed one | §2.3 | [C-39](#c-39) |
| [N-59](#n-59) | Rejections Leave a Trace | Every rejection is recorded in the audit trail with its reason; a rejection never produces a decision record | §2.3 | [C-40](#c-40) |
| [N-60](#n-60) | The Epoch Names the State | log_epoch identifies the decision-log state the grading read, and advances whenever that state changes | §5.6 | [C-14](#c-14) |
| [N-61](#n-61) | Precedent Ages Only by Policy | An organization may expire precedent by age; where it does, the bound lives in the versioned weight table | §6.3 | [C-5](#c-5) |
| [N-62](#n-62) | A Deployment Names Its Window | A deployment may cite one maintenance window; execution outside the cited window reconciles as divergent | §4 | [C-41](#c-41) |
| [N-63](#n-63) | Children Are Graded First | A bundle is not decided until every intent it composes or requires has been graded | §4 | [C-20](#c-20) |
| [N-64](#n-64) | No One Grades Their Own Ask | Where grading is done by hand, the person grading is never the requesting actor or its accountable human | §11.1 | [C-42](#c-42) |
| [N-65](#n-65) | Say the Level You Claim | An implementation claiming a level stamps that level into every decision record it emits | §11.1 | [C-43](#c-43) |
| [N-66](#n-66) | A Grant Is Graded by Its Reach | A grant's base level is the most restrictive cell its match rule or permission grid can cover, never its own declaration | §7.5 | [C-44](#c-44) |
| [N-67](#n-67) | A Grant Is Never Graded Below Its Cap | A grant's computed level is at least as restrictive as `caps.max_level`; a lower computation is raised to it and recorded | §7.5 | [C-44](#c-44) |
| [N-68](#n-68) | Every Grant Gets a Human Decision | No grant becomes active without a recorded human decision permitting it, whatever level it computed to | §7.5 | [C-44](#c-44) |
| [N-69](#n-69) | The Register Keeps the Six Fields | An L1 record keeps the six pattern fields verbatim in place of the hash; L2 and L3 records keep the hash | §11.1 | [C-14](#c-14) |
| [N-70](#n-70) | First Reports Are Never Gated | Record-plane throttling may limit repeats of a `dedup_key`, never the first report of a distinct one within its window | §4 | [C-37](#c-37) |
| [N-71](#n-71) | Lifecycle Changes Leave a Trace | A grant is submitted only as `requested`; every later status transition is made by the implementation and recorded | §7.3 | [C-27](#c-27) |
| [N-72](#n-72) | Two Logs, Never One | The intent log and the adjudication log are distinct append-only streams; a rejection goes to the first and never the second | §9.1 | [C-45](#c-45) |
| [N-73](#n-73) | Logged as Received | Every submission is written to the intent log exactly as received; unparseable input is kept as text | §9.1 | [C-45](#c-45) |
| [N-74](#n-74) | The Adjudication Log Holds Only Decisions | The adjudication log holds decision records and single disposition or reconciliation attachments that cite their decision, nothing else | §9.2 | [C-45](#c-45) |
| [N-75](#n-75) | The Epoch Is a Sequence Number | `log_epoch` is `seq-` plus the shared sequence number of the latest log entry the grading read | §9.3 | [C-14](#c-14) |
| [N-76](#n-76) | One Counter Orders Both Logs | Every entry in either log carries a `seq` from one shared, strictly increasing counter assigned at write | §9.3 | [C-45](#c-45) |

Every **MUST** and **MUST NOT** above is checked by an item in §11. The
entries showing — (N-41) leave a choice open rather than
impose an obligation, so §11 has nothing to assert about them.

### A.2 The checklist

An L1 item can be met with paper, an L2 item needs execution feedback, and an
L3 item needs the grant machinery; §11.1 defines the levels.

| # | Level | Name | What it says | Checks |
|---|---|---|---|---|
| [C-1](#c-1) | L1 | Malformed Intents Rejected | Schema validation gates adjudication, with no defaulting | [N-1](#n-1) |
| [C-2](#c-2) | L1 | The Permanent No Comes First | Framework §12.5's prohibition is checked before everything and survives every override | [N-12](#n-12) |
| [C-3](#c-3) | L1 | Single Source Matrix | One effective matrix supplies the base level; no second matrix exists | [N-13](#n-13) |
| [C-4](#c-4) | L1 | Never Less Restrictive | No mechanism produces a level below base | [N-14](#n-14) |
| [C-4a](#c-4a) | L1 | Escalation Stops Early | Escalation stops at `elevated_approval`; likelihood never reaches `prohibited` | [N-14a](#n-14a) |
| [C-5](#c-5) | L1 | Five Factors, No Negatives | All five likelihood factors are implemented, no weight is negative, and any precedent age bound lives in the versioned weight table | [N-17](#n-17), [N-18](#n-18), [N-61](#n-61) |
| [C-6](#c-6) | L2 | Pattern Key Exactly Six | The action pattern key covers the six §6.1 fields, no more and no fewer, serialized per RFC 8785 | [N-22](#n-22), [N-56](#n-56) |
| [C-7](#c-7) | L2 | Precedent Comes From Checks | Precedent comes only from executions that were checked and succeeded | [N-25](#n-25) |
| [C-8](#c-8) | L1 | Accountable Human Required | Non-human actors without a resolvable `on_behalf_of` are rejected | [N-5](#n-5) |
| [C-9](#c-9) | L1 | Unknown Actors Fail Closed | Unresolvable authorization escalates non-Read operations to at least approval, and Read too on confidential and restricted | [N-6](#n-6) |
| [C-10](#c-10) | L3 | Grants Never Change Levels | Grants leave computed levels untouched and never cover `prohibited` | [N-27](#n-27), [N-29](#n-29) |
| [C-11](#c-11) | L3 | Match Rules Closed and Declarative | Match rules match the closed field set, all fields at once, with no executable code | [N-30](#n-30), [N-31](#n-31) |
| [C-12](#c-12) | L3 | Bounded and Expiring Grants | Every grant carries an expiry and a child cap; blanket and indefinite grants are rejected | [N-32](#n-32), [N-33](#n-33) |
| [C-13](#c-13) | L1 | Profile Ceiling Holds | Adjudication never grants what the bound profile withholds | [N-20](#n-20) |
| [C-14](#c-14) | L1 | Reproducible Permanent Records | Every adjudication emits a permanent record carrying all four reproducibility inputs, the log epoch names a real log prefix, and the pattern key or its six fields are kept | [N-21](#n-21), [N-43](#n-43), [N-60](#n-60), [N-69](#n-69), [N-75](#n-75) |
| [C-15](#c-15) | L1 | Prohibition Source Recorded | Prohibited decisions distinguish `pinned` from `extended` | [N-44](#n-44) |
| [C-16](#c-16) | L2 | No False Matches | Unreconcilable executions are never recorded as `matched` | [N-49](#n-49) |
| [C-17](#c-17) | L1 | The Envelope Is the Whole Input | Only fields this specification and the schema define may grade an intent; a missing classification resolves to the most sensitive tier; a rollback claim never lowers the level | [N-2](#n-2), [N-3](#n-3), [N-4](#n-4) |
| [C-18](#c-18) | L1 | Actors Are Recorded, Not Trusted | Actor kind never changes the computed level, and no grade an actor asserts about itself is honoured | [N-7](#n-7), [N-8](#n-8) |
| [C-19](#c-19) | L1 | The Type Registry Is Flat | Maturity is never a rank, and every registered type uses the common envelope and adjudication contract | [N-9](#n-9), [N-10](#n-10) |
| [C-20](#c-20) | L1 | Bundles Take the Worst | A bundle computes to the most restrictive level among itself and its children, never softens a child, and is decided only after every child is graded | [N-11](#n-11), [N-63](#n-63) |
| [C-21](#c-21) | L1 | Prohibited Has Two Sources | `prohibited` is reachable only as `pinned` or `extended`, and the pinned set is never narrowed | [N-14b](#n-14b) |
| [C-22](#c-22) | L1 | Impact Is Declared, Not Supplied | Impact is the four-tier classification ordering, and any substitute is profile-declared and stamped into every record | [N-15](#n-15), [N-16](#n-16) |
| [C-23](#c-23) | L1 | No Factor Subtracts | No likelihood factor contributes negative steps | [N-19](#n-19) |
| [C-24](#c-24) | L1 | One Target, One Class | `target_class` is computed the same way every time, and a value the actor supplies never wins | [N-23](#n-23), [N-24](#n-24) |
| [C-25](#c-25) | L2 | A Mismatch Clears Precedent | A material mismatch clears the action pattern's precedent and demotes the actor | [N-26](#n-26) |
| [C-26](#c-26) | L3 | Coverage Needs Every Condition | A child is covered only when every one of the six coverage conditions holds, including the profile and actor an exception names | [N-28](#n-28) |
| [C-27](#c-27) | L3 | Grants End Cleanly | Revocation takes effect immediately, children already decided are recorded as affected, and every lifecycle change is traced | [N-34](#n-34), [N-35](#n-35), [N-71](#n-71) |
| [C-28](#c-28) | L3 | Exceptions Stay Inside §12.5 | An exception tripping any of framework §12.5's five prohibitions is rejected, and adjudication never decides the grant | [N-36](#n-36), [N-37](#n-37) |
| [C-29](#c-29) | L2 | Budgets and Demotion Escalate | Budget standing comes from the bound profile, and breach and demotion escalate rather than deny or reduce | [N-38](#n-38), [N-39](#n-39), [N-40](#n-40) |
| [C-30](#c-30) | L1 | Emergencies Only Raise Ceilings | An emergency never lowers a level, waives a factor, or touches the pinned cells | [N-42](#n-42) |
| [C-31](#c-31) | L2 | One Joined Audit Trail | Decision records join the interception audit trail on `intent_id` | [N-45](#n-45) |
| [C-32](#c-32) | L2 | Reconciliation Classifies Everything | Every executed action is classed into one of the four results, and divergence is recorded as a governance event | [N-47](#n-47), [N-48](#n-48) |
| [C-33](#c-33) | L1 | The Sequence Is Honoured | Adjudication applies the §5.1 steps in order | [N-50](#n-50) |
| [C-34](#c-34) | L2 | The Intent ID Travels | Where both modes are deployed, `intent_id` reaches the interception record | [N-46](#n-46) |
| [C-35](#c-35) | L2 | Intents Carry an Expiry | Production-plane intents declare an expiry, and nothing executes after it | [N-52](#n-52) |
| [C-36](#c-36) | L2 | No Unchecked Self-Declaration | A factor reading a declared value is attested or reconciled | [N-51](#n-51) |
| [C-37](#c-37) | L1 | Incident Keys Are Computed | `dedup_key` is computed, an actor-supplied key cannot mint a new incident, and a first report is never gated | [N-53](#n-53), [N-54](#n-54), [N-70](#n-70) |
| [C-38](#c-38) | L3 | Cap Checks Are Atomic | Cap consumption and revocation are ordered, and unresolvable order fails closed | [N-55](#n-55) |
| [C-39](#c-39) | L1 | The Lifecycle Is Enforced | Ids are accepted once and emitted decision records are never re-graded | [N-57](#n-57), [N-58](#n-58) |
| [C-40](#c-40) | L1 | Rejections Are Recorded | Every rejection lands in the audit trail; none produces a decision record | [N-59](#n-59) |
| [C-41](#c-41) | L2 | Windows Bind Deployments | A deployment that cites a maintenance window is held to it at reconciliation | [N-62](#n-62) |
| [C-42](#c-42) | L1 | Graders Are Not Requesters | Hand grading is never done by the actor who asked | [N-64](#n-64) |
| [C-43](#c-43) | L1 | Claimed Levels Are Stamped | A claimed implementation level appears in every decision record | [N-65](#n-65) |
| [C-44](#c-44) | L3 | Grants Are Graded by Their Reach | A grant is graded by the most severe cell it can cover, never below its cap, and always gets a human decision | [N-66](#n-66), [N-67](#n-67), [N-68](#n-68) |
| [C-45](#c-45) | L1 | The Logs Are Kept | Two append-only logs on one counter: submissions as received in one, decisions and their attachments in the other | [N-72](#n-72), [N-73](#n-73), [N-74](#n-74), [N-76](#n-76) |

---

## See also

- [`intents.md`](intents.md) — the model and why it is built this way, in
  plain words: the intent ladder, the two planes, campaigns, budgets, a worked
  example, and how to adopt the model in stages.
- `schemas/intent.schema.json` — the intent envelope and per-type constraints.
- `schemas/intent-decision.schema.json` — the decision record.
- `schemas/intent-log-entry.schema.json` and
  `schemas/adjudication-log-entry.schema.json` — the two logs (§9.1, §9.2).
- `docs/audit-evidence.md` — the audit trail decision records join (N-45).
- `RMACD_Framework_v1.4.md` §2.4 (autonomy levels), §3 (the matrix),
  §12 (exceptions and the immutable floor).
