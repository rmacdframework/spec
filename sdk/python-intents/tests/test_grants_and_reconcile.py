"""Waves 2 and 3: coverage (§7), reconciliation (§10), demotion and review marks (§9.1)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from rmacd import AutonomyLevel

from rmacd_intents import DecisionRecord, MemoryStore, Rejection
from rmacd_intents.grading import Engine
from rmacd_intents.models import GrantStatus
from rmacd_intents.reconcile import Reconciler

from .conftest import Clock, example, intent


def factors_of(rec: DecisionRecord) -> dict[str, int]:
    return {f.factor: f.steps for f in rec.escalation_factors}


def active_campaign(engine: Engine, **pred: Any) -> str:
    """Submit, approve and activate the cert-rotation campaign; returns its id."""
    camp = example("campaign-cert-rotation.json")
    camp["status"] = "requested"
    camp["class_predicate"].update(pred)
    rec = engine.submit(camp)
    assert isinstance(rec, DecisionRecord), rec
    engine.decide(rec.decision_id, "approved", "cab@company.com")
    engine.transition(camp["intent_id"], GrantStatus.ACTIVE, "cab@company.com")
    return str(camp["intent_id"])


def covered_child(**overrides: Any) -> dict[str, Any]:
    """A change the cert-rotation campaign covers: C, internal, production, edge TLS."""
    doc = intent(intent_id="int-chg-cover-1", grant_ref="int-cmp-20260801-0002")
    doc["declaration"].update(
        {
            "operation": "C",
            "target": "fleet://edge-nodes/node-17/tls-cert",
            "target_class": "fleet://edge-nodes/*",
            "data_classification": "internal",
            "environment": "production",
            "blast_radius": {"scope_percentage": 2},
        }
    )
    doc["declaration"]["reversibility"] = {
        "rollback_declared": True, "attested_by": "release-engineering@company.com"
    }
    doc.update(overrides)
    return doc


def audit_record(
    intent_id: str | None, op: str, target: str, tier: str = "internal", *,
    rid: str = "aud-1", ts: str = "2026-08-15T12:00:00Z", agent: str = "devops-agent-007",
) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "record_id": rid, "timestamp": ts, "agent_id": agent, "profile_id": "rmacd-3d-devops-v1",
        "operation": {"type": op, "target": target, "classification": tier},
        "policy_decision": {"result": "EXECUTED", "autonomy_level": "approval"},
        "execution": {"status": "SUCCESS", "duration_ms": 12},
    }
    if intent_id:
        rec["extra"] = {"intent_id": intent_id}
    return rec


# ------------------------------------------------------------------- coverage


def test_a_child_above_the_grants_max_level_is_not_covered(engine: Engine) -> None:
    active_campaign(engine)
    rec = engine.submit(covered_child())
    assert isinstance(rec, DecisionRecord)
    # devops internal.C is approval; +precedent +environment = elevated_approval,
    # above the campaign's max_level of approval — so this child is NOT covered.
    assert rec.computed_level is AutonomyLevel.ELEVATED_APPROVAL
    assert rec.grant_ref is None  # N-28 condition 2


def test_full_coverage_path_with_a_matching_predicate(
    store: MemoryStore, resolver: Any, clock: Clock
) -> None:
    engine = Engine(store, resolver, clock=clock)
    grant = active_campaign(engine, data_classification="public", environment="staging")
    child = covered_child(intent_id="int-chg-cover-3")
    child["declaration"].update({"data_classification": "public", "environment": "staging"})
    rec = engine.submit(child)
    assert isinstance(rec, DecisionRecord)
    assert rec.base_level is AutonomyLevel.NOTIFICATION  # devops overrides public.C
    assert rec.computed_level is AutonomyLevel.APPROVAL  # +1 precedent
    assert rec.grant_ref == grant  # N-27: approval in advance; level untouched
    assert rec.disposition is None  # the grant is the decision; nothing to attach


def test_child_cap_is_consumed_atomically_and_then_refused(
    store: MemoryStore, resolver: Any, clock: Clock
) -> None:
    engine = Engine(store, resolver, clock=clock)
    camp = example("campaign-cert-rotation.json")
    camp["status"] = "requested"
    camp["class_predicate"].update({"data_classification": "public", "environment": "staging"})
    camp["caps"]["max_children"] = 2
    rec = engine.submit(camp)
    assert isinstance(rec, DecisionRecord)
    engine.decide(rec.decision_id, "approved", "cab@company.com")
    engine.transition(camp["intent_id"], GrantStatus.ACTIVE, "cab@company.com")
    outcomes = []
    for i in range(3):
        child = covered_child(intent_id=f"int-chg-cap-{i}")
        child["declaration"].update({"data_classification": "public", "environment": "staging"})
        r = engine.submit(child)
        assert isinstance(r, DecisionRecord)
        outcomes.append(r.grant_ref)
    # N-55: the third child finds the cap consumed and routes to a human.
    assert outcomes == [camp["intent_id"], camp["intent_id"], None]


def test_revoked_grant_covers_nothing_and_marks_its_children(
    store: MemoryStore, resolver: Any, clock: Clock
) -> None:
    engine = Engine(store, resolver, clock=clock)
    grant = active_campaign(engine, data_classification="public", environment="staging")
    child = covered_child(intent_id="int-chg-rev-1")
    child["declaration"].update({"data_classification": "public", "environment": "staging"})
    first = engine.submit(child)
    assert isinstance(first, DecisionRecord) and first.grant_ref == grant
    engine.transition(grant, GrantStatus.REVOKED, "ciso@company.com")  # N-34
    marks = [e for e in store.intent_entries() if e.kind == "review"]
    assert [m.intent_id for m in marks] == ["int-chg-rev-1"]  # N-35, N-78
    assert marks[0].cause is not None and grant in marks[0].cause
    later = covered_child(intent_id="int-chg-rev-2")
    later["declaration"].update({"data_classification": "public", "environment": "staging"})
    rec = engine.submit(later)
    assert isinstance(rec, DecisionRecord) and rec.grant_ref is None


def test_exception_covers_only_its_profile_and_actor(
    store: MemoryStore, resolver: Any, clock: Clock
) -> None:
    engine = Engine(store, resolver, clock=clock)
    exc = example("exception-urgent.json")  # base_profile_id observer-3d, actor devops-agent-007
    exc["base_profile_id"] = "rmacd-3d-devops-v1"
    rec = engine.submit(exc)
    assert isinstance(rec, DecisionRecord)
    engine.decide(rec.decision_id, "approved", "ciso@company.com")
    engine.transition(exc["intent_id"], GrantStatus.ACTIVE, "ciso@company.com")
    # Same actor, inside the grid (confidential A), bound to devops, no caps: covered.
    child = intent(intent_id="int-chg-exc-1", grant_ref=exc["intent_id"])
    child["declaration"].update({"operation": "A", "environment": "staging"})
    r1 = engine.submit(child)
    assert isinstance(r1, DecisionRecord) and r1.grant_ref == exc["intent_id"]
    # A different actor on the same profile: not covered (N-28 condition 6).
    other = intent(intent_id="int-chg-exc-2", grant_ref=exc["intent_id"])
    other["actor"] = {"kind": "pipeline", "id": "ci-release-pipeline",
                      "authorization": "spiffe://corp/ns/ci/release-pipeline",
                      "on_behalf_of": "release-engineering@company.com"}
    other["declaration"].update({"operation": "A", "environment": "staging"})
    r2 = engine.submit(other)
    assert isinstance(r2, DecisionRecord) and r2.grant_ref is None


def test_blanket_grant_is_refused(engine: Engine) -> None:
    camp = example("campaign-cert-rotation.json")
    camp["status"] = "requested"
    camp["class_predicate"] = {"intent_type": "change"}
    r = engine.submit(camp)
    assert isinstance(r, Rejection) and "N-32" in r.failure


# --------------------------------------------------------------- reconciliation


def approved_change(engine: Engine, **overrides: Any) -> DecisionRecord:
    doc = intent(**overrides)
    rec = engine.submit(doc)
    assert isinstance(rec, DecisionRecord)
    engine.decide(rec.decision_id, "approved", "cab@company.com")
    return rec


def test_matched_execution_retires_the_unprecedented_factor(
    engine: Engine, store: MemoryStore
) -> None:
    first = approved_change(engine)
    assert factors_of(first).get("precedent") == 1
    report = Reconciler(engine).run(
        [audit_record(first.intent_id, "C", "svc://payments-api/config/connection-pool",
                      "confidential")]
    )
    assert report.matched == [first.decision_id]
    logical = store.decision(first.decision_id)
    assert logical is not None and logical.reconciliation is not None
    assert logical.reconciliation.result == "matched"
    second = engine.submit(intent(intent_id="int-chg-20260815-0099"))
    assert isinstance(second, DecisionRecord)
    assert "precedent" not in factors_of(second)  # N-25: one reconciled success retires it


def test_divergent_execution_demotes_and_wipes_precedent(
    engine: Engine, store: MemoryStore
) -> None:
    first = approved_change(engine)
    Reconciler(engine).run(
        [audit_record(first.intent_id, "C", "svc://payments-api/config/connection-pool",
                      "confidential")]
    )
    second = approved_change(engine, intent_id="int-chg-20260815-0099")
    assert "precedent" not in factors_of(second)
    # Declared C, executed D on a different target class.
    report = Reconciler(engine).run(
        [audit_record(second.intent_id, "D", "db://prod/payments/customers", "confidential",
                      rid="aud-2")]
    )
    assert report.divergent == [second.decision_id] and report.demoted == ["devops-agent-007"]
    logical = store.decision(second.decision_id)
    assert logical is not None and logical.reconciliation is not None
    fields = {d.field for d in logical.reconciliation.discrepancies or []}
    assert fields == {"operation", "target_class"}
    demotion = store.demotion("devops-agent-007", engine.clock())
    assert demotion is not None and demotion.kind == "demotion"  # N-77
    third = engine.submit(intent(intent_id="int-chg-20260815-0100"))
    assert isinstance(third, DecisionRecord)
    assert factors_of(third)["precedent"] == 1  # N-26: wiped
    assert factors_of(third)["budget_standing"] == 2  # N-40: demotion is escalation
    engine.lift_demotion("devops-agent-007", "ciso@company.com")
    fourth = engine.submit(intent(intent_id="int-chg-20260815-0101"))
    assert isinstance(fourth, DecisionRecord)
    assert "budget_standing" not in factors_of(fourth)  # lifted


def test_demotion_expires_by_its_declared_bound(
    engine: Engine, store: MemoryStore, clock: Clock
) -> None:
    rec = approved_change(engine)
    Reconciler(engine).run([audit_record(rec.intent_id, "D", "x://y/z", "confidential")])
    assert store.demotion("devops-agent-007", clock()) is not None
    clock.now = clock.now + timedelta(days=31)
    assert store.demotion("devops-agent-007", clock()) is None  # weights.demotion_days = 30


def test_undeclared_execution_is_reported_and_demotes_the_agent(
    engine: Engine, store: MemoryStore
) -> None:
    report = Reconciler(engine).run(
        [audit_record(None, "C", "svc://payments-api/config/x", agent="claude-code")]
    )
    assert report.undeclared == ["aud-1"] and report.demoted == ["claude-code"]  # N-48
    report2 = Reconciler(engine).run(
        [audit_record(None, "C", "svc://a/b", agent="other-agent", rid="aud-9")],
        undeclared="report",
    )
    assert report2.undeclared == ["aud-9"] and report2.demoted == []


def test_unexecuted_after_expiry_and_unset_before(
    engine: Engine, store: MemoryStore, clock: Clock
) -> None:
    rec = approved_change(engine)  # valid_until 2026-08-15T18:00:00Z; clock is 10:00
    report = Reconciler(engine).run([])
    assert report.skipped == [rec.decision_id]  # N-49: not matched, not anything
    logical = store.decision(rec.decision_id)
    assert logical is not None and logical.reconciliation is None
    clock.now = clock.now + timedelta(hours=9)
    report = Reconciler(engine).run([])
    assert report.unexecuted == [rec.decision_id]  # N-52


def test_unreconciled_is_never_matched_and_a_record_reconciles_once(
    engine: Engine, store: MemoryStore
) -> None:
    rec = approved_change(engine)
    Reconciler(engine).run(
        [audit_record(rec.intent_id, "C", "svc://payments-api/config/connection-pool",
                      "confidential")]
    )
    again = Reconciler(engine).run(
        [audit_record(rec.intent_id, "C", "svc://payments-api/config/connection-pool",
                      "confidential", rid="aud-2")]
    )
    assert again.matched == [] and again.divergent == []  # already reconciled; N-74: once
    assert store.reconciliation_count(rec.decision_id) == 1


def test_execution_outside_the_cited_window_is_divergent(
    engine: Engine, store: MemoryStore
) -> None:
    mw = intent(intent_id="int-mw-1", intent_type="maintenance_window",
                window={"start": "2026-08-16T02:00:00Z", "end": "2026-08-16T04:00:00Z"},
                service_commitment="payments-sla-gold")
    mw["declaration"].update({"operation": "M", "target": "svc://payments-api"})
    assert isinstance(engine.submit(mw), DecisionRecord)
    rel = example("release-composed.json")
    rel["composes"] = []
    del rel["composes"]
    rel["intent_type"] = "change"
    rel["intent_id"] = "int-chg-rel-1"
    assert isinstance(engine.submit(rel), DecisionRecord)
    dep = intent(intent_id="int-dep-1", intent_type="deployment", requires=["int-chg-rel-1"],
                 window_ref="int-mw-1")
    dep["declaration"].update({"target": "svc://payments-api/deploy/2026.8.3"})
    rec = engine.submit(dep)
    assert isinstance(rec, DecisionRecord)
    engine.decide(rec.decision_id, "approved", "cab@company.com")
    report = Reconciler(engine).run(
        [audit_record("int-dep-1", "C", "svc://payments-api/deploy/2026.8.3", "confidential",
                      ts="2026-08-16T05:30:00Z")]
    )
    assert report.divergent == [rec.decision_id]
    logical = store.decision(rec.decision_id)
    assert logical is not None and logical.reconciliation is not None
    assert [d.field for d in logical.reconciliation.discrepancies or []] == ["window"]  # N-62


def test_l1_engine_keeps_the_six_fields_instead_of_the_hash(
    store: MemoryStore, resolver: Any, clock: Clock
) -> None:
    engine = Engine(store, resolver, clock=clock, implementation_level="L1")
    rec = engine.submit(intent())
    assert isinstance(rec, DecisionRecord)
    assert rec.action_pattern_key is None and rec.action_pattern_fields is not None  # N-69
    assert rec.implementation_level == "L1"


def test_normalization_records_an_overridden_target_class(engine: Engine) -> None:
    doc = intent()
    doc["declaration"]["target_class"] = "svc://payments-api/*"  # broader than the derived class
    rec = engine.submit(doc)
    assert isinstance(rec, DecisionRecord)
    assert rec.normalization.supplied_target_class == "svc://payments-api/*"  # N-24
    assert rec.normalization.target_class_rule == "last-segment-wildcard"  # N-23
    missing = intent(intent_id="int-chg-nocls")
    del missing["declaration"]["data_classification"]
    missing["declaration"]["operation"] = "R"
    rec2 = engine.submit(missing)
    assert isinstance(rec2, DecisionRecord)
    assert rec2.normalization.classification_assumed is True  # N-3


@pytest.mark.parametrize("name", ["intent-log-demotion.json", "intent-log-review.json"])
def test_new_log_examples_parse(name: str) -> None:
    from rmacd_intents.models import IntentLogEntry

    IntentLogEntry.model_validate(example(name))
