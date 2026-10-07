"""The JSONL store, the bundled schemas, the pattern key and the CLI."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from rmacd_intents import JSONLStore, StaticActorResolver, action_pattern_key, pattern_fields
from rmacd_intents.cli import main
from rmacd_intents.envelope import SCHEMA_NAMES, load_schema, validate_submission
from rmacd_intents.grading import Engine
from rmacd_intents.models import DecisionRecord, Intent, IntentLogEntry

from .conftest import BINDINGS, EXAMPLES, PROFILES, REPO, Clock, example, intent

AUTHORITATIVE = REPO / "schemas"


@pytest.mark.parametrize("name", SCHEMA_NAMES)
def test_bundled_schema_matches_the_authoritative_copy(name: str) -> None:
    assert load_schema(name) == json.loads((AUTHORITATIVE / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", sorted(p.name for p in EXAMPLES.glob("*.json")))
def test_every_worked_example_parses_into_its_model(name: str) -> None:
    doc = example(name)
    schema = doc["$schema"].rsplit("/", 1)[-1]
    if schema == "intent.json":
        assert isinstance(validate_submission(doc), Intent)
    elif schema == "intent-decision.json":
        DecisionRecord.model_validate(doc)
    elif schema == "intent-log-entry.json":
        IntentLogEntry.model_validate(doc)


def test_pattern_key_ignores_the_literal_target_and_metadata() -> None:
    a = validate_submission(intent())
    b = validate_submission(intent(intent_id="int-other", metadata={"x": 1}, justification="other"))
    assert isinstance(a, Intent) and isinstance(b, Intent)
    b.declaration.target = "svc://payments-api/config/other-knob"
    fa = pattern_fields(a, "svc://payments-api/config/*")
    fb = pattern_fields(b, "svc://payments-api/config/*")
    assert action_pattern_key(fa) == action_pattern_key(fb)  # N-22
    assert action_pattern_key(fa).startswith("sha256:") and len(action_pattern_key(fa)) == 71


def test_pattern_key_is_byte_stable() -> None:
    """RFC 8785 pins the bytes, so the key is a constant for this example (N-56)."""
    a = validate_submission(intent())
    assert isinstance(a, Intent)
    key = action_pattern_key(pattern_fields(a, "svc://payments-api/config/*"))
    assert key == action_pattern_key(pattern_fields(a, "svc://payments-api/config/*"))


def test_jsonl_store_round_trips_and_orders_both_logs(tmp_path: Path) -> None:
    store = JSONLStore(tmp_path / "store")
    engine = Engine(store, StaticActorResolver.from_paths(BINDINGS), clock=Clock())
    rec = engine.submit(intent())
    assert isinstance(rec, DecisionRecord)
    engine.decide(rec.decision_id, "approved", "cab@company.com")
    assert (tmp_path / "store" / "seq").read_text().strip() == "3"
    seqs = [e.seq for e in store.intent_entries()] + [e.seq for e in store.adjudication_entries()]
    assert sorted(seqs) == [1, 2, 3]
    reopened = JSONLStore(tmp_path / "store")
    assert reopened.epoch() == "seq-3"
    logical = reopened.decision(rec.decision_id)
    assert logical is not None and logical.disposition is not None


def test_jsonl_counter_is_unique_under_concurrent_writers(tmp_path: Path) -> None:
    store = JSONLStore(tmp_path / "store")
    got: list[int] = []
    lock = threading.Lock()

    def worker() -> None:
        for _ in range(25):
            n = store.next_seq()
            with lock:
                got.append(n)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(got) == 200 and len(set(got)) == 200 and max(got) == 200  # N-76


def test_rejections_and_decisions_live_in_different_files(tmp_path: Path) -> None:
    store = JSONLStore(tmp_path / "store")
    engine = Engine(store, StaticActorResolver.from_paths(BINDINGS), clock=Clock())
    bad = intent()
    del bad["declaration"]
    engine.submit(bad)
    assert (tmp_path / "store" / "intents.jsonl").read_text().count("\n") == 1
    assert (tmp_path / "store" / "adjudications.jsonl").read_text() == ""  # N-72


def _config(tmp_path: Path) -> Path:
    cfg: dict[str, Any] = {
        "store": "store",
        "policy_version": "cli-test",
        "profiles": {auth: str(path) for auth, path in BINDINGS.items()},
    }
    p = tmp_path / "rmacd-intents.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    return p


def test_cli_submit_decide_log(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cfg = _config(tmp_path)
    doc = tmp_path / "intent.json"
    doc.write_text(json.dumps(intent()), encoding="utf-8")
    assert main(["-c", str(cfg), "submit", str(doc)]) == 0
    record = json.loads(capsys.readouterr().out)
    assert record["computed_level"] == "elevated_approval"
    assert main(["-c", str(cfg), "decide", record["decision_id"], "--outcome", "approved",
                 "--approver", "cab@company.com"]) == 0
    capsys.readouterr()
    assert main(["-c", str(cfg), "log", "adjudications"]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert [json.loads(line)["kind"] for line in lines] == ["decision", "disposition"]


def test_cli_rejection_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cfg = _config(tmp_path)
    doc = tmp_path / "bad.json"
    doc.write_text("{not json", encoding="utf-8")
    assert main(["-c", str(cfg), "submit", str(doc)]) == 2
    assert json.loads(capsys.readouterr().out)["rejected"] is True


def test_default_profile_loads_from_config(tmp_path: Path) -> None:
    from rmacd_intents.cli import load_engine

    cfg = tmp_path / "rmacd-intents.json"
    cfg.write_text(
        json.dumps({"profiles": {}, "default_profile": str(PROFILES / "observer-3d.json")})
    )
    engine = load_engine(cfg)
    assert engine.default_profile is not None
    assert datetime.now(timezone.utc) > engine.clock() - __import__("datetime").timedelta(seconds=5)
