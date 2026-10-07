"""The two logs on one counter (spec §9.1–§9.3).

``Store`` is the protocol the engine writes through. ``JSONLStore`` is the
default: two append-only files and a ``seq`` file, with every write taken
under one exclusive lock so the counter is a total order (N-76) and
``epoch()`` names an exact prefix of both logs (N-75). ``MemoryStore`` is the
same contract in a dict, for tests and for shadow-mode experiments.

Read-side queries are defined once over the two iterators, so both stores
answer every question the same way: duplicate ids (N-57), the logical
decision record with its attachments (N-43, N-74), reconciled successes after
the last mismatch (N-25, N-26), budget counts, demotion standing (N-77) and
grant state. The one write that must be atomic — consuming a grant's child
cap while emitting the covered decision (N-55) — is ``append_decision_if_cap``.
"""

from __future__ import annotations

import fcntl
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from .models import (
    ActionPatternFields,
    AdjudicationLogEntry,
    DecisionRecord,
    GrantStatus,
    IntentLogEntry,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Store(Protocol):
    def append_intent(self, entry: IntentLogEntry) -> int: ...
    def append_decision(self, entry: AdjudicationLogEntry) -> int: ...
    def append_decision_if_cap(
        self, entry: AdjudicationLogEntry, grant_id: str, max_children: int
    ) -> bool: ...
    def next_seq(self) -> int: ...
    def epoch(self) -> str: ...
    def has_intent(self, intent_id: str) -> bool: ...
    def submission(self, intent_id: str) -> IntentLogEntry | None: ...
    def decision_for(self, intent_id: str) -> DecisionRecord | None: ...
    def decision(self, decision_id: str) -> DecisionRecord | None: ...
    def decisions(self) -> Iterator[DecisionRecord]: ...
    def disposition_count(self, decision_id: str) -> int: ...
    def reconciliation_count(self, decision_id: str) -> int: ...
    def reconciled_successes(self, pattern: ActionPatternFields, key: str) -> int: ...
    def accepted_by_actor_since(self, actor_id: str, since: datetime) -> int: ...
    def demotion(self, actor_id: str, now: datetime) -> IntentLogEntry | None: ...
    def grant_status(self, intent_id: str) -> GrantStatus | None: ...
    def covered_by(self, grant_id: str) -> list[DecisionRecord]: ...
    def intent_entries(self) -> Iterator[IntentLogEntry]: ...
    def adjudication_entries(self) -> Iterator[AdjudicationLogEntry]: ...


class _BaseStore:
    """Read-side queries shared by both stores, defined over the two iterators."""

    def intent_entries(self) -> Iterator[IntentLogEntry]:  # pragma: no cover - abstract
        raise NotImplementedError

    def adjudication_entries(self) -> Iterator[AdjudicationLogEntry]:  # pragma: no cover
        raise NotImplementedError

    def has_intent(self, intent_id: str) -> bool:
        return self.submission(intent_id) is not None

    def submission(self, intent_id: str) -> IntentLogEntry | None:
        for e in self.intent_entries():
            if e.kind == "submission" and e.intent_id == intent_id:
                return e
        return None

    def decision_for(self, intent_id: str) -> DecisionRecord | None:
        for e in self.adjudication_entries():
            if e.kind == "decision" and e.record is not None and e.record.intent_id == intent_id:
                return self._with_attachments(e.record)
        return None

    def decision(self, decision_id: str) -> DecisionRecord | None:
        for e in self.adjudication_entries():
            if e.kind == "decision" and e.decision_id == decision_id and e.record is not None:
                return self._with_attachments(e.record)
        return None

    def decisions(self) -> Iterator[DecisionRecord]:
        for e in self.adjudication_entries():
            if e.kind == "decision" and e.record is not None:
                yield self._with_attachments(e.record)

    def _with_attachments(self, record: DecisionRecord) -> DecisionRecord:
        """The logical record: the emitted record plus its attachments (N-43, N-74)."""
        out = record
        for e in self.adjudication_entries():
            if e.decision_id != record.decision_id:
                continue
            if e.kind == "disposition" and e.disposition is not None:
                out = out.model_copy(update={"disposition": e.disposition})
            elif e.kind == "reconciliation" and e.reconciliation is not None:
                out = out.model_copy(update={"reconciliation": e.reconciliation})
        return out

    def disposition_count(self, decision_id: str) -> int:
        return sum(
            1
            for e in self.adjudication_entries()
            if e.kind == "disposition" and e.decision_id == decision_id
        )

    def reconciliation_count(self, decision_id: str) -> int:
        return sum(
            1
            for e in self.adjudication_entries()
            if e.kind == "reconciliation" and e.decision_id == decision_id
        )

    def _same_pattern(self, record: DecisionRecord, pattern: ActionPatternFields, key: str) -> bool:
        if record.action_pattern_key is not None:
            return record.action_pattern_key == key
        return record.action_pattern_fields == pattern

    def reconciled_successes(self, pattern: ActionPatternFields, key: str) -> int:
        """Confirmed successes for one action pattern since its last mismatch.

        A decision counts only when execution was permitted — a permitting
        disposition or a covering grant — and reconciled as ``matched``
        (N-25). A ``divergent`` or ``undeclared`` reconciliation on the same
        pattern wipes everything before it (N-26, N-48), so the count is taken
        over the suffix of the log after the latest mismatch.
        """
        records = {
            e.decision_id: e.record
            for e in self.adjudication_entries()
            if e.kind == "decision" and e.record is not None
            and self._same_pattern(e.record, pattern, key)
        }
        if not records:
            return 0
        permitted = {
            did
            for did, rec in records.items()
            if rec.grant_ref is not None
            or any(
                e.kind == "disposition" and e.decision_id == did
                and e.disposition is not None and e.disposition.permits
                for e in self.adjudication_entries()
            )
        }
        count = 0
        for e in self.adjudication_entries():
            if (
                e.kind != "reconciliation"
                or e.decision_id not in records
                or e.reconciliation is None
            ):
                continue
            if e.reconciliation.result in ("divergent", "undeclared"):
                count = 0
            elif e.reconciliation.result == "matched" and e.decision_id in permitted:
                count += 1
        return count

    def accepted_by_actor_since(self, actor_id: str, since: datetime) -> int:
        n = 0
        for e in self.intent_entries():
            if e.kind != "submission" or e.document is None or e.logged_at < since:
                continue
            actor = e.document.get("actor")
            if isinstance(actor, dict) and actor.get("id") == actor_id:
                n += 1
        return n

    def demotion(self, actor_id: str, now: datetime) -> IntentLogEntry | None:
        """The demotion in force for an actor, or None (N-77)."""
        latest: IntentLogEntry | None = None
        for e in self.intent_entries():
            if e.kind in ("demotion", "demotion_lifted") and e.actor_id == actor_id:
                latest = e
        if latest is None or latest.kind != "demotion":
            return None
        if latest.until is not None and latest.until <= now:
            return None
        return latest

    def grant_status(self, intent_id: str) -> GrantStatus | None:
        status: GrantStatus | None = None
        for e in self.intent_entries():
            if e.intent_id != intent_id:
                continue
            if e.kind == "submission" and e.document is not None:
                raw = e.document.get("status")
                status = GrantStatus(raw) if raw else GrantStatus.REQUESTED
            elif e.kind == "transition" and e.to_status is not None:
                status = e.to_status
        return status

    def covered_by(self, grant_id: str) -> list[DecisionRecord]:
        return [r for r in self.decisions() if r.grant_ref == grant_id]


class MemoryStore(_BaseStore):
    def __init__(self) -> None:
        self._seq = 0
        self._intents: list[IntentLogEntry] = []
        self._adjudications: list[AdjudicationLogEntry] = []

    def next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def epoch(self) -> str:
        return f"seq-{self._seq}"

    def append_intent(self, entry: IntentLogEntry) -> int:
        self._intents.append(entry)
        self._seq = max(self._seq, entry.seq)
        return entry.seq

    def append_decision(self, entry: AdjudicationLogEntry) -> int:
        self._adjudications.append(entry)
        self._seq = max(self._seq, entry.seq)
        return entry.seq

    def append_decision_if_cap(
        self, entry: AdjudicationLogEntry, grant_id: str, max_children: int
    ) -> bool:
        if len(self.covered_by(grant_id)) >= max_children:
            return False
        self.append_decision(entry)
        return True

    def intent_entries(self) -> Iterator[IntentLogEntry]:
        return iter(list(self._intents))

    def adjudication_entries(self) -> Iterator[AdjudicationLogEntry]:
        return iter(list(self._adjudications))


class JSONLStore(_BaseStore):
    """``intents.jsonl`` + ``adjudications.jsonl`` + ``seq``, one lock.

    Single-host atomicity: every counter read, increment and append happens
    under an exclusive ``flock`` on the ``seq`` file, and
    ``append_decision_if_cap`` counts and appends under that same lock. That
    is enough for the L1 and L2 obligations and for one host's grant caps; a
    multi-host L3 deployment wants a transactional store behind the same
    protocol.
    """

    def __init__(self, directory: str | os.PathLike[str]) -> None:
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.intents_path = self.dir / "intents.jsonl"
        self.adjudications_path = self.dir / "adjudications.jsonl"
        self.seq_path = self.dir / "seq"
        for p in (self.intents_path, self.adjudications_path):
            p.touch(exist_ok=True)
        if not self.seq_path.exists():
            self.seq_path.write_text("0\n", encoding="utf-8")

    @contextmanager
    def _locked(self) -> Iterator[None]:
        with open(self.seq_path, "r+", encoding="utf-8") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    def _read_seq(self) -> int:
        return int(self.seq_path.read_text(encoding="utf-8").strip() or "0")

    def _write_seq(self, n: int) -> None:
        self.seq_path.write_text(f"{n}\n", encoding="utf-8")

    def next_seq(self) -> int:
        with self._locked():
            n = self._read_seq() + 1
            self._write_seq(n)
            return n

    def epoch(self) -> str:
        with self._locked():
            return f"seq-{self._read_seq()}"

    def _append_unlocked(self, path: Path, line: str, seq: int) -> int:
        current = self._read_seq()
        if seq < current:
            # An entry must be written at the position its seq was issued
            # for; anything else would make the epoch lie about the prefix.
            raise ValueError(f"seq {seq} is behind the counter ({current})")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        if seq > current:
            self._write_seq(seq)
        return seq

    def append_intent(self, entry: IntentLogEntry) -> int:
        with self._locked():
            return self._append_unlocked(
                self.intents_path, json.dumps(entry.to_json_dict(), ensure_ascii=False), entry.seq
            )

    def append_decision(self, entry: AdjudicationLogEntry) -> int:
        with self._locked():
            return self._append_unlocked(
                self.adjudications_path,
                json.dumps(entry.to_json_dict(), ensure_ascii=False),
                entry.seq,
            )

    def append_decision_if_cap(
        self, entry: AdjudicationLogEntry, grant_id: str, max_children: int
    ) -> bool:
        with self._locked():
            if len(self.covered_by(grant_id)) >= max_children:
                return False
            self._append_unlocked(
                self.adjudications_path,
                json.dumps(entry.to_json_dict(), ensure_ascii=False),
                entry.seq,
            )
            return True

    def intent_entries(self) -> Iterator[IntentLogEntry]:
        for line in self.intents_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                yield IntentLogEntry.model_validate_json(line)

    def adjudication_entries(self) -> Iterator[AdjudicationLogEntry]:
        for line in self.adjudications_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                yield AdjudicationLogEntry.model_validate_json(line)
