"""Tests for build_system_prompt (SDK 0.6.0).

These verify that the prompt fragment includes the right structural
pieces for each profile model (3D / 2D / DC2D). They do not assert on
exact wording, so future copy edits won't break the suite — only the
contract that the fragment carries each profile's permitted operations,
autonomy stance, and hard prohibitions.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rmacd import (
    Profile2D,
    Profile3D,
    ProfileDC2D,
    ProfileLoader,
    build_system_prompt,
)

FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "schemas" / "examples"


@pytest.fixture
def admin_3d() -> Profile3D:
    return ProfileLoader().load_file(FIXTURE_DIR / "administrator-3d.json")  # type: ignore[return-value]


@pytest.fixture
def observer_3d() -> Profile3D:
    return ProfileLoader().load_file(FIXTURE_DIR / "observer-3d.json")  # type: ignore[return-value]


@pytest.fixture
def observer_2d() -> Profile2D:
    return ProfileLoader().load_file(FIXTURE_DIR / "observer-2d.json")  # type: ignore[return-value]


@pytest.fixture
def dc2d_profile() -> ProfileDC2D:
    return ProfileLoader().load_file(FIXTURE_DIR / "regulated-data-handler-dc2d.json")  # type: ignore[return-value]


def test_prompt_contains_profile_id_for_3d(admin_3d):
    out = build_system_prompt(admin_3d)
    assert admin_3d.profile_id in out


def test_prompt_lists_all_four_tiers_for_3d(admin_3d):
    out = build_system_prompt(admin_3d)
    for tier in ("Public", "Internal", "Confidential", "Restricted"):
        assert f"**{tier}**" in out, f"missing tier {tier}"


def test_prompt_includes_all_five_operations_in_3d_matrix(admin_3d):
    out = build_system_prompt(admin_3d)
    for op_name in ("Read", "Move", "Add", "Change", "Delete"):
        assert f"**{op_name}**" in out, f"missing op {op_name}"


def test_prompt_flags_matrix_prohibitions(admin_3d):
    # Change/Delete on Restricted are always prohibited; the prompt must say so.
    out = build_system_prompt(admin_3d)
    assert "Hard prohibitions" in out
    assert "Change on Restricted" in out
    assert "Delete on Restricted" in out


def test_prompt_marks_ungranted_cells_in_3d(observer_3d):
    # Observer profile is R-only; the cells for M/A/C/D on Public should
    # be marked "not granted" in the matrix.
    out = build_system_prompt(observer_3d)
    assert "not granted" in out


def test_prompt_honours_autonomy_overrides_in_3d(admin_3d):
    # Administrator profile sets autonomy_overrides like "restricted.M":
    # "elevated_approval". The rendered table should reflect that.
    out = build_system_prompt(admin_3d)
    assert "elevated approval" in out.lower()


def test_prompt_for_2d_profile_lists_operations(observer_2d):
    out = build_system_prompt(observer_2d)
    assert observer_2d.profile_id in out
    # The 2D shape has a single permissions list rather than a per-tier map.
    # Heading shouldn't mention tiers.
    assert "Permitted operations:" in out


def test_prompt_for_dc2d_describes_tier_access(dc2d_profile):
    out = build_system_prompt(dc2d_profile)
    assert dc2d_profile.profile_id in out
    # DC2D specifies a per-tier table; restricted is allowed=false in the fixture.
    assert "DC2D" in out
    # "Access stance per data tier" is the section title we render.
    assert "Access stance per data tier" in out


def test_prompt_for_dc2d_mentions_redaction_when_configured(dc2d_profile):
    # The fixture has redaction enabled for confidential+restricted.
    out = build_system_prompt(dc2d_profile)
    assert "Redaction" in out


def test_prompt_for_dc2d_mentions_egress_when_configured(dc2d_profile):
    # The fixture sets block_external_models=true and an allow-list.
    out = build_system_prompt(dc2d_profile)
    assert "Egress allow-list" in out
    assert "External model block" in out


def test_prompt_custom_title_overrides_profile_name(admin_3d):
    out = build_system_prompt(admin_3d, title="CustomTitle Agent")
    assert "# CustomTitle Agent" in out
    # The profile name should NOT appear as an H1 when a title is given.
    assert admin_3d.profile_name not in out.splitlines()[0]


def test_prompt_includes_behaviour_section(admin_3d):
    out = build_system_prompt(admin_3d)
    assert "## Behaviour" in out
    assert "Respect denials" in out


def test_prompt_ends_with_newline(admin_3d):
    out = build_system_prompt(admin_3d)
    assert out.endswith("\n")
