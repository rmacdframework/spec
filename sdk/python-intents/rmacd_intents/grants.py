"""Grants: coverage, match rules and the grant's own bounds (spec §7).

Coverage is approval recorded in advance, never a discount (N-27). A child is
covered only when every one of N-28's six conditions holds; the pure
conditions are evaluated here, and the one that consumes capacity — the
child cap — is left to the store so it can be checked and consumed under one
lock (N-55).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from fnmatch import fnmatchcase

from rmacd import AutonomyLevel, DataClassification, Operation

from .models import LADDER, GrantStatus, Intent


@dataclass(frozen=True)
class Coverage:
    covered: bool
    reason: str
    #: Set when every pure condition held and only the child cap remains.
    max_children: int | None = None


def is_blanket(intent: Intent) -> str | None:
    """N-32: a match rule that would cover every intent of a type is refused."""
    if intent.intent_type != "campaign" or intent.class_predicate is None:
        return None
    fields = {
        k: v for k, v in intent.class_predicate.model_dump().items() if v is not None
    }
    narrowing = {k: v for k, v in fields.items() if k != "intent_type"}
    if not narrowing:
        return "class_predicate names no field beyond intent_type; that is a blanket grant (N-32)"
    if set(narrowing) == {"target_class"} and str(narrowing["target_class"]).strip("*") == "":
        return "class_predicate matches every target; that is a blanket grant (N-32)"
    return None


def predicate_matches(grant: Intent, child: Intent, child_target_class: str) -> bool:
    """N-30, N-31: every named field matches, wildcards only in target_class."""
    pred = grant.class_predicate
    if pred is None:
        return False
    checks: list[tuple[object, object]] = []
    if pred.intent_type is not None:
        checks.append((pred.intent_type, child.intent_type))
    if pred.operation is not None:
        checks.append((pred.operation, child.declaration.operation))
    if pred.data_classification is not None:
        checks.append((pred.data_classification, child.declaration.data_classification))
    if pred.environment is not None:
        checks.append((pred.environment, child.declaration.environment))
    if pred.actor_id is not None:
        checks.append((pred.actor_id, child.actor.id))
    if pred.on_behalf_of is not None:
        checks.append((pred.on_behalf_of, child.actor.on_behalf_of))
    if any(a != b for a, b in checks):
        return False
    if pred.target_class is not None and not fnmatchcase(child_target_class, pred.target_class):
        return False
    return True


def grid_admits(grant: Intent, tier: DataClassification | None, op: Operation) -> bool:
    grid = grant.escalated_permissions
    if grid is None or tier is None:
        return False
    ops = getattr(grid, tier.value) or []
    return op.value in {o if isinstance(o, str) else o.value for o in ops}


def evaluate_coverage(
    grant: Intent,
    grant_status: GrantStatus | None,
    child: Intent,
    child_target_class: str,
    child_tier: DataClassification | None,
    child_level: AutonomyLevel,
    child_profile_id: str,
    now: datetime,
) -> Coverage:
    """The five pure conditions of N-28, plus the exception binding (condition 6)."""
    if not grant.is_grant:
        return Coverage(False, f"{grant.intent_id} is not a grant")
    # 1. inside the declared bounds
    if grant.intent_type == "campaign":
        if not predicate_matches(grant, child, child_target_class):
            return Coverage(False, "child does not match the campaign's class match rule")
    else:
        if not grid_admits(grant, child_tier, child.declaration.operation):
            return Coverage(
                False, "child's (classification, operation) is outside the exception's grid"
            )
        # 6. an exception covers only the profile and actor it names
        if grant.base_profile_id != child_profile_id:
            return Coverage(False, "child is not bound to the exception's base_profile_id")
        if child.actor.id != grant.actor.id and (
            child.actor.on_behalf_of is None or child.actor.on_behalf_of != grant.actor.on_behalf_of
        ):
            return Coverage(False, "child is not the actor the exception names")
    # 5. never prohibited
    if child_level is AutonomyLevel.PROHIBITED:
        return Coverage(False, "no grant covers a prohibited child (N-29)")
    # 2. not above the level the human approved the grant at
    if grant.caps is not None and LADDER.index(child_level) > LADDER.index(grant.caps.max_level):
        return Coverage(
            False,
            f"child computed to {child_level.value}, above the grant's max_level "
            f"{grant.caps.max_level.value}",
        )
    # 3. active and unexpired
    if grant_status is not GrantStatus.ACTIVE:
        status = grant_status.value if grant_status else "unknown"
        return Coverage(False, f"grant is {status}, not active")
    if grant.expires_at is not None and grant.expires_at <= now:
        return Coverage(False, "grant has expired")
    # 4. caps other than the child count
    if grant.caps is not None and grant.caps.max_blast_radius_percentage is not None:
        blast = child.declaration.blast_radius
        declared = blast.scope_percentage if blast else None
        if declared is None or declared > grant.caps.max_blast_radius_percentage:
            return Coverage(False, "child's blast radius is undeclared or exceeds the grant's cap")
    return Coverage(True, "covered", max_children=grant.caps.max_children if grant.caps else None)
