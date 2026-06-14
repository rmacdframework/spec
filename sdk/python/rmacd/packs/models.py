"""
RMACD Governance Packs - Data Model
===================================

A *governance pack* is a declarative, reusable, signable bundle of rules that
map a concrete tool call ``(tool_name, args)`` to RMACD terms
``(operation, data tier, target)`` — as data, not hand-written code. This module
defines the pack data model, canonical serialization, and content hashing.

The model mirrors ``schemas/pack.schema.json``. A pack is authored in YAML or
JSON; the *canonical* form used for hashing and signing is compact, key-sorted
JSON with the ``content_hash`` and ``signature`` fields removed.

Runtime classification is performed by ``rmacd.packs.engine`` (Phase 1), which
compiles each :class:`Rule` into the ``ToolClassifier`` callable the registry
already understands. Nothing here gates a tool call — the §12.5 floor, the agent
profile, and the tool capability ceiling remain the authoritative runtime gates.

Author: Kash Kashyap
License: CC BY 4.0
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# RMACD enum *values* (R/M/A/C/D and the four tiers) expressed as Literals so a
# pack round-trips as plain strings without importing the runtime enums here.
OperationStr = Literal["R", "M", "A", "C", "D"]
TierStr = Literal["public", "internal", "confidential", "restricted"]


class _Strict(BaseModel):
    """Base model: reject unknown keys, allow population by field name or alias."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ArgRegex(_Strict):
    """A regular expression matched against a (possibly dot-pathed) argument."""

    arg: str
    pattern: str


class ArgvContains(_Strict):
    """An ordered token sequence that must appear in a parsed command argument."""

    arg: str
    tokens: list[str]


class Selector(_Strict):
    """Conditions deciding whether a rule applies to a call (ANDed together)."""

    tool: str | list[str] | None = None
    arg_equals: dict[str, Any] | None = None
    arg_present: str | None = None
    arg_regex: ArgRegex | None = None
    argv_contains: ArgvContains | None = None


class ParseSpec(_Strict):
    """How to turn a string argument into tokens for verb matching."""

    arg: str
    strip_wrappers: list[str] = Field(default_factory=list)
    delimiter: str | None = None
    token: Literal["first", "last"] | None = None
    verb_prefix_delimiters: list[str] = Field(default_factory=list)


class PatternMapEntry(_Strict):
    """A single ``arg_regex -> tier`` mapping in a tier ``pattern_map``."""

    arg_regex: ArgRegex
    tier: TierStr


class TierSpec(_Strict):
    """Object form of a tier rule.

    ``pattern_map`` is tried first (most-sensitive match wins), then the named
    ``resolver`` (fed the ``from`` argument), then ``default``. A bare tier
    string is also accepted wherever a ``TierSpec`` is allowed.
    """

    pattern_map: list[PatternMapEntry] | None = None
    resolver: str | None = None
    from_arg: str | None = Field(default=None, alias="from")
    default: TierStr | None = None


# A tier may be a bare string or the object form above.
TierField = TierStr | TierSpec


class ClassifySpec(_Strict):
    """Literal classification form (fixed operation)."""

    operation: OperationStr | None = None
    tier: TierField | None = None
    target: str | None = None


class Rule(_Strict):
    """A single classification rule.

    Operation source is either ``classify.operation`` / ``operation`` (a literal)
    or ``verb_table`` (with a fail-closed ``default``); tier and target may be
    given inline or via ``classify``. See ``docs/governance-packs/``.
    """

    id: str
    when: Selector
    parse: ParseSpec | None = None
    classify: ClassifySpec | None = None
    operation: OperationStr | None = None
    verb_table: dict[str, OperationStr] | None = None
    default: OperationStr | None = None
    tier: TierField | None = None
    target: str | None = None
    capability: list[OperationStr] | None = None
    confidence: Literal["high", "low"] = "high"


class ResolverDecl(_Strict):
    """A named live-lookup hook the pack expects to be registered at runtime."""

    name: str
    description: str = ""
    fail_closed_default: TierStr = "restricted"


class Provenance(BaseModel):
    """Authoring/review metadata (open-ended)."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    authored_by: str | None = None
    llm_assisted: bool | None = None
    reviewed_by: str | None = None
    source_hash: str | None = None


class GovernancePack(_Strict):
    """A declarative governance pack — the top-level artifact."""

    pack: str
    version: str
    description: str = ""
    default_operation: OperationStr = "C"
    provenance: Provenance | None = None
    content_hash: str | None = None
    signature: str | None = None
    resolvers: list[ResolverDecl] = Field(default_factory=list)
    rules: list[Rule]

    # ----- (de)serialization -------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict using schema field names (``from``, etc.)."""
        return self.model_dump(by_alias=True, exclude_none=True, mode="json")

    def to_json(self, *, indent: int | None = 2) -> str:
        """Serialize to a JSON string (human-readable by default)."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GovernancePack:
        """Build a pack from a plain dict (validating it against the model)."""
        return cls.model_validate(data)

    @classmethod
    def from_json(cls, text: str) -> GovernancePack:
        """Build a pack from a JSON string."""
        return cls.model_validate(json.loads(text))

    # ----- canonical form + hashing ------------------------------------------

    def canonical_dict(self) -> dict[str, Any]:
        """The dict hashed/signed: schema field names, minus hash + signature."""
        data = self.to_dict()
        data.pop("content_hash", None)
        data.pop("signature", None)
        return data

    def canonical_json(self) -> str:
        """Deterministic JSON: key-sorted, compact, UTF-8 — stable across runs."""
        return json.dumps(
            self.canonical_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    def compute_content_hash(self) -> str:
        """Return the canonical content hash as ``sha256:<hex>``."""
        digest = hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()
        return f"sha256:{digest}"

    def freeze(self) -> GovernancePack:
        """Return a copy with ``content_hash`` set to the computed hash."""
        return self.model_copy(update={"content_hash": self.compute_content_hash()})

    def verify_hash(self) -> bool:
        """True if ``content_hash`` is set and matches the canonical content."""
        return self.content_hash is not None and self.content_hash == self.compute_content_hash()


__all__ = [
    "OperationStr",
    "TierStr",
    "TierField",
    "ArgRegex",
    "ArgvContains",
    "Selector",
    "ParseSpec",
    "PatternMapEntry",
    "TierSpec",
    "ClassifySpec",
    "Rule",
    "ResolverDecl",
    "Provenance",
    "GovernancePack",
]
