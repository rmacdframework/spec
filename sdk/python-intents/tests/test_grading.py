"""The nine steps, each pinned to the rule it implements."""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest
from rmacd import AutonomyLevel

from rmacd_intents import DecisionRecord, MemoryStore, Rejection
from rmacd_intents.envelope import DECISION_SCHEMA_ID, assert_valid
from rmacd_intents.grading import Engine, escalate
from rmacd_intents.models import LADDER

from .conftest import example, intent


def factors_of(rec: DecisionRecord) -> dict[str, int]:
    return {f.factor: f.steps for f in rec.escalation_factors}


# ---------------------------------------------------------------- §11 worked example


def test_the_worked_example_in_intents_md_section_11(engine: Engine) -> None:
    """change-production.json under devops-3d: base elevated_approval, two factors absorbed."""
    rec = engine.submit(example("change-production.json"))
    assert isinstance(rec, DecisionRecord)
    assert rec.base_level is AutonomyLevel.ELEVATED_APPROVAL
    assert rec.computed_level is AutonomyLevel.ELEVATED_APPROVAL
    # Both factors fired and are recorded even though the ceiling absorbed them.
    assert factors_of(rec) == {"precedent": 1, "environment": 1}
    assert rec.profile_id == "rmacd-3d-devops-v1"
    assert rec.implementation_level == "L1"
    assert rec.action_pattern_key is None and rec.action_pattern_fields is not None  # N-69
    assert rec.action_pattern_fields.target_class == "svc://payments-api/config/*"


def test_the_neighbouring_internal_change_moves_from_approval_to_elevated(engine: Engine) -> None:
    """decision-record.json's story: internal.C is overridden to approval; +2 lifts it."""
    doc = intent(intent_id="int-chg-20260815-0032")
    doc["declaration"]["data_classification"] = "internal"
    doc["declaration"]["reversibility"] = {
        "rollback_declared": True, "attested_by": "release-engineering@company.com"
    }
    rec = engine.submit(doc)
    assert isinstance(rec, DecisionRecord)
    assert rec.base_level is AutonomyLevel.APPROVAL
    assert rec.computed_level is AutonomyLevel.ELEVATED_APPROVAL
    assert factors_of(rec) == {"precedent": 1, "environment": 1}


# ------------------------------------------------------------------ step 1: validate


def test_malformed_is_rejected_never_defaulted_and_logged(
    engine: Engine, store: MemoryStore
) -> None:
    doc = intent()
    del doc["actor"]
    r = engine.submit(doc)
    assert isinstance(r, Rejection) and "actor" in r.failure
    entries = list(store.intent_entries())
    assert [e.kind for e in entries] == ["rejection"]  # N-59
    assert entries[0].document == doc and entries[0].intent_id == doc["intent_id"]
    assert list(store.adjudication_entries()) == []  # N-72: never in the adjudication log


def test_not_json_is_kept_as_raw_text(engine: Engine, store: MemoryStore) -> None:
    r = engine.submit(b"{this is not json")
    assert isinstance(r, Rejection)
    e = next(store.intent_entries())
    assert e.kind == "rejection" and e.raw == "{this is not json" and e.document is None  # N-73


def test_asserted_rating_is_refused_by_the_envelope(engine: Engine) -> None:
    r = engine.submit(intent(autonomy_level="autonomous"))
    assert isinstance(r, Rejection)  # N-8 via N-1: the schema admits no such field


def test_duplicate_intent_id_is_refused(engine: Engine, store: MemoryStore) -> None:
    assert isinstance(engine.submit(intent()), DecisionRecord)
    r = engine.submit(intent(justification="changed my mind"))
    assert isinstance(r, Rejection) and "N-57" in r.failure
    assert sum(1 for e in store.adjudication_entries()) == 1  # N-58: graded once


def test_valid_until_must_follow_submitted_at(engine: Engine) -> None:
    r = engine.submit(intent(valid_until="2026-08-15T09:00:00Z"))
    assert isinstance(r, Rejection) and "N-52" in r.failure


def test_submission_is_logged_exactly_as_received(engine: Engine, store: MemoryStore) -> None:
    doc = intent()
    engine.submit(doc)
    sub = next(e for e in store.intent_entries() if e.kind == "submission")
    assert sub.document == doc  # N-73


