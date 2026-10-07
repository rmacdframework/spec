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

**Implementation level claimed by this release: L1 (Adjudicating).** Every
record it emits is stamped `implementation_level: "L1"` (N-65). L2
(reconciliation with the interception audit trail) and L3 (grants) are the
next two releases; see the specification's §11.1.
