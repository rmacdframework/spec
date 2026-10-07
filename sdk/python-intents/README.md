# rmacd-intents

The adjudication engine for [RMACD Intents](../../docs/intents.md): an actor
declares what it wants to do, the engine grades the declaration against the
bound profile's effective matrix and escalates one way only, a human decides
where the grade demands it, and every step leaves a record in two append-only
logs. It implements the
[Intent Specification](../../docs/intent-specification.md); the package
version tracks the specification's major.

```bash
pip install rmacd-intents        # pulls rmacd-framework>=0.16
```

The engine depends on `rmacd-framework` and never the other way round: the base
level for every intent is read from the SDK's `PolicyEvaluator`, so the §12.5
floor and every profile override are inherited rather than reimplemented
(N-13). Adjudication never grants — the profile remains the ceiling and
interception still gates execution (N-20).

**Implementation level claimed by this release: L3 (Delegating)** — every
checklist item at L1, L2 and L3 holds, and every record it emits is stamped
with the level it was configured to claim (N-65; `implementation_level` in the
config, `L3` by default). An L1 deployment that keeps a paper register can
claim `L1` and the engine then records the six pattern fields in place of the
hash (N-69).

Reconciliation reads the SDK's Appendix C.6 audit trail and joins on
`extra.intent_id`; grants are campaigns and exceptions with atomic child caps
on the JSONL store's lock (single host) — see `docs/audit-evidence.md` §1.3
and the specification's §7, §9 and §10.
