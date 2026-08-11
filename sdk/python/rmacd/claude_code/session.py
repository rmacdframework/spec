"""Profile/registry binding for a governed Claude Code session.

Binding order for the profile (first hit wins):

1. ``RMACD_PROFILE_PATH`` environment variable.
2. ``.claude/rmacd-profile.json`` in the session's working directory, then in
   each parent directory — nearest wins.
3. ``$CLAUDE_PROJECT_DIR/.claude/rmacd-profile.json``, for a cwd that has moved
   outside the project tree.
4. Otherwise the session is **unbound** — :func:`bind_session` returns ``None``
   and the hook passes every call through untouched.

Steps 2-3 both matter: Claude Code reports the session's *current* directory on
every hook event, so probing only that directory meant a governed project
became silently ungoverned the moment the agent worked from a subdirectory.

The distinction between *unbound* and *broken* matters for the fail-mode
table: an unconfigured session must be zero-friction (passthrough), while a
session whose configuration exists but cannot be loaded must **fail closed**.
:func:`bind_session` therefore returns ``None`` only when no profile source is
configured at all, and raises :class:`SessionBindingError` for every
configured-but-broken state (missing file behind the env var, invalid profile,
bad pack, malformed classification map, ...).

Environment variables read here:

- ``RMACD_PROFILE_PATH`` — profile JSON to bind (overrides the project file).
- ``RMACD_PACKS`` — comma-separated extra governance packs (built-in names or
  file paths) merged on top of the default ``shell`` + ``filesystem`` packs.
- ``RMACD_CLASSIFICATION_MAP`` — path-glob → tier map, either inline JSON
  (``{"/etc/*": "restricted"}``) or a path to a JSON file of the same shape.
- ``RMACD_DEFAULT_TIER`` — tier assumed for targets no map rule matches
  (default ``internal``; 3D/DC2D evaluation requires a tier).
- ``RMACD_UNKNOWN_TOOL`` — ``deny`` (default) or ``ask`` for MCP/unmapped
  tools the registry does not know.
- ``RMACD_AGENT_ID`` — audit identity for the session (default
  ``claude-code``).
- ``RMACD_ENVIRONMENT`` — optional deployment environment fed to profile
  constraints (``development`` / ``staging`` / ``production`` / ...).
"""

from __future__ import annotations

import contextlib
import fnmatch
import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote

from rmacd.enforcer import PolicyEnforcer
from rmacd.evaluator import AnyProfile
from rmacd.loader import ProfileLoader
from rmacd.models import DataClassification, Environment, Profile2D, Profile3D, ProfileDC2D
from rmacd.packs import load_packs
from rmacd.registry.tools import ToolsRegistry

ENV_PROFILE_PATH = "RMACD_PROFILE_PATH"
ENV_PACKS = "RMACD_PACKS"
ENV_CLASSIFICATION_MAP = "RMACD_CLASSIFICATION_MAP"
ENV_DEFAULT_TIER = "RMACD_DEFAULT_TIER"
ENV_UNKNOWN_TOOL = "RMACD_UNKNOWN_TOOL"
ENV_AGENT_ID = "RMACD_AGENT_ID"
ENV_ENVIRONMENT = "RMACD_ENVIRONMENT"
#: Set by Claude Code to the session's project root. Used as the last resort
#: when the session's cwd sits outside any directory carrying a profile.
ENV_PROJECT_DIR = "CLAUDE_PROJECT_DIR"

DEFAULT_PACKS: tuple[str, ...] = ("shell", "filesystem")
DEFAULT_AGENT_ID = "claude-code"
PROJECT_PROFILE_RELPATH = Path(".claude") / "rmacd-profile.json"

# Sensitivity ordering for "highest matching tier wins" map resolution.
_TIER_RANK: dict[DataClassification, int] = {
    DataClassification.PUBLIC: 0,
    DataClassification.INTERNAL: 1,
    DataClassification.CONFIDENTIAL: 2,
    DataClassification.RESTRICTED: 3,
}


