"""
RMACD Governance Packs - Loading & Registration
===============================================

Turn a pack (a built-in name, a file path, a dict, or a :class:`GovernancePack`)
into registered tools on a :class:`~rmacd.registry.tools.ToolsRegistry`.

- :func:`load_pack` resolves any of the above to a validated ``GovernancePack``.
- :func:`apply_pack` registers a :class:`DeclarativeClassifier`-backed
  ``ToolDefinition`` for each concrete tool (exact names from the pack's rules,
  or an explicit ``tool_names`` list e.g. from an MCP ``tools/list``).
- :func:`load_packs` is the one-liner: build a registry from several packs and
  hand it to ``PolicyEnforcer(registry=...)``.

Built-in packs ship as JSON wheel data under ``rmacd/packs/data/``. Custom packs
may be authored in YAML (requires ``pyyaml``) or JSON.

Author: Kash Kashyap
License: CC BY 4.0
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Mapping
from importlib import resources
from pathlib import Path
from typing import Any

from rmacd.models import DataClassification, Operation
from rmacd.packs.composition import compose_pack_tool
from rmacd.packs.engine import DeclarativeClassifier, ResolverFn, capability_for
from rmacd.packs.models import GovernancePack
from rmacd.packs.validation import validate_pack_dict
from rmacd.registry.tools import ToolCapability, ToolDefinition, ToolsRegistry

_DATA_PACKAGE = "rmacd.packs.data"

# Sources accepted by load_pack.
PackSource = "str | Path | Mapping[str, Any] | GovernancePack"


def _load_text_as_dict(text: str, *, is_yaml: bool) -> dict[str, Any]:
    if is_yaml:
        try:
            import yaml
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise ImportError(
                "YAML packs require PyYAML. Install it with "
                "`pip install rmacd-framework[yaml]` (or author the pack as JSON)."
            ) from exc
        data: Any = yaml.safe_load(text)
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Pack document must be a mapping at the top level")
    return data


def _builtin_pack_text(name: str) -> str | None:
    """Return the bundled JSON text for a built-in pack name, or None."""
    resource = resources.files(_DATA_PACKAGE) / f"{name}.json"
    if resource.is_file():
        return resource.read_text(encoding="utf-8")
    return None


def builtin_pack_names() -> list[str]:
    """Names of the packs bundled with the SDK (under ``rmacd/packs/data/``)."""
    names: list[str] = []
    for entry in resources.files(_DATA_PACKAGE).iterdir():
        fname = entry.name
        if fname.endswith(".json"):
            names.append(fname[: -len(".json")])
    return sorted(names)


def _enforce_signed(pack: GovernancePack, trusted_keys: str | list[str] | None) -> None:
    """Raise unless *pack* carries a valid signature from one of *trusted_keys*."""
    from rmacd.packs.signing import PackSignatureError, verify_pack

    keys = [trusted_keys] if isinstance(trusted_keys, str) else list(trusted_keys or [])
    if not keys:
        raise ValueError(
            "require_signed=True needs trusted_keys (one or more Ed25519 public-key PEMs)"
        )
    if not any(verify_pack(pack, key) for key in keys):
        raise PackSignatureError(
            f"pack '{pack.pack}' v{pack.version} is not signed by a trusted key "
            "(content hash mismatch, missing signature, or untrusted key)"
        )


def load_pack(
    source: Any,
    *,
    validate: bool = True,
    require_signed: bool = False,
    trusted_keys: str | list[str] | None = None,
) -> GovernancePack:
    """Resolve *source* to a validated :class:`GovernancePack`.

    *source* may be a :class:`GovernancePack` (returned as-is), a mapping, a path
    to a ``.json``/``.yaml``/``.yml`` file, or a bare built-in pack name.

    Set ``require_signed=True`` with ``trusted_keys`` (PEM public key, or a list)
    to refuse any pack that is not validly signed by a trusted key — the
    recommended production posture, since built-in packs ship unsigned.
    """
    if isinstance(source, GovernancePack):
        pack = source
    else:
        if isinstance(source, Mapping):
            data = dict(source)
        else:
            path = Path(str(source))
            if path.exists():
                suffix = path.suffix.lower()
                data = _load_text_as_dict(
                    path.read_text(encoding="utf-8"), is_yaml=suffix in (".yaml", ".yml")
                )
            else:
                # Treat a bare name as a built-in pack.
                text = _builtin_pack_text(str(source))
                if text is None:
                    raise FileNotFoundError(
                        f"No pack file at '{source}' and no built-in pack named "
                        f"'{source}' (built-ins: {', '.join(builtin_pack_names()) or 'none'})"
                    )
                data = _load_text_as_dict(text, is_yaml=False)

        if validate:
            validate_pack_dict(data)
        pack = GovernancePack.from_dict(data)

    if require_signed:
        _enforce_signed(pack, trusted_keys)
    return pack


def _is_exact_tool(name: str) -> bool:
    if name.startswith("/") and name.endswith("/"):
        return False  # regex
    return not any(ch in name for ch in "*?[")


def exact_tool_names(pack: GovernancePack) -> list[str]:
    """Concrete (non-glob, non-regex) tool names named by the pack's selectors."""
    names: set[str] = set()
    for rule in pack.rules:
        tool = rule.when.tool
        if tool is None:
            continue
        candidates = tool if isinstance(tool, list) else [tool]
        names.update(c for c in candidates if _is_exact_tool(c))
    return sorted(names)


