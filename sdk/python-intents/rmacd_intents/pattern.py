"""Action patterns: target normalization and the six-field key (spec §6).

Whatever the pattern excludes becomes a gradient an actor can walk down to
erode its own scrutiny, so the fields are exactly the six of N-22 and the
bytes are RFC 8785 (N-56). ``target_class`` is derived the same way every
time and the derivation wins over anything the actor supplied (N-23, N-24).
"""

from __future__ import annotations

import hashlib
import re

import rfc8785

from .models import ActionPatternFields, Intent

_LAST_SEGMENT = re.compile(r"([^/:]+)$")


def derive_target_class(target: str) -> tuple[str, str]:
    """``(target_class, rule)`` for a target with no matching pack rule.

    The default rule replaces the final identifier segment with ``*``
    (N-23). A target that already ends in ``*`` is its own class. The rule
    name is recorded in the decision record's cause so an auditor can see
    which normalization produced the class.
    """
    if target.endswith("*"):
        return target, "literal-wildcard"
    m = _LAST_SEGMENT.search(target)
    if not m or m.start() == 0:
        return target, "no-segment"
    return target[: m.start()] + "*", "last-segment-wildcard"


def resolve_target_class(intent: Intent) -> tuple[str, str | None]:
    """The class the engine uses, and a discrepancy note if the actor's differed (N-24)."""
    derived, rule = derive_target_class(intent.declaration.target)
    supplied = intent.declaration.target_class
    if supplied is not None and supplied != derived:
        return derived, (
            f"actor supplied target_class {supplied!r}; derived {derived!r} by {rule} governs"
        )
    return derived, None


def pattern_fields(intent: Intent, target_class: str) -> ActionPatternFields:
    return ActionPatternFields(
        intent_type=intent.intent_type,
        operation=intent.declaration.operation,
        data_classification=intent.declaration.data_classification,
        environment=intent.declaration.environment.value,
        target_class=target_class,
        actor_kind=intent.actor.kind,
    )


def action_pattern_key(fields: ActionPatternFields) -> str:
    """``sha256:<hex>`` over the RFC 8785 canonical bytes of exactly the six fields."""
    payload = {
        "intent_type": fields.intent_type,
        "declaration.operation": fields.operation.value,
        "declaration.data_classification": (
            fields.data_classification.value if fields.data_classification else None
        ),
        "declaration.environment": fields.environment,
        "declaration.target_class": fields.target_class,
        "actor.kind": fields.actor_kind.value,
    }
    canonical: bytes = rfc8785.dumps(payload)
    return "sha256:" + hashlib.sha256(canonical).hexdigest()
