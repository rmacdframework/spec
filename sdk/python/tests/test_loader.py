"""Tests for ProfileLoader error paths and dispatch."""

from __future__ import annotations

from pathlib import Path

import pytest

from rmacd.loader import ProfileLoader, ProfileLoadError
from rmacd.models import Profile2D, Profile3D, ProfileDC2D

EXAMPLES_DIR = Path(__file__).resolve().parents[3] / "schemas" / "examples"


@pytest.fixture
def loader() -> ProfileLoader:
    return ProfileLoader()


class TestLoaderDispatch:
    @pytest.mark.parametrize(
        "example,cls",
        [
            ("administrator-3d.json", Profile3D),
            ("observer-2d.json", Profile2D),
            ("regulated-data-handler-dc2d.json", ProfileDC2D),
        ],
    )
    def test_loads_each_model_type(self, loader, example, cls) -> None:
        profile = loader.load_file(EXAMPLES_DIR / example)
        assert isinstance(profile, cls)


class TestLoaderErrors:
    def test_missing_file(self, loader) -> None:
        with pytest.raises(ProfileLoadError, match="not found"):
            loader.load_file("/nonexistent/x.json")

    def test_non_json_suffix(self, loader, tmp_path) -> None:
        p = tmp_path / "profile.txt"
        p.write_text("{}")
        with pytest.raises(ProfileLoadError, match="must be a JSON file"):
            loader.load_file(p)

    def test_invalid_json(self, loader, tmp_path) -> None:
        p = tmp_path / "bad.json"
        p.write_text("{not valid json")
        with pytest.raises(ProfileLoadError, match="Invalid JSON"):
            loader.load_file(p)

    def test_missing_model_field(self, loader) -> None:
        with pytest.raises(ProfileLoadError, match="missing 'model'"):
            loader.load_dict({"profile_id": "rmacd-3d-x"})

    def test_unknown_model_type(self, loader) -> None:
        with pytest.raises(ProfileLoadError, match="Unknown model type"):
            loader.load_dict({"model": "five-dimensional"})

    def test_pydantic_validation_error_wrapped(self, loader) -> None:
        # A 3D profile missing required permissions should raise ProfileLoadError,
        # not a raw pydantic ValidationError.
        with pytest.raises(ProfileLoadError):
            loader.load_dict(
                {
                    "model": "three-dimensional",
                    "profile_id": "rmacd-3d-x",
                    "profile_name": "X",
                    "version": "1.0",
                }
            )
