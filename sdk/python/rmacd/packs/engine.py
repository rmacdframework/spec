"""
RMACD Governance Packs - Declarative Classification Engine
==========================================================

Compile a :class:`~rmacd.packs.models.GovernancePack` into runtime classification
of a tool call ``(tool_name, args)`` to RMACD terms ``(operation, tier, target)``.

The engine is fully deterministic and fail-closed:

- **Selectors** decide which rules apply (tool-name exact/glob/regex + argument
  predicates).
- **Extraction** turns a string argument into verb tokens (shell tokenization with
  wrapper stripping and ``$(...)`` recursion, or a simple delimiter split for SDK
  method names).
- **verb_table** maps tokens to operations, taking the **MAX** operation over all
  matched tokens; an unmatched verb falls back to the rule/pack default.
- **pattern_map / resolver** decide the data tier (most-sensitive wins); a resolver
  failure falls back to its declared ``fail_closed_default``.
- **Cross-rule combination** takes the highest operation and the most sensitive
  tier across every matching rule (so a tier-only overlay rule can raise the tier
  without touching the operation).

:class:`DeclarativeClassifier` binds a pack + a concrete tool name into the
``ToolClassifier`` callable the registry already understands, so a compiled rule
is a drop-in for a hand-written classifier — no enforcer changes.

Author: Kash Kashyap
License: CC BY 4.0
"""

from __future__ import annotations

import logging
import re
import shlex
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from typing import Any

from rmacd.packs.models import (
    GovernancePack,
    ParseSpec,
    Rule,
    Selector,
    TierSpec,
)

logger = logging.getLogger(__name__)

# ----- orderings (by string value; independent of enum declaration order) ----
_OP_RANK: dict[str, int] = {"R": 0, "M": 1, "A": 2, "C": 3, "D": 4}
_TIER_RANK: dict[str, int] = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}

# Cap the input length fed to pack-supplied regexes (ReDoS defence in depth;
# the validator also flags risky patterns at authoring time).
_MAX_REGEX_INPUT = 8192

# See the bash classifier's _SPLIT_RE: `(?<!>)&(?![&>])` treats a bare `&`
# (background operator) as a separator while sparing `&&`, `&>`, and `2>&1`.
# (Code review C2, 2026-07-19.)
_SEGMENT_SEP = re.compile(r"\|\||&&|(?<!>)&(?![&>])|\||;|\n")
_SUBSHELL = re.compile(r"\$\(([^()]*)\)")
_BACKTICK = re.compile(r"`([^`]*)`")
_TEMPLATE_TOKEN = re.compile(r"\{([^{}]+)\}")


# ----- resolvers -------------------------------------------------------------
@dataclass
class ResolverContext:
    """Context passed to a tier resolver alongside the looked-up argument value."""

    tool_name: str
    args: dict[str, Any]
    arg_name: str | None = None


# A resolver maps an argument value (+ context) to a tier string. Returning None
# or raising triggers the rule's fail-closed default.
ResolverFn = Callable[[str, ResolverContext], "str | None"]


@dataclass
class ResolverLookup:
    """Record of a single resolver invocation (for audit reconstructability)."""

    resolver: str
    arg: str | None
    value: Any
    result: str
    failed: bool


@dataclass
class ClassificationResult:
    """The outcome of classifying a call against a pack."""

    operation: str
    tier: str | None
    target: str | None
    matched_rule_ids: list[str] = field(default_factory=list)
    capability: list[str] | None = None
    resolver_lookups: list[ResolverLookup] = field(default_factory=list)


# ----- argument access -------------------------------------------------------
def _get_arg(args: Mapping[str, Any], path: str) -> Any:
    """Look up an argument by name or dot-path (e.g. ``params.Bucket``)."""
    cur: Any = args
    for part in path.split("."):
        if isinstance(cur, Mapping) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


# ----- tokenization ----------------------------------------------------------
def _strip_wrappers(tokens: list[str], wrappers: list[str]) -> list[str]:
    """Drop leading wrapper binaries (sudo/env/...) and their option/assignment args."""
    i = 0
    while i < len(tokens) and tokens[i] in wrappers:
        i += 1
        while i < len(tokens) and ("=" in tokens[i] or tokens[i].startswith("-")):
            i += 1
    return tokens[i:]


