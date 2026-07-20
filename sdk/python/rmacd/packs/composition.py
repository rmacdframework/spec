"""
RMACD Governance Packs - Multi-Pack Composition
===============================================

Several governance packs legitimately govern the *same* tool name: ``git``,
``docker``, ``terraform``, and ``make`` all overlay shell tools (``bash``,
``sh``, ...) with rules for their own binary. Before composition existed,
``apply_pack`` simply replaced the prior registration, so only the last-applied
pack governed a shared tool name ("last pack wins").

:class:`ComposedToolDefinition` fixes that: it keeps an **ordered chain** of
pack-backed tool definitions for one tool name and resolves each call against
the chain. The winning entry contributes its classification *and its own
capability ceiling* — ceilings are never unioned across packs, so a call the
git pack claims can never inherit the docker pack's ceiling.

Winner selection (deterministic, fail-closed)
---------------------------------------------

A pack **claims** a call when at least one of its rules matches (an empty
``matched_rule_ids`` is the "not mine" sentinel — the chain falls through to
the next pack). Claims are ranked by, in order:

1. **Specificity** — how precisely the pack's matched rules identified the call:

   - ``2`` *argv-anchored*: a matched rule used an ``argv_contains`` selector
     (the pack positively identified its binary as a command token);
   - ``1`` *arg-predicated*: a matched rule used ``arg_regex`` / ``arg_equals``
     / ``arg_present`` (a textual overlay match);
   - ``0`` *base*: only tool-name-only rules matched (a pack's own broad
     fallback rule, e.g. the shell pack's coreutils verb table). Base rules
     participate in the chain but never shadow another pack's specific claim,
     regardless of load order.

2. **Severity** — among equally specific claims, the most severe classification
   wins (highest operation, then most sensitive tier). This is the fail-closed
   choice when two packs' overlay regexes both match (e.g. a compound shell
   command touching two binaries) and keeps disjoint rule-sets order-independent.

3. **Chain position** — apply order (``load_packs`` list order) breaks exact
   ties; earlier wins.

If no pack claims the call, the **pre-pack fallback** — the tool definition
that was registered before any pack took the name (a user's ``register_tool``
or an MCP-bridge registration) — classifies it, gated by its own ceiling. If
there is no fallback either, the first-applied pack's default classification
applies (its pack-wide fail-closed default operation and ceiling), mirroring
single-pack semantics for unmatched calls.

Re-applying a pack already in the chain **replaces its entry in place**
(idempotent reload, chain position preserved). Direct ``register_tool`` calls
keep plain replace semantics — composition is strictly a pack-layer behaviour
applied by ``apply_pack``.

Author: Kash Kashyap
License: CC BY 4.0
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from rmacd.models import Operation
from rmacd.packs.engine import _SEGMENT_SEP, ClassificationResult, DeclarativeClassifier
from rmacd.packs.models import GovernancePack, Rule
from rmacd.registry.tools import (
    _OP_ORDER,
    _TIER_ORDER,
    ResolvedCall,
    ToolCapability,
    ToolDefinition,
    parse_data_classification,
    parse_operation,
)

# Claim specificity levels (see module docstring).
_SPEC_ARGV = 2
_SPEC_ARG = 1
_SPEC_BASE = 0


def _rule_specificity(rule: Rule) -> int:
    """How precisely a rule's selector identifies a call (see module docstring)."""
    sel = rule.when
    if sel.argv_contains is not None:
        return _SPEC_ARGV
    if any(v is not None for v in (sel.arg_equals, sel.arg_present, sel.arg_regex)):
        return _SPEC_ARG
    return _SPEC_BASE


def _claim_specificity(pack: GovernancePack, matched_rule_ids: list[str]) -> int:
    """The specificity of a pack's claim: the max over its matched rules."""
    matched = set(matched_rule_ids)
    return max(
        (_rule_specificity(r) for r in pack.rules if r.id in matched),
        default=_SPEC_BASE,
    )


def _entry_classifier(entry: ToolDefinition) -> DeclarativeClassifier:
    """The declarative classifier a chain entry must carry (invariant check)."""
    classifier = entry.classifier
    if not isinstance(classifier, DeclarativeClassifier):
        raise TypeError(
            f"composed chain entry '{entry.tool_id}' must be pack-backed "
            f"(DeclarativeClassifier), got {type(classifier).__name__}"
        )
    return classifier


def entry_pack_name(entry: ToolDefinition) -> str:
    """The governance-pack name a chain entry belongs to."""
    name = entry.metadata.get("pack")
    return str(name) if name else entry.tool_id