# ------------------------------------------------------------- step 2: the actor


def test_agent_without_accountable_human_is_rejected(engine: Engine) -> None:
    doc = intent()
    del doc["actor"]["on_behalf_of"]
    r = engine.submit(doc)
    assert isinstance(r, Rejection)  # N-5 — the schema catches this one at step 1


def test_unresolved_actor_fails_closed_to_at_least_approval(resolver: Any, clock: Any) -> None:
    from rmacd import ProfileLoader

    from .conftest import PROFILES

    engine = Engine(
        MemoryStore(), resolver, clock=clock,
        default_profile=ProfileLoader().load_file(PROFILES / "administrator-3d.json"),
    )
    doc = intent()
    doc["actor"]["authorization"] = "spiffe://nobody/knows/this"
    doc["declaration"].update({"operation": "R", "data_classification": "public",
                               "environment": "development"})
    rec = engine.submit(doc)
    assert isinstance(rec, DecisionRecord)
    assert "unresolved_authorization" not in factors_of(rec)  # Read on public is exempt
    doc = intent(intent_id="int-chg-20260815-0099")
    doc["actor"]["authorization"] = "spiffe://nobody/knows/this"
    doc["declaration"].update({"operation": "R", "data_classification": "confidential",
                               "environment": "development"})
    rec = engine.submit(doc)
    assert isinstance(rec, DecisionRecord)
    assert "unresolved_authorization" in factors_of(rec)  # N-6: Read on confidential escalates
    assert rec.computed_level.value != "autonomous"
    assert LADDER.index(rec.computed_level) >= LADDER.index(AutonomyLevel.APPROVAL)


def test_unresolved_actor_with_no_profile_anywhere_is_rejected(engine: Engine) -> None:
    doc = intent()
    doc["actor"]["authorization"] = "spiffe://nobody/knows/this"
    r = engine.submit(doc)
    assert isinstance(r, Rejection) and "N-13" in r.failure


def test_actor_kind_never_changes_the_level(engine: Engine) -> None:
    a = intent(intent_id="int-a")
    b = intent(intent_id="int-b")
    b["actor"] = {"kind": "human", "id": "j.smith@company.com",
                  "authorization": "spiffe://corp/ns/agents/devops-agent-007"}
    ra, rb = engine.submit(a), engine.submit(b)
    assert isinstance(ra, DecisionRecord) and isinstance(rb, DecisionRecord)
    assert ra.computed_level is rb.computed_level and factors_of(ra) == factors_of(rb)  # N-7


# ---------------------------------------------------------------- step 3: the floor


@pytest.mark.parametrize("op", ["A", "C", "D"])
def test_pinned_floor_comes_first_and_records_its_source(engine: Engine, op: str) -> None:
    doc = intent(intent_id=f"int-floor-{op.lower()}")
    doc["actor"]["authorization"] = "okta://company.com/users/j.smith"
    doc["actor"] = {"kind": "human", "id": "j.smith@company.com",
                    "authorization": "okta://company.com/users/j.smith"}
    doc["declaration"].update({"operation": op, "data_classification": "restricted"})
    rec = engine.submit(doc)
    assert isinstance(rec, DecisionRecord)
    assert rec.computed_level is AutonomyLevel.PROHIBITED
    assert rec.prohibition_source == "pinned"  # N-12, N-44
    assert rec.escalation_factors == []  # no factor ran after the stop


def test_extended_prohibition_is_recorded_as_extended(
    store: MemoryStore, resolver: Any, clock: Any
) -> None:
    from rmacd import DataClassification, Operation

    engine = Engine(store, resolver, clock=clock,
                    extended_prohibitions={(DataClassification.CONFIDENTIAL, Operation.DELETE)})
    doc = intent()
    doc["declaration"]["operation"] = "D"
    rec = engine.submit(doc)
    assert isinstance(rec, DecisionRecord)
    assert rec.computed_level is AutonomyLevel.PROHIBITED and rec.prohibition_source == "extended"


