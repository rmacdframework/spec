"""Summarize RMACD audit JSONL into auditor-facing evidence.

Pure functions over parsed audit records (spec Appendix C.6, as written by
``rmacd.audit.JSONLAuditLogger``): parse → filter → summarize → render.
The CLI wiring (``rmacd audit summarize``) lives in ``rmacd.cli`` and stays
thin; everything here is side-effect-free so tests and SIEM pipelines can
call it directly.

Design notes:

- **Tolerant parser.** Malformed lines (bad JSON, or JSON that is not an
  audit record) are skipped and counted, never fatal. Only an unreadable
  file is an error, and that is raised by the caller of :func:`load_records`
  as a normal ``OSError``.
- **Deterministic output.** The summary contains no wall-clock fields, so
  re-running over the same log produces byte-identical evidence — the JSON
  form can be hashed or diffed across runs.
- **Records vs. operations.** An approval-gated operation emits up to three
  records (``QUEUED`` → ``APPROVED``/``REJECTED`` → ``ALLOW``), so the record
  count exceeds the operation count. The operation × tier matrix therefore
  counts *terminal* decisions only: ``allowed`` = ``ALLOW`` records,
  ``denied`` = ``DENY`` + ``REJECTED`` records.
"""

from __future__ import annotations

import json
import statistics
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SUMMARY_SCHEMA = "rmacd-audit-summary/v1"
"""Identifier stamped into every summary so consumers can detect drift."""

UNCLASSIFIED = "unclassified"
"""Tier bucket for records without a data classification (2D profiles)."""

OPERATIONS: tuple[str, ...] = ("R", "M", "A", "C", "D")
TIERS: tuple[str, ...] = ("public", "internal", "confidential", "restricted")

#: ``policy_decision.result`` values the SDK's enforcer writes (Appendix C.6).
#: ``EXECUTED`` is written by ``@guard`` and by the PostToolUse session hook
#: after a call runs; it was previously absent here, so every execution record
#: fell into the "other" bucket — which made a session audit read as ~50 %
#: unclassified.
RESULTS: tuple[str, ...] = ("ALLOW", "DENY", "QUEUED", "APPROVED", "REJECTED", "EXECUTED")

_DENIED_RESULTS = frozenset({"DENY", "REJECTED"})

#: (restricted, operation) pairs covered by the §12.5 immutable floor.
_FLOOR_OPS = frozenset({"A", "C", "D"})

_TOP_DENIED_LIMIT = 10


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_timestamp(value: Any) -> datetime | None:
    """Parse an ISO-8601 timestamp; naive values are assumed UTC.

    Returns ``None`` for anything unparseable (including non-strings) so
    callers can treat a bad timestamp as a malformed record rather than an
    exception. Accepts a trailing ``Z`` on Python 3.10, where
    ``datetime.fromisoformat`` does not.
    """
    if not isinstance(value, str):
        return None
    try:
        ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def _is_record(obj: Any) -> bool:
    """Minimal structural check for an Appendix C.6 audit record."""
    if not isinstance(obj, dict):
        return False
    if not isinstance(obj.get("agent_id"), str) or not isinstance(obj.get("profile_id"), str):
        return False
    if parse_timestamp(obj.get("timestamp")) is None:
        return False
    operation = obj.get("operation")
    if not isinstance(operation, dict) or not isinstance(operation.get("target"), str):
        return False
    if operation.get("type") not in OPERATIONS:
        return False
    policy_decision = obj.get("policy_decision")
    return isinstance(policy_decision, dict) and isinstance(policy_decision.get("result"), str)


def parse_lines(lines: Iterable[str]) -> tuple[list[dict[str, Any]], int]:
    """Parse JSONL lines into ``(records, malformed_count)``.

    Blank lines are ignored. Lines that are not valid JSON, or that parse
    but do not look like audit records, are skipped and counted.
    """
    records: list[dict[str, Any]] = []
    malformed = 0
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if not _is_record(obj):
            malformed += 1
            continue
        records.append(obj)
    return records, malformed


def load_records(path: str | Path) -> tuple[list[dict[str, Any]], int]:
    """Read an audit JSONL file. Raises ``OSError`` if the file is unreadable."""
    text = Path(path).read_text(encoding="utf-8")
    return parse_lines(text.splitlines())


# ---------------------------------------------------------------------------
# Record accessors (records are pre-validated by _is_record)
# ---------------------------------------------------------------------------