def max_tier(
    a: DataClassification | None, b: DataClassification | None
) -> DataClassification | None:
    """Return the more sensitive of two (possibly-unset) tiers."""
    if a is None:
        return b
    if b is None:
        return a
    return a if _TIER_RANK[a] >= _TIER_RANK[b] else b


_LEADING_SLASHES = re.compile(r"^/{2,}")

#: Scheme prefix treated as "a local path with a scheme on it".
_FILE_URL_PREFIX = "file://"


def _path_variants(target: str, cwd: Path | None) -> list[str]:
    """Every form of *target* a classification rule may legitimately match.

    Always includes the literal string (so relative patterns keep working),
    plus — for path-shaped targets — the ``~``-expanded, cwd-anchored,
    ``..``-collapsed absolute form. Matching all of them is what stops
    ``rm -rf /data/../data/secret`` and ``rm -rf ./secret`` from evading the
    ``/data/secret/*`` rule that plain ``rm -rf /data/secret`` trips — an
    evasion that turned a §12.5 hard deny into an approvable prompt.
    """
    variants = [target]
    if not target:
        return variants
    # `file://` is a path wearing a scheme, and packs render targets that way:
    # 90 of the built-in target templates are URI-shaped, so bailing on every
    # "://" made `classify_path(resolved.target)` — the defence-in-depth half of
    # the MCP overlay — a no-op for the entire pack catalog. Unwrap file URLs and
    # classify what they point at; leave genuinely remote schemes alone, since
    # `s3://bucket/secret` is not the local path `/bucket/secret`.
    # Parsed by hand rather than with ``urlparse``, which raises on inputs a
    # rendered target can genuinely contain (a template that interpolated a
    # list yields `file://['/a/b']`, and the bracket reads as a malformed IPv6
    # host). Classification must never raise: it runs inside the decision path,
    # where an exception becomes a fail-closed deny of an otherwise fine call.
    if target.startswith(_FILE_URL_PREFIX):
        rest = target[len(_FILE_URL_PREFIX) :]
        slash = rest.find("/")  # skips any authority in file://host/path
        unwrapped = unquote(rest[slash:]) if slash != -1 else ""
        if unwrapped and unwrapped not in variants:
            variants.append(unwrapped)
            target = unwrapped
        else:
            return variants
    elif "://" in target:
        return variants
    candidate = os.path.expanduser(target)
    if not os.path.isabs(candidate) and cwd is not None:
        candidate = os.path.join(str(cwd), candidate)
    normalized = os.path.normpath(candidate)
    # POSIX reserves a leading "//" as implementation-defined and normpath
    # preserves it, but Linux resolves it to "/" — so "//data//secret" reaches
    # the same file as "/data/secret" and must match the same rules.
    for form in (candidate, normalized, _LEADING_SLASHES.sub("/", normalized)):
        if form not in variants:
            variants.append(form)
    return variants


class SessionBindingError(Exception):
    """A profile *is* configured but the session could not be bound.

    The hook maps this to a fail-closed deny — a broken governance
    configuration must never silently degrade to an ungoverned session.
    """


@dataclass(frozen=True)
class ClassificationRule:
    """One path-glob → tier rule from ``RMACD_CLASSIFICATION_MAP``."""

    pattern: str
    tier: DataClassification

    def matches(self, target: str) -> bool:
        if fnmatch.fnmatchcase(target, self.pattern):
            return True
        # `/data/secret/*` should also cover the directory itself, so that
        # `rm -rf /data/secret` is classified as strictly as its contents.
        if self.pattern.endswith("/*"):
            root = self.pattern[:-2]
            if target == root or target.startswith(root + "/"):
                return True
        return False