def is_pack_tool(tool: ToolDefinition) -> bool:
    """True if *tool* was registered by ``apply_pack`` (composable entry)."""
    return isinstance(tool.classifier, DeclarativeClassifier) and bool(
        tool.metadata.get("pack")
    )


@dataclass
class _Claim:
    """One pack's claim on a concrete call, with its ranking key components."""

    entry: ToolDefinition
    resolved: ResolvedCall
    specificity: int
    position: int

    def rank(self) -> tuple[int, int, int, int]:
        tier_rank = _TIER_ORDER[self.resolved.tier] if self.resolved.tier is not None else -1
        # Higher is better on every component; position is negated so the
        # earlier-applied pack wins exact ties.
        return (
            self.specificity,
            _OP_ORDER[self.resolved.operation],
            tier_rank,
            -self.position,
        )


def _resolved_severity(resolved: ResolvedCall) -> tuple[int, int]:
    """A resolved call's (operation, tier) severity — the cross-segment MAX key (C3)."""
    tier_rank = _TIER_ORDER[resolved.tier] if resolved.tier is not None else -1
    return (_OP_ORDER[resolved.operation], tier_rank)


@dataclass
class ComposedToolDefinition(ToolDefinition):
    """An ordered chain of pack-backed definitions sharing one tool name.

    The inherited static fields (``rmacd_level``, ``data_access``,
    ``capability``) hold a conservative *summary* across the chain (worst-case
    operation, most sensitive tier, union ceiling) for catalog/advisory use;
    authoritative per-call classification and ceiling come from
    :meth:`resolve_call`, which attaches the winning entry's own ceiling to the
    returned :class:`ResolvedCall`.
    """

    entries: list[ToolDefinition] = field(default_factory=list)
    fallback: ToolDefinition | None = None

    # ----- runtime classification --------------------------------------------

    def resolve_call(self, args: dict[str, Any] | None = None) -> ResolvedCall:
        args = args or {}
        # A shell ``command`` may chain several binaries (``git log; shred x``,
        # ``ls & rm -rf /``). Resolve each segment independently and take the
        # MOST SEVERE result: specificity-first ownership is preserved *within*
        # a segment (so one pack's loose verb overlay can't cross-match a
        # different binary and over-block), while a dangerous co-located command
        # can never be hidden by a more-specific but less-severe sibling.
        # (Code review C3, 2026-07-19.)
        command = args.get("command")
        if isinstance(command, str):
            segments = [seg for seg in (s.strip() for s in _SEGMENT_SEP.split(command)) if seg]
            if len(segments) > 1:
                resolved = [
                    self._resolve_single({**args, "command": seg}) for seg in segments
                ]
                return max(resolved, key=_resolved_severity)
        return self._resolve_single(args)

    def _resolve_single(self, args: dict[str, Any]) -> ResolvedCall:
        """Resolve one (non-compound) call through the chain, specificity-first."""
        claims: list[_Claim] = []
        for position, entry in enumerate(self.entries):
            classifier = _entry_classifier(entry)
            result = classifier.resolve(args)
            if not result.matched_rule_ids:
                continue  # "not mine": no rule matched — fall through the chain
            claims.append(
                _Claim(
                    entry=entry,
                    resolved=self._entry_resolved(entry, result, args),
                    specificity=_claim_specificity(classifier.pack, result.matched_rule_ids),
                    position=position,
                )
            )

        if claims:
            return max(claims, key=_Claim.rank).resolved

        if self.fallback is not None:
            resolved = self.fallback.resolve_call(args)
            resolved.capability = (
                self.fallback.capability
                if self.fallback.capability is not None
                else ToolCapability()
            )
            resolved.source = f"fallback:{self.fallback.tool_id}"
            return resolved

        # No pack claimed the call and nothing predates the packs: apply the
        # first-applied pack's fail-closed default (single-pack semantics).
        first = self.entries[0]
        return self._entry_resolved(first, _entry_classifier(first).resolve(args), args)

    def _entry_resolved(
        self, entry: ToolDefinition, result: ClassificationResult, args: dict[str, Any]
    ) -> ResolvedCall:
        """Materialize one entry's classification, carrying that entry's ceiling."""
        operation = parse_operation(result.operation)
        tier = (
            parse_data_classification(result.tier)
            if result.tier is not None
            else entry.data_access
        )
        target = result.target if result.target is not None else entry._render_target(args)
        capability = entry.capability if entry.capability is not None else ToolCapability()
        return ResolvedCall(
            operation=operation,
            tier=tier,
            target=target,
            capability=capability,
            source=entry_pack_name(entry),
        )

    # ----- serialization ------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize the whole chain (entries are declarative, hence data).

        A *fallback* with a hand-written classifier lambda degrades to its
        static fields on export, exactly like a plain tool export does today.
        """
        data = super().to_dict()
        data["classifier"] = {
            "kind": "composed",
            "entries": [entry.to_dict() for entry in self.entries],
            "fallback": self.fallback.to_dict() if self.fallback is not None else None,
        }
        return data

    @classmethod
    def from_tool_dict(cls, data: Mapping[str, Any]) -> ComposedToolDefinition:
        """Rebuild a composed definition from a registry-export tool dict."""
        spec = data.get("classifier")
        if not isinstance(spec, Mapping) or spec.get("kind") != "composed":
            raise ValueError("not a composed tool dict (classifier.kind != 'composed')")
        entries = [ToolDefinition.from_dict(dict(e)) for e in spec.get("entries", [])]
        if not entries:
            raise ValueError("composed classifier spec has no entries")
        fallback_data = spec.get("fallback")
        fallback = (
            ToolDefinition.from_dict(dict(fallback_data))
            if isinstance(fallback_data, Mapping)
            else None
        )
        return _build_composed(
            str(data["tool_id"]), str(data["tool_name"]), entries, fallback
        )


def _summary_capability(
    entries: list[ToolDefinition], fallback: ToolDefinition | None
) -> ToolCapability | None:
    """Union ceiling across the chain — the static worst-case *summary* only.

    Runtime gating never uses this union: each resolved call carries the
    matching entry's own ceiling. If any member is unconstrained (``None``) or
    uses the per-tier form, the summary is ``None`` (unconstrained statically).
    """
    members = list(entries) + ([fallback] if fallback is not None else [])
    operations: set[Operation] = set()
    for member in members:
        capability = member.capability
        if capability is None or capability.operations is None:
            return None
        operations |= capability.operations
    return ToolCapability(operations=operations)


def _build_composed(
    tool_id: str,
    tool_name: str,
    entries: list[ToolDefinition],
    fallback: ToolDefinition | None,
) -> ComposedToolDefinition:
    """Assemble a composed definition with conservative summary statics."""
    for entry in entries:
        _entry_classifier(entry)  # enforce the pack-backed invariant early

    members = list(entries) + ([fallback] if fallback is not None else [])
    rmacd_level = max((m.rmacd_level for m in members), key=lambda o: _OP_ORDER[o])
    tiers = [m.data_access for m in members if m.data_access is not None]
    data_access = max(tiers, key=lambda t: _TIER_ORDER[t]) if tiers else None

    tags: set[str] = {"pack", "composed"}
    for member in members:
        tags |= member.tags

    pack_names = [entry_pack_name(e) for e in entries]
    return ComposedToolDefinition(
        tool_id=tool_id,
        tool_name=tool_name,
        rmacd_level=rmacd_level,
        description=f"Composed governance-pack chain ({', '.join(pack_names)})",
        data_access=data_access,
        capability=_summary_capability(entries, fallback),
        tags=tags,
        metadata={
            "composed": True,
            "packs": pack_names,
            "pack_versions": {
                entry_pack_name(e): e.metadata.get("pack_version") for e in entries
            },
        },
        entries=entries,
        fallback=fallback,
    )


def compose_pack_tool(existing: ToolDefinition, new: ToolDefinition) -> ToolDefinition:
    """Merge a newly-applied pack tool into whatever already owns the name.

    - Same pack again (plain or chained): replace that pack's registration in
      place — idempotent reload, chain position preserved.
    - Different pack over a pack-owned name: extend (or start) the chain, in
      apply order.
    - Different pack over a *user-registered* tool: start a chain with the
      user's definition preserved as the no-claim fallback.
    """
    if not is_pack_tool(new):
        raise TypeError("compose_pack_tool: 'new' must be a pack-backed ToolDefinition")

    if isinstance(existing, ComposedToolDefinition):
        entries = list(existing.entries)
        new_pack = entry_pack_name(new)
        for i, entry in enumerate(entries):
            if entry_pack_name(entry) == new_pack:
                entries[i] = new  # idempotent reapply: same slot, no duplicate
                break
        else:
            entries.append(new)
        return _build_composed(new.tool_id, new.tool_name, entries, existing.fallback)

    if is_pack_tool(existing):
        if entry_pack_name(existing) == entry_pack_name(new):
            return new  # same pack re-applied: plain replace, as before
        return _build_composed(new.tool_id, new.tool_name, [existing, new], None)

    # Pre-pack registration (user register_tool / MCP bridge): keep it as the
    # chain's final fallback rather than silently discarding it.
    return _build_composed(new.tool_id, new.tool_name, [new], existing)


__all__ = [
    "ComposedToolDefinition",
    "compose_pack_tool",
    "entry_pack_name",
    "is_pack_tool",
]
