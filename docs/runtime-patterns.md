# RMACD Runtime Patterns

**Companion to:** `RMACD_Framework_v1.4.md` (Appendices C and D)
**Targets:** SDK ≥ 0.10.0 (`rmacd-framework` on PyPI)

The canonical specification (Appendix C) describes the four-component
enforcement architecture (Policy Store, PDP, PEP, Audit Engine) and the
evaluation algorithm in pseudocode. It does not, however, specify how an
agent runtime *consumes* that architecture: how it learns which profile is
its own, how it discovers the classification of a resource at the moment of
a tool call, what happens when an approval-gated operation collides with an
LLM tool-call timeout, what exception contract the SDK exposes, or what an
agent should be told about its own profile so it can self-restrict.

This document fills those gaps by describing the runtime patterns the
`rmacd-framework` SDK (≥ 0.4.0) implements and the reference Claude Agent
SDK integration (`spec/examples/agent-integration-claude-sdk/`) demonstrates.

## Contents

- [1. Two layers: evaluator vs enforcer](#1-two-layers-evaluator-vs-enforcer)
- [2. Profile binding — how the agent knows its profile](#2-profile-binding--how-the-agent-knows-its-profile)
- [3. Resource classification lookup](#3-resource-classification-lookup)
- [4. Dynamic operation classification](#4-dynamic-operation-classification)
- [5. Approval-wait semantics for LLM agents](#5-approval-wait-semantics-for-llm-agents)
- [6. SDK error contract](#6-sdk-error-contract)
- [7. Agent self-restriction via system prompt](#7-agent-self-restriction-via-system-prompt)
- [8. DC2D runtime enforcement: redaction and egress](#8-dc2d-runtime-enforcement-redaction-and-egress)
- [9. End-to-end integration checklist](#9-end-to-end-integration-checklist)

---

## 1. Two layers: evaluator vs enforcer

The SDK provides two distinct call surfaces, each appropriate for a
different consumer:

| Surface | Class | Returns | Side effects | Typical caller |
|---|---|---|---|---|
| Pure decision | `PolicyEvaluator` | `PolicyDecision` | None | Dry-run UIs, batch policy analysis, profile linters |
| Decide + act | `PolicyEnforcer` | `PolicyDecision` or raises | Approval round-trip, audit emission, exception on denial | Agent runtimes (this is the layer all framework integrations hit) |

```python
# Decision-only: "would this be allowed?"
decision = PolicyEvaluator(profile).evaluate(
    operation="C",
    data_classification="internal",
)
# → PolicyDecision(allowed=True, autonomy_level=APPROVAL, requires_approval=True, ...)

# Decide + act: actually try to perform the operation
enforcer = PolicyEnforcer(
    profile=profile,
    agent_id="devops-agent-001",
    approval_gateway=...,
    audit_logger=...,
)
enforcer.enforce(operation="C", target="server://web-01", classification="internal")
# → raises RMACDApprovalDeniedError if the human says no
# → raises RMACDProhibitedError on Change/Restricted
# → returns a PolicyDecision otherwise
```

The split exists because some callers genuinely want the decision without
the round-trip (a profile-coverage report, an offline policy linter, a UI
that shows "this would require approval" before the user commits). The
enforcer wraps the evaluator and adds the side effects every real agent
runtime needs: approval routing, audit emission, exception classification.

---

## 2. Profile binding — how the agent knows its profile

**Gap addressed:** Appendix C.2 says "PDP loads the agent's assigned permission
profile" without specifying *how* the binding is established at runtime.

### Pattern A: explicit injection (recommended for testable code)

```python
from rmacd import PolicyEnforcer, ProfileLoader

profile = ProfileLoader().load_file("/etc/rmacd/profiles/devops-agent.json")
enforcer = PolicyEnforcer(
    profile=profile,
    agent_id="devops-agent-001",
    approval_gateway=...,
    audit_logger=...,
)
```

The agent declares its identity (`agent_id`) and is handed its profile by
whatever process started it (a deployment controller, an orchestration
runtime, a test harness). The enforcer holds both for the life of the
process. This is the form used in the reference Claude Agent SDK example.

### Pattern B: environment-driven (12-factor deployments)

```python
# At process startup
enforcer = PolicyEnforcer.from_env()
# Reads RMACD_AGENT_ID, RMACD_PROFILE_PATH, optionally RMACD_ENVIRONMENT.
# Raises ValueError with a clear message if either required var is missing.
```

Right for container deployments where the runtime injects identity and
profile path via env vars. The same pattern composes with Kubernetes
projected ServiceAccount tokens, AWS IAM role STS, Azure Managed Identity,
or SPIFFE/SPIRE SVIDs: derive `agent_id` from the workload identity, then
let RMACD enforce against the profile that workload was authorized to run.

### Pattern C: central policy store (production)

For deployments with many agents, profiles should live in a central
Policy Store (Appendix C.1) rather than be shipped with each agent
container. The SDK does not (yet) ship a built-in store client; integrators
wrap `ProfileLoader` to fetch from their store:

```python
class PolicyStoreClient:
    """Fetch + verify a profile from the central store."""
    def fetch(self, profile_id: str) -> Profile3D:
        signed_bytes = self._http_get(f"{self.base_url}/profiles/{profile_id}")
        self._verify_signature(signed_bytes)  # mTLS + JWS or similar
        return ProfileLoader().load_dict(json.loads(signed_bytes))

profile = PolicyStoreClient(base_url=..., ca_bundle=...).fetch(my_profile_id)
enforcer = PolicyEnforcer(profile=profile, agent_id=..., ...)
```

### Multi-agent processes

The enforcer is *one profile per instance*. A process hosting several
agents with different profiles instantiates one `PolicyEnforcer` per
agent. There is intentionally no global enforcer registry — colocating
profile state with the agent that owns it makes audit attribution
unambiguous.

---

## 3. Resource classification lookup

**Gap addressed:** Appendix C.7 says "ensure all data sources are tagged"
with their classification but does not specify how the runtime discovers
the tag at the moment of a tool call.

### The contract

For each tool call, the PEP must derive three pieces of information *before*
invoking the enforcer:

1. **The RMACD operation** (R/M/A/C/D) — a property of the *tool*.
2. **The target identifier** (URI, path, ID) — derived from the tool's
   arguments. Logged verbatim in audit records.
3. **The data classification** (`public`/`internal`/`confidential`/`restricted`)
   — a property of the *resource the tool is acting on*, not the tool itself.

The reference Claude Agent SDK integration encapsulates this in a single
function:

```python
def classify_tool_call(tool_name: str, tool_input: dict) -> ToolClassification:
    """Return (operation, target, classification) for a tool call."""
```

See `examples/agent-integration-claude-sdk/rmacd_demo/classifier.py` for
the full implementation.

### Lookup sources, by maturity

| Source | When to use | Notes |
|---|---|---|
| In-code dict | Demos, prototypes only | The mock infra approach used in the reference example. Brittle; do not ship to production. |
| Resource tags | Cloud-native workloads | AWS resource tags + a tag policy that enforces classification; Azure Resource Tags; GCP labels. Read at call time via the cloud SDK. |
| Data catalog | Mature data governance | DataHub, OpenMetadata, Collibra. Catalog is authoritative; the runtime calls the catalog or a cache thereof at call time. |
| DLP / classification product | AI-DLP heavy stacks | Microsoft Purview, Cyberhaven, Strac. The product owns classification; the agent runtime asks it per-call. |
| URI convention | Simple deployments | E.g., `s3://confidential-*/...` always Confidential. Cheap but only as safe as the URI namespace discipline. |

### Failure modes and safe defaults

When a classification lookup fails — the catalog is unreachable, the URI
is unknown, the tag is missing — the safe default is to **fail more
restrictively, not less**. The reference classifier treats unknown servers
as Confidential rather than Public:

```python
server = infra.get(server_id)
if server is None:
    # Unknown target: assume Confidential. An attacker who can name
    # arbitrary targets must not be able to *downgrade* classification.
    return ToolClassification(
        operation=op,
        target=f"server://{server_id}",
        classification="confidential",
    )
```

### Authoritativeness at call time

The classification must be the *current* tier at the moment of the call,
not the tier as of process startup. A cached or stale tag that misses a
recent reclassification can let Confidential data through as Internal. If
the lookup is expensive, use a short-lived in-process cache (seconds, not
hours) and never trust a tag older than the cache TTL.

---

## 4. Dynamic operation classification

**Gap addressed:** the Tools Registry classifies tools statically, but some
tools have an RMACD level that depends on which resource the LLM picked or
on resource state.

### The cases

| Case | Example | Resolution |
|---|---|---|
| Same tool, different tier | `update_config` on `web-stage-01` is Internal; on `db-prod-01` is Confidential | Classifier resolves the tier from the resource the LLM picked at call time (this is just §3 applied dynamically) |
| Same tool, different verb | `kubectl apply` is Add if the resource doesn't exist, Change if it does | Classifier performs a pre-flight existence check and returns the appropriate verb |
| Verb depends on payload | `db.exec(sql)` is R for SELECT, C for UPDATE, D for DELETE | Classifier parses the payload and chooses the verb |

### Implementation

The classifier is just a function. It can:

1. Look up the target resource state (existence check, type lookup).
2. Inspect the call arguments (SQL parsing, payload classification).
3. Combine static tool metadata with dynamic resource attributes.

```python
def classify_db_exec(tool_name: str, tool_input: dict) -> ToolClassification:
    sql = tool_input.get("sql", "")
    verb = _parse_sql_verb(sql)  # "SELECT" → "R", "UPDATE" → "C", "DELETE" → "D"
    table = _extract_table(sql)
    classification = _data_catalog.lookup_table_classification(table)
    return ToolClassification(operation=verb, target=f"db://{table}", classification=classification)
```

### Worst-case-default for ambiguous calls

If the classifier cannot definitively determine the verb (e.g., a payload
it cannot parse), it should return the **most restrictive** verb that
matches the tool's capability surface. For `kubectl apply`, that's
Change (Change is strictly more risky than Add per the RMACD hierarchy).
The agent will get a more conservative gate than strictly necessary, which
is the right trade — false positives on the cautious side are
recoverable; false negatives on the permissive side are not.

### Classification at tool-onboarding time

The patterns above classify a *call*. A separate classification problem is
onboarding the *tool itself* — assigning a default RMACD level to each of an
MCP server's advertised tools. The SDK ships two engines for this
(SDK ≥ 0.10.0): a deterministic keyword heuristic and an optional
Claude-backed `LLMToolClassifier` for the ambiguous tail, both via
`MCPRegistryBridge` with capability ceilings and provenance recorded per
tool. See `framework-adapters.md` → *Auto-classifying MCP tools*. Both are
advisory inputs at registration time; runtime enforcement stays
deterministic.

---

## 5. Approval-wait semantics for LLM agents

**Gap addressed:** Appendix C.4 says "function blocks until approval received"
which does not work for an LLM tool call with a tight effective timeout.

### The protocol

Approval is mediated by an `ApprovalGateway`:

```python
class ApprovalGateway(Protocol):
    def request(self, req: ApprovalRequest) -> ApprovalDecision: ...
```

The gateway returns one of three outcomes:

- `ApprovalOutcome.APPROVED` — the operation proceeds.
- `ApprovalOutcome.DENIED` — the enforcer raises `RMACDApprovalDeniedError`.
- `ApprovalOutcome.TIMEOUT` — the enforcer raises `RMACDApprovalTimeoutError`.

The enforcer is contract-agnostic about *how* the gateway gets the answer.
Implementations can:

- Prompt on stdin (the reference `CLIApprovalGateway`).
- Send a Slack message and `await` a button click within the request's
  `timeout_seconds`.
- Spawn a ServiceNow incident, poll for resolution, return the outcome.
- Suspend a background thread on a future that another process resolves.

### Picking a strategy by approval latency

| Expected latency | Strategy | LLM behaviour |
|---|---|---|
| Sub-second | In-process gateway (rare) | Tool call resolves normally |
| Seconds to ~minute | Synchronous gateway (Slack, CLI prompt) | Tool call sits idle for the duration; safe up to whatever the LLM transport tolerates |
| Minutes to hours | Asynchronous handoff: tool returns a "pending approval" response to the LLM, agent surfaces it to the user, work resumes on a fresh agent turn once approval lands | Use the `pending` content type or an out-of-band channel |
| Days | Out of scope for a single agent session entirely; route through a workflow system, not the agent |

### Asynchronous handoff pattern (long-running approvals)

For approvals that may take longer than a single LLM session, the
gateway persists the approval request out-of-band and returns
`ApprovalOutcome.TIMEOUT` so the enforcer raises
`RMACDApprovalTimeoutError`. The tool wrapper catches that exception
and surfaces a "pending approval" tool result to the LLM, letting the
session end cleanly. When the approver acts later, a separate code path
(a webhook handler, a queue consumer) performs the operation against a
freshly-instantiated enforcer using the same profile. The audit log
ties the two halves together by `request_id`.

### Timeouts are explicit

Gateways that cannot reach an approver within `request.timeout_seconds`
must return `ApprovalOutcome.TIMEOUT` rather than raise. This is what
lets the enforcer surface a clean `RMACDApprovalTimeoutError` to the
caller instead of an opaque exception.

### Fail-closed default

If the enforcer is constructed without an explicit gateway, it uses
`RejectAllApprovalGateway`, which denies every request. This is
intentional: an unconfigured approval surface is a deployment bug, and
the cost of failing closed (legitimate approval-gated work blocked until
an operator wires up a gateway) is far lower than the cost of failing
open (approval-gated work silently auto-approved).

---

## 6. SDK error contract

**Gap addressed:** Appendix C.4 references `RMACDPermissionError` once
without defining it as a contract.

### The hierarchy

```
RMACDError                          base for everything
└── RMACDPolicyError                base for policy-driven failures
    ├── RMACDPermissionDeniedError  profile does not grant this (op, tier)
    ├── RMACDProhibitedError        autonomy matrix prohibits — never granted
    ├── RMACDConstraintError        env / time window / quota blocked it
    ├── RMACDApprovalRequiredError  approval needed and no gateway was wired up
    ├── RMACDApprovalDeniedError    human approver said no
    └── RMACDApprovalTimeoutError   approval request timed out
```

Every `RMACDPolicyError` carries the underlying `PolicyDecision` so
callers can inspect the autonomy level, blocked reason, and constraints
that were evaluated.

### Why the split matters

A tool-call wrapper, an MCP bridge, or an agent UI typically wants to
react differently to each failure mode:

| Subclass | Recommended agent reaction |
|---|---|
| `RMACDPermissionDeniedError` | Surface to the LLM as a recoverable tool error. The agent may try a lower-risk alternative or recommend filing a §12 exception request. |
| `RMACDProhibitedError` | Hard stop. Tell the user the operation requires their direct execution (§12.5: cannot be granted via exceptions). |
| `RMACDConstraintError` | Tell the user the constraint that fired (e.g., "outside production change window") and offer to retry inside the window. |
| `RMACDApprovalDeniedError` | The human said no. Respect it. Do not retry the same operation. |
| `RMACDApprovalTimeoutError` | The human never answered. The agent may retry once, then escalate. |
| `RMACDApprovalRequiredError` | Deployment bug — no gateway wired up. Surface to ops, not to the user. |

### Distinguishing profile-denied from matrix-prohibited

When an operation is missing from the agent's profile **and** the default
matrix would have prohibited it anyway, the enforcer raises
`RMACDProhibitedError` rather than `RMACDPermissionDeniedError`. The
reason: the user-actionable advice is different.

- Profile gap on a non-prohibited cell → "you could file an exception
  request."
- Matrix prohibition → "no exception can grant this; only a human can
  perform this action."

Surfacing the right subclass tells the agent (and the agent's user) which
path forward is even available.

### Reference: how the Claude Agent SDK hook uses the contract

```python
try:
    enforcer.enforce(operation=op, target=target, classification=tier)
except RMACDProhibitedError as exc:
    return _deny(f"RMACD: {op} on tier {tier} is prohibited by the autonomy matrix for any agent. ...")
except RMACDPermissionDeniedError as exc:
    return _deny(f"RMACD: your profile does not grant {op} on tier {tier}. ...")
except RMACDApprovalDeniedError as exc:
    return _deny(f"RMACD: human approver denied {op} on {target}. ...")
except RMACDApprovalTimeoutError as exc:
    return _deny(f"RMACD: approval for {op} on {target} timed out after {exc.timeout_seconds}s.")
except RMACDConstraintError as exc:
    return _deny(f"RMACD: constraint blocked operation: {exc}")
```

See `examples/agent-integration-claude-sdk/rmacd_demo/hook.py` for the
full hook including the unknown-tool and unexpected-exception paths.

---

## 7. Agent self-restriction via system prompt

**Gap addressed:** the spec is entirely enforcement-side. An LLM agent
that doesn't know its own profile wastes turns proposing operations the
PEP will deny — at best inefficient, at worst confusing to the user.

### What to put in the system prompt

The minimum information that lets an agent self-restrict productively:

1. **Profile identity** — the `profile_id` it's bound to.
2. **Permitted operations per tier** — the cells of the agent's profile
   that grant access at all.
3. **Expected autonomy stance per cell** — which calls are autonomous,
   which are logged, which trigger notifications, which require approval,
   which are prohibited.
4. **Hard prohibitions** — Change/Delete on Restricted is prohibited for
   any agent; an exception request cannot lift this.
5. **Behaviour-on-denial** — do not retry denied operations; choose a
   lower-risk alternative or surface to the user.

### Reference prompt

```markdown
# DevOps agent — RMACD-governed

You are a DevOps assistant operating under the RMACD governance framework.
Every tool call is intercepted by a Policy Enforcement Point before it runs.

## Your profile (rmacd-3d-devops-demo-v1)

Permissions:
- Public: R, M, A, C, D
- Internal: R, M, A, C
- Confidential: R, M, A
- Restricted: R (with operator notification)

Default autonomy stance applies on top of those permissions:
- Reads on Public/Internal are autonomous.
- Reads on Confidential are logged; reads on Restricted notify the operator.
- Changes on Internal require approval.
- Adds on Confidential require elevated approval (CAB).
- Change/Delete on Restricted are prohibited for any agent.

## Behaviour

- Prefer the lowest-risk operation that achieves the goal.
- Explain the plan before acting on Confidential or Restricted data.
- Respect denials: do not retry; choose a lower-risk alternative or
  surface to the user.
- You cannot self-modify your profile. If a task genuinely requires
  permissions you don't have, recommend a §12 exception request via
  the formal process.
```

See `examples/agent-integration-claude-sdk/rmacd_demo/system_prompt.md`
for the version used in the reference integration.

For programmatic generation, use `rmacd.build_system_prompt(profile)`
(SDK 0.6.0+), which renders the prompt fragment directly from a loaded
profile — supports 2D / 3D / DC2D, includes the autonomy table for 3D,
surfaces redaction and egress controls for DC2D, and lists hard
prohibitions from the autonomy matrix:

```python
from rmacd import ProfileLoader, build_system_prompt

profile = ProfileLoader().load_file("/etc/rmacd/profiles/my-agent.json")
system_prompt_fragment = build_system_prompt(profile)
# prepend to your agent's existing system prompt
```

Deriving the prompt mechanically from the live profile is what keeps the
model's self-understanding consistent with runtime enforcement; drift
between a hand-written prompt and the profile is the most common source
of wasted turns.

---

## 8. DC2D runtime enforcement: redaction and egress

**Gap addressed:** the Data-Classification 2D variant (Appendix D) drops the
operations axis on the assumption that an upstream IAM/DLP layer governs
*what* an agent can do, leaving redaction and egress as the primary control
surfaces. The spec defines the schema for these surfaces but does not
specify how a runtime enforces them.

### The two surfaces

| Surface | When it fires | What it does |
|---|---|---|
| Redaction | After access is allowed, before the read content reaches the agent's response | Masks/tokenizes content per `constraints.redaction` |
| Egress controls | Before data flows to a downstream destination | Allows or blocks per `constraints.egress_controls` |

Both are explicit SDK surfaces because the access decision can't see them:
the read content doesn't exist until after `enforce()` returns, and the
destination of a downstream send is generally chosen by code that runs
after the read.

### Redaction

`PolicyEnforcer.apply_redaction(content, tier)` returns a `RedactionResult`
containing the transformed content and a structured list of what was
redacted. The transform is driven by the profile's `RedactionPolicy`:

```python
result = enforcer.apply_redaction(
    "Customer email: jane@example.com, SSN 123-45-6789",
    tier="confidential",
)
# result.content        → "Customer email: [TOKEN_email_a1b2c3d4], SSN [TOKEN_ssn_ef567890]"
# result.redactions_applied → ["email", "ssn"]
```

Three knobs in `RedactionPolicy`:

- `mask_pii` — global on/off switch. When false, redaction is disabled for
  all tiers.
- `redact_tiers` — list of tiers whose content must be redacted. Tiers
  not on the list pass through unchanged.
- `tokenize_identifiers` — when true, each unique value redacts to a
  stable hash-prefix token (`[TOKEN_<pattern>_<digest>]`) within the
  process. The same email value redacts to the same token consistently,
  so multi-row outputs stay internally coherent. When false, all matches
  collapse to a generic placeholder like `[REDACTED_EMAIL]`.

The SDK ships two `Redactor` implementations:

- `NullRedactor` — pass-through, used as the default for non-DC2D profiles.
- `RegexRedactor` — pattern-based, with sensible defaults for emails,
  SSNs, credit-card-shaped numbers, US phones, and IPv4 addresses.

`RegexRedactor` covers regular-shape PII (email, SSN, credit-card,
US phone, IPv4) and tokenizes matches stably within a process. It does
not perform entity extraction, language-aware redaction, or structured
PII detection. Deployments needing those capabilities implement
`Redactor` against a dedicated PII engine (Presidio, Microsoft Purview,
AWS Macie, Cyberhaven) and pass it to the enforcer via `redactor=`.

### Egress controls

`PolicyEnforcer.check_egress(tier, destination)` returns an
`EgressDecision`. With `raise_on_deny=True` the method raises
`RMACDEgressBlockedError` instead, which is often more ergonomic at the
call site:

```python
enforcer.check_egress(
    tier="confidential",
    destination="https://api.openai.com/v1/chat/completions",
    raise_on_deny=True,
)
# Raises RMACDEgressBlockedError if the destination isn't in the allow-list
# or is a known external model host (with block_external_models=true).
```

The default `PolicyDrivenEgressGate` evaluates two rules from the profile's
`EgressControls`:

1. **`allowed_destinations`** — if set, treated as an exhaustive
   allow-list. Destinations not in the list (matched by equality or
   substring) are denied. The list applies to all tiers — a Public
   destination still has to be on the list if the list is set.
2. **`block_external_models`** — if true, Confidential and Restricted
   data egressing to a known external-model host (OpenAI, Anthropic, etc.)
   is denied. Public and Internal tiers are unaffected by this rule.

The gate is conservative on hostname matching: it parses the destination as
a URL and compares the host against a default external-model registry.
Deployments with a real network policy product should implement their own
`EgressGate` rather than rely on this default.

### Why these surfaces are separate from `enforce()`

`enforce()` runs once per access; redaction and egress run per data flow.
A single Confidential read can produce content that flows to multiple
destinations (logged, sent to a downstream LLM, returned to the user),
each with its own egress decision and each potentially redacted
differently. Keeping the surfaces separate means each one can be wired
into the code that has the relevant data — read content for redaction,
destination URL for egress — without forcing the access decision to
know about either.

### Reference: see it in action

The demo at `examples/dc2d-customer-support/demo.py` shows the full
pipeline: load a DC2D profile, attempt to read records at four tiers,
apply redaction to allowed reads, then check egress to four destinations.
It's a 130-line self-contained script with no LLM integration — the data
flows are deterministic so the surfaces are easy to inspect.

---

## 9. End-to-end integration checklist

Wiring an agent runtime to RMACD requires the following pieces. Use this
list to audit a new integration:

| # | Concern | Mechanism | Reference |
|---|---|---|---|
| 1 | Profile binding | `PolicyEnforcer(profile=..., agent_id=...)` or `.from_env()` | §2 |
| 2 | Resource classification | A classifier function (or service call) per tool call | §3 |
| 3 | Dynamic verb selection | Classifier inspects payload / target state | §4 |
| 4 | Approval routing | `ApprovalGateway` implementation matched to expected latency | §5 |
| 5 | Audit emission | `AuditLogger` implementation (default `NullAuditLogger`, use real sink in prod) | §1, Appendix C.6 |
| 6 | Exception handling | Catch the six `RMACDPolicyError` subclasses and surface per-subclass reactions | §6 |
| 7 | Agent self-restriction | System prompt that summarises the profile | §7 |
| 8 | Identity attestation | Derive `agent_id` from workload identity (not a hardcoded string in production) | §2 |
| 9 | Emergency escalation | `EvaluationContext.emergency_active` + profile's `emergency_escalation` block | Appendix C.3 |
| 10 | Real-time alerts | Wire `audit_requirements.alert_channels` into your `AuditLogger` implementation | Appendix C.6 |
| 11 | Rate limit enforcement | External rate limiter (Redis, Envoy) — the SDK validates the schema but does not enforce per-call rates | §9.5 |
| 12 | Multi-environment routing | Different profile per environment (dev/staging/production), bound via the same mechanism in §2 | §9.2 |
| 13 | DC2D redaction | `PolicyEnforcer.apply_redaction(content, tier)` after each read; plug in real PII detector for production | §8 |
| 14 | DC2D egress controls | `PolicyEnforcer.check_egress(tier, destination)` before each outbound send | §8 |

### What the SDK provides vs what integrators provide

| Piece | Shipped in SDK | Integrator provides |
|---|---|---|
| `PolicyEvaluator`, `PolicyEnforcer` | ✅ | — |
| Profile / decision / audit / approval models | ✅ | — |
| `ApprovalGateway` Protocol + `RejectAll` / `AutoApprove` reference impls | ✅ | Production gateway (Slack / ServiceNow / Jira / webhook) |
| `AuditLogger` Protocol + `JSONLAuditLogger` / `NullAuditLogger` | ✅ | Production sink (immutable storage, SIEM forwarder) |
| `RMACDError` hierarchy | ✅ | — |
| Profile loader (filesystem) | ✅ | Central policy-store client (HTTPS / mTLS / signature verification) |
| Tools Registry (static tool classification) | ✅ | Tool-to-RMACD-operation mapping for tools not in the catalog |
| Resource classifier | — (pattern only) | Lookup against catalog / tag registry / DLP product |
| Workload identity attestation | — | Kubernetes ServiceAccount / IAM role / SPIFFE SVID → `agent_id` |
| Rate limit runtime | — (schema validation only) | External rate limiter |
| DC2D redactor protocol + `RegexRedactor` reference | ✅ | Production PII detector (Presidio / Macie / Purview) as a `Redactor` impl |
| DC2D egress gate protocol + `PolicyDrivenEgressGate` reference | ✅ | Network policy product / API gateway integration as an `EgressGate` impl |

This list is the boundary between "what we ship" and "what your
deployment owns." Items in the right column are deployment concerns; the
SDK aims to give them a clean interface to plug into, not to own them
itself.

---

## Pointers

- SDK source: `spec/sdk/python/rmacd/`
- Reference integration: `spec/examples/agent-integration-claude-sdk/`
- Canonical spec: `spec/docs/RMACD_Framework_v1.4.md` (Appendices C and D)
- Issue tracker: `https://github.com/rmacdframework/spec/issues`