def test_missing_classification_is_graded_as_restricted(engine: Engine) -> None:
    doc = intent()
    del doc["declaration"]["data_classification"]
    rec = engine.submit(doc)
    assert isinstance(rec, DecisionRecord)
    assert rec.impact_basis.value == "restricted"  # N-3
    assert rec.computed_level is AutonomyLevel.PROHIBITED  # Change on restricted is pinned


# -------------------------------------------------------------- steps 4–6: grading


def test_base_comes_from_the_profile_matrix_not_a_second_one(engine: Engine) -> None:
    doc = intent()
    doc["declaration"].update({"operation": "C", "data_classification": "public",
                                               "environment": "development"})
    rec = engine.submit(doc)
    assert isinstance(rec, DecisionRecord)
    assert rec.base_level is AutonomyLevel.NOTIFICATION  # devops overrides public.C


@pytest.mark.parametrize("base", LADDER[:5])
@pytest.mark.parametrize("steps", [0, 1, 2, 3, 7, 100])
def test_escalate_is_one_way_and_stops_below_prohibited(base: AutonomyLevel, steps: int) -> None:
    out = escalate(base, steps)
    assert LADDER.index(out) >= LADDER.index(base)  # N-14
    assert out is not AutonomyLevel.PROHIBITED  # N-14a


def test_negative_steps_are_impossible() -> None:
    with pytest.raises(ValueError):
        escalate(AutonomyLevel.LOGGED, -1)  # N-19


def test_negative_weights_are_refused_at_load() -> None:
    from pydantic import ValidationError

    from rmacd_intents import WeightTable

    with pytest.raises(ValidationError):
        WeightTable(environment=-1)  # N-18


def test_rollback_buys_no_discount_and_self_attestation_does_not_count(engine: Engine) -> None:
    attested = intent(intent_id="int-att")
    unattested = intent(intent_id="int-unatt")
    del unattested["declaration"]["reversibility"]
    selfatt = intent(intent_id="int-self")
    selfatt["declaration"]["reversibility"]["attested_by"] = "devops-agent-007"
    for doc in (attested, unattested, selfatt):
        doc["declaration"].update({"data_classification": "internal", "environment": "staging"})
    ra, ru, rs = (engine.submit(d) for d in (attested, unattested, selfatt))
    assert isinstance(ra, DecisionRecord)
    assert isinstance(ru, DecisionRecord)
    assert isinstance(rs, DecisionRecord)
    assert "reversibility" not in factors_of(ra)
    assert factors_of(ru)["reversibility"] == 1  # N-4: the attestation only fails to add a step
    assert factors_of(rs)["reversibility"] == 1  # N-51: self-attestation is not attestation
    assert LADDER.index(ra.computed_level) >= LADDER.index(ra.base_level)


def test_blast_radius_against_the_profile_cap(engine: Engine) -> None:
    near = intent(intent_id="int-near")
    near["declaration"]["blast_radius"] = {"scope_percentage": 9}
    over = intent(intent_id="int-over")
    over["declaration"]["blast_radius"] = {"scope_percentage": 40}
    rn, ro = engine.submit(near), engine.submit(over)
    assert isinstance(rn, DecisionRecord) and isinstance(ro, DecisionRecord)
    assert factors_of(rn)["blast_radius"] == 1  # within 80% of the devops cap of 10
    assert factors_of(ro)["blast_radius"] == 2  # over the cap


def test_budget_breach_escalates_never_denies(
    store: MemoryStore, resolver: Any, clock: Any
) -> None:
    from rmacd_intents import WeightTable

    engine = Engine(store, resolver, clock=clock, weights=WeightTable(version="t"))
    # devops-3d: operations_per_hour = 50. Flood 51 accepted intents, then one more.
    for i in range(51):
        doc = intent(intent_id=f"int-flood-{i}")
        doc["declaration"].update({"data_classification": "internal", "environment": "staging"})
        assert isinstance(engine.submit(doc), DecisionRecord)
    doc = intent(intent_id="int-flood-last")
    doc["declaration"].update({"data_classification": "internal", "environment": "staging"})
    rec = engine.submit(doc)
    assert isinstance(rec, DecisionRecord)  # N-39: not a denial
    assert factors_of(rec)["budget_standing"] == 2


# -------------------------------------------------------------- step 7: bundles


