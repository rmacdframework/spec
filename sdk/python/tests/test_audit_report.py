"""Tests for rmacd.audit_report and the `rmacd audit summarize` CLI.

The JSONL fixtures are built by *running the SDK's own audit logger*
(``PolicyEnforcer`` + ``JSONLAuditLogger``), never by hand-writing record
dicts, so the summarizer's expectations cannot drift from what the writer
actually produces.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from rmacd import (
    AutoApproveGateway,
    JSONLAuditLogger,
    PolicyEnforcer,
    ProfileLoader,
    RejectAllApprovalGateway,
    RMACDApprovalDeniedError,
    RMACDPolicyError,
    cli,
)
from rmacd import audit_report as ar

EXAMPLES_DIR = Path(__file__).resolve().parents[3] / "schemas" / "examples"


def _enforcer(
    profile_name: str, log_path: Path, agent_id: str, *, approve: bool = True
) -> PolicyEnforcer:
    profile = ProfileLoader().load_file(EXAMPLES_DIR / profile_name)
    gateway = AutoApproveGateway() if approve else RejectAllApprovalGateway()
    return PolicyEnforcer(
        profile=profile,
        agent_id=agent_id,
        approval_gateway=gateway,
        audit_logger=JSONLAuditLogger(log_path),
    )


def _ts(record: dict[str, Any]) -> datetime:
    ts = ar.parse_timestamp(record["timestamp"])
    assert ts is not None
    return ts


@pytest.fixture
def log_3d(tmp_path: Path) -> Path:
    """Mixed 3D activity written by the real logger.

    Record inventory (9 records total):
      - R public          -> ALLOW
      - R confidential    -> ALLOW (logged)
      - C internal        -> QUEUED + APPROVED + ALLOW (auto-approved)
      - C restricted      -> DENY (S12.5 floor territory)
      - D restricted      -> DENY (S12.5 floor territory)
      - C public (agent2) -> QUEUED + REJECTED (reject-all gateway)
    """
    path = tmp_path / "audit.jsonl"
    enforcer = _enforcer("administrator-3d.json", path, "agent-alpha")
    enforcer.enforce("R", "doc://public/readme", "public")
    enforcer.enforce("R", "db://customers", "confidential")
    enforcer.enforce("C", "config://app.yaml", "internal")
    with pytest.raises(RMACDPolicyError):
        enforcer.enforce("C", "vault://keys", "restricted")
    with pytest.raises(RMACDPolicyError):
        enforcer.enforce("D", "vault://keys", "restricted")

    rejecting = _enforcer("administrator-3d.json", path, "agent-beta", approve=False)
    with pytest.raises(RMACDApprovalDeniedError):
        rejecting.enforce("C", "config://beta.yaml", "public")
    return path


def _summary(path: Path, **filters: Any) -> dict[str, Any]:
    records, malformed = ar.load_records(path)
    records = ar.filter_records(records, **filters)
    return ar.summarize(records, source=str(path), malformed=malformed)


class TestParsing:
    def test_load_counts_all_logger_written_records(self, log_3d: Path) -> None:
        records, malformed = ar.load_records(log_3d)
        assert len(records) == 9
        assert malformed == 0

    def test_malformed_lines_skipped_and_counted(self, log_3d: Path) -> None:
        with log_3d.open("a", encoding="utf-8") as f:
            f.write("this is not json\n")
            f.write('{"valid_json": "but not an audit record"}\n')
            f.write("\n")  # blank lines are ignored, not malformed
        records, malformed = ar.load_records(log_3d)
        assert len(records) == 9
        assert malformed == 2

    def test_unreadable_file_raises_oserror(self, tmp_path: Path) -> None:
        with pytest.raises(OSError):
            ar.load_records(tmp_path / "missing.jsonl")

    def test_parse_timestamp_accepts_z_suffix_and_naive(self) -> None:
        aware = ar.parse_timestamp("2026-01-10T14:30:22.456Z")
        naive = ar.parse_timestamp("2026-01-10T14:30:22.456")
        assert aware is not None and naive is not None
        assert aware == naive  # naive assumed UTC
        assert ar.parse_timestamp("not-a-date") is None
        assert ar.parse_timestamp(None) is None


class TestSummaryCounts:
    def test_decision_breakdown(self, log_3d: Path) -> None:
        summary = _summary(log_3d)
        assert summary["decisions"] == {
            "allow": 3,
            "deny": 2,
            "queued": 2,
            "approved": 1,
            "rejected": 1,
            # Outcome records, not decisions — counted separately so they never
            # dilute the decision percentages. Absent from this fixture.
            "executed": 0,
            "other": 0,
        }
        assert summary["records"] == {"included": 9, "malformed": 0}

    def test_header_fields(self, log_3d: Path) -> None:
        summary = _summary(log_3d)
        assert summary["schema"] == ar.SUMMARY_SCHEMA
        assert summary["agents"] == ["agent-alpha", "agent-beta"]
        assert summary["profiles"] == ["rmacd-3d-administrator-v1"]
        first = ar.parse_timestamp(summary["time_range"]["first"])
        last = ar.parse_timestamp(summary["time_range"]["last"])
        assert first is not None and last is not None and first <= last

    def test_matrix_counts_terminal_decisions_only(self, log_3d: Path) -> None:
        matrix = _summary(log_3d)["matrix"]
        assert matrix["R"]["public"] == {"allowed": 1, "denied": 0}
        assert matrix["R"]["confidential"] == {"allowed": 1, "denied": 0}
        assert matrix["C"]["internal"] == {"allowed": 1, "denied": 0}
        assert matrix["C"]["restricted"] == {"allowed": 0, "denied": 1}
        assert matrix["D"]["restricted"] == {"allowed": 0, "denied": 1}
        # The rejected approval is a terminal denial on C/public; the QUEUED
        # and APPROVED intermediates must not inflate any cell.
        assert matrix["C"]["public"] == {"allowed": 0, "denied": 1}
        total = sum(c["allowed"] + c["denied"] for cells in matrix.values() for c in cells.values())
        assert total == 6  # 6 operations, 9 records

    def test_top_denied_flags_floor_hits(self, log_3d: Path) -> None:
        summary = _summary(log_3d)
        assert summary["floor_denials"] == 2
        vault = [e for e in summary["top_denied"] if e["target"] == "vault://keys"]
        assert vault, "expected vault://keys denials in top_denied"
        assert all(e["floor"] for e in vault)
        assert sum(e["count"] for e in vault) == 2
        beta = [e for e in summary["top_denied"] if e["target"] == "config://beta.yaml"]
        assert len(beta) == 1
        assert beta[0]["floor"] is False
        assert beta[0]["reason"] == "approval rejected"

    def test_approval_latency_present_and_sane(self, log_3d: Path) -> None:
        latency = _summary(log_3d)["approval_latency"]
        assert latency is not None
        assert latency["count"] == 2  # one approved + one rejected round-trip
        assert 0 <= latency["min_seconds"] <= latency["median_seconds"] <= latency["max_seconds"]


class TestFilters:
    def test_since_and_until(self, log_3d: Path) -> None:
        records, _ = ar.load_records(log_3d)
        timestamps = sorted(_ts(r) for r in records)
        # Cut after the very first record.
        since = timestamps[0] + timedelta(microseconds=1)
        assert len(ar.filter_records(records, since=since)) < len(records)
        # An until before the first record excludes everything.
        until = timestamps[0] - timedelta(seconds=1)
        assert ar.filter_records(records, until=until) == []
        # Bounds are inclusive.
        kept = ar.filter_records(records, since=timestamps[0], until=timestamps[-1])
        assert len(kept) == len(records)

    def test_agent_filter(self, log_3d: Path) -> None:
        summary = _summary(log_3d, agent="agent-beta")
        assert summary["agents"] == ["agent-beta"]
        assert summary["records"]["included"] == 2  # QUEUED + REJECTED

    def test_denials_only(self, log_3d: Path) -> None:
        summary = _summary(log_3d, denials_only=True)
        assert summary["records"]["included"] == 3  # 2 DENY + 1 REJECTED
        assert summary["decisions"]["allow"] == 0
        assert summary["decisions"]["queued"] == 0
        assert summary["decisions"]["deny"] == 2
        assert summary["decisions"]["rejected"] == 1


class Test2DCollapse:
    def test_2d_records_collapse_to_single_unclassified_row(self, tmp_path: Path) -> None:
        path = tmp_path / "audit-2d.jsonl"
        enforcer = _enforcer("operations-2d.json", path, "ops-agent")
        enforcer.enforce("R", "server://web-01")
        with pytest.raises(RMACDPolicyError):
            enforcer.enforce("D", "server://web-01")  # D not granted by this profile
        records, malformed = ar.load_records(path)
        summary = ar.summarize(records, source=str(path), malformed=malformed)
        assert summary["matrix"]["R"] == {ar.UNCLASSIFIED: {"allowed": 1, "denied": 0}}
        assert summary["matrix"]["D"] == {ar.UNCLASSIFIED: {"allowed": 0, "denied": 1}}
        text = ar.render_text(summary)
        assert ar.UNCLASSIFIED in text
        # The tier dimension collapsed: no per-tier rows appear.
        assert "confidential" not in text


class TestRenderers:
    def test_json_round_trips_documented_keys_only(self, log_3d: Path) -> None:
        summary = _summary(log_3d)
        rendered = ar.render_json(summary)
        assert json.loads(rendered) == summary
        assert set(summary.keys()) == {
            "schema",
            "source",
            "filters",
            "records",
            "time_range",
            "agents",
            "profiles",
            "decisions",
            "matrix",
            "top_denied",
            "floor_denials",
            "approval_latency",
        }
        assert set(summary["filters"]) == {"since", "until", "agent", "denials_only"}
        for entry in summary["top_denied"]:
            assert set(entry) == {"target", "reason", "count", "floor"}

    def test_text_report_sections(self, log_3d: Path) -> None:
        text = ar.render_text(_summary(log_3d))
        assert "RMACD audit summary" in text
        assert "Decision breakdown" in text
        assert "Operation x tier" in text
        assert "Top denied" in text
        assert "[S12.5 floor]" in text
        assert "Approval latency" in text

    def test_markdown_report_sections(self, log_3d: Path) -> None:
        md = ar.render_markdown(_summary(log_3d))
        assert md.startswith("# RMACD audit summary")
        assert "## Decision breakdown" in md
        assert "## Operation × tier" in md
        assert "| `vault://keys` |" in md
        assert "**yes**" in md  # floor column flagged
        assert "## Approval latency" in md

    def test_empty_log_summarizes_cleanly(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.jsonl"
        path.write_text("", encoding="utf-8")
        records, malformed = ar.load_records(path)
        summary = ar.summarize(records, source=str(path), malformed=malformed)
        assert summary["records"] == {"included": 0, "malformed": 0}
        assert summary["time_range"] == {"first": None, "last": None}
        assert summary["approval_latency"] is None
        # All renderers cope with the empty summary.
        assert "0 included" in ar.render_text(summary)
        assert "(no terminal decisions)" in ar.render_markdown(summary)
        assert json.loads(ar.render_json(summary)) == summary


class TestCLI:
    def _run(self, monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> int:
        monkeypatch.setattr("sys.argv", ["rmacd", *argv])
        return cli.main()

    def test_summarize_text(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        log_3d: Path,
    ) -> None:
        rc = self._run(monkeypatch, ["audit", "summarize", str(log_3d)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "RMACD audit summary" in out
        assert "9 included" in out

    def test_summarize_json_is_parseable(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        log_3d: Path,
    ) -> None:
        rc = self._run(monkeypatch, ["audit", "summarize", str(log_3d), "--format", "json"])
        assert rc == 0
        summary = json.loads(capsys.readouterr().out)
        assert summary["schema"] == ar.SUMMARY_SCHEMA

    def test_summarize_md(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        log_3d: Path,
    ) -> None:
        rc = self._run(monkeypatch, ["audit", "summarize", str(log_3d), "--format", "md"])
        assert rc == 0
        assert capsys.readouterr().out.startswith("# RMACD audit summary")

    def test_summarize_filters(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        log_3d: Path,
    ) -> None:
        rc = self._run(
            monkeypatch,
            ["audit", "summarize", str(log_3d), "--agent", "agent-beta", "--denials-only"],
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "1 included" in out  # agent-beta's single REJECTED record
        assert "agent=agent-beta" in out
        assert "denials-only" in out

    def test_unreadable_file_is_nonzero(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        tmp_path: Path,
    ) -> None:
        rc = self._run(monkeypatch, ["audit", "summarize", str(tmp_path / "nope.jsonl")])
        assert rc == 1
        assert "cannot read" in capsys.readouterr().err

    def test_malformed_lines_do_not_fail(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        log_3d: Path,
    ) -> None:
        with log_3d.open("a", encoding="utf-8") as f:
            f.write("garbage line\n")
        rc = self._run(monkeypatch, ["audit", "summarize", str(log_3d)])
        assert rc == 0
        assert "1 malformed line(s) skipped" in capsys.readouterr().out

    def test_bad_since_is_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        log_3d: Path,
    ) -> None:
        rc = self._run(monkeypatch, ["audit", "summarize", str(log_3d), "--since", "yesterday"])
        assert rc == 1
        assert "--since" in capsys.readouterr().err

    def test_audit_without_subcommand_prints_help(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        rc = self._run(monkeypatch, ["audit"])
        assert rc == 0
        assert "summarize" in capsys.readouterr().out