@dataclass
class SessionBinding:
    """Everything the hook needs to govern one tool call."""

    profile: AnyProfile
    profile_path: Path
    enforcer: PolicyEnforcer
    registry: ToolsRegistry
    pack_sources: list[str]
    classification_rules: list[ClassificationRule] = field(default_factory=list)
    default_tier: DataClassification = DataClassification.INTERNAL
    unknown_tool_decision: str = "deny"  # "deny" | "ask"
    agent_id: str = DEFAULT_AGENT_ID
    #: The session's working directory, used to resolve relative tool targets
    #: to absolute paths before classification-map matching.
    cwd: Path | None = None

    @property
    def profile_id(self) -> str:
        return self.profile.profile_id

    @property
    def shape(self) -> str:
        if isinstance(self.profile, ProfileDC2D):
            return "DC2D"
        if isinstance(self.profile, Profile3D):
            return "3D"
        return "2D"

    @property
    def is_2d(self) -> bool:
        return isinstance(self.profile, Profile2D)

    @property
    def is_dc2d(self) -> bool:
        return isinstance(self.profile, ProfileDC2D)

    def classify_path(self, target: str) -> DataClassification | None:
        """Most sensitive tier any classification-map rule assigns to *target*.

        Every normalized form of *target* is tested (see :func:`_path_variants`),
        so a rule cannot be sidestepped by spelling the same path with ``..``,
        ``~`` or a cwd-relative prefix.
        """
        best: DataClassification | None = None
        for form in _path_variants(target, self.cwd):
            for rule in self.classification_rules:
                if rule.matches(form):
                    best = max_tier(best, rule.tier)
        return best


def resolve_profile_path(
    cwd: str | Path | None = None, env: Mapping[str, str] | None = None
) -> Path | None:
    """The profile path this session would bind, or ``None`` when unbound.

    Search order:

    1. ``RMACD_PROFILE_PATH`` (explicit wins outright).
    2. ``<cwd>/.claude/rmacd-profile.json``, then the same file in each parent
       directory — nearest match wins, so a subproject may bind a stricter
       profile than its repository root.
    3. ``$CLAUDE_PROJECT_DIR/.claude/rmacd-profile.json``, for the case where
       the session's cwd has wandered outside the project tree entirely.

    The upward walk matters: Claude Code reports the session's *current*
    directory in each hook event, so without it a governed project silently
    became ungoverned the moment the agent worked from a subdirectory.
    """
    environ = os.environ if env is None else env
    explicit = environ.get(ENV_PROFILE_PATH, "").strip()
    if explicit:
        return Path(explicit)

    start = Path(cwd) if cwd is not None else Path.cwd()
    # An unreadable or vanished cwd falls back to the literal path.
    with contextlib.suppress(OSError):
        start = start.resolve()

    roots: list[Path] = [start, *start.parents]
    project_dir = environ.get(ENV_PROJECT_DIR, "").strip()
    if project_dir:
        roots.append(Path(project_dir))

    seen: set[Path] = set()
    for root in roots:
        if root in seen:
            continue
        seen.add(root)
        candidate = root / PROJECT_PROFILE_RELPATH
        if candidate.is_file():
            return candidate
    return None


def _parse_classification_map(raw: str) -> list[ClassificationRule]:
    text = raw.strip()
    if not text:
        return []
    if not text.startswith("{"):
        map_path = Path(text)
        if not map_path.is_file():
            raise SessionBindingError(
                f"{ENV_CLASSIFICATION_MAP} points to '{text}', which is neither inline "
                f"JSON nor an existing file"
            )
        text = map_path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SessionBindingError(f"{ENV_CLASSIFICATION_MAP} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise SessionBindingError(
            f"{ENV_CLASSIFICATION_MAP} must be a JSON object of path-glob -> tier"
        )
    rules: list[ClassificationRule] = []
    for pattern, tier in data.items():
        try:
            # Expand ``~`` so a map written as {"~/.ssh/*": "restricted"} lines
            # up with the absolute paths targets normalize to.
            rules.append(
                ClassificationRule(
                    pattern=os.path.expanduser(str(pattern)),
                    tier=DataClassification(str(tier)),
                )
            )
        except ValueError as exc:
            raise SessionBindingError(
                f"{ENV_CLASSIFICATION_MAP} entry '{pattern}': invalid tier '{tier}' "
                f"(expected public/internal/confidential/restricted)"
            ) from exc
    return rules


