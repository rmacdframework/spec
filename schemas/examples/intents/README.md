# Intent examples

Worked examples of `schemas/intent.schema.json` and
`schemas/intent-decision.schema.json`. See
[`docs/intent-specification.md`](../../../docs/intent-specification.md).

These live in a subdirectory deliberately. The examples in the parent
directory are RMACD **permission profiles**, and CI validates them with
`rmacd validate schemas/examples/*.json` — a non-recursive glob that dispatches
on a profile's `model` discriminator. Intents are not profiles and would be
rejected by that job, so they are kept one level down where the glob does not
reach.

| File | Type | Demonstrates |
|---|---|---|
| `change-production.json` | `change` | The lattice root; a production change with an attested rollback |
| `release-composed.json` | `release` | Composition — the release inherits its most severe child |
| `campaign-cert-rotation.json` | `campaign` | A bounded grant: closed predicate, hard caps, mandatory expiry |
| `exception-urgent.json` | `exception` | Framework §12.3–12.4 expressed as an intent; Restricted capped at R/M |
| `incident-record-plane.json` | `incident` | The record plane and the first-report invariant |
| `decision-record.json` | — | The evidence artifact, showing escalation factors and reproducibility inputs |
