"""Phase 5 — signing & verification, drift detection, ReDoS guard, CLI."""

from __future__ import annotations

import argparse
import json

import pytest

from rmacd.packs import (
    GovernancePack,
    compile_pack,
    find_redos_risks,
    generate_keypair,
    is_signed,
    pack_drift,
    sign_pack,
    verify_pack,
)

PACK_DICT = {
    "pack": "demo",
    "version": "1.0.0",
    "rules": [
        {"id": "r", "when": {"tool": "t"}, "operation": "R", "tier": "internal"}
    ],
}


# --- signing / verification ---------------------------------------------------
def test_sign_then_verify_roundtrip() -> None:
    priv, pub = generate_keypair()
    pack = GovernancePack.from_dict(PACK_DICT)
    signed = sign_pack(pack, priv)
    assert is_signed(signed)
    assert signed.content_hash is not None
    assert signed.signature is not None and signed.signature.startswith("ed25519:")
    assert verify_pack(signed, pub) is True


def test_tampered_pack_fails_verification() -> None:
    priv, pub = generate_keypair()
    signed = sign_pack(GovernancePack.from_dict(PACK_DICT), priv)
    tampered = signed.model_copy(update={"description": "evil edit after signing"})
    assert tampered.verify_hash() is False
    assert verify_pack(tampered, pub) is False


def test_wrong_key_fails_verification() -> None:
    priv, _ = generate_keypair()
    _, other_pub = generate_keypair()
    signed = sign_pack(GovernancePack.from_dict(PACK_DICT), priv)
    assert verify_pack(signed, other_pub) is False


def test_unsigned_pack_does_not_verify() -> None:
    _, pub = generate_keypair()
    assert verify_pack(GovernancePack.from_dict(PACK_DICT), pub) is False


def test_signature_excluded_from_content_hash() -> None:
    priv, _ = generate_keypair()
    pack = GovernancePack.from_dict(PACK_DICT)
    before = pack.compute_content_hash()
    signed = sign_pack(pack, priv)
    # The signature/hash fields must not feed back into the content hash.
    assert signed.compute_content_hash() == before


# --- drift detection ----------------------------------------------------------
TOOLS_V1 = [
    {"name": "list_things", "description": "list", "inputSchema": {}},
    {"name": "delete_thing", "description": "delete", "inputSchema": {}},
]


def test_no_drift_when_source_unchanged() -> None:
    pack = compile_pack(TOOLS_V1, pack_name="things")
    drift = pack_drift(pack, TOOLS_V1)
    assert drift["drifted"] is False
    assert drift["added"] == [] and drift["removed"] == []


def test_drift_detects_added_and_removed_tools() -> None:
    pack = compile_pack(TOOLS_V1, pack_name="things")
    tools_v2 = [
        {"name": "list_things", "description": "list", "inputSchema": {}},
        {"name": "purge_thing", "description": "purge", "inputSchema": {}},  # new
    ]
    drift = pack_drift(pack, tools_v2)
    assert drift["drifted"] is True
    assert drift["added"] == ["purge_thing"]
    assert drift["removed"] == ["delete_thing"]


def test_drift_detects_changed_definition_same_names() -> None:
    pack = compile_pack(TOOLS_V1, pack_name="things")
    tools_changed = [
        {"name": "list_things", "description": "list", "inputSchema": {}},
        {"name": "delete_thing", "description": "DELETE EVERYTHING NOW", "inputSchema": {}},
    ]
    drift = pack_drift(pack, tools_changed)
    assert drift["drifted"] is True
    assert drift["added"] == [] and drift["removed"] == []


# --- ReDoS guard --------------------------------------------------------------
def test_find_redos_risks_flags_nested_quantifier() -> None:
    bad = {
        "pack": "redos",
        "version": "1.0.0",
        "rules": [
            {
                "id": "r",
                "when": {"tool": "t", "arg_regex": {"arg": "x", "pattern": "(a+)+$"}},
                "operation": "R",
            }
        ],
    }
    risks = find_redos_risks(bad)
    assert any("nested quantifier" in r for r in risks)


def test_find_redos_risks_clean_pack() -> None:
    pack = compile_pack(TOOLS_V1, pack_name="things")
    assert find_redos_risks(pack.to_dict()) == []


def test_builtin_packs_have_no_redos_risks() -> None:
    from rmacd.packs import builtin_pack_names, load_pack

    for name in builtin_pack_names():
        assert find_redos_risks(load_pack(name).to_dict()) == [], name


