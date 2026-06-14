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
import re
from importlib import resources
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

SCHEMA_NAME = "pack.schema.json"

# ReDoS guard: pattern length cap and a heuristic for nested quantifiers like
# "(a+)+" / "(a*)*" that can cause catastrophic backtracking.
_MAX_PATTERN_LEN = 1000
_NESTED_QUANTIFIER = re.compile(r"\([^()]*[+*][^()]*\)\s*[+*]")


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


def _iter_regex_patterns(data: dict[str, Any]) -> list[tuple[str, str]]:
    """Yield (location, pattern) for every regex a pack would compile at runtime."""
    found: list[tuple[str, str]] = []

    def _scan_tier(loc: str, tier: Any) -> None:
        if isinstance(tier, dict):
            for i, entry in enumerate(tier.get("pattern_map") or []):
                ar = entry.get("arg_regex") if isinstance(entry, dict) else None
                if isinstance(ar, dict) and "pattern" in ar:
                    found.append((f"{loc}.pattern_map[{i}]", ar["pattern"]))

    for i, rule in enumerate(data.get("rules") or []):
        if not isinstance(rule, dict):
            continue
        loc = f"rules[{i}]({rule.get('id', '?')})"
        when = rule.get("when") or {}
        ar = when.get("arg_regex") if isinstance(when, dict) else None
        if isinstance(ar, dict) and "pattern" in ar:
            found.append((f"{loc}.when.arg_regex", ar["pattern"]))
        _scan_tier(f"{loc}.tier", rule.get("tier"))
        classify = rule.get("classify")
        if isinstance(classify, dict):
            _scan_tier(f"{loc}.classify.tier", classify.get("tier"))
    return found


def find_redos_risks(data: dict[str, Any]) -> list[str]:
    """Return human-readable warnings for pack regexes that look ReDoS-prone."""
    risks: list[str] = []
    for loc, pattern in _iter_regex_patterns(data):
        if len(pattern) > _MAX_PATTERN_LEN:
            risks.append(f"{loc}: pattern too long ({len(pattern)} > {_MAX_PATTERN_LEN})")
        if _NESTED_QUANTIFIER.search(pattern):
            risks.append(
                f"{loc}: nested quantifier (ReDoS backtracking risk): {pattern!r}"
            )
        try:
            re.compile(pattern)
        except re.error as exc:
            risks.append(f"{loc}: invalid regex: {exc}")
    return risks


__all__ = [
    "SCHEMA_NAME",
    "PackValidationError",
    "get_schema",
    "validate_pack_dict",
    "is_valid_pack",
    "validate_pack_file",
    "find_redos_risks",
]
