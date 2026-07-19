"""Tests for the RMACD MCP server (rmacd.mcp_server).

The tool functions are plain callables (FastMCP wraps them at server build
time), so everything except server construction is exercised directly — no
transport or network involved.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("mcp")

from rmacd import cli, mcp_server  # noqa: E402
from rmacd.loader import ProfileLoadError  # noqa: E402
from rmacd.packs import builtin_pack_names  # noqa: E402

EXAMPLES_DIR = Path(__file__).resolve().parents[3] / "schemas" / "examples"
ADMIN_3D = str(EXAMPLES_DIR / "administrator-3d.json")
OBSERVER_2D = str(EXAMPLES_DIR / "observer-2d.json")

EXPECTED_TOOLS = {
    "rmacd_evaluate",
    "rmacd_validate_profile",
    "rmacd_matrix",
    "rmacd_list_packs",
    "rmacd_pack_info",
    "rmacd_classify_bash",
}


@pytest.fixture
def tools() -> dict[str, Callable[..., Any]]:
    return mcp_server.build_tools()


@pytest.fixture
def pinned_tools() -> dict[str, Callable[..., Any]]:
    return mcp_server.build_tools(pinned_profile=ADMIN_3D)


class TestEvaluate:
    def test_section_12_5_denial(self, tools) -> None:
        """Delete on Restricted is prohibited even for the administrator profile."""
        result = tools["rmacd_evaluate"](
            operation="D",
            target="prod-db",
            classification="restricted",
            profile_path=ADMIN_3D,
        )
        assert result["allowed"] is False
        assert result["autonomy_level"] == "prohibited"
        assert result["profile_id"] == "rmacd-3d-administrator-v1"
        assert result["target"] == "prod-db"

    def test_allowed_read(self, tools) -> None:
        result = tools["rmacd_evaluate"](
            operation="R",
            target="dashboard",
            classification="internal",
            profile_path=ADMIN_3D,
        )
        assert result["allowed"] is True
        assert result["operation"] == "R"

    def test_environment_accepted(self, tools) -> None:
        result = tools["rmacd_evaluate"](
            operation="R",
            target="x",
            classification="public",
            environment="production",
            profile_path=ADMIN_3D,
        )
        assert result["allowed"] is True

    def test_invalid_operation(self, tools) -> None:
        with pytest.raises(ValueError, match="Invalid operation"):
            tools["rmacd_evaluate"](operation="X", target="t", profile_path=ADMIN_3D)

    def test_invalid_classification(self, tools) -> None:
        with pytest.raises(ValueError, match="Invalid classification"):
            tools["rmacd_evaluate"](
                operation="R", target="t", classification="secret", profile_path=ADMIN_3D
            )

    def test_invalid_environment(self, tools) -> None:
        with pytest.raises(ValueError, match="Invalid environment"):
            tools["rmacd_evaluate"](
                operation="R",
                target="t",
                classification="public",
                environment="qa",
                profile_path=ADMIN_3D,
            )

    def test_profile_path_required_when_not_pinned(self, tools) -> None:
        with pytest.raises(ValueError, match="profile_path is required"):
            tools["rmacd_evaluate"](operation="R", target="t", classification="public")

    def test_missing_profile_file(self, tools) -> None:
        with pytest.raises(ProfileLoadError):
            tools["rmacd_evaluate"](
                operation="R", target="t", profile_path="/nonexistent/p.json"
            )


class TestValidateProfile:
    def test_valid_file(self, tools) -> None:
        result = tools["rmacd_validate_profile"](profile_path=ADMIN_3D)
        assert result == {"valid": True, "errors": []}

    def test_invalid_json_string(self, tools) -> None:
        bad = '{"model": "three-dimensional", "profile_id": "bad"}'
        result = tools["rmacd_validate_profile"](profile_json=bad)
        assert result["valid"] is False
        assert result["errors"]

    def test_malformed_json_string(self, tools) -> None:
        result = tools["rmacd_validate_profile"](profile_json="{not json")
        assert result["valid"] is False
        assert "Invalid JSON" in result["errors"][0]

    def test_missing_file(self, tools) -> None:
        result = tools["rmacd_validate_profile"](profile_path="/nonexistent/p.json")
        assert result["valid"] is False
        assert result["errors"]

    def test_neither_arg(self, tools) -> None:
        with pytest.raises(ValueError, match="profile_path or profile_json"):
            tools["rmacd_validate_profile"]()

    def test_both_args(self, tools) -> None:
        with pytest.raises(ValueError, match="not both"):
            tools["rmacd_validate_profile"](profile_path=ADMIN_3D, profile_json="{}")


class TestMatrix:
    def test_3d_matrix_floor(self, tools) -> None:
        result = tools["rmacd_matrix"](profile_path=ADMIN_3D)
        assert result["model"] == "three-dimensional"
        matrix = result["matrix"]
        # §12.5 floor is visible in the effective matrix.
        assert matrix["restricted"]["C"] == "prohibited"
        assert matrix["restricted"]["D"] == "prohibited"

    def test_2d_matrix(self, tools) -> None:
        result = tools["rmacd_matrix"](profile_path=OBSERVER_2D)
        assert result["model"] == "two-dimensional"
        assert "R" in result["matrix"]


class TestPacks:
    def test_list_packs_matches_builtins(self, tools) -> None:
        result = tools["rmacd_list_packs"]()
        builtin = builtin_pack_names()
        assert result["count"] == len(builtin) > 0
        names = [p["name"] for p in result["packs"]]
        assert len(names) == len(builtin)
        for entry in result["packs"]:
            assert entry["version"]
            assert entry["rules"] > 0

    def test_pack_info_builtin(self, tools) -> None:
        result = tools["rmacd_pack_info"](name_or_path="shell")
        assert result["name"] == "shell"
        assert result["rule_count"] > 0
        assert result["signature_status"]["signed"] is False

    def test_pack_info_unknown(self, tools) -> None:
        with pytest.raises(FileNotFoundError):
            tools["rmacd_pack_info"](name_or_path="no-such-pack")


class TestClassifyBash:
    def test_delete_command(self, tools) -> None:
        result = tools["rmacd_classify_bash"](command="rm -rf /tmp/scratch")
        assert result["operation"] == "D"
        assert "advisory" in result

    def test_read_command(self, tools) -> None:
        result = tools["rmacd_classify_bash"](command="ls -la /etc")
        assert result["operation"] == "R"


class TestPinnedProfile:
    def test_evaluate_uses_pinned(self, pinned_tools) -> None:
        result = pinned_tools["rmacd_evaluate"](
            operation="D", target="t", classification="restricted"
        )
        assert result["allowed"] is False
        assert result["profile_id"] == "rmacd-3d-administrator-v1"

    def test_evaluate_rejects_profile_path(self, pinned_tools) -> None:
        with pytest.raises(ValueError, match="pinned"):
            pinned_tools["rmacd_evaluate"](
                operation="R",
                target="t",
                classification="public",
                profile_path=OBSERVER_2D,
            )

    def test_matrix_rejects_profile_path(self, pinned_tools) -> None:
        with pytest.raises(ValueError, match="pinned"):
            pinned_tools["rmacd_matrix"](profile_path=OBSERVER_2D)

    def test_matrix_uses_pinned(self, pinned_tools) -> None:
        result = pinned_tools["rmacd_matrix"]()
        assert result["profile_id"] == "rmacd-3d-administrator-v1"

    def test_validate_defaults_to_pinned(self, pinned_tools) -> None:
        result = pinned_tools["rmacd_validate_profile"]()
        assert result == {"valid": True, "errors": []}

    def test_validate_still_accepts_other_files(self, pinned_tools) -> None:
        # Validation is a lint, not a policy decision — pinning does not gate it.
        result = pinned_tools["rmacd_validate_profile"](profile_path=OBSERVER_2D)
        assert result["valid"] is True

    def test_bad_pinned_profile_fails_at_build(self) -> None:
        with pytest.raises(ProfileLoadError):
            mcp_server.build_tools(pinned_profile="/nonexistent/p.json")


class TestServer:
    def test_create_server_registers_six_tools(self) -> None:
        server = mcp_server.create_server()
        listed = asyncio.run(server.list_tools())
        assert {t.name for t in listed} == EXPECTED_TOOLS

    def test_server_name(self) -> None:
        server = mcp_server.create_server()
        assert server.name == mcp_server.SERVER_NAME == "rmacd"


class TestMissingExtra:
    """Simulate the [mcp] extra being absent (base install unaffected)."""

    @pytest.fixture
    def no_mcp(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for mod in list(sys.modules):
            if mod == "mcp" or mod.startswith("mcp."):
                monkeypatch.setitem(sys.modules, mod, None)

    def test_build_tools_works_without_mcp(self, no_mcp) -> None:
        tools = mcp_server.build_tools()
        result = tools["rmacd_classify_bash"](command="cat /etc/hosts")
        assert result["operation"] == "R"

    def test_create_server_raises_helpful_error(self, no_mcp) -> None:
        with pytest.raises(ImportError, match=r"rmacd-framework\[mcp\]"):
            mcp_server.create_server()

    def test_cli_prints_pip_hint(self, no_mcp, monkeypatch, capsys) -> None:
        monkeypatch.setattr("sys.argv", ["rmacd", "mcp-serve"])
        rc = cli.main()
        assert rc == 1
        err = capsys.readouterr().err
        assert "pip install 'rmacd-framework[mcp]'" in err


class TestCLI:
    def test_mcp_serve_bad_profile(self, monkeypatch, capsys) -> None:
        monkeypatch.setattr(
            "sys.argv", ["rmacd", "mcp-serve", "--profile", "/nonexistent/p.json"]
        )
        rc = cli.main()
        assert rc == 1
        assert "ERROR" in capsys.readouterr().err
