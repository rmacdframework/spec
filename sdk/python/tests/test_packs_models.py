"""Phase 0 — governance pack data model, schema validation, canonical hashing."""

from __future__ import annotations

import copy

import pytest

from rmacd.packs import (
    GovernancePack,
    PackValidationError,
    Rule,
    TierSpec,
    get_schema,
    is_valid_pack,
    validate_pack_dict,
)

# A representative pack exercising both rule styles, a tier overlay, a resolver,
# a passthrough capability ceiling, and provenance.
SAMPLE_PACK: dict = {
    "pack": "sample",
    "version": "1.0.0",
    "description": "Sample pack for tests",
    "default_operation": "C",
    "provenance": {"authored_by": "tests", "llm_assisted": False},
    "resolvers": [
        {
            "name": "resource_tier",
            "description": "resolve a resource id to its tier",
            "fail_closed_default": "confidential",
        }
    ],
    "rules": [
        {
            "id": "literal-delete",
            "when": {"tool": "thing_delete"},
            "classify": {
                "operation": "D",
                "tier": {"resolver": "resource_tier", "from": "id", "default": "confidential"},
                "target": "thing://{id}",
            },
            "confidence": "high",
        },
        {
            "id": "verb-table",
            "when": {"tool": "shellish"},
            "parse": {"arg": "command", "strip_wrappers": ["sudo"]},
            "verb_table": {"get": "R", "set": "C", "rm": "D"},
            "default": "C",
            "tier": {
                "pattern_map": [
                    {"arg_regex": {"arg": "command", "pattern": "prod"}, "tier": "confidential"}
                ],
                "default": "internal",
            },
            "target": "sh://{command}",
            "capability": ["R", "M", "A", "C", "D"],
        },
    ],
}


def test_get_schema_is_pack_schema() -> None:
    schema = get_schema()
    assert schema["$id"].endswith("/pack.json")
    assert "rules" in schema["properties"]


def test_sample_pack_is_schema_valid() -> None:
    assert validate_pack_dict(SAMPLE_PACK) is True
    assert is_valid_pack(SAMPLE_PACK) is True


def test_from_dict_builds_model() -> None:
    pack = GovernancePack.from_dict(SAMPLE_PACK)
    assert pack.pack == "sample"
    assert pack.version == "1.0.0"
    assert pack.default_operation == "C"
    assert len(pack.rules) == 2
    assert pack.resolvers[0].name == "resource_tier"
    # `from` alias round-trips to the python field name
    assert pack.rules[0].classify is not None
    tier = pack.rules[0].classify.tier
    assert isinstance(tier, TierSpec)
    assert tier.from_arg == "id"


def test_to_dict_uses_from_alias() -> None:
    pack = GovernancePack.from_dict(SAMPLE_PACK)
    out = pack.to_dict()
    classify = out["rules"][0]["classify"]
    assert classify["tier"]["from"] == "id"  # alias, not from_arg
    assert "from_arg" not in classify["tier"]


def test_round_trip_dict_json() -> None:
    pack = GovernancePack.from_dict(SAMPLE_PACK)
    again = GovernancePack.from_json(pack.to_json())
    assert again.to_dict() == pack.to_dict()


def test_canonical_json_is_key_order_independent() -> None:
    pack_a = GovernancePack.from_dict(SAMPLE_PACK)
    # Shuffle top-level key order; canonical form must be identical.
    shuffled = dict(reversed(list(SAMPLE_PACK.items())))
    pack_b = GovernancePack.from_dict(shuffled)
    assert pack_a.canonical_json() == pack_b.canonical_json()


def test_content_hash_is_deterministic_and_prefixed() -> None:
    pack = GovernancePack.from_dict(SAMPLE_PACK)
    h1 = pack.compute_content_hash()
    h2 = pack.compute_content_hash()
    assert h1 == h2
    assert h1.startswith("sha256:")
    assert len(h1) == len("sha256:") + 64


def test_content_hash_excludes_hash_and_signature() -> None:
    base = GovernancePack.from_dict(SAMPLE_PACK)
    expected = base.compute_content_hash()
    # Adding content_hash/signature must not change the computed hash.
    with_meta = copy.deepcopy(SAMPLE_PACK)
    with_meta["content_hash"] = "sha256:" + "0" * 64
    with_meta["signature"] = "deadbeef"
    other = GovernancePack.from_dict(with_meta)
    assert other.compute_content_hash() == expected


def test_freeze_and_verify_hash() -> None:
    pack = GovernancePack.from_dict(SAMPLE_PACK)
    assert pack.verify_hash() is False  # no hash yet
    frozen = pack.freeze()
    assert frozen.content_hash is not None
    assert frozen.verify_hash() is True


def test_freeze_then_mutation_breaks_verification() -> None:
    frozen = GovernancePack.from_dict(SAMPLE_PACK).freeze()
    tampered = frozen.model_copy(update={"description": "changed after freeze"})
    assert tampered.verify_hash() is False


def test_missing_required_field_rejected() -> None:
    bad = {"pack": "x", "version": "1.0.0"}  # no rules
    assert is_valid_pack(bad) is False
    with pytest.raises(PackValidationError):
        validate_pack_dict(bad)


def test_unknown_top_level_key_rejected_by_schema() -> None:
    bad = copy.deepcopy(SAMPLE_PACK)
    bad["surprise"] = True
    assert is_valid_pack(bad) is False


def test_bad_operation_value_rejected() -> None:
    bad = copy.deepcopy(SAMPLE_PACK)
    bad["rules"][0]["classify"]["operation"] = "X"  # not R/M/A/C/D
    assert is_valid_pack(bad) is False


def test_bare_string_tier_accepted() -> None:
    data = {
        "pack": "tiers",
        "version": "1.0.0",
        "rules": [
            {"id": "r", "when": {"tool": "t"}, "operation": "R", "tier": "restricted"}
        ],
    }
    assert validate_pack_dict(data) is True
    pack = GovernancePack.from_dict(data)
    assert pack.rules[0].tier == "restricted"


def test_version_pattern_enforced_by_schema() -> None:
    bad = copy.deepcopy(SAMPLE_PACK)
    bad["version"] = "v1"  # not semver
    assert is_valid_pack(bad) is False


def test_rule_model_defaults() -> None:
    rule = Rule(id="r", when={"tool": "t"})  # type: ignore[arg-type]
    assert rule.confidence == "high"
    assert rule.parse is None
    assert rule.verb_table is None
