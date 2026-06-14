"""Phase 4 — AI-compile authoring (compile_pack, review_items, CLI)."""

from __future__ import annotations

import argparse
import json

from rmacd.packs import (
    GovernancePack,
    classify_call,
    compile_pack,
    is_valid_pack,
    review_items,
)
from rmacd.registry.llm import ToolClassification

# A small MCP tools/list-style source.
TOOLS = [
    {"name": "list_widgets", "description": "List all widgets", "inputSchema": {}},
    {"name": "delete_widget", "description": "Permanently delete a widget", "inputSchema": {}},
    {
        "name": "do_thing",
        "description": "Performs the thing",  # vague -> low confidence
        "inputSchema": {},
    },
    {
        "name": "rotate_api_key",
        "description": "Rotate the API key",
        "inputSchema": {"properties": {"api_key": {"type": "string"}}},
    },
]


def test_compile_pack_builds_valid_pack() -> None:
    pack = compile_pack(TOOLS, pack_name="widgets", version="0.1.0")
    assert isinstance(pack, GovernancePack)
    assert pack.pack == "widgets"
    assert is_valid_pack(pack.to_dict()) is True
    assert len(pack.rules) == 4
    # provenance records source hash + ai-drafted status
    assert pack.provenance is not None
    assert (pack.provenance.source_hash or "").startswith("sha256:")
    assert pack.provenance.review_status == "ai-drafted"
    assert pack.provenance.llm_assisted is False


def test_compiled_rules_classify_by_keyword() -> None:
    pack = compile_pack(TOOLS, pack_name="widgets")
    assert classify_call(pack, "list_widgets", {}).operation == "R"
    assert classify_call(pack, "delete_widget", {}).operation == "D"


def test_secret_schema_raises_tier() -> None:
    pack = compile_pack(TOOLS, pack_name="widgets")
    # rotate_api_key has an api_key field -> restricted by the keyword heuristic
    assert classify_call(pack, "rotate_api_key", {}).tier == "restricted"


def test_review_items_flags_lowconf_and_delete() -> None:
    pack = compile_pack(TOOLS, pack_name="widgets")
    flagged = {it["id"]: it["reason"] for it in review_items(pack)}
    assert "delete_widget" in flagged  # delete-capable
    assert "do_thing" in flagged  # low-confidence (vague description)
    assert "list_widgets" not in flagged


def test_capability_ceiling_recorded() -> None:
    pack = compile_pack(TOOLS, pack_name="widgets")
    delete_rule = next(r for r in pack.rules if r.id == "delete_widget")
    assert delete_rule.capability == ["R", "M", "A", "C", "D"]


class _FakeLLM:
    """Duck-typed stand-in for LLMToolClassifier (no network)."""

    model = "fake-model"

    def classify(self, *, name, description="", input_schema=None, operations=None):  # noqa: ANN001
        # Force everything to a confident Delete/restricted to prove the LLM path runs.
        return ToolClassification(
            rmacd_level="D",
            data_access="restricted",
            required_hitl="elevated_approval",
            rationale="fake",
            confidence=0.95,
        )


def test_compile_with_llm_classifier_always() -> None:
    pack = compile_pack(
        [{"name": "do_thing", "description": "vague", "inputSchema": {}}],
        pack_name="x",
        llm_classifier=_FakeLLM(),
        llm_mode="always",
    )
    assert pack.provenance is not None and pack.provenance.llm_assisted is True
    rule = pack.rules[0]
    assert rule.classify is not None and rule.classify.operation == "D"
    assert rule.classify.tier == "restricted"
    assert rule.confidence == "high"  # llm confidence 0.95 -> high


# --- CLI -----------------------------------------------------------------------
def test_cli_classify_and_review(tmp_path, capsys) -> None:
    from rmacd.cli import cmd_classify, cmd_pack_review

    src = tmp_path / "tools.json"
    src.write_text(json.dumps({"tools": TOOLS}), encoding="utf-8")
    out = tmp_path / "widgets.json"

    rc = cmd_classify(
        argparse.Namespace(
            source=str(src), name="widgets", output=str(out),
            pack_version="0.1.0", llm=False, llm_mode="fallback",
        )
    )
    assert rc == 0
    assert out.exists()
    assert is_valid_pack(json.loads(out.read_text())) is True

    rc = cmd_pack_review(argparse.Namespace(pack=str(out)))
    assert rc == 0
    output = capsys.readouterr().out
    assert "need review" in output
    assert "delete_widget" in output
