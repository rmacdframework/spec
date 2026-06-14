"""Phase 2 — pack loading, registration, serialization round-trip, resolvers."""

from __future__ import annotations

import json

import pytest

from rmacd import PolicyEnforcer, RMACDProhibitedError
from rmacd.approval import AutoApproveGateway
from rmacd.models import AutonomyLevel, Profile3D
from rmacd.models import DataClassification as DC
from rmacd.models import Operation as Op
from rmacd.packs import (
    GovernancePack,
    apply_pack,
    builtin_pack_names,
    clear_resolvers,
    exact_tool_names,
    load_pack,
    load_packs,
    register_resolver,
)
from rmacd.registry import ToolsRegistry

JIRA_PACK_DICT = {
    "pack": "jira",
    "version": "1.0.0",
    "default_operation": "C",
    "resolvers": [{"name": "jira_project_tier", "fail_closed_default": "confidential"}],
    "rules": [
        {
            "id": "jira-read",
            "when": {"tool": ["jira_search", "jira_get_issue"]},
            "classify": {
                "operation": "R",
                "tier": {"resolver": "jira_project_tier", "from": "project_key",
                         "default": "internal"},
                "target": "jira://{project_key}/{issue_key}",
            },
        },
        {
            "id": "jira-delete",
            "when": {"tool": "jira_delete_issue"},
            "classify": {
                "operation": "D",
                "tier": "confidential",
                "target": "jira://{project_key}/{issue_key}",
            },
        },
    ],
}


@pytest.fixture(autouse=True)
def _clean_resolvers() -> None:
    clear_resolvers()
    yield
    clear_resolvers()


# --- load_pack from each source ----------------------------------------------
def test_load_pack_from_dict() -> None:
    pack = load_pack(JIRA_PACK_DICT)
    assert isinstance(pack, GovernancePack)
    assert pack.pack == "jira"


def test_load_pack_passthrough_governancepack() -> None:
    pack = GovernancePack.from_dict(JIRA_PACK_DICT)
    assert load_pack(pack) is pack


def test_load_pack_from_json_file(tmp_path) -> None:
    p = tmp_path / "jira.json"
    p.write_text(json.dumps(JIRA_PACK_DICT), encoding="utf-8")
    pack = load_pack(p)
    assert pack.pack == "jira"


def test_load_pack_from_yaml_file(tmp_path) -> None:
    yaml = pytest.importorskip("yaml")
    p = tmp_path / "jira.yaml"
    p.write_text(yaml.safe_dump(JIRA_PACK_DICT), encoding="utf-8")
    pack = load_pack(p)
    assert pack.pack == "jira"
    assert len(pack.rules) == 2


def test_load_pack_unknown_name_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_pack("definitely-not-a-real-pack")


def test_load_pack_invalid_is_rejected() -> None:
    from rmacd.packs import PackValidationError

    with pytest.raises(PackValidationError):
        load_pack({"pack": "x", "version": "1.0.0"})  # no rules


def test_builtin_pack_names_returns_list() -> None:
    # Phase 2 ships no built-in packs yet; just assert the API works.
    assert isinstance(builtin_pack_names(), list)


# --- exact tool name extraction ----------------------------------------------
def test_exact_tool_names_skips_globs() -> None:
    pack = GovernancePack.from_dict(
        {
            "pack": "mix",
            "version": "1.0.0",
            "rules": [
                {"id": "a", "when": {"tool": "exact_one"}, "operation": "R"},
                {"id": "b", "when": {"tool": ["exact_two", "glob_*"]}, "operation": "R"},
                {"id": "c", "when": {"tool": "/regex_.*/"}, "operation": "R"},
            ],
        }
    )
    assert exact_tool_names(pack) == ["exact_one", "exact_two"]


# --- apply_pack registration --------------------------------------------------
def test_apply_pack_registers_exact_tools_with_classifier() -> None:
    reg = ToolsRegistry()
    apply_pack(reg, load_pack(JIRA_PACK_DICT))
    ids = {t.tool_id for t in reg.list_tools()}
    assert ids == {"jira_search", "jira_get_issue", "jira_delete_issue"}

    tool = reg.get_tool("jira_delete_issue")
    assert tool is not None
    rc = tool.resolve_call({"project_key": "ENG", "issue_key": "ENG-1"})
    assert rc.operation == Op.DELETE
    assert rc.tier == DC.CONFIDENTIAL
    assert "pack" in tool.tags and "jira" in tool.tags


def test_apply_pack_with_explicit_tool_names_for_glob_pack() -> None:
    pack = GovernancePack.from_dict(
        {
            "pack": "azure-mcp",
            "version": "1.0.0",
            "rules": [
                {"id": "del", "when": {"tool": "azmcp_*_delete"},
                 "classify": {"operation": "D", "tier": "internal"}},
            ],
        }
    )
    reg = ToolsRegistry()
    apply_pack(reg, pack, tool_names=["azmcp_storage_delete"])
    tool = reg.get_tool("azmcp_storage_delete")
    assert tool is not None
    assert tool.resolve_call({}).operation == Op.DELETE


