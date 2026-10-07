"""Step 1 of adjudication: validate the envelope (spec §2, N-1).

A submission is bytes until the bundled schema says otherwise. Anything that
fails is a ``Rejection`` carrying the document (or the raw text where it was
not JSON) and the failure, which is exactly what the intent log keeps (N-59,
N-73). Nothing malformed is ever graded or defaulted.
"""

from __future__ import annotations

import json
from functools import cache
from importlib import resources
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError
from pydantic import ValidationError as PydanticValidationError
from referencing import Registry, Resource

from .models import Intent, Rejection

SCHEMA_NAMES = (
    "intent.schema.json",
    "intent-decision.schema.json",
    "intent-log-entry.schema.json",
    "adjudication-log-entry.schema.json",
)
INTENT_SCHEMA_ID = "https://rmacd-framework.org/schema/v2/intent.json"
DECISION_SCHEMA_ID = "https://rmacd-framework.org/schema/v2/intent-decision.json"
INTENT_LOG_SCHEMA_ID = "https://rmacd-framework.org/schema/v2/intent-log-entry.json"
ADJUDICATION_LOG_SCHEMA_ID = "https://rmacd-framework.org/schema/v2/adjudication-log-entry.json"


def load_schema(name: str) -> dict[str, Any]:
    text = resources.files("rmacd_intents.schemas").joinpath(name).read_text(encoding="utf-8")
    loaded: dict[str, Any] = json.loads(text)
    return loaded


@cache
def _registry() -> Registry:
    schemas = [load_schema(n) for n in SCHEMA_NAMES]
    return Registry().with_resources([(s["$id"], Resource.from_contents(s)) for s in schemas])


@cache
def validator_for(schema_id: str) -> Draft202012Validator:
    schema = next(s for s in (load_schema(n) for n in SCHEMA_NAMES) if s["$id"] == schema_id)
    return Draft202012Validator(schema, registry=_registry(), format_checker=FormatChecker())


def _describe(err: ValidationError) -> str:
    path = "/".join(str(p) for p in err.absolute_path) or "(root)"
    return f"{path}: {err.message}"


def validate_submission(raw: bytes | str | dict[str, Any]) -> Intent | Rejection:
    """Parse and validate one submission; never raises on bad input."""
    document: dict[str, Any] | None = None
    text: str | None = None
    if isinstance(raw, dict):
        document = raw
    else:
        text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            return Rejection(failure=f"not valid JSON: {exc.msg} at position {exc.pos}", raw=text)
        if not isinstance(parsed, dict):
            return Rejection(failure="a submission must be a JSON object", raw=text)
        document = parsed

    intent_id = document.get("intent_id") if isinstance(document.get("intent_id"), str) else None
    errors = sorted(
        validator_for(INTENT_SCHEMA_ID).iter_errors(document), key=lambda e: list(e.path)
    )
    if errors:
        failure = "; ".join(_describe(e) for e in errors[:5])
        if len(errors) > 5:
            failure += f"; and {len(errors) - 5} more"
        return Rejection(intent_id=intent_id, failure=failure, document=document)
    try:
        intent = Intent.model_validate(document)
    except PydanticValidationError as exc:  # pragma: no cover - schema should catch first
        return Rejection(intent_id=intent_id, failure=str(exc), document=document)
    if intent.valid_until is not None and intent.valid_until <= intent.submitted_at:
        return Rejection(
            intent_id=intent_id,
            failure="valid_until must be later than submitted_at (N-52)",
            document=document,
        )
    return intent


def assert_valid(schema_id: str, document: dict[str, Any]) -> None:
    """Raise if ``document`` does not conform; used on everything the engine emits."""
    errors = list(validator_for(schema_id).iter_errors(document))
    if errors:
        raise ValueError("; ".join(_describe(e) for e in errors[:5]))
