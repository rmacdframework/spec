# Intent examples

Worked examples of `schemas/intent.schema.json`,
`schemas/intent-decision.schema.json` and the two log-entry schemas. See
[`docs/intent-specification.md`](../../../docs/intent-specification.md).

These live in a subdirectory deliberately. The examples in the parent
directory are RMACD **permission profiles**, and CI validates them with
`rmacd validate schemas/examples/*.json` — a non-recursive glob that dispatches
on a profile's `model` discriminator. Intents are not profiles and would be
rejected by that job, so they are kept one level down where the glob does not
reach.

| File | Type | Demonstrates |
|---|---|---|
| `change-production.json` | `change` | The building block; a production change with an attested rollback |
| `release-composed.json` | `release` | Composition — the release inherits its most severe child |
| `campaign-cert-rotation.json` | `campaign` | A bounded grant: closed match rule, hard caps, mandatory expiry |
| `exception-urgent.json` | `exception` | Framework §12.3–12.4 expressed as an intent; Restricted capped at R/M |
| `incident-record-plane.json` | `incident` | The record plane and the first-report invariant |
| `decision-record.json` | — | The evidence artifact, showing escalation factors and reproducibility inputs |
| `intent-log-submission.json` | log entry | The intent log: a submission kept exactly as received (N-73) |
| `intent-log-rejection.json` | log entry | A rejection, with the document and the failure, in the intent log and never the adjudication log (N-59, N-72) |
| `intent-log-transition.json` | log entry | A grant moving from `requested` to `active`, made by the implementation and traced (N-71) |
| `adjudication-log-decision.json` | log entry | The adjudication log: a decision record as emitted, without attachments (N-74) |
| `adjudication-log-disposition.json` | log entry | A disposition attached later as its own entry, citing the decision; the record is never rewritten (N-43, N-74) |