# --- CLI ----------------------------------------------------------------------
def test_cli_sign_verify_diff(tmp_path, capsys) -> None:
    from rmacd.cli import cmd_pack_diff, cmd_pack_sign, cmd_pack_verify

    priv, pub = generate_keypair()
    priv_f = tmp_path / "key.pem"
    priv_f.write_text(priv, encoding="utf-8")
    pub_f = tmp_path / "key.pub"
    pub_f.write_text(pub, encoding="utf-8")

    pack_f = tmp_path / "things.json"
    pack_f.write_text(compile_pack(TOOLS_V1, pack_name="things").to_json(), encoding="utf-8")

    assert cmd_pack_sign(argparse.Namespace(pack=str(pack_f), key=str(priv_f), output=None)) == 0
    assert cmd_pack_verify(argparse.Namespace(pack=str(pack_f), key=str(pub_f))) == 0

    # drift: same source -> in sync (rc 0); changed source -> drift (rc 1)
    src = tmp_path / "tools.json"
    src.write_text(json.dumps({"tools": TOOLS_V1}), encoding="utf-8")
    assert cmd_pack_diff(argparse.Namespace(pack=str(pack_f), source=str(src))) == 0

    src.write_text(json.dumps({"tools": TOOLS_V1[:1]}), encoding="utf-8")
    assert cmd_pack_diff(argparse.Namespace(pack=str(pack_f), source=str(src))) == 1
    out = capsys.readouterr().out
    assert "DRIFTED" in out


def test_cli_verify_rejects_tampered(tmp_path) -> None:
    from rmacd.cli import cmd_pack_verify

    priv, pub = generate_keypair()
    (tmp_path / "k.pem").write_text(priv, encoding="utf-8")
    (tmp_path / "k.pub").write_text(pub, encoding="utf-8")
    signed = sign_pack(GovernancePack.from_dict(PACK_DICT), priv)
    tampered = signed.model_copy(update={"description": "evil"})
    pf = tmp_path / "p.json"
    pf.write_text(tampered.to_json(), encoding="utf-8")
    assert cmd_pack_verify(argparse.Namespace(pack=str(pf), key=str(tmp_path / "k.pub"))) == 1


def test_load_pack_require_signed(tmp_path) -> None:
    from rmacd.packs import PackSignatureError, load_pack

    priv, pub = generate_keypair()
    signed = sign_pack(load_pack("jira"), priv)
    pf = tmp_path / "jira-signed.json"
    pf.write_text(signed.to_json(), encoding="utf-8")

    # valid signature + trusted key -> loads
    pack = load_pack(pf, require_signed=True, trusted_keys=pub)
    assert pack.pack == "jira"

    # wrong key -> refused
    _, other_pub = generate_keypair()
    with pytest.raises(PackSignatureError):
        load_pack(pf, require_signed=True, trusted_keys=other_pub)

    # unsigned built-in -> refused
    with pytest.raises(PackSignatureError):
        load_pack("jira", require_signed=True, trusted_keys=pub)

    # require_signed without a key is a usage error
    with pytest.raises(ValueError):
        load_pack(pf, require_signed=True)


def test_load_packs_require_signed_builds_registry(tmp_path) -> None:
    from rmacd.packs import load_pack, load_packs

    priv, pub = generate_keypair()
    pf = tmp_path / "jira-signed.json"
    pf.write_text(sign_pack(load_pack("jira"), priv).to_json(), encoding="utf-8")
    reg = load_packs([str(pf)], require_signed=True, trusted_keys=pub)
    assert reg.get_tool("jira_delete_issue") is not None


def test_cli_pack_validate_flags_redos(tmp_path, capsys) -> None:
    from rmacd.cli import cmd_pack_validate

    bad = {
        "pack": "redos", "version": "1.0.0",
        "rules": [{
            "id": "r",
            "when": {"tool": "t", "arg_regex": {"arg": "x", "pattern": "(a+)+$"}},
            "operation": "R",
        }],
    }
    pf = tmp_path / "redos.json"
    pf.write_text(GovernancePack.from_dict(bad).to_json(), encoding="utf-8")
    rc = cmd_pack_validate(argparse.Namespace(pack=str(pf)))
    assert rc == 1
    assert "regex safety" in capsys.readouterr().err


def test_signed_builtin_pack_verifies() -> None:
    from rmacd.packs import load_pack

    priv, pub = generate_keypair()
    signed = sign_pack(load_pack("jira"), priv)
    assert verify_pack(signed, pub) is True
    # sanity: a malformed private key is surfaced, not silently passed
    with pytest.raises(ValueError):
        sign_pack(load_pack("jira"), "not-a-key")
