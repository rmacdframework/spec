"""``PolicyEvaluator.required_autonomy``: the effective-matrix cell, nothing else.

Adjudication (Intent Specification N-13, N-20) needs the level the matrix
requires even when the profile withholds the permission. ``evaluate`` folds
permission and autonomy together; this accessor must not.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rmacd import (
    AutonomyLevel,
    DataClassification,
    Operation,
    PolicyEvaluator,
    ProfileLoader,
)
from rmacd.evaluator import DEFAULT_AUTONOMY_3D, IMMUTABLE_PROHIBITIONS

FIXTURES = Path(__file__).resolve().parent.parent.parent.parent / "schemas" / "examples"


def evaluator(name: str) -> PolicyEvaluator:
    return PolicyEvaluator(ProfileLoader().load_file(FIXTURES / name))


def test_profile_override_wins_over_the_default() -> None:
    # devops-3d declares internal.C -> approval; the §3.1 default is approval too,
    # so use confidential.M, which it overrides from approval to approval... pick
    # public.C: default approval, override notification.
    ev = evaluator("devops-3d.json")
    assert DEFAULT_AUTONOMY_3D["public"]["C"] is AutonomyLevel.APPROVAL
    assert ev.required_autonomy("C", "public") is AutonomyLevel.NOTIFICATION


def test_unoverridden_cell_is_the_section_3_1_default() -> None:
    ev = evaluator("devops-3d.json")
    # The worked example in intents.md §11 relies on exactly this cell.
    assert ev.required_autonomy(Operation.CHANGE, DataClassification.CONFIDENTIAL) is (
        AutonomyLevel.ELEVATED_APPROVAL
    )


def test_withheld_permission_still_has_a_level() -> None:
    # observer-3d grants R only. evaluate() says "not allowed"; the matrix cell
    # for Delete on internal still exists and adjudication grades from it.
    ev = evaluator("observer-3d.json")
    decision = ev.evaluate(
        operation=Operation.DELETE, data_classification=DataClassification.INTERNAL
    )
    assert not decision.allowed
    assert ev.required_autonomy("D", "internal") is AutonomyLevel.ELEVATED_APPROVAL


@pytest.mark.parametrize("op", ["A", "C", "D"])
def test_immutable_floor_applies_on_every_profile_shape(op: str) -> None:
    for name in ("administrator-3d.json", "regulated-data-handler-dc2d.json"):
        assert evaluator(name).required_autonomy(op, "restricted") is AutonomyLevel.PROHIBITED
    assert (DataClassification.RESTRICTED, Operation(op)) in IMMUTABLE_PROHIBITIONS


def test_dc2d_reads_the_tier_policy_and_ignores_the_operation() -> None:
    ev = evaluator("regulated-data-handler-dc2d.json")
    expected = ev.profile.data_access.for_tier(DataClassification.CONFIDENTIAL).autonomy  # type: ignore[union-attr]
    assert ev.required_autonomy("R", "confidential") is expected
    assert ev.required_autonomy("M", "confidential") is expected


def test_dc2d_without_a_tier_is_an_error() -> None:
    with pytest.raises(ValueError, match="indexed by tier"):
        evaluator("regulated-data-handler-dc2d.json").required_autonomy("R")


def test_2d_ignores_a_supplied_tier() -> None:
    ev = evaluator("operations-2d.json")
    assert ev.required_autonomy("C") is ev.required_autonomy("C", "restricted")


def test_matches_the_effective_matrix_accessor_everywhere() -> None:
    ev = evaluator("administrator-3d.json")
    matrix = ev.get_effective_autonomy_matrix()
    for tier, row in matrix.items():
        assert isinstance(row, dict)
        for op, level in row.items():
            assert ev.required_autonomy(op, tier).value == level