def _parse_pack_sources(env: Mapping[str, str]) -> list[str]:
    sources = list(DEFAULT_PACKS)
    for extra in env.get(ENV_PACKS, "").split(","):
        name = extra.strip()
        if name and name not in sources:
            sources.append(name)
    return sources


def bind_session(
    cwd: str | Path | None = None, env: Mapping[str, str] | None = None
) -> SessionBinding | None:
    """Bind the session's profile, registry, and fail-mode knobs.

    Returns ``None`` when no profile is configured (unbound → passthrough).
    Raises :class:`SessionBindingError` when a profile is configured but any
    part of the binding fails (→ the hook fails closed).
    """
    environ: Mapping[str, str] = os.environ if env is None else env

    profile_path = resolve_profile_path(cwd, environ)
    if profile_path is None:
        return None

    session_cwd = Path(cwd) if cwd is not None else Path.cwd()
    with contextlib.suppress(OSError):
        session_cwd = session_cwd.resolve()

    try:
        profile = ProfileLoader().load_file(profile_path)
    except Exception as exc:
        raise SessionBindingError(f"cannot load profile '{profile_path}': {exc}") from exc

    pack_sources = _parse_pack_sources(environ)
    try:
        registry = load_packs(pack_sources, registry_id="claude-code-session")
    except Exception as exc:
        raise SessionBindingError(
            f"cannot build the tools registry from packs {pack_sources}: {exc}"
        ) from exc

    rules = _parse_classification_map(environ.get(ENV_CLASSIFICATION_MAP, ""))

    default_tier_raw = environ.get(ENV_DEFAULT_TIER, "").strip() or "internal"
    try:
        default_tier = DataClassification(default_tier_raw)
    except ValueError as exc:
        raise SessionBindingError(
            f"{ENV_DEFAULT_TIER}='{default_tier_raw}' is not a valid tier "
            f"(expected public/internal/confidential/restricted)"
        ) from exc

    # Fail closed on an unrecognised override value rather than erroring: the
    # stricter of the two documented behaviours is the safe default.
    unknown_tool = environ.get(ENV_UNKNOWN_TOOL, "").strip().lower()
    if unknown_tool not in ("deny", "ask"):
        unknown_tool = "deny"

    environment: Environment | None = None
    env_raw = environ.get(ENV_ENVIRONMENT, "").strip()
    if env_raw:
        try:
            environment = Environment(env_raw)
        except ValueError as exc:
            raise SessionBindingError(
                f"{ENV_ENVIRONMENT}='{env_raw}' is not a valid environment"
            ) from exc

    agent_id = environ.get(ENV_AGENT_ID, "").strip() or DEFAULT_AGENT_ID

    # No approval gateway on purpose: the hook process is short-lived and has
    # no interactive stdin, so approval-level autonomy is surfaced as Claude
    # Code's own permission prompt (permissionDecision "ask") instead. The
    # enforcer is used via evaluate_only/check_egress, which never invoke a
    # gateway.
    enforcer = PolicyEnforcer(
        profile=profile,
        agent_id=agent_id,
        environment=environment,
        registry=registry,
    )

    return SessionBinding(
        profile=profile,
        profile_path=profile_path,
        enforcer=enforcer,
        registry=registry,
        pack_sources=pack_sources,
        classification_rules=rules,
        default_tier=default_tier,
        unknown_tool_decision=unknown_tool,
        agent_id=agent_id,
        cwd=session_cwd,
    )


__all__ = [
    "ClassificationRule",
    "SessionBinding",
    "SessionBindingError",
    "bind_session",
    "max_tier",
    "resolve_profile_path",
    "DEFAULT_PACKS",
    "ENV_AGENT_ID",
    "ENV_CLASSIFICATION_MAP",
    "ENV_DEFAULT_TIER",
    "ENV_ENVIRONMENT",
    "ENV_PACKS",
    "ENV_PROFILE_PATH",
    "ENV_PROJECT_DIR",
    "ENV_UNKNOWN_TOOL",
    "PROJECT_PROFILE_RELPATH",
]