def _record_ts(record: dict[str, Any]) -> datetime:
    ts = parse_timestamp(record["timestamp"])
    assert ts is not None  # guaranteed by _is_record
    return ts


def _result(record: dict[str, Any]) -> str:
    result: str = record["policy_decision"]["result"]
    return result


def _tier(record: dict[str, Any]) -> str:
    classification = record["operation"].get("classification")
    return classification if isinstance(classification, str) else UNCLASSIFIED


def _is_floor_hit(record: dict[str, Any]) -> bool:
    """True when a denial is a §12.5 immutable-floor prohibition.

    Detected structurally — a denied A/C/D on Restricted *is* the floor,
    independent of the ``blocked_reason`` wording.
    """
    return (
        _result(record) in _DENIED_RESULTS
        and _tier(record) == "restricted"
        and record["operation"]["type"] in _FLOOR_OPS
    )


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


def filter_records(
    records: Iterable[dict[str, Any]],
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    agent: str | None = None,
    denials_only: bool = False,
) -> list[dict[str, Any]]:
    """Apply the summarize filters; each is inclusive and independent."""
    kept: list[dict[str, Any]] = []
    for record in records:
        ts = _record_ts(record)
        if since is not None and ts < since:
            continue
        if until is not None and ts > until:
            continue
        if agent is not None and record["agent_id"] != agent:
            continue
        if denials_only and _result(record) not in _DENIED_RESULTS:
            continue
        kept.append(record)
    return kept


# ---------------------------------------------------------------------------
# Summarizing
# ---------------------------------------------------------------------------


def _approval_latencies(records: list[dict[str, Any]]) -> list[float]:
    """Latency in seconds from each QUEUED record to its APPROVED/REJECTED.

    Records are paired by ``approval_id``. The decision end time prefers the
    ``approved_at`` timestamp inside the decision record and falls back to
    that record's own ``timestamp``.
    """
    queued_at: dict[str, datetime] = {}
    latencies: list[float] = []
    for record in records:
        decision = record["policy_decision"]
        approval_id = decision.get("approval_id")
        if not isinstance(approval_id, str):
            continue
        result = _result(record)
        if result == "QUEUED":
            queued_at.setdefault(approval_id, _record_ts(record))
        elif result in ("APPROVED", "REJECTED") and approval_id in queued_at:
            end = parse_timestamp(decision.get("approved_at")) or _record_ts(record)
            latencies.append((end - queued_at.pop(approval_id)).total_seconds())
    return latencies


