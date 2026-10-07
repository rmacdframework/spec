"""Reconciliation with interception (spec §10).

Input: the SDK's audit trail — Appendix C.6 records, JSON Lines, with
``extra.intent_id`` where the call executed an adjudicated intent. Output: a
``reconciliation`` attachment on each permitted decision (N-47, N-74), a
``demotion`` entry for the actor behind every ``divergent`` or ``undeclared``
result (N-48, N-77), and a report of what was seen.

What is compared is what both sides carry. A C.6 record has an operation, a
target and a classification; it has no environment and no scope, so those
two of N-47's five fields cannot diverge here and are left to an
interception record format that carries them. A cited maintenance window is
checked against the record's timestamp (N-62).
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from rmacd import DataClassification, Operation

from .envelope import ADJUDICATION_LOG_SCHEMA_ID, INTENT_LOG_SCHEMA_ID, assert_valid
from .models import (
    AdjudicationLogEntry,
    DecisionRecord,
    Discrepancy,
    Intent,
    IntentLogEntry,
    InterceptionRecord,
    Reconciliation,
)
from .pattern import derive_target_class

UndeclaredPolicy = Literal["demote", "report"]


@dataclass
class ReconcileReport:
    matched: list[str] = field(default_factory=list)
    divergent: list[str] = field(default_factory=list)
    unexecuted: list[str] = field(default_factory=list)
    undeclared: list[str] = field(default_factory=list)
    demoted: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def load_records(source: str | Path | Iterable[dict[str, object]]) -> list[InterceptionRecord]:
    if isinstance(source, (str, Path)):
        lines = Path(source).read_text(encoding="utf-8").splitlines()
        raw = [json.loads(ln) for ln in lines if ln.strip()]
    else:
        raw = list(source)
    return [InterceptionRecord.model_validate(r) for r in raw]


def _compare(
    intent: Intent,
    record: DecisionRecord,
    evidence: InterceptionRecord,
    window: tuple[datetime, datetime] | None,
) -> list[Discrepancy]:
    out: list[Discrepancy] = []
    declared_op = intent.declaration.operation
    executed_op = evidence.operation.get("type")
    if executed_op != declared_op.value:
        out.append(
            Discrepancy(field="operation", declared=declared_op.value, executed=str(executed_op))
        )
    declared_class = (
        record.action_pattern_fields.target_class
        if record.action_pattern_fields is not None
        else derive_target_class(intent.declaration.target)[0]
    )
    executed_class = derive_target_class(str(evidence.operation.get("target", "")))[0]
    if executed_class != declared_class:
        out.append(
            Discrepancy(field="target_class", declared=declared_class, executed=executed_class)
        )
    declared_tier = record.impact_basis.value
    executed_tier = evidence.operation.get("classification")
    if (
        executed_tier is not None
        and declared_tier != "unclassified"
        and executed_tier != declared_tier
    ):
        out.append(
            Discrepancy(
                field="data_classification", declared=declared_tier, executed=str(executed_tier)
            )
        )
    if window is not None and not (window[0] <= evidence.timestamp <= window[1]):
        out.append(
            Discrepancy(
                field="window",
                declared=f"{window[0].isoformat()}/{window[1].isoformat()}",
                executed=evidence.timestamp.isoformat(),
            )
        )
    return out


class Reconciler:
    def __init__(self, engine: Engine) -> None:  # noqa: F821 - avoids an import cycle
        self.engine = engine

    def _attach(self, record: DecisionRecord, result: Reconciliation) -> None:
        store = self.engine.store
        if store.reconciliation_count(record.decision_id) > 0:
            raise ValueError(f"{record.decision_id} already carries a reconciliation (N-74)")
        entry = AdjudicationLogEntry(
            seq=store.next_seq(),
            logged_at=self.engine.clock(),
            kind="reconciliation",
            decision_id=record.decision_id,
            reconciliation=result,
        )
        assert_valid(ADJUDICATION_LOG_SCHEMA_ID, entry.to_json_dict())
        store.append_decision(entry)

    def demote(self, actor_id: str, cause: str) -> IntentLogEntry:
        """N-48, N-77: a demotion begins as an entry; nothing else demotes."""
        now = self.engine.clock()
        days = self.engine.weights.demotion_days
        entry = IntentLogEntry(
            seq=self.engine.store.next_seq(),
            logged_at=now,
            kind="demotion",
            actor_id=actor_id,
            cause=cause,
            until=now + timedelta(days=days) if days is not None else None,
        )
        assert_valid(INTENT_LOG_SCHEMA_ID, entry.to_json_dict())
        self.engine.store.append_intent(entry)
        return entry

    def _window_for(self, intent: Intent) -> tuple[datetime, datetime] | None:
        if intent.window_ref is None:
            return None
        sub = self.engine.store.submission(intent.window_ref)
        if sub is None or sub.document is None:
            return None
        mw = Intent.model_validate(sub.document)
        if mw.window is None:
            return None
        return mw.window.start, mw.window.end

    def run(
        self,
        source: str | Path | Iterable[dict[str, object]],
        *,
        undeclared: UndeclaredPolicy = "demote",
    ) -> ReconcileReport:
        store = self.engine.store
        now = self.engine.clock()
        report = ReconcileReport()
        evidence = load_records(source)
        by_intent: dict[str, list[InterceptionRecord]] = {}
        for rec in evidence:
            if not rec.is_execution_evidence:
                continue
            if rec.intent_id is None:
                # N-47 undeclared, N-49: never matched to anything.
                report.undeclared.append(rec.record_id)
                if undeclared == "demote" and rec.agent_id not in report.demoted:
                    self.demote(
                        rec.agent_id,
                        f"undeclared: audit record {rec.record_id} carried no intent_id",
                    )
                    report.demoted.append(rec.agent_id)
                continue
            by_intent.setdefault(rec.intent_id, []).append(rec)

        for record in list(store.decisions()):
            if record.reconciliation is not None:
                continue
            permitted = record.grant_ref is not None or (
                record.disposition is not None and record.disposition.permits
            )
            sub = store.submission(record.intent_id)
            if sub is None or sub.document is None:
                report.skipped.append(record.decision_id)
                continue
            intent = Intent.model_validate(sub.document)
            runs = by_intent.get(record.intent_id, [])
            executed = [r for r in runs if r.executed_successfully] or [
                r for r in runs if r.policy_decision.get("result") == "ALLOW"
            ]
            if not executed:
                if intent.valid_until is not None and intent.valid_until <= now:
                    self._attach(record, Reconciliation(result="unexecuted", reconciled_at=now))
                    report.unexecuted.append(record.decision_id)
                else:
                    report.skipped.append(record.decision_id)  # N-49: stays unset
                continue
            if not permitted:
                # Executed without a permitting decision: that is divergence from
                # "awaiting decision", and the actor answers for it.
                discrepancies = [
                    Discrepancy(
                        field="operation", declared="awaiting decision", executed="executed"
                    )
                ]
            else:
                discrepancies = []
                window = self._window_for(intent)
                for ev in executed:
                    discrepancies.extend(_compare(intent, record, ev, window))
            first = executed[0]
            if discrepancies:
                self._attach(
                    record,
                    Reconciliation(
                        result="divergent",
                        reconciled_at=now,
                        audit_record_id=first.record_id,
                        discrepancies=discrepancies,
                    ),
                )
                report.divergent.append(record.decision_id)
                cause = (
                    f"divergent: {record.intent_id} "
                    + "; ".join(
                        f"{d.field} declared {d.declared}, executed {d.executed}"
                        for d in discrepancies
                    )
                    + f" ({record.decision_id})"
                )
                self.demote(intent.actor.id, cause)
                report.demoted.append(intent.actor.id)
            else:
                self._attach(
                    record,
                    Reconciliation(
                        result="matched", reconciled_at=now, audit_record_id=first.record_id
                    ),
                )
                report.matched.append(record.decision_id)
        return report


# Names used only in annotations above; imported late to avoid a cycle.
from .grading import Engine  # noqa: E402

__all__ = ["Reconciler", "ReconcileReport", "load_records", "DataClassification", "Operation"]