def test_bundle_inherits_the_worst_child(engine: Engine) -> None:
    benign = intent(intent_id="int-chg-20260815-0031")
    benign["declaration"].update({"data_classification": "public", "environment": "development"})
    assert isinstance(engine.submit(benign), DecisionRecord)
    risky = example("change-production.json")
    risky["intent_id"] = "int-chg-20260815-0033"
    assert isinstance(engine.submit(risky), DecisionRecord)
    release = example("release-composed.json")
    release["composes"] = ["int-chg-20260815-0031", "int-chg-20260815-0033"]
    # A third-party attestation, so the release's own factors stop at precedent.
    release["actor"]["on_behalf_of"] = "platform-team@company.com"
    release["declaration"].update({"data_classification": "public", "environment": "development"})
    rec = engine.submit(release)
    assert isinstance(rec, DecisionRecord)
    assert rec.computed_level is AutonomyLevel.ELEVATED_APPROVAL  # N-11
    assert "composition_floor" in factors_of(rec)


def test_bundle_cannot_be_decided_before_its_children(engine: Engine) -> None:
    release = example("release-composed.json")  # composes three ungraded children
    rec = engine.submit(release)
    assert isinstance(rec, DecisionRecord)
    with pytest.raises(ValueError, match="N-63"):
        engine.decide(rec.decision_id, "approved", "cab@company.com")


# ------------------------------------------------------------------ grants (§7.5)


def test_a_campaign_is_graded_by_its_reach_not_its_declaration(engine: Engine) -> None:
    camp = example("campaign-cert-rotation.json")
    camp["status"] = "requested"
    # The requester wrote a harmless declaration; the match rule reaches C on internal
    # in production.
    camp["declaration"].update({"operation": "R", "data_classification": "public",
                                "environment": "development"})
    rec = engine.submit(camp)
    assert isinstance(rec, DecisionRecord)
    assert rec.base_level is AutonomyLevel.APPROVAL  # administrator-3d internal.C  (N-66)
    # Not autonomous, which is what its own declaration would have earned it.
    assert LADDER.index(rec.computed_level) >= LADDER.index(AutonomyLevel.APPROVAL)


def test_a_grant_is_never_graded_below_its_cap(engine: Engine) -> None:
    camp = example("campaign-cert-rotation.json")
    camp["status"] = "requested"
    camp["class_predicate"] = {
        "intent_type": "change", "operation": "R", "data_classification": "public",
        "environment": "development", "target_class": "doc://*",
    }
    camp["caps"]["max_level"] = "elevated_approval"
    camp["declaration"].update({"operation": "R", "data_classification": "public",
                                "environment": "development"})
    rec = engine.submit(camp)
    assert isinstance(rec, DecisionRecord)
    assert rec.computed_level is AutonomyLevel.ELEVATED_APPROVAL
    assert "grant_cap" in factors_of(rec)  # N-67


def test_a_grant_reaching_a_pinned_cell_is_refused(engine: Engine) -> None:
    camp = example("campaign-cert-rotation.json")
    camp["status"] = "requested"
    camp["class_predicate"] = {"intent_type": "change", "operation": "D",
                               "data_classification": "restricted", "target_class": "x://*"}
    r = engine.submit(camp)
    assert isinstance(r, Rejection) and "N-29" in r.failure


def test_a_grant_needs_a_human_decision_before_it_is_active(engine: Engine) -> None:
    from rmacd_intents.models import GrantStatus

    camp = example("campaign-cert-rotation.json")
    camp["status"] = "requested"
    rec = engine.submit(camp)
    assert isinstance(rec, DecisionRecord)
    with pytest.raises(ValueError, match="N-68"):
        engine.transition(camp["intent_id"], GrantStatus.ACTIVE, "cab@company.com")
    engine.decide(rec.decision_id, "approved", "cab@company.com")
    entry = engine.transition(camp["intent_id"], GrantStatus.ACTIVE, "cab@company.com")
    assert entry.from_status is GrantStatus.REQUESTED  # N-71
    assert entry.to_status is GrantStatus.ACTIVE