def apply_pack(
    registry: ToolsRegistry,
    pack: GovernancePack,
    *,
    tool_names: Iterable[str] | None = None,
    resolvers: Mapping[str, ResolverFn] | None = None,
) -> list[ToolDefinition]:
    """Register a declarative-classifier-backed tool for each concrete tool name.

    By default the exact tool names named in the pack are registered; pass
    ``tool_names`` (e.g. an MCP ``tools/list``) to govern a glob/regex pack.

    **Composition**: when a tool name is already registered by a *different*
    pack (several packs overlaying the same shell tool, e.g. ``git`` + ``docker``
    on ``bash``), the packs are composed into an ordered chain rather than
    replaced — per call, the pack whose rules match governs (with *its own*
    capability ceiling), falling through on no-match; a pre-pack user
    registration is preserved as the chain's final fallback. Re-applying the
    same pack replaces its own entry (idempotent reload). See
    :mod:`rmacd.packs.composition` for the exact winner-selection rules. Direct
    ``registry.register_tool`` calls keep plain replace semantics.
    """
    names = list(tool_names) if tool_names is not None else exact_tool_names(pack)

    # Warn when a pack's glob/regex rules can't be registered for lack of a
    # concrete tool list — otherwise those rules silently govern nothing.
    if tool_names is None:
        glob_rules = [
            r.id for r in pack.rules
            if r.when.tool is not None
            and not all(_is_exact_tool(t) for t in (
                r.when.tool if isinstance(r.when.tool, list) else [r.when.tool]
            ))
        ]
        if glob_rules:
            logging.getLogger(__name__).warning(
                "pack '%s' has %d glob/regex rule(s) (%s) that register nothing without an "
                "explicit tool_names list (e.g. from an MCP tools/list); only its %d exact "
                "tool(s) were registered",
                pack.pack, len(glob_rules), ", ".join(glob_rules), len(names),
            )

    registered: list[ToolDefinition] = []
    for name in names:
        classifier = DeclarativeClassifier(pack, name, resolvers=resolvers)
        # Static defaults (no args): silence the engine's resolver fail-closed
        # warnings for this registration-time probe — they're expected here and
        # only meaningful at actual call time.
        _engine_log = logging.getLogger("rmacd.packs.engine")
        _prev_level = _engine_log.level
        _engine_log.setLevel(logging.ERROR)
        try:
            static = classifier.resolve({})
        finally:
            _engine_log.setLevel(_prev_level)

        cap_ops = capability_for(pack, name)
        capability = (
            ToolCapability(operations={Operation(o) for o in cap_ops}) if cap_ops else None
        )
        data_access = DataClassification(static.tier) if static.tier else None

        tool = ToolDefinition(
            tool_id=name,
            tool_name=name,
            rmacd_level=Operation(static.operation),
            data_access=data_access,
            classifier=classifier,
            capability=capability,
            tags={"pack", pack.pack},
            metadata={"pack": pack.pack, "pack_version": pack.version},
        )
        existing = registry.get_tool(name)
        if existing is not None:
            # Compose instead of clobber: chain packs that share a tool name,
            # replace in place on a same-pack reload, keep a pre-pack user
            # registration as the chain's fallback.
            tool = compose_pack_tool(existing, tool)
        registry.register_tool(tool, expect_replace=existing is not None)
        registered.append(tool)
    return registered


def load_packs(
    sources: Iterable[Any],
    *,
    registry: ToolsRegistry | None = None,
    registry_id: str = "packs",
    resolvers: Mapping[str, ResolverFn] | None = None,
    require_signed: bool = False,
    trusted_keys: str | list[str] | None = None,
) -> ToolsRegistry:
    """Build (or extend) a registry from several packs — the integration one-liner.

    Pass ``require_signed=True`` with ``trusted_keys`` to refuse any unsigned or
    untrusted pack (recommended in production).

    Example::

        enforcer = PolicyEnforcer(profile, agent_id, registry=load_packs(["shell", "jira"]))
    """
    reg = registry if registry is not None else ToolsRegistry(registry_id)
    for source in sources:
        pack = load_pack(source, require_signed=require_signed, trusted_keys=trusted_keys)
        apply_pack(reg, pack, resolvers=resolvers)
    return reg


__all__ = [
    "PackSource",
    "load_pack",
    "load_packs",
    "apply_pack",
    "exact_tool_names",
    "builtin_pack_names",
]