def _shell_tokens(command: str, wrappers: list[str]) -> list[str]:
    """Tokenize a shell command across pipes/sub-commands; returns all verb tokens."""
    tokens: list[str] = []
    for segment in (s for s in _SEGMENT_SEP.split(command) if s.strip()):
        # Recurse into $(...) and `...` first, then strip them from the segment.
        for sub in _SUBSHELL.findall(segment) + _BACKTICK.findall(segment):
            tokens.extend(_shell_tokens(sub, wrappers))
        cleaned = _BACKTICK.sub(" ", _SUBSHELL.sub(" ", segment))
        try:
            seg_tokens = shlex.split(cleaned)
        except ValueError:
            seg_tokens = cleaned.split()
        tokens.extend(_strip_wrappers(seg_tokens, wrappers))
    return tokens


def _verb_tokens(value: str, parse: ParseSpec | None) -> list[str]:
    """Produce the tokens a verb_table matches against."""
    if parse is not None and parse.delimiter is not None:
        parts = value.split(parse.delimiter)
        if parse.token == "first":
            return parts[:1]
        if parse.token == "last":
            return parts[-1:]
        return parts
    wrappers = parse.strip_wrappers if parse is not None else []
    return _shell_tokens(value, wrappers)


# ----- selector evaluation ---------------------------------------------------
def _match_tool(pattern: str | list[str] | None, tool_name: str) -> bool:
    """Match a tool name against an exact/glob/``/regex/`` pattern (or a list)."""
    if pattern is None:
        return True
    if isinstance(pattern, list):
        return any(_match_tool(p, tool_name) for p in pattern)
    if len(pattern) >= 2 and pattern.startswith("/") and pattern.endswith("/"):
        return re.fullmatch(pattern[1:-1], tool_name) is not None
    if "*" in pattern or "?" in pattern or "[" in pattern:
        return fnmatchcase(tool_name, pattern)
    return pattern == tool_name


def _selector_matches(sel: Selector, tool_name: str, args: Mapping[str, Any]) -> bool:
    if not _match_tool(sel.tool, tool_name):
        return False
    if sel.arg_present is not None:
        val = _get_arg(args, sel.arg_present)
        if val is None or val == "":
            return False
    if sel.arg_equals is not None:
        for name, expected in sel.arg_equals.items():
            if _get_arg(args, name) != expected:
                return False
    if sel.arg_regex is not None:
        val = _get_arg(args, sel.arg_regex.arg)
        if not isinstance(val, str) or (
            re.search(sel.arg_regex.pattern, val[:_MAX_REGEX_INPUT]) is None
        ):
            return False
    if sel.argv_contains is not None:
        val = _get_arg(args, sel.argv_contains.arg)
        if not isinstance(val, str):
            return False
        tokens = _shell_tokens(val, [])
        it = iter(tokens)
        if not all(tok in it for tok in sel.argv_contains.tokens):
            return False
    return True


# ----- operation / tier / target resolution ---------------------------------
def _max_op(ops: Sequence[str]) -> str | None:
    return max(ops, key=lambda o: _OP_RANK[o]) if ops else None


def _most_sensitive(tiers: Sequence[str]) -> str | None:
    return max(tiers, key=lambda t: _TIER_RANK[t]) if tiers else None


def _rule_operation(rule: Rule, args: Mapping[str, Any]) -> str | None:
    """The operation a single rule asserts, or None if it asserts none."""
    if rule.classify is not None and rule.classify.operation is not None:
        return rule.classify.operation
    if rule.operation is not None:
        return rule.operation
    if rule.verb_table is not None:
        value = _get_arg(args, rule.parse.arg) if rule.parse is not None else None
        tokens = _verb_tokens(value, rule.parse) if isinstance(value, str) else []
        delims = rule.parse.verb_prefix_delimiters if rule.parse is not None else []
        matched = [op for t in tokens if (op := _match_verb(t, rule.verb_table, delims))]
        return _max_op(matched) or rule.default
    return None


