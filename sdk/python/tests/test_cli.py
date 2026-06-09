"""Tests for the rmacd CLI entry point."""

from __future__ import annotations

from pathlib import Path

import pytest

from rmacd import cli

EXAMPLES_DIR = Path(__file__).resolve().parents[3] / "schemas" / "examples"
ADMIN_3D = str(EXAMPLES_DIR / "administrator-3d.json")


def _run(monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> int:
    monkeypatch.setattr("sys.argv", ["rmacd", *argv])
    return cli.main()


class TestValidateCommand:
    def test_validate_valid_profile(self, monkeypatch, capsys) -> None:
        rc = _run(monkeypatch, ["validate", ADMIN_3D])
        assert rc == 0
        assert "VALID" in capsys.readouterr().out

    def test_validate_missing_file(self, monkeypatch, capsys) -> None:
        rc = _run(monkeypatch, ["validate", "/nonexistent/profile.json"])
        assert rc == 1
        assert "not found" in capsys.readouterr().err.lower()


class TestEvaluateCommand:
    def test_evaluate_allowed_returns_zero(self, monkeypatch, capsys) -> None:
        rc = _run(monkeypatch, ["evaluate", ADMIN_3D, "R", "-c", "public"])
        assert rc == 0
        assert "ALLOWED" in capsys.readouterr().out

    def test_evaluate_denied_returns_two(self, monkeypatch, capsys) -> None:
        # Change on Restricted is prohibited -> denied -> exit code 2.
        rc = _run(monkeypatch, ["evaluate", ADMIN_3D, "C", "-c", "restricted"])
        assert rc == 2
        assert "DENIED" in capsys.readouterr().out

    def test_evaluate_invalid_operation(self, monkeypatch, capsys) -> None:
        rc = _run(monkeypatch, ["evaluate", ADMIN_3D, "X", "-c", "public"])
        assert rc == 1
        assert "Invalid operation" in capsys.readouterr().err

    def test_evaluate_invalid_classification(self, monkeypatch, capsys) -> None:
        rc = _run(monkeypatch, ["evaluate", ADMIN_3D, "R", "-c", "topsecret"])
        assert rc == 1
        assert "Invalid classification" in capsys.readouterr().err

    def test_evaluate_json_output(self, monkeypatch, capsys) -> None:
        rc = _run(monkeypatch, ["evaluate", ADMIN_3D, "R", "-c", "public", "--json"])
        assert rc == 0
        assert '"allowed": true' in capsys.readouterr().out


class TestInfoAndMatrix:
    def test_info_runs(self, monkeypatch, capsys) -> None:
        assert _run(monkeypatch, ["info", ADMIN_3D]) == 0
        assert capsys.readouterr().out.strip() != ""

    def test_matrix_json_floors_restricted(self, monkeypatch, capsys) -> None:
        rc = _run(monkeypatch, ["matrix", ADMIN_3D, "--json"])
        assert rc == 0
        out = capsys.readouterr().out
        # Restricted C/D must show as prohibited in the effective matrix.
        assert "prohibited" in out

    def test_no_command_prints_help(self, monkeypatch, capsys) -> None:
        assert _run(monkeypatch, []) == 0
        assert "usage" in capsys.readouterr().out.lower()
