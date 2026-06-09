"""Tests for ProfileValidator and the tightened safety-boundary schema rules."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from rmacd.validator import ProfileValidator, SchemaValidationError

EXAMPLES_DIR = Path(__file__).resolve().parents[3] / "schemas" / "examples"


def _base_3d() -> dict:
    return {
        "$schema": "https://rmacd-framework.org/schema/v1/profile-3d.json",
        "profile_id": "rmacd-3d-test",
        "profile_name": "Test",
        "model": "three-dimensional",
        "version": "1.0",
        "permissions": {
            "public": ["R"],
            "internal": ["R"],
            "confidential": ["R"],
            "restricted": ["R"],
        },
        "metadata": {"created": "2026-06-08T00:00:00Z", "author": "tester"},
    }


@pytest.fixture
def validator() -> ProfileValidator:
    return ProfileValidator()


class TestValidatorBasics:
    def test_valid_baseline_3d(self, validator: ProfileValidator) -> None:
        assert validator.is_valid(_base_3d()) is True

    def test_validate_raises_on_unknown_model(self, validator: ProfileValidator) -> None:
        bad = _base_3d()
        bad["model"] = "four-dimensional"
        with pytest.raises(SchemaValidationError):
            validator.validate(bad)

    @pytest.mark.parametrize(
        "example",
        [
            "administrator-3d.json",
            "devops-3d.json",
            "observer-2d.json",
            "operations-2d.json",
            "regulated-data-handler-dc2d.json",
        ],
    )
    def test_shipped_examples_validate(self, validator: ProfileValidator, example: str) -> None:
        # The tightened schema must not break any profile we ship.
        assert validator.validate_file(EXAMPLES_DIR / example) is True


class TestSafetyBoundarySchema:
    """§12.5 — the schema must reject any profile that tries to grant
    Add/Change/Delete on Restricted data."""

    @pytest.mark.parametrize("op", ["A", "C", "D"])
    def test_restricted_acd_in_permissions_rejected(
        self, validator: ProfileValidator, op: str
    ) -> None:
        bad = _base_3d()
        bad["permissions"]["restricted"] = ["R", op]
        assert validator.is_valid(bad) is False

    @pytest.mark.parametrize("op", ["A", "C", "D"])
    @pytest.mark.parametrize("level", ["autonomous", "logged", "approval", "elevated_approval"])
    def test_restricted_acd_override_to_nonprohibited_rejected(
        self, validator: ProfileValidator, op: str, level: str
    ) -> None:
        bad = _base_3d()
        bad["autonomy_overrides"] = {f"restricted.{op}": level}
        assert validator.is_valid(bad) is False

    @pytest.mark.parametrize("op", ["A", "C", "D"])
    def test_restricted_acd_override_to_prohibited_allowed(
        self, validator: ProfileValidator, op: str
    ) -> None:
        ok = _base_3d()
        ok["autonomy_overrides"] = {f"restricted.{op}": "prohibited"}
        assert validator.is_valid(ok) is True

    def test_restricted_read_move_still_allowed(self, validator: ProfileValidator) -> None:
        ok = _base_3d()
        ok["permissions"]["restricted"] = ["R", "M"]
        ok["autonomy_overrides"] = {"restricted.R": "logged", "restricted.M": "elevated_approval"}
        assert validator.is_valid(ok) is True