def _match_verb(token: str, verb_table: Mapping[str, str], delims: list[str]) -> str | None:
    """Match a token against the verb table, optionally by prefix before a delimiter.

    Matching is case-insensitive (verb tables are lowercase by convention, so SQL
    ``SELECT`` matches ``select``). A direct hit wins; otherwise the token's prefix
    before any configured delimiter is tried (so ``describe-instances`` matches a
    ``describe`` verb).
    """
    t = token.lower()
    if t in verb_table:
        return verb_table[t]
    for d in delims:
        prefix = t.split(d, 1)[0]
        if prefix and prefix in verb_table:
            return verb_table[prefix]
    return None


def _resolve_tier(
    spec: str | TierSpec | None,
    tool_name: str,
    args: Mapping[str, Any],
    resolvers: Mapping[str, ResolverFn],
    fail_closed_defaults: Mapping[str, str],
    lookups: list[ResolverLookup],
) -> str | None:
    """Resolve a tier spec to a tier, fail-closed. Records any resolver lookup."""
    if spec is None:
        return None
    if isinstance(spec, str):
        return spec

    candidates: list[str] = []

    if spec.pattern_map:
        for entry in spec.pattern_map:
            val = _get_arg(args, entry.arg_regex.arg)
            if isinstance(val, str) and (
                re.search(entry.arg_regex.pattern, val[:_MAX_REGEX_INPUT]) is not None
            ):
                candidates.append(entry.tier)

    if spec.resolver is not None:
        arg_name = spec.from_arg
        value = _get_arg(args, arg_name) if arg_name is not None else None
        fn = resolvers.get(spec.resolver)
        fail_default = fail_closed_defaults.get(spec.resolver, "restricted")
        result: str | None = None
        failed = False
        if fn is not None and value is not None:
            try:
                result = fn(str(value), ResolverContext(tool_name, dict(args), arg_name))
            except Exception:  # noqa: BLE001 — any resolver failure is fail-closed
                result = None
        if result is None:
            failed = True
            result = fail_default
        lookup = ResolverLookup(
            resolver=spec.resolver, arg=arg_name, value=value, result=result, failed=failed
        )
        lookups.append(lookup)
        # Audit-trail the resolution so a (non-deterministic) live lookup stays
        # reconstructable. Failures are warned; successes logged at debug.
        if failed:
            logger.warning(
                "resolver '%s' fell back to '%s' (arg %s=%r)",
                spec.resolver, result, arg_name, value,
            )
        else:
            logger.debug(
                "resolver '%s' -> '%s' (arg %s=%r)", spec.resolver, result, arg_name, value
            )
        candidates.append(result)

    if candidates:
        return _most_sensitive(candidates)
    return spec.default


def _render_target(template: str | None, args: Mapping[str, Any]) -> str | None:
    """Substitute ``{arg}`` / ``{dot.path}`` tokens; leave unknown tokens literal."""
    if template is None:
        return None

    def repl(match: re.Match[str]) -> str:
        value = _get_arg(args, match.group(1))
        return str(value) if value is not None else match.group(0)

    return _TEMPLATE_TOKEN.sub(repl, template)


def _rule_tier_spec(rule: Rule) -> str | TierSpec | None:
    if rule.classify is not None and rule.classify.tier is not None:
        return rule.classify.tier
    return rule.tier


def _rule_target(rule: Rule) -> str | None:
    if rule.classify is not None and rule.classify.target is not None:
        return rule.classify.target
    return rule.target


# ----- top-level classification ----------------------------------------------
def classify_call(
    pack: GovernancePack,
    tool_name: str,
    args: Mapping[str, Any] | None = None,
    *,
    resolvers: Mapping[str, ResolverFn] | None = None,
) -> ClassificationResult:
    """Classify a tool call against a pack, combining all matching rules."""
    args = args or {}
    resolvers = resolvers if resolvers is not None else get_resolvers()
    fail_closed_defaults = {r.name: r.fail_closed_default for r in pack.resolvers}

    ops: list[str] = []
    tiers: list[str] = []
    target: str | None = None
    matched_ids: list[str] = []
    capability: set[str] = set()
    lookups: list[ResolverLookup] = []

    for rule in pack.rules:
        if not _selector_matches(rule.when, tool_name, args):
            continue
        matched_ids.append(rule.id)

        op = _rule_operation(rule, args)
        if op is not None:
            ops.append(op)

        tier = _resolve_tier(
            _rule_tier_spec(rule), tool_name, args, resolvers, fail_closed_defaults, lookups
        )
        if tier is not None:
            tiers.append(tier)

        if target is None:
            target = _render_target(_rule_target(rule), args)

        if rule.capability:
            capability.update(rule.capability)

    operation = _max_op(ops) or pack.default_operation
    return ClassificationResult(
        operation=operation,
        tier=_most_sensitive(tiers),
        target=target,
        matched_rule_ids=matched_ids,
        capability=sorted(capability, key=lambda o: _OP_RANK[o]) if capability else None,
        resolver_lookups=lookups,
    )


