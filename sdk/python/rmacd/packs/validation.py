"""
RMACD Governance Packs - Schema Validation
==========================================

Validate a pack document against the bundled ``pack.schema.json`` (JSON Schema
Draft 2020-12). This is the *structural* gate; semantic checks (e.g. a rule
referencing an undeclared resolver) live in :mod:`rmacd.packs.engine`.

Author: Kash Kashyap
License: CC BY 4.0
"""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

SCHEMA_NAME = "pack.schema.json"


class PackValidationError(Exception):
    """Raised when a pack document fails schema validation."""

    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.errors = errors or []


_validator: Draft202012Validator | None = None


def _load_schema() -> dict[str, Any]:
    resource = resources.files("rmacd") / "schemas" / SCHEMA_NAME
    schema: dict[str, Any] = json.loads(resource.read_text(encoding="utf-8"))
    return schema


def get_schema() -> dict[str, Any]:
    """Return the bundled governance-pack JSON Schema."""
    return _load_schema()


def _get_validator() -> Draft202012Validator:
    global _validator
    if _validator is None:
        _validator = Draft202012Validator(_load_schema())
    return _validator


def _format_error(error: Any) -> str:
    path = ".".join(str(p) for p in error.absolute_path) if error.absolute_path else "<root>"
    return f"{path}: {error.message}"


def validate_pack_dict(data: dict[str, Any]) -> bool:
    """Validate a pack dict against the schema. Raises on failure, else True."""
    validator = _get_validator()
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    if errors:
        messages = [_format_error(e) for e in errors]
        raise PackValidationError(
            f"Pack schema validation failed with {len(messages)} error(s)",
            errors=messages,
        )
    return True


def is_valid_pack(data: dict[str, Any]) -> bool:
    """Return True if the pack dict is schema-valid, without raising."""
    try:
        return validate_pack_dict(data)
    except PackValidationError:
        return False


def validate_pack_file(path: str | Path) -> bool:
    """Validate a JSON pack file against the schema."""
    with open(Path(path), encoding="utf-8") as f:
        data = json.load(f)
    return validate_pack_dict(data)


__all__ = [
    "SCHEMA_NAME",
    "PackValidationError",
    "get_schema",
    "validate_pack_dict",
    "is_valid_pack",
    "validate_pack_file",
]