def test_an_actor_cannot_submit_an_already_active_grant(engine: Engine) -> None:
    camp = example("campaign-cert-rotation.json")  # the example is "active"
    r = engine.submit(camp)
    assert isinstance(r, Rejection) and "N-71" in r.failure


# -------------------------------------------------------------- step 9 + decide


def test_every_record_is_schema_valid_and_carries_the_four_inputs(engine: Engine) -> None:
    rec = engine.submit(intent())
    assert isinstance(rec, DecisionRecord)
    d = rec.to_json_dict()
    assert_valid(DECISION_SCHEMA_ID, d)
    for key in ("matrix_version", "likelihood_weights_version", "policy_version", "log_epoch"):
        assert d[key]  # N-21
    assert d["log_epoch"] == "seq-1"  # N-75: the submission entry is what the grading read


def test_epoch_is_the_shared_counter(engine: Engine, store: MemoryStore) -> None:
    a = engine.submit(intent(intent_id="int-a"))
    b = engine.submit(intent(intent_id="int-b"))
    assert isinstance(a, DecisionRecord) and isinstance(b, DecisionRecord)
    assert a.log_epoch == "seq-1" and b.log_epoch == "seq-3"
    seqs = [e.seq for e in store.intent_entries()] + [e.seq for e in store.adjudication_entries()]
    assert sorted(seqs) == [1, 2, 3, 4]  # N-76: one counter, no gaps, no repeats


def test_decide_attaches_once_and_never_rewrites(engine: Engine, store: MemoryStore) -> None:
    rec = engine.submit(intent())
    assert isinstance(rec, DecisionRecord)
    engine.decide(rec.decision_id, "approved", "cab@company.com", note="ok")
    with pytest.raises(ValueError, match="N-43"):
        engine.decide(rec.decision_id, "denied", "cab@company.com")
    kinds = [e.kind for e in store.adjudication_entries()]
    assert kinds == ["decision", "disposition"]  # N-74: an attachment, not a rewrite
    logical = store.decision(rec.decision_id)
    assert logical is not None and logical.disposition is not None and logical.disposition.permits


def test_no_one_grades_their_own_ask(engine: Engine) -> None:
    rec = engine.submit(intent())
    assert isinstance(rec, DecisionRecord)
    for who in ("devops-agent-007", "platform-team@company.com"):
        with pytest.raises(ValueError, match="N-64"):
            engine.decide(rec.decision_id, "approved", who)


def test_prohibited_cannot_be_approved(engine: Engine) -> None:
    doc = intent()
    doc["declaration"]["data_classification"] = "restricted"
    rec = engine.submit(doc)
    assert isinstance(rec, DecisionRecord) and rec.computed_level is AutonomyLevel.PROHIBITED
    with pytest.raises(ValueError, match="N-12"):
        engine.decide(rec.decision_id, "approved", "ciso@company.com")
    engine.decide(rec.decision_id, "denied", "ciso@company.com")  # recording the refusal is fine


def test_same_inputs_same_level(resolver: Any) -> None:
    """N-21: two engines over the same logs and versions grade identically."""
    from .conftest import Clock

    results: list[dict[str, Any]] = []
    for _ in range(2):
        engine = Engine(MemoryStore(), resolver, clock=Clock(), policy_version="p")
        rec = engine.submit(copy.deepcopy(intent()))
        assert isinstance(rec, DecisionRecord)
        results.append(rec.to_json_dict())
    assert results[0] == results[1]


def test_every_worked_example_grades_or_is_refused_for_a_stated_reason(engine: Engine) -> None:
    outcomes = {}
    for name in ("change-production.json", "incident-record-plane.json", "release-composed.json",
                 "exception-urgent.json", "campaign-cert-rotation.json"):
        r = engine.submit(example(name))
        outcomes[name] = type(r).__name__ if isinstance(r, DecisionRecord) else r.failure
    assert outcomes["change-production.json"] == "DecisionRecord"
    assert outcomes["incident-record-plane.json"] == "DecisionRecord"
    assert outcomes["release-composed.json"] == "DecisionRecord"
    assert outcomes["exception-urgent.json"] == "DecisionRecord"
    assert "N-71" in outcomes["campaign-cert-rotation.json"]  # the example is already active
    assert json.dumps(outcomes)  # serialisable, for the record