def capability_for(pack: GovernancePack, tool_name: str) -> list[str] | None:
    """The union of capability ceilings declared by rules that can match this tool.

    Selector argument predicates are ignored here (capability is a static ceiling
    derived from tool-name matches), so a passthrough tool keeps its worst-case
    ceiling regardless of which concrete arguments a call carries.
    """
    caps: set[str] = set()
    for rule in pack.rules:
        if rule.capability and _match_tool(rule.when.tool, tool_name):
            caps.update(rule.capability)
    return sorted(caps, key=lambda o: _OP_RANK[o]) if caps else None


class DeclarativeClassifier:
    """A pack rule-set bound to one tool name, callable as a ``ToolClassifier``.

    Calling it with a tool call's ``args`` returns ``(operation, tier, target)``
    as strings — exactly the shape ``ToolDefinition.classifier`` expects, so a
    compiled pack rule is a drop-in for a hand-written classifier.
    """

    def __init__(
        self,
        pack: GovernancePack,
        tool_name: str,
        *,
        resolvers: Mapping[str, ResolverFn] | None = None,
    ) -> None:
        self.pack = pack
        self.tool_name = tool_name
        self._resolvers = resolvers

    def resolve(self, args: Mapping[str, Any] | None = None) -> ClassificationResult:
        """Full classification result (operation/tier/target + provenance)."""
        return classify_call(self.pack, self.tool_name, args, resolvers=self._resolvers)

    def __call__(
        self, args: dict[str, Any]
    ) -> tuple[str | None, str | None, str | None]:
        result = self.resolve(args)
        return (result.operation, result.tier, result.target)

    # ----- serialization (self-contained; survives registry export) ----------
    def to_spec(self) -> dict[str, Any]:
        """A serializable, self-contained spec: the pack data + bound tool name.

        Unlike a hand-written ``classifier`` lambda (which the registry drops on
        export), a declarative classifier round-trips because it is data.
        """
        return {"kind": "declarative", "tool": self.tool_name, "pack": self.pack.to_dict()}

    @classmethod
    def from_spec(cls, spec: Mapping[str, Any]) -> DeclarativeClassifier:
        """Rebuild a classifier from :meth:`to_spec` output (resolvers stay global)."""
        return cls(GovernancePack.from_dict(spec["pack"]), spec["tool"])


# ----- resolver registry -----------------------------------------------------
# A process-global registry of named tier resolvers. Packs declare resolvers by
# name; deployments register one implementation per *concept* (not per tool).
_RESOLVERS: dict[str, ResolverFn] = {}


def register_resolver(name: str, fn: ResolverFn | None = None) -> Any:
    """Register a tier resolver. Usable as ``register_resolver("x", fn)`` or as a
    decorator ``@register_resolver("x")``."""

    def _register(func: ResolverFn) -> ResolverFn:
        _RESOLVERS[name] = func
        return func

    if fn is not None:
        return _register(fn)
    return _register


def get_resolvers() -> dict[str, ResolverFn]:
    """The current global resolver registry (a live view)."""
    return _RESOLVERS


def clear_resolvers() -> None:
    """Remove all globally-registered resolvers (test helper)."""
    _RESOLVERS.clear()


__all__ = [
    "ResolverContext",
    "ResolverFn",
    "ResolverLookup",
    "ClassificationResult",
    "classify_call",
    "capability_for",
    "DeclarativeClassifier",
    "register_resolver",
    "get_resolvers",
    "clear_resolvers",
]
