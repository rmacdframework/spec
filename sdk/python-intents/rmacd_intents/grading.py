"""The adjudication contract (spec §5) — the nine steps, in order (N-50).

``Engine.submit`` takes bytes and returns either a ``DecisionRecord`` or a
``Rejection``; nothing else is possible, and both leave a trace in the logs
(N-59, N-73). ``Engine.decide`` attaches a human decision (N-43, N-63, N-64)
and ``Engine.transition`` moves a grant through its lifecycle (N-68, N-71).

The base level is never computed here. Step 4 calls the SDK's
``PolicyEvaluator.required_autonomy`` so the §12.5 floor and every profile
override are inherited structurally (N-12, N-13). Everything this module adds
moves a level toward more oversight or leaves it alone — never the other way
(N-14).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from itertools import product
from typing import Any, Literal

from rmacd import AutonomyLevel, DataClassification, Operation, PolicyEvaluator
from rmacd.evaluator import IMMUTABLE_PROHIBITIONS, AnyProfile
from rmacd.models import Profile2D, Profile3D, ProfileDC2D

from .actors import ActorResolver
from .envelope import (
    ADJUDICATION_LOG_SCHEMA_ID,
    DECISION_SCHEMA_ID,
    INTENT_LOG_SCHEMA_ID,
    assert_valid,
    validate_submission,
)
from .models import (
    ESCALATION_CEILING,
    LADDER,
    ActorKind,
    AdjudicationLogEntry,
    DecisionRecord,
    Disposition,
    Environment,
    EscalationFactor,
    GrantStatus,
    ImpactBasis,
    Intent,
    IntentLogEntry,
    Rejection,
)
from .pattern import action_pattern_key, pattern_fields, resolve_target_class
from .store import Store
from .weights import DEFAULT_WEIGHTS, WeightTable

logger = logging.getLogger("rmacd_intents")

Level = Literal["L1", "L2", "L3"]
Cell = tuple[DataClassification, Operation]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def level_index(level: AutonomyLevel) -> int:
    return LADDER.index(level)


def escalate(base: AutonomyLevel, steps: int) -> AutonomyLevel:
    """One-way, toward more oversight, stopping below ``prohibited`` (N-14, N-14a).

    A pinned or extended ``prohibited`` never arrives here: step 3 stops the
    algorithm before any factor runs.
    """
    if steps < 0:
        raise ValueError("escalation steps are never negative (N-19)")
    if base is AutonomyLevel.PROHIBITED:
        return base
    return LADDER[min(level_index(base) + steps, ESCALATION_CEILING)]


@dataclass(frozen=True)
class Graded:
    """What step 9 writes: the record, and whether a grant's own cap raised it."""

    record: DecisionRecord