def summarize(
    records: list[dict[str, Any]],
    *,
    source: str = "-",
    malformed: int = 0,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the ``rmacd-audit-summary/v1`` summary dict.

    ``records`` should already be filtered (see :func:`filter_records`);
    ``filters`` is echoed into the output so evidence is self-describing.
    The returned dict contains exactly the documented keys — it is the JSON
    output format (see ``docs/audit-evidence.md``).
    """
    echo: dict[str, Any] = {
        "since": None,
        "until": None,
        "agent": None,
        "denials_only": False,
    }
    if filters:
        echo.update(filters)

    timestamps = sorted(_record_ts(r) for r in records)
    decisions = {result.lower(): 0 for result in RESULTS}
    decisions["other"] = 0

    matrix: dict[str, dict[str, dict[str, int]]] = {}
    denied_groups: dict[tuple[str, str], dict[str, Any]] = {}
    floor_denials = 0

    for record in records:
        result = _result(record)
        decisions[result.lower() if result in RESULTS else "other"] += 1

        # Terminal decisions only — see module docstring.
        terminal = "allowed" if result == "ALLOW" else (
            "denied" if result in _DENIED_RESULTS else None
        )
        if terminal is not None:
            op: str = record["operation"]["type"]
            cell = matrix.setdefault(op, {}).setdefault(_tier(record), {"allowed": 0, "denied": 0})
            cell[terminal] += 1

        if result in _DENIED_RESULTS:
            target: str = record["operation"]["target"]
            reason = record["policy_decision"].get("blocked_reason")
            if not isinstance(reason, str) or not reason:
                reason = "approval rejected" if result == "REJECTED" else "unspecified"
            floor = _is_floor_hit(record)
            if floor:
                floor_denials += 1
            entry = denied_groups.setdefault(
                (target, reason),
                {"target": target, "reason": reason, "count": 0, "floor": floor},
            )
            entry["count"] += 1
            entry["floor"] = entry["floor"] or floor

    top_denied = sorted(
        denied_groups.values(), key=lambda e: (-int(e["count"]), str(e["target"]))
    )[:_TOP_DENIED_LIMIT]

    latencies = _approval_latencies(records)
    approval_latency: dict[str, Any] | None = None
    if latencies:
        approval_latency = {
            "count": len(latencies),
            "min_seconds": round(min(latencies), 3),
            "median_seconds": round(statistics.median(latencies), 3),
            "max_seconds": round(max(latencies), 3),
        }

    return {
        "schema": SUMMARY_SCHEMA,
        "source": source,
        "filters": echo,
        "records": {"included": len(records), "malformed": malformed},
        "time_range": {
            "first": timestamps[0].isoformat() if timestamps else None,
            "last": timestamps[-1].isoformat() if timestamps else None,
        },
        "agents": sorted({r["agent_id"] for r in records}),
        "profiles": sorted({r["profile_id"] for r in records}),
        "decisions": decisions,
        "matrix": matrix,
        "top_denied": top_denied,
        "floor_denials": floor_denials,
        "approval_latency": approval_latency,
    }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


_DECISION_LABELS: tuple[tuple[str, str], ...] = (
    ("allow", "allowed"),
    ("deny", "denied"),
    ("approved", "approval granted"),
    ("rejected", "approval denied"),
    ("queued", "approval queued"),
    # Not a decision — the outcome of a call a decision already permitted.
    # Counted separately so it never dilutes the decision percentages.
    ("executed", "executed (outcome)"),
    ("other", "other"),
)


def _percent(count: int, total: int) -> str:
    return f"{(100.0 * count / total):5.1f}%" if total else "   - "


def _tiers_in(matrix: dict[str, dict[str, dict[str, int]]]) -> list[str]:
    """Tier rows in canonical order; 2D logs collapse to one row."""
    seen = {tier for cells in matrix.values() for tier in cells}
    ordered = [t for t in TIERS if t in seen]
    if UNCLASSIFIED in seen:
        ordered.append(UNCLASSIFIED)
    return ordered


def _matrix_rows(summary: dict[str, Any]) -> list[list[str]]:
    """Rows of the operation × tier table: header, then one row per tier.

    Cells are ``allowed/denied`` terminal-decision counts, ``-`` when the
    (operation, tier) pair never occurs. For logs without classifications
    (2D profiles) the single ``unclassified`` row carries every operation —
    the tier dimension collapses as the spec's 2D shape prescribes.
    """
    matrix: dict[str, dict[str, dict[str, int]]] = summary["matrix"]
    ops = [op for op in OPERATIONS if op in matrix]
    rows = [["tier", *ops]]
    for tier in _tiers_in(matrix):
        row = [tier]
        for op in ops:
            cell = matrix.get(op, {}).get(tier)
            row.append(f"{cell['allowed']}/{cell['denied']}" if cell else "-")
        rows.append(row)
    return rows


def _filters_line(summary: dict[str, Any]) -> str:
    echo: dict[str, Any] = summary["filters"]
    parts: list[str] = []
    if echo.get("since"):
        parts.append(f"since={echo['since']}")
    if echo.get("until"):
        parts.append(f"until={echo['until']}")
    if echo.get("agent"):
        parts.append(f"agent={echo['agent']}")
    if echo.get("denials_only"):
        parts.append("denials-only")
    return ", ".join(parts) if parts else "(none)"


def render_json(summary: dict[str, Any]) -> str:
    """Machine-readable form: the summary dict itself, stable key order."""
    return json.dumps(summary, indent=2)


def render_text(summary: dict[str, Any]) -> str:
    """Terminal-facing plain-text report."""
    included: int = summary["records"]["included"]
    malformed: int = summary["records"]["malformed"]
    time_range: dict[str, Any] = summary["time_range"]

    lines = [
        "RMACD audit summary",
        f"  Source:     {summary['source']}",
        f"  Time range: {time_range['first'] or '-'} -> {time_range['last'] or '-'}",
        f"  Records:    {included} included, {malformed} malformed line(s) skipped",
        f"  Agents:     {', '.join(summary['agents']) or '-'}",
        f"  Profiles:   {', '.join(summary['profiles']) or '-'}",
        f"  Filters:    {_filters_line(summary)}",
        "",
        "Decision breakdown",
    ]
    decisions: dict[str, int] = summary["decisions"]
    for key, label in _DECISION_LABELS:
        count = decisions.get(key, 0)
        if key == "other" and count == 0:
            continue
        lines.append(f"  {label:<18} {count:>6}  {_percent(count, included)}")

    rows = _matrix_rows(summary)
    lines += ["", "Operation x tier (terminal decisions, allowed/denied)"]
    if len(rows) > 1:
        widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
        for row in rows:
            lines.append("  " + "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))
    else:
        lines.append("  (no terminal decisions)")

    lines += ["", "Top denied (target, rule, count)"]
    top_denied: list[dict[str, Any]] = summary["top_denied"]
    if top_denied:
        for i, entry in enumerate(top_denied, start=1):
            floor = "  [S12.5 floor]" if entry["floor"] else ""
            lines.append(f"  {i}. {entry['target']} -- {entry['reason']} ({entry['count']}){floor}")
    else:
        lines.append("  (none)")
    lines.append(f"  S12.5 floor hits: {summary['floor_denials']}")

    latency: dict[str, Any] | None = summary["approval_latency"]
    lines += ["", "Approval latency (QUEUED -> decision)"]
    if latency:
        lines.append(
            f"  approvals: {latency['count']}  min {latency['min_seconds']}s"
            f"  median {latency['median_seconds']}s  max {latency['max_seconds']}s"
        )
    else:
        lines.append("  (no completed approval round-trips in range)")

    return "\n".join(lines) + "\n"


def render_markdown(summary: dict[str, Any]) -> str:
    """Markdown report suitable for pasting into an audit ticket."""
    included: int = summary["records"]["included"]
    malformed: int = summary["records"]["malformed"]
    time_range: dict[str, Any] = summary["time_range"]

    lines = [
        "# RMACD audit summary",
        "",
        f"- **Source:** `{summary['source']}`",
        f"- **Time range:** {time_range['first'] or '-'} → {time_range['last'] or '-'}",
        f"- **Records:** {included} included, {malformed} malformed line(s) skipped",
        f"- **Agents:** {', '.join(summary['agents']) or '-'}",
        f"- **Profiles:** {', '.join(summary['profiles']) or '-'}",
        f"- **Filters:** {_filters_line(summary)}",
        "",
        "## Decision breakdown",
        "",
        "| Decision | Count | % |",
        "|---|---:|---:|",
    ]
    decisions: dict[str, int] = summary["decisions"]
    for key, label in _DECISION_LABELS:
        count = decisions.get(key, 0)
        if key == "other" and count == 0:
            continue
        lines.append(f"| {label} | {count} | {_percent(count, included).strip()} |")

    rows = _matrix_rows(summary)
    lines += [
        "",
        "## Operation × tier",
        "",
        "Terminal decisions per cell, `allowed/denied`.",
        "",
    ]
    if len(rows) > 1:
        lines.append("| " + " | ".join(rows[0]) + " |")
        lines.append("|" + "---|" * len(rows[0]))
        for row in rows[1:]:
            lines.append("| " + " | ".join(row) + " |")
    else:
        lines.append("(no terminal decisions)")

    lines += ["", "## Top denied", ""]
    top_denied: list[dict[str, Any]] = summary["top_denied"]
    if top_denied:
        lines += ["| Target | Rule | Count | §12.5 floor |", "|---|---|---:|---|"]
        for entry in top_denied:
            floor = "**yes**" if entry["floor"] else "no"
            lines.append(
                f"| `{entry['target']}` | {entry['reason']} | {entry['count']} | {floor} |"
            )
    else:
        lines.append("(none)")
    lines.append("")
    lines.append(f"**§12.5 floor hits:** {summary['floor_denials']}")

    latency: dict[str, Any] | None = summary["approval_latency"]
    lines += ["", "## Approval latency", ""]
    if latency:
        lines.append(
            f"{latency['count']} completed approval round-trip(s): "
            f"min {latency['min_seconds']}s, median {latency['median_seconds']}s, "
            f"max {latency['max_seconds']}s."
        )
    else:
        lines.append("No completed approval round-trips in range.")

    return "\n".join(lines) + "\n"


__all__ = [
    "OPERATIONS",
    "RESULTS",
    "SUMMARY_SCHEMA",
    "TIERS",
    "UNCLASSIFIED",
    "filter_records",
    "load_records",
    "parse_lines",
    "parse_timestamp",
    "render_json",
    "render_markdown",
    "render_text",
    "summarize",
]
