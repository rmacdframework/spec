# Audit-to-Evidence Pipeline

How to turn the audit trail the RMACD SDK writes into evidence an auditor or
SIEM accepts, tied to the spec's
[§10 regulatory compliance mapping](RMACD_Framework_v1.4.md#10-regulatory-compliance-mapping).

Two producers write the same record format:

| Producer | Default sink | Covered in |
|---|---|---|
| `PolicyEnforcer` (SDK-governed application code) | Whatever path the app gives `JSONLAuditLogger` (`audit.jsonl` by convention) | [Section 1](#1-the-audit-record-spec-appendix-c6) |
| The governed Claude Code session (`PreToolUse` / `PostToolUse` hooks) | `.claude/rmacd-audit.jsonl`, beside the profile that bound the session | [Section 2](#2-records-from-a-governed-claude-code-session) |

The pipeline has three stages:

```
PolicyEnforcer      ─┐
                     ├─> JSONL audit log ──> collector (filebeat/vector) ──> SIEM
Claude Code hooks   ─┘          │
(PreToolUse/PostToolUse)        └──> rmacd audit summarize ──> evidence report
                                                               (text/json/md)
```

Everything below assumes records written by `rmacd.audit.JSONLAuditLogger`
(the SDK's built-in sink, used by both producers) or any `AuditLogger`
implementation that preserves the same shape.

## 1. The audit record (spec Appendix C.6)

Every enforced operation emits one or more JSON Lines records. The shape is
[Appendix C.6](RMACD_Framework_v1.4.md#c6-audit-log-format) of the spec;
`rmacd.audit.AuditRecord` is the SDK's implementation of it.

```json
{
  "record_id": "aud-45bb26dfd2db4d96",
  "timestamp": "2026-07-19T07:18:06.688861Z",
  "agent_id": "support-agent-demo",
  "profile_id": "rmacd-dc2d-regulated-data-handler-v1",
  "operation": {
    "type": "R",
    "target": "customer://cust-003",
    "classification": "confidential"
  },
  "policy_decision": {
    "result": "QUEUED",
    "autonomy_level": "approval",
    "blocked_reason": null,
    "approval_id": "apr-84b7e7a8898b4535",
    "approved_by": null,
    "approved_at": null,
    "constraints_applied": [],
    "emergency_mode": false
  },
  "execution": null,
  "compliance_tags": ["GDPR", "HIPAA", "ISO27001"]
}
```

### 1.1 Field reference

| Field | Type | Meaning |
|---|---|---|
| `record_id` | string | Unique record id (`aud-<hex>`). |
| `timestamp` | ISO 8601 | When the record was written (UTC). |
| `agent_id` | string | The agent the enforcer was bound to. |
| `profile_id` | string | RMACD profile in force (`rmacd-2d-*` / `rmacd-3d-*` / `rmacd-dc2d-*`). |
| `operation.type` | `R`\|`M`\|`A`\|`C`\|`D` | RMACD operation. |
| `operation.target` | string | Resource identifier the operation acted on. |
| `operation.classification` | tier or `null` | PICR tier (`public`/`internal`/`confidential`/`restricted`); `null` for 2D Operational profiles, which have no data-classification dimension. |
| `policy_decision.result` | string | `ALLOW`, `DENY`, `QUEUED`, `APPROVED`, `REJECTED`, or `EXECUTED` — see lifecycle below. |
| `policy_decision.autonomy_level` | string | Effective HITL level (`autonomous` … `prohibited`). |
| `policy_decision.blocked_reason` | string or `null` | Why a denial happened (profile grant, autonomy policy, constraint). |
| `policy_decision.approval_id` | string or `null` | Correlates the `QUEUED` record with its `APPROVED`/`REJECTED` outcome. |
| `policy_decision.approved_by` | string or `null` | Approver identity from the gateway. |
| `policy_decision.approved_at` | ISO 8601 or `null` | When the approval decision was made. |
| `policy_decision.constraints_applied` | string[] | Constraint names that shaped the decision. |
| `policy_decision.emergency_mode` | bool | Whether §12 emergency escalation was active. |
| `execution.status` | string or absent | `SUCCESS`/`FAILURE`/`SKIPPED` — written by post-execution auditing when the caller reports it. |
| `execution.duration_ms` / `execution.error` | int / string | Execution timing and error detail. |
| `compliance_tags` | string[] | The profile's `audit_requirements.compliance_tags` (§10.4), stamped on records the enforcer writes (see [2.6](#26-configuration-and-failure-behavior) for the session-hook caveat). |
| `extra` | object or absent | Sink-specific context outside the C.6 shape. Omitted entirely when unset, so enforcer records stay byte-for-byte Appendix C.6; the Claude Code hooks populate it (see [2.3](#23-the-extra-block-session-and-subagent-identity)). |

### 1.2 Result lifecycle: records vs. operations

Autonomy levels that require approval produce **up to three records for one
operation**, correlated by `approval_id`:

```
QUEUED ──> APPROVED ──> ALLOW        (operation proceeded)
QUEUED ──> REJECTED                  (operation blocked, RMACDApprovalDeniedError)
```

Non-gated operations produce a single `ALLOW` or `DENY`.

`EXECUTED` is not a decision at all — it is the outcome of a call some earlier
decision already permitted, written after the fact by `@guard` and by the
`PostToolUse` session hook
([Section 2](#2-records-from-a-governed-claude-code-session)). It carries the
`execution` block.

When counting "how many operations were allowed/denied", count **terminal**
results only:

- **allowed** — `ALLOW`
- **denied** — `DENY` and `REJECTED`
- **neither** — `QUEUED` (an intermediate state), `APPROVED` (superseded by the
  `ALLOW` that follows it), and `EXECUTED` (an outcome, not a decision)

`rmacd audit summarize` does this for you in its operation × tier matrix, and
counts `EXECUTED` on its own line so executions never dilute the decision
percentages.

## 2. Records from a governed Claude Code session

The second producer is the Claude Code plugin
([claude-code.md](claude-code.md)). A session bound by a profile writes its
trail to `.claude/rmacd-audit.jsonl` — beside the profile that bound it — in
the Appendix C.6 format of §1, through the same `JSONLAuditLogger`. Everything
else in this document therefore applies to it unchanged: the same summarizer,
the same SIEM shipping, the same compliance mapping.

### 2.1 Two hooks, two record kinds

| Hook | Records | `policy_decision.result` values |
|---|---|---|
| `PreToolUse` (`rmacd.claude_code.hook`) | The **decision**, before the call runs | `ALLOW`, `DENY`, `QUEUED` |
| `PostToolUse` (`rmacd.claude_code.post_hook`) | The **execution**, for calls that ran | `EXECUTED`, plus an `execution.status` of `SUCCESS` or `FAILURE` and `execution.error` |

One tool call produces at most one of each, and the two join on
`extra.tool_use_id`. Read as a pair they answer both audit questions at once:
*was this permitted*, and *what did it actually do*.

An execution record with no matching decision should never occur; a decision
record with no matching execution is normal and expected — the call was denied,
or it was routed to the `ask` prompt and the user declined, so it never ran.

### 2.2 Why decisions are recorded before execution

Recording at `PreToolUse` rather than after the call is the deliberate design
choice on which the evidentiary value of the whole trail rests. A denied call
never runs, so it never reaches `PostToolUse`. A trail assembled only from
executions would contain every action the agent took and not one of the actions
it was stopped from taking — it would omit every denial, which is precisely the
evidence an auditor asks for. "Here is everything the agent did" is an activity
log; "here is everything the agent attempted, and here is where the boundary
held" is evidence that a control exists and works.

For the same reason, **every** return path in `decide()` records before it
returns. That includes the first two below, which short-circuit before any
policy evaluation runs:

- **Unknown / unmapped tool** — recorded as `DENY` (or `QUEUED` when
  `RMACD_UNKNOWN_TOOL=ask` routes it to the user's prompt) against the tool
  name. It is deliberately filed as a **Delete** with no classification: an
  unmapped tool has no known operation, so it is recorded at the most severe
  one, and no reader can mistake "we could not classify this" for "it was a
  read".
- **Capability ceiling** — `DENY` at the operation and tier the ceiling
  rejected.
- **Profile / autonomy denial** — `DENY`, with the evaluator's `blocked_reason`.
- **Egress denial** (DC2D, outbound destinations) — `DENY`, with the blocked
  destination and matched rule in `blocked_reason`.
- **Approval-gated autonomy** — `QUEUED`; Claude Code's own `ask` prompt is the
  human-in-the-loop step.
- **Permitted** — `ALLOW`.

The audit write is an append to the session's own sink and never feeds back
into the decision, which stays side-effect-free (`evaluate_only`).

### 2.3 The `extra` block: session and subagent identity

Session records carry an `extra` object alongside the C.6 fields. Each key is
copied from the hook event and omitted when the event does not carry it.

| Field | Meaning |
|---|---|
| `session_id` | The Claude Code session. Groups a whole conversation's records. |
| `tool_use_id` | The individual tool call. The join key between the decision and execution records. |
| `tool_name` | The Claude Code tool as invoked (`Read`, `Write`, `Bash`, an MCP tool name) — before RMACD mapping, so it complements `operation.type`. |
| `cwd` | The working directory the call was made from. |
| `agent_id` | **Subagent only.** The subagent instance that made the call. |
| `agent_type` | **Subagent only.** The subagent's type (e.g. `Explore`). |

Two things about this block matter for evidence:

- **The absence of `agent_id` is itself meaningful.** It is written only when
  the call came from a subagent, so a record without it says the call came from
  the main conversation. Attribution inside a fan-out is not lost.
- **`extra.agent_id` is not the top-level `agent_id`.** The top-level field is
  the governed agent identity from the binding (`claude-code` unless
  `RMACD_AGENT_ID` overrides it) and is what `rmacd audit summarize --agent`
  and the [SIEM mappings](#5-shipping-to-a-siem) key on. The one inside `extra`
  is the subagent.

### 2.4 Example: a decision and its execution

Two records from one governed session, joined by the same `tool_use_id`. First
the decision — an allowed read:

```json
{
  "record_id": "aud-e252ca2d46044aa0",
  "timestamp": "2026-08-11T01:24:46.135348Z",
  "agent_id": "claude-code",
  "profile_id": "rmacd-3d-devops-v1",
  "operation": {
    "type": "R",
    "target": "/home/dev/checkout/src/app.py",
    "classification": "internal"
  },
  "policy_decision": {
    "result": "ALLOW",
    "autonomy_level": "autonomous",
    "blocked_reason": null,
    "approval_id": null,
    "approved_by": null,
    "approved_at": null,
    "constraints_applied": [],
    "emergency_mode": false
  },
  "execution": null,
  "compliance_tags": [],
  "extra": {
    "session_id": "3f2b1c9a-1111-4a55-9f0e-7ac2d6b8e401",
    "tool_use_id": "toolu_01Ab2Cd3Ef4Gh5Ij6Kl7Mn8",
    "tool_name": "Read",
    "cwd": "/home/dev/checkout"
  }
}
```

Then its execution, written by `PostToolUse` after the read ran:

```json
{
  "record_id": "aud-2517d5ca4cbd491f",
  "timestamp": "2026-08-11T01:24:46.136687Z",
  "agent_id": "claude-code",
  "profile_id": "rmacd-3d-devops-v1",
  "operation": {
    "type": "R",
    "target": "/home/dev/checkout/src/app.py",
    "classification": "internal"
  },
  "policy_decision": {
    "result": "EXECUTED",
    "autonomy_level": "autonomous",
    "blocked_reason": null,
    "approval_id": null,
    "approved_by": null,
    "approved_at": null,
    "constraints_applied": [],
    "emergency_mode": false
  },
  "execution": {
    "status": "SUCCESS",
    "duration_ms": null,
    "error": null
  },
  "compliance_tags": [],
  "extra": {
    "session_id": "3f2b1c9a-1111-4a55-9f0e-7ac2d6b8e401",
    "tool_use_id": "toolu_01Ab2Cd3Ef4Gh5Ij6Kl7Mn8",
    "tool_name": "Read",
    "cwd": "/home/dev/checkout"
  }
}
```

A denial from a subagent, in the same trail — no execution record follows it,
because the call never ran:

```json
{
  "record_id": "aud-4d64ffddf9b349a8",
  "timestamp": "2026-08-11T01:24:46.136145Z",
  "agent_id": "claude-code",
  "profile_id": "rmacd-3d-devops-v1",
  "operation": {
    "type": "A",
    "target": "/home/dev/checkout/secrets/keys.env",
    "classification": "restricted"
  },
  "policy_decision": {
    "result": "DENY",
    "autonomy_level": "prohibited",
    "blocked_reason": "Operation A not permitted for this profile",
    "approval_id": null,
    "approved_by": null,
    "approved_at": null,
    "constraints_applied": [],
    "emergency_mode": false
  },
  "execution": null,
  "compliance_tags": [],
  "extra": {
    "session_id": "3f2b1c9a-1111-4a55-9f0e-7ac2d6b8e401",
    "tool_use_id": "toolu_01Zz9Yy8Xx7Ww6Vv5Uu4Tt3",
    "tool_name": "Write",
    "agent_id": "agent_01Qq",
    "agent_type": "Explore",
    "cwd": "/home/dev/checkout"
  }
}
```

That last record is a §12.5-floor hit — a denied `A` on Restricted — and
[`rmacd audit summarize`](#3-rmacd-audit-summarize) flags and totals it as such.

### 2.5 The execution record carries the decision's autonomy level

The execution record does **not** recompute its RMACD terms. `PreToolUse` hands
its result forward to `PostToolUse` in a short-lived JSON sidecar keyed by
`(session_id, tool_use_id)` (`rmacd.claude_code.handoff`), which `PostToolUse`
consumes and deletes. The sidecar carries the operation, target,
classification, resolved audit path, and the `autonomy_level` the decision
computed.

That last field is the one that matters for evidence. It was previously
hardcoded to `autonomous`, so a call a human had explicitly approved through the
`ask` prompt was filed as one the agent had made on its own — an execution
record that asserted the opposite of what happened. The decision record held the
truth, but "what did this agent actually do?" is a question asked of execution
rows.

It cannot be recovered from anything else on the row, either: C.6 serializes
`policy_decision.autonomy_level` but **not** `requires_approval`, so that single
field is all an auditor reading an execution record can see about whether a
human was in the loop. Carrying it forward is what makes the
[SOC 2 CC6.2 evidence](#6-mapping-audit-fields-to-compliance-requirements) hold
up when the execution rows are read on their own.

Sidecars are best-effort and self-cleaning (unlinked on read, TTL-swept
otherwise). A missing one costs an execution record, never a decision record:
denials are written inline by `PreToolUse` and never depend on the handoff.

### 2.6 Configuration and failure behavior

| Variable | Effect |
|---|---|
| `RMACD_AUDIT_PATH` | Explicit sink path. Wins outright over the default location. |
| `RMACD_AUDIT` | Set to a falsey value (`0`, `off`, `false`, `no`) to disable session audit entirely — it wins over `RMACD_AUDIT_PATH`. Any other value, or unset, leaves auditing on. |
| `RMACD_AGENT_ID` | Overrides the top-level `agent_id` on session records (default `claude-code`). |

Operational notes:

- **Auditing never affects a decision.** Writing is best-effort: an unwritable
  sink emits a note on stderr and the governance outcome stands unchanged.
  Turning a bookkeeping failure into a denial would take a working session down;
  turning it into an exception would fail the hook closed for the same reason.
- **No profile, no trail.** An unbound session records nothing at all: the hook
  passes the call through before any auditor exists. That is correct — an
  unbound session is ungoverned and has no decisions to record.
- **`.gitignore` the sink.** Add `.claude/rmacd-audit.jsonl` unless the evidence
  is meant to be committed.
- **Session records carry an empty `compliance_tags`.** The hooks do not
  currently stamp the profile's `audit_requirements.compliance_tags` onto
  records, so slice session trails by `profile_id` rather than by tag until they
  do.

Summarize a session trail exactly like any other:

```bash
rmacd audit summarize .claude/rmacd-audit.jsonl
```

## 3. `rmacd audit summarize`

```
rmacd audit summarize <path.jsonl> [--format text|json|md]
                      [--since ISO] [--until ISO] [--agent ID] [--denials-only]
```

| Option | Effect |
|---|---|
| `--format` | `text` (terminal, default), `md` (paste into an audit ticket), `json` (stable machine-readable, schema below). |
| `--since` / `--until` | Inclusive ISO-8601 time bounds on `timestamp` (naive values are treated as UTC). |
| `--agent` | Only records with this `agent_id`. |
| `--denials-only` | Only `DENY` and `REJECTED` records. |

Behavior guarantees:

- **Tolerant parser.** Lines that are not valid JSON, or that parse but are
  not audit records, are skipped and counted ("N malformed line(s) skipped").
  The exit code is non-zero only when the file itself cannot be read.
- **Deterministic.** The output contains no wall-clock fields — re-running
  over the same log yields byte-identical evidence, so the JSON form can be
  hashed for integrity or diffed across reviews.
- **§12.5 called out.** Any denial of `A`/`C`/`D` on Restricted data — the
  combinations the immutable floor
  ([§12.5](RMACD_Framework_v1.4.md#125-prohibited-exceptions)) prohibits for
  any agent — is flagged (`[S12.5 floor]` in text, a **yes** column in md,
  `"floor": true` in JSON) and totalled as `floor_denials`.
- **2D collapses tiers.** Records from 2D Operational profiles carry no
  classification; they aggregate under a single `unclassified` row, so the
  matrix degrades to operation × decision exactly as the 2D shape prescribes.

### 3.1 JSON output schema (`rmacd-audit-summary/v1`)

`--format json` emits exactly these keys — nothing incidental — so the
output is safe to parse and archive:

| Key | Type | Meaning |
|---|---|---|
| `schema` | string | Always `"rmacd-audit-summary/v1"`. |
| `source` | string | The summarized file path. |
| `filters` | object | Echo of the applied filters: `since`, `until`, `agent` (string or `null`), `denials_only` (bool). |
| `records` | object | `included` (after filters) and `malformed` (skipped lines). |
| `time_range` | object | `first`/`last` record timestamps in range (ISO 8601 or `null`). |
| `agents` | string[] | Sorted distinct `agent_id`s. |
| `profiles` | string[] | Sorted distinct `profile_id`s. |
| `decisions` | object | Record counts by result: `allow`, `deny`, `queued`, `approved`, `rejected`, `executed`, `other`. |
| `matrix` | object | `{operation: {tier: {allowed, denied}}}` — terminal decisions only (see lifecycle above). |
| `top_denied` | array | Up to 10 of `{target, reason, count, floor}`, most-denied first. |
| `floor_denials` | int | Total §12.5-floor-territory denials. |
| `approval_latency` | object or `null` | `{count, min_seconds, median_seconds, max_seconds}` over completed `QUEUED → APPROVED/REJECTED` round-trips (paired by `approval_id`, using `approved_at` when present). |

## 4. Worked example: the DC2D customer-support demo

Regenerate the log by running the demo (no LLM or API keys needed), then
summarize it:

```bash
cd spec/examples/dc2d-customer-support
python demo.py                                # writes ./audit.jsonl
python -m rmacd.cli audit summarize audit.jsonl
```

The demo reads four customer records (one per tier) under
`rmacd-dc2d-regulated-data-handler-v1`, which yields six audit records:

```
RMACD audit summary
  Source:     audit.jsonl
  Time range: 2026-07-19T07:18:06.688526+00:00 -> 2026-07-19T07:18:06.690366+00:00
  Records:    6 included, 0 malformed line(s) skipped
  Agents:     support-agent-demo
  Profiles:   rmacd-dc2d-regulated-data-handler-v1
  Filters:    (none)

Decision breakdown
  allowed                 3   50.0%
  denied                  1   16.7%
  approval granted        1   16.7%
  approval denied         0    0.0%
  approval queued         1   16.7%
  executed (outcome)      0    0.0%

Operation x tier (terminal decisions, allowed/denied)
  tier          R
  public        1/0
  internal      1/0
  confidential  1/0
  restricted    0/1

Top denied (target, rule, count)
  1. customer://cust-004 -- Access to restricted tier not permitted by this profile (1)
  S12.5 floor hits: 0

Approval latency (QUEUED -> decision)
  approvals: 1  min 0.0s  median 0.0s  max 0.0s
```

Reading it: four read operations were attempted, one per tier. Public and
Internal read straight through (`allowed`). The Confidential read was
approval-gated — hence one `approval queued`, one `approval granted`, and its
terminal `allowed`, three records for one operation. The Restricted read was
denied by the profile (`restricted: allowed=false`). Floor hits are 0 because
the denial was a **Read** — §12.5 covers autonomous `A`/`C`/`D` on Restricted.
The latency stats round to 0.0s because the demo's `AutoApproveGateway`
answers instantly; a human gateway produces real numbers here. The
`executed (outcome)` line is 0 because this demo records decisions only — a
governed Claude Code session
([Section 2](#2-records-from-a-governed-claude-code-session)) and `@guard` fill
that line.

## 5. Shipping to a SIEM

The log is plain JSONL, so any collector that tails files can ship it.

### 5.1 Filebeat → Elasticsearch

```yaml
# filebeat.yml
filebeat.inputs:
  - type: filestream
    id: rmacd-audit
    paths:
      - /var/log/rmacd/audit.jsonl
    parsers:
      - ndjson:
          target: "rmacd"
          overwrite_keys: true
    fields:
      event.kind: "audit"
      event.provider: "rmacd"
    fields_under_root: true

output.elasticsearch:
  hosts: ["https://elastic.internal:9200"]
  index: "rmacd-audit-%{+yyyy.MM}"
```

Useful ECS-style mappings once ingested:

| Audit field | ECS / index field |
|---|---|
| `timestamp` | `@timestamp` |
| `agent_id` | `user.id` (or `service.name` for service agents) |
| `operation.type` | `event.action` |
| `operation.target` | `event.target` / custom `rmacd.target` |
| `policy_decision.result` | `event.outcome` (`ALLOW` → `success`, `DENY`/`REJECTED` → `failure`) |
| `operation.classification` | custom `rmacd.tier` (keyword) — drives per-tier retention (below) |
| `compliance_tags` | `labels` |

### 5.2 Vector → Splunk HEC

```toml
# vector.toml
[sources.rmacd_audit]
type = "file"
include = ["/var/log/rmacd/audit.jsonl"]

[transforms.parse]
type = "remap"
inputs = ["rmacd_audit"]
source = '''
. = parse_json!(.message)
.sourcetype = "rmacd:audit"
'''

[sinks.splunk]
type = "splunk_hec_logs"
inputs = ["parse"]
endpoint = "https://splunk.internal:8088"
default_token = "${SPLUNK_HEC_TOKEN}"
indexed_fields = ["agent_id", "profile_id"]
```

A Splunk search for §12.5-floor territory (should always return zero
successful events):

```
sourcetype="rmacd:audit" operation.classification=restricted
  operation.type IN (A, C, D) policy_decision.result=ALLOW
```

### 5.3 Retention guidance per tier

Retention follows the strictest regulation attached to the data the records
describe (spec [§10.2](RMACD_Framework_v1.4.md#102-compliance-matrix),
[§10.3](RMACD_Framework_v1.4.md#103-additional-regulatory-frameworks)):

| Records covering | Baseline retention | Driver (spec §10) |
|---|---|---|
| Restricted (PHI) | 6 years | HIPAA (§10.2) |
| Restricted (cardholder data) | 1 year online, then archive | PCI-DSS (§10.2) |
| Confidential (financial) | 7 years | SOX (§10.2) |
| Confidential (personal data) | ≥ 24 months | CCPA/CPRA (§10.3) |
| Any tier, FedRAMP systems | ≥ 90 days online, 1 year archive | FedRAMP AU controls (§10.3) |
| Public / Internal | Per risk assessment | ISO 27001 (§10.2) |

When one log stream mixes tiers, apply the longest applicable period to the
whole stream (spec §10.4: "apply the most restrictive control"), or route by
`operation.classification` at the collector and retain per index. Deployments
whose profiles set `audit_requirements.immutable_logging: true` should back
the sink with WORM storage (S3 Object Lock, Azure Immutable Blob).

## 6. Mapping audit fields to compliance requirements

Reusing the spec's §10 mapping — cite these sections in audit responses:

| Evidence requirement | Audit fields that satisfy it | Spec citation |
|---|---|---|
| SOC 2 CC6.1 — logical access restricted to authorized users | `profile_id` + `policy_decision.result` show every operation was gated by a least-privilege profile | §10.1 (framework alignment), §3 governance matrix |
| SOC 2 CC6.2 — access authorization prior to access | `QUEUED`/`APPROVED` records with `approved_by`, `approved_at` prove pre-access human authorization | §10.1; Appendix C.5 approval workflow |
| SOC 2 CC6.3 — access modified/removed per policy | `DENY` records with `blocked_reason`; `floor_denials` shows the §12.5 boundary held | §12.5 |
| ISO 27001 A.8 (asset/data handling) | `operation.classification` ties every action to a classified asset tier | §10.2 (ISO 27001 row: classification-based controls) |
| ISO 27001 A.9 (access control) | `operation.type` × `autonomy_level` demonstrate enforced authorization levels per operation | §10.2; §3.2 |
| GDPR Art. 30-style processing records | `timestamp`, `agent_id` (processor), `operation.target` (data), `operation.type` (processing activity), `compliance_tags` | §10.1 (GDPR), §10.2 ("Processing activity logs") |
| HIPAA audit controls | Complete record trail over Restricted-tier access, 6-year retention | §10.1, §10.2 |
| FedRAMP AU-2/AU-11 | Full decision log + retention schedule above | §10.3 (FedRAMP AU row) |

`compliance_tags` on every record come from the profile's
`audit_requirements.compliance_tags` (§10.4), letting a SIEM slice one
unified log per regulation.

## 7. The evidence pack

For a periodic access review or an audit ticket, bundle three artifacts:

```bash
PROFILE=schemas/examples/regulated-data-handler-dc2d.json

# 1. What the agent did (this quarter), as markdown evidence
rmacd audit summarize audit.jsonl --format md \
  --since 2026-04-01T00:00:00Z --until 2026-06-30T23:59:59Z > evidence-activity.md

# 2. What the agent was allowed to do (the policy in force)
cp "$PROFILE" evidence-profile.json

# 3. The effective autonomy matrix derived from that policy
rmacd matrix "$PROFILE" > evidence-matrix.txt
```

The three answer the auditor's questions in order:

| Artifact | Question it answers |
|---|---|
| `evidence-activity.md` | What happened. |
| `evidence-profile.json` | What was authorized. |
| `evidence-matrix.txt` | What that authorization means operationally. |

Because the summary is deterministic, re-running it over the archived log
during the audit reproduces `evidence-activity.md` exactly — the evidence is
verifiable, not just asserted.

For deeper dives, `--denials-only` isolates the exception report, and
`--agent` scopes the bundle to a single agent under review. For a Claude Code
session the same three artifacts apply, with `.claude/rmacd-audit.jsonl` as the
log and `.claude/rmacd-profile.json` as the profile in force.