def test_apply_pack_warns_on_glob_only_pack(caplog) -> None:
    import logging

    pack = GovernancePack.from_dict(
        {
            "pack": "globby",
            "version": "1.0.0",
            "rules": [
                {"id": "del", "when": {"tool": "azmcp_*_delete"},
                 "classify": {"operation": "D", "tier": "internal"}},
            ],
        }
    )
    reg = ToolsRegistry()
    with caplog.at_level(logging.WARNING):
        registered = apply_pack(reg, pack)  # no tool_names
    assert registered == []
    assert any("register nothing without" in r.message for r in caplog.records)


def test_resolver_used_through_registry() -> None:
    register_resolver("jira_project_tier", lambda v, ctx: "internal")
    reg = load_packs([JIRA_PACK_DICT])
    tool = reg.get_tool("jira_search")
    assert tool is not None
    rc = tool.resolve_call({"project_key": "ENG"})
    assert rc.tier == DC.INTERNAL


# --- serialization round-trip (the closed gap) -------------------------------
def test_declarative_classifier_survives_registry_export_import(tmp_path) -> None:
    reg = load_packs([JIRA_PACK_DICT])
    out = tmp_path / "registry.json"
    reg.export_to_json(out)

    # The exported JSON carries the declarative classifier spec.
    raw = json.loads(out.read_text())
    delete_entry = next(t for t in raw["tools"] if t["tool_id"] == "jira_delete_issue")
    assert delete_entry["classifier"]["kind"] == "declarative"

    # Reimport into a fresh registry; dynamic classification must still work.
    reg2 = ToolsRegistry()
    assert reg2.import_from_json(out) is True
    tool = reg2.get_tool("jira_delete_issue")
    assert tool is not None
    rc = tool.resolve_call({"project_key": "ENG", "issue_key": "ENG-2"})
    assert rc.operation == Op.DELETE
    assert rc.tier == DC.CONFIDENTIAL
    assert rc.target == "jira://ENG/ENG-2"


# --- end-to-end enforcement through a pack-built registry --------------------
def test_enforce_tool_call_through_pack_registry() -> None:
    profile = Profile3D(
        profile_id="rmacd-3d-packtest",
        profile_name="Pack Test",
        model="three-dimensional",
        version="1.0",
        permissions={
            DC.PUBLIC: [Op.READ, Op.MOVE, Op.ADD, Op.CHANGE, Op.DELETE],
            DC.INTERNAL: [Op.READ, Op.MOVE, Op.ADD, Op.CHANGE, Op.DELETE],
            DC.CONFIDENTIAL: [Op.READ, Op.MOVE, Op.ADD, Op.CHANGE, Op.DELETE],
            DC.RESTRICTED: [Op.READ],
        },
    )
    registry = load_packs([JIRA_PACK_DICT])
    enforcer = PolicyEnforcer(
        profile=profile,
        agent_id="agent-1",
        registry=registry,
        approval_gateway=AutoApproveGateway(),
    )

    # Read on (resolver-less -> confidential) is permitted.
    decision = enforcer.evaluate_tool_call("jira_search", {"project_key": "ENG"})
    assert decision.operation == Op.READ
    assert decision.data_classification == DC.CONFIDENTIAL

    # Delete classified confidential -> allowed by this profile.
    decision = enforcer.evaluate_tool_call(
        "jira_delete_issue", {"project_key": "ENG", "issue_key": "ENG-1"}
    )
    assert decision.operation == Op.DELETE
    assert decision.data_classification == DC.CONFIDENTIAL


def test_restricted_delete_blocked_by_floor_through_pack() -> None:
    # A pack that classifies a delete as restricted must hit the §12.5 floor.
    pack = {
        "pack": "danger",
        "version": "1.0.0",
        "rules": [
            {"id": "wipe", "when": {"tool": "wipe_secrets"},
             "classify": {"operation": "D", "tier": "restricted"}}
        ],
    }
    profile = Profile3D(
        profile_id="rmacd-3d-floor",
        profile_name="Floor",
        model="three-dimensional",
        version="1.0",
        permissions={
            DC.PUBLIC: [Op.READ],
            DC.INTERNAL: [Op.READ],
            DC.CONFIDENTIAL: [Op.READ],
            DC.RESTRICTED: [Op.READ],
        },
    )
    enforcer = PolicyEnforcer(
        profile=profile, agent_id="a", registry=load_packs([pack]),
        approval_gateway=AutoApproveGateway(),
    )
    with pytest.raises(RMACDProhibitedError):
        enforcer.enforce_tool_call("wipe_secrets", {})


def test_load_packs_returns_registry_with_all_tools() -> None:
    reg = load_packs([JIRA_PACK_DICT])
    assert isinstance(reg, ToolsRegistry)
    assert len(reg.list_tools()) == 3
    assert AutonomyLevel  # imported symbol used to keep linters quiet