class Engine:
    def __init__(
        self,
        store: Store,
        resolver: ActorResolver,
        *,
        weights: WeightTable = DEFAULT_WEIGHTS,
        policy_version: str = "unversioned",
        matrix_version: str = "1.4",
        implementation_level: Level = "L1",
        extended_prohibitions: Iterable[Cell] = (),
        default_profile: AnyProfile | None = None,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self.store = store
        self.resolver = resolver
        self.weights = weights
        self.policy_version = policy_version
        self.matrix_version = matrix_version
        self.implementation_level: Level = implementation_level
        # An organization may forbid more than the framework does, never less
        # (N-14b): the pinned set is always inside the extended one.
        self.extended_prohibitions: frozenset[Cell] = frozenset(extended_prohibitions)
        self.default_profile = default_profile
        self.clock = clock

    # ------------------------------------------------------------------ logging

    def _log_rejection(self, rejection: Rejection) -> Rejection:
        entry = IntentLogEntry(
            seq=self.store.next_seq(),
            logged_at=self.clock(),
            kind="rejection",
            intent_id=rejection.intent_id,
            document=rejection.document,
            raw=rejection.raw,
            failure=rejection.failure,
        )
        assert_valid(INTENT_LOG_SCHEMA_ID, entry.to_json_dict())
        self.store.append_intent(entry)
        return rejection

    def _log_submission(self, intent: Intent, document: dict[str, Any]) -> int:
        entry = IntentLogEntry(
            seq=self.store.next_seq(),
            logged_at=self.clock(),
            kind="submission",
            intent_id=intent.intent_id,
            document=document,
        )
        assert_valid(INTENT_LOG_SCHEMA_ID, entry.to_json_dict())
        return self.store.append_intent(entry)

    # ------------------------------------------------------------------- submit

    def submit(self, raw: bytes | str | dict[str, Any]) -> DecisionRecord | Rejection:
        """Steps 1–9 for one submission. Never raises on bad input."""
        document: dict[str, Any] | None = raw if isinstance(raw, dict) else None
        if document is None:
            text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
            try:
                parsed = json.loads(text)
                document = parsed if isinstance(parsed, dict) else None
            except json.JSONDecodeError:
                document = None
            if document is None:
                result = validate_submission(text)
                assert isinstance(result, Rejection)
                return self._log_rejection(result)

        # 1. Validate the envelope (N-1, N-52).
        result = validate_submission(document)
        if isinstance(result, Rejection):
            return self._log_rejection(result)
        intent = result

        # Still step 1: the facts the schema cannot see.
        if self.store.has_intent(intent.intent_id):
            return self._log_rejection(
                Rejection(
                    intent_id=intent.intent_id,
                    failure=f"intent_id {intent.intent_id} was already accepted (N-57)",
                    document=document,
                )
            )
        if intent.status not in (None, GrantStatus.REQUESTED):
            return self._log_rejection(
                Rejection(
                    intent_id=intent.intent_id,
                    failure="an actor submits a grant as 'requested' or with no status (N-71)",
                    document=document,
                )
            )

        # 2. Resolve the actor (N-5, N-6).
        resolution = self.resolver.resolve(intent.actor)
        if intent.actor.kind is not ActorKind.HUMAN and not resolution.accountable:
            return self._log_rejection(
                Rejection(
                    intent_id=intent.intent_id,
                    failure="actor.on_behalf_of is absent or does not resolve to an accountable "
                    "human or team (N-5)",
                    document=document,
                )
            )
        profile = resolution.profile or self.default_profile
        if profile is None:
            return self._log_rejection(
                Rejection(
                    intent_id=intent.intent_id,
                    failure="no profile is bound for this actor and the engine has no default; "
                    "there is no effective matrix to grade against (N-13)",
                    document=document,
                )
            )
        evaluator = PolicyEvaluator(profile)

        # Grants are graded by what they can cover, not what they declare
        # (N-66); a reach that touches a pinned cell is refused outright (N-29).
        if intent.is_grant:
            reach = self._grant_reach(intent)
            if any(cell in IMMUTABLE_PROHIBITIONS for cell in reach):
                return self._log_rejection(
                    Rejection(
                        intent_id=intent.intent_id,
                        failure="the grant's match rule or permission grid reaches a cell "
                        "framework §12.5 prohibits; no grant covers prohibited (N-29, N-66)",
                        document=document,
                    )
                )

        # Accepted. Everything from here produces exactly one decision record.
        self._log_submission(intent, document)
        return self._grade(intent, document, profile, evaluator, resolution.authorized)

    # -------------------------------------------------------------------- grade

    def _classification(
        self, intent: Intent, profile: AnyProfile
    ) -> tuple[DataClassification | None, str | None]:
        """The impact tier, with N-3 applied: missing on 3D/DC2D ⇒ the most sensitive tier."""
        tier = intent.declaration.data_classification
        if isinstance(profile, Profile2D):
            return None, None
        if tier is None:
            return DataClassification.RESTRICTED, (
                "data_classification absent in a classified deployment; graded as restricted (N-3)"
            )
        return tier, None

    def _grant_reach(self, intent: Intent) -> list[Cell]:
        """Every ``(tier, operation)`` cell a grant can cover (N-66)."""
        if intent.intent_type == "campaign" and intent.class_predicate is not None:
            pred = intent.class_predicate
            ops = [pred.operation] if pred.operation else list(Operation)
            tiers = (
                [pred.data_classification] if pred.data_classification else list(DataClassification)
            )
            return [(t, o) for t, o in product(tiers, ops)]
        if intent.intent_type == "exception" and intent.escalated_permissions is not None:
            grid = intent.escalated_permissions
            cells: list[Cell] = []
            for tier in DataClassification:
                ops_for_tier = getattr(grid, tier.value) or []
                cells.extend((tier, Operation(o)) for o in ops_for_tier)
            return cells
        return []

    def _grade(
        self,
        intent: Intent,
        document: dict[str, Any],
        profile: AnyProfile,
        evaluator: PolicyEvaluator,
        authorized: bool,
    ) -> DecisionRecord:
        factors: list[EscalationFactor] = []
        causes: list[str] = []
        op = intent.declaration.operation
        tier, tier_note = self._classification(intent, profile)
        if tier_note:
            causes.append(tier_note)

        target_class, class_note = resolve_target_class(intent)
        if class_note:
            causes.append(class_note)
        fields = pattern_fields(intent, target_class)

        prohibition: Literal["pinned", "extended"] | None = None
        # 3. The prohibited floor, pinned then extended, before anything else (N-12, N-14b).
        if tier is not None and (tier, op) in IMMUTABLE_PROHIBITIONS:
            prohibition = "pinned"
        elif tier is not None and (tier, op) in self.extended_prohibitions:
            prohibition = "extended"

        # 4. Base level from the effective matrix (N-13); a grant from its reach (N-66).
        if intent.is_grant:
            reach = self._grant_reach(intent)
            if reach:
                base = max(
                    (evaluator.required_autonomy(o, t) for t, o in reach), key=level_index
                )
            else:
                base = evaluator.required_autonomy(op, tier)
        else:
            base = evaluator.required_autonomy(op, tier)

        if prohibition is not None:
            computed = AutonomyLevel.PROHIBITED
        else:
            # 5. Likelihood factors, each ≥ 0 (N-17, N-19).
            factors.extend(
                self._factors(intent, profile, fields.model_dump(mode="json"), authorized, base)
            )
            steps = sum(f.steps for f in factors)
            # 6. Escalate one way, stopping below prohibited (N-14, N-14a).
            computed = escalate(base, steps)
            # 7. Bundle floor: the most restrictive level among the children (N-11).
            computed = self._bundle_floor(intent, computed, factors)
            # 8. Grant coverage approves in advance, never lowers (N-27, N-28) — L3;
            # at L1 a cited grant is simply not consulted and the intent routes to a
            # human. A grant's own level is never below its cap (N-67).
            if intent.is_grant and intent.caps is not None:
                cap = intent.caps.max_level
                if level_index(cap) > level_index(computed):
                    factors.append(
                        EscalationFactor(
                            factor="grant_cap",
                            steps=level_index(cap) - level_index(computed),
                            cause=f"raised to caps.max_level {cap.value} (N-67)",
                        )
                    )
                    computed = cap

        # 9. Emit the record (N-43, N-21, N-60, N-65, N-69, N-75).
        epoch = self.store.epoch()
        seq = self.store.next_seq()
        now = self.clock()
        decision_id = f"dec-{now.strftime('%Y%m%d%H%M%S')}-{seq}"
        record = DecisionRecord(
            decision_id=decision_id,
            intent_id=intent.intent_id,
            decided_at=now,
            action_pattern_key=(
                None if self.implementation_level == "L1" else action_pattern_key(fields)
            ),
            action_pattern_fields=fields if self.implementation_level == "L1" else None,
            base_level=base,
            computed_level=computed,
            escalation_factors=factors,
            impact_basis=ImpactBasis(
                scheme="data_classification", value=tier.value if tier else "unclassified"
            ),
            profile_id=profile.profile_id,
            implementation_level=self.implementation_level,
            matrix_version=self.matrix_version,
            likelihood_weights_version=self.weights.version,
            policy_version=self.policy_version,
            log_epoch=epoch,
            prohibition_source=prohibition,
        )
        for note in causes:
            # N-3 and N-24 want these recorded; the decision schema has no field
            # for a normalization note yet, so they go to the engine log for now.
            logger.info("%s: %s", intent.intent_id, note)
        assert_valid(DECISION_SCHEMA_ID, record.to_json_dict())
        entry = AdjudicationLogEntry(
            seq=seq, logged_at=now, kind="decision", decision_id=decision_id, record=record
        )
        assert_valid(ADJUDICATION_LOG_SCHEMA_ID, entry.to_json_dict())
        self.store.append_decision(entry)
        return record

    def _factors(
        self,
        intent: Intent,
        profile: AnyProfile,
        fields: dict[str, Any],
        authorized: bool,
        base: AutonomyLevel,
    ) -> list[EscalationFactor]:
        w = self.weights
        out: list[EscalationFactor] = []
        decl = intent.declaration

        # N-6: an unresolvable actor escalates to at least approval — every
        # operation except Read; Read too on confidential/restricted, and in
        # a deployment with no classification tier.
        if not authorized:
            tier = decl.data_classification
            read_exempt = decl.operation is Operation.READ and (
                not isinstance(profile, Profile2D)
                and tier in (DataClassification.PUBLIC, DataClassification.INTERNAL)
            )
            if not read_exempt:
                need = max(0, level_index(AutonomyLevel.APPROVAL) - level_index(base))
                out.append(
                    EscalationFactor(
                        factor="unresolved_authorization",
                        steps=need,
                        cause="actor.authorization could not be resolved; fail closed (N-6)",
                    )
                )

        # L1 Unprecedented: no reconciled success for this pattern (N-25, N-61).
        successes = self.store.reconciled_successes(fields)
        if successes == 0:
            out.append(
                EscalationFactor(
                    factor="precedent",
                    steps=w.unprecedented,
                    cause="no confirmed prior success for this action pattern; "
                    "the decision log holds 0 reconciled successes",
                )
            )

        # L2 Reversibility: an attested rollback path fails to add a step; a
        # self-attested one does not count (N-4, N-51).
        rev = decl.reversibility
        attested = bool(
            rev
            and rev.rollback_declared
            and rev.attested_by
            and rev.attested_by not in (intent.actor.id, intent.actor.on_behalf_of)
        )
        if not attested:
            out.append(
                EscalationFactor(
                    factor="reversibility",
                    steps=w.reversibility,
                    cause="no rollback path attested by a party other than the actor",
                )
            )

        # L3 Environment.
        if decl.environment in (Environment.PRODUCTION, Environment.DISASTER_RECOVERY):
            out.append(
                EscalationFactor(
                    factor="environment",
                    steps=w.environment,
                    cause=f"declared environment is {decl.environment.value}",
                )
            )

        # L4 Budget standing: at or over the profile's operations_per_hour (N-38, N-39).
        limit = _operations_per_hour(profile)
        if limit is not None:
            recent = self.store.accepted_by_actor_since(
                intent.actor.id, self.clock() - timedelta(hours=1)
            )
            # The submission being graded was logged before grading and counts.
            if recent > limit:
                out.append(
                    EscalationFactor(
                        factor="budget_standing",
                        steps=w.budget_standing,
                        cause=(
                            f"{recent} accepted intents in the last hour "
                            f"against a budget of {limit}"
                        ),
                    )
                )

        # L5 Blast radius against the profile's cap.
        cap = _blast_radius_cap(profile)
        declared = decl.blast_radius.scope_percentage if decl.blast_radius else None
        if cap is not None and declared is not None:
            if declared > cap:
                out.append(
                    EscalationFactor(
                        factor="blast_radius",
                        steps=w.blast_radius_over_cap,
                        cause=f"declared scope {declared}% exceeds the profile cap of {cap}%",
                    )
                )
            elif cap > 0 and declared >= w.near_cap_fraction * cap:
                out.append(
                    EscalationFactor(
                        factor="blast_radius",
                        steps=w.blast_radius_near_cap,
                        cause=(
                            f"declared scope {declared}% is within "
                            f"{int(w.near_cap_fraction * 100)}% of the cap of {cap}%"
                        ),
                    )
                )
        return [f for f in out if f.steps > 0 or f.factor == "unresolved_authorization"]

    def _bundle_floor(
        self, intent: Intent, computed: AutonomyLevel, factors: list[EscalationFactor]
    ) -> AutonomyLevel:
        """N-11: the most restrictive level among the bundle and its graded children.

        Ungraded children leave the level provisional; ``decide`` refuses
        until every child has a record (N-63).
        """
        for child_id in intent.children:
            child = self.store.decision_for(child_id)
            if child is None:
                continue
            if level_index(child.computed_level) > level_index(computed):
                factors.append(
                    EscalationFactor(
                        factor="composition_floor",
                        steps=level_index(child.computed_level) - level_index(computed),
                        cause=f"child {child_id} computed to {child.computed_level.value} (N-11)",
                    )
                )
                computed = child.computed_level
        return computed

    # ------------------------------------------------------------------- decide

    def decide(
        self,
        decision_id: str,
        outcome: Literal["approved", "approved_with_modifications", "deferred", "denied"],
        approver: str,
        note: str | None = None,
    ) -> Disposition:
        """Attach the human decision to a record (N-43), under N-63 and N-64."""
        record = self.store.decision(decision_id)
        if record is None:
            raise KeyError(f"no decision record {decision_id}")
        if self.store.disposition_count(decision_id) > 0:
            raise ValueError(f"{decision_id} already carries a disposition (N-43, N-74)")
        submission = self.store.submission(record.intent_id)
        if submission is None or submission.document is None:  # pragma: no cover - invariant
            raise RuntimeError(f"no submission logged for {record.intent_id}")
        intent = Intent.model_validate(submission.document)
        if approver in (intent.actor.id, intent.actor.on_behalf_of):
            raise ValueError(
                "the person deciding is the requesting actor or its accountable human (N-64)"
            )
        if record.computed_level is AutonomyLevel.PROHIBITED and outcome in (
            "approved",
            "approved_with_modifications",
        ):
            raise ValueError("no human decision can authorize a prohibited action (N-12)")
        ungraded = [c for c in intent.children if self.store.decision_for(c) is None]
        if ungraded:
            raise ValueError(
                f"bundle children not yet graded: {', '.join(ungraded)} (N-63)"
            )
        disposition = Disposition(
            outcome=outcome, approver=approver, decided_at=self.clock(), note=note
        )
        entry = AdjudicationLogEntry(
            seq=self.store.next_seq(),
            logged_at=self.clock(),
            kind="disposition",
            decision_id=decision_id,
            disposition=disposition,
        )
        assert_valid(ADJUDICATION_LOG_SCHEMA_ID, entry.to_json_dict())
        self.store.append_decision(entry)
        return disposition

    # --------------------------------------------------------------- transition

    def transition(self, intent_id: str, to_status: GrantStatus, changed_by: str) -> IntentLogEntry:
        """Move a grant through its lifecycle; every move is traced (N-71, N-68)."""
        submission = self.store.submission(intent_id)
        if submission is None or submission.document is None:
            raise KeyError(f"no accepted intent {intent_id}")
        intent = Intent.model_validate(submission.document)
        if not intent.is_grant:
            raise ValueError(f"{intent_id} is a {intent.intent_type}; only grants carry status")
        if to_status is GrantStatus.ACTIVE:
            record = self.store.decision_for(intent_id)
            if record is None or record.disposition is None or not record.disposition.permits:
                raise ValueError(
                    "a grant becomes active only on a recorded human decision permitting it (N-68)"
                )
        entry = IntentLogEntry(
            seq=self.store.next_seq(),
            logged_at=self.clock(),
            kind="transition",
            intent_id=intent_id,
            from_status=self.store.grant_status(intent_id),
            to_status=to_status,
            changed_by=changed_by,
        )
        assert_valid(INTENT_LOG_SCHEMA_ID, entry.to_json_dict())
        self.store.append_intent(entry)
        return entry


def _operations_per_hour(profile: AnyProfile) -> int | None:
    constraints = profile.constraints
    if constraints is None or constraints.rate_limits is None:
        return None
    limit = getattr(constraints.rate_limits, "operations_per_hour", None)
    return int(limit) if isinstance(limit, int) else None


def _blast_radius_cap(profile: AnyProfile) -> int | None:
    if isinstance(profile, ProfileDC2D):
        return None
    constraints = profile.constraints
    if constraints is None or constraints.change_controls is None:
        return None
    return int(constraints.change_controls.max_blast_radius_percentage)


__all__ = ["Engine", "escalate", "level_index", "Profile3D"]
