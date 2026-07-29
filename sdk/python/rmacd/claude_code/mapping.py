"""Claude Code tool call → RMACD ``(operation, tier, target)`` mapping.

One function, :func:`map_tool_call`, turns a PreToolUse event's
``(tool_name, tool_input)`` into a :class:`MappedCall` the hook can evaluate
against the bound profile:

- ``Bash`` → :func:`rmacd.registry.bash.classify_bash_command` on the command
  line; the classification map is applied to the command's path-like tokens so
  ``rm -rf /data/secret`` picks up the tier mapped to ``/data/secret/*``.
- ``Write`` / ``Edit`` / ``MultiEdit`` / ``NotebookEdit`` → filesystem pack
  semantics: **Add** when the target path does not exist yet, **Change** when
  it does; target = the path.
- ``Read`` / ``Glob`` / ``Grep`` / ``NotebookRead`` / ``LS`` → **Read**.
- ``WebFetch`` / ``WebSearch`` → **Read**, plus an egress destination the hook
  checks against DC2D ``egress_controls``.
- ``mcp__<server>__<tool>`` → strip the prefix and resolve through the
  session registry (governance packs / MCP bridge registrations). A tool the
  registry does not know raises :class:`UnknownToolError` (the hook applies
  the ``RMACD_UNKNOWN_TOOL`` fail mode); a call the tool's own capability
  ceiling forbids raises :class:`CapabilityCeilingError`.
- Session-internal tools (Task, TodoWrite, AskUserQuestion, ...) → **Read**
  on ``public`` — they orchestrate the session and touch no external data,
  but they stay governed (a profile that denies Read denies them too).
- Anything else raises :class:`UnknownToolError` (fail closed by default).

Everything here is deterministic and stdlib-only beyond ``rmacd`` itself —
no LLM, no network — so the hook adds no meaningful latency.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from rmacd.claude_code.session import max_tier
from rmacd.models import DataClassification, Operation
from rmacd.registry.bash import classify_bash_command

if TYPE_CHECKING:
    from rmacd.claude_code.session import SessionBinding

MCP_PREFIX = "mcp__"

#: Human-readable operation names for decision reasons.
OP_WORDS: dict[Operation, str] = {
    Operation.READ: "Read",
    Operation.MOVE: "Move",
    Operation.ADD: "Add",
    Operation.CHANGE: "Change",
    Operation.DELETE: "Delete",
}

# Claude Code tools that orchestrate the session itself (subagents, todos,
# plan mode, user questions, shell bookkeeping). They do not act on external
# data, so they classify as Read on public rather than failing closed —
# denying Task/TodoWrite would make a governed session unusable without
# adding any governance value.
SESSION_INTERNAL_TOOLS = frozenset(
    {
        "Task",
        "Agent",
        "TodoWrite",
        "TodoRead",
        "AskUserQuestion",
        "ExitPlanMode",
        "EnterPlanMode",
        "SlashCommand",
        "Skill",
        "BashOutput",
        "TaskOutput",
        "KillShell",
        "KillBash",
        "TaskStop",
        "ListMcpResources",
    }
)

_READ_TOOLS = frozenset({"Read", "Glob", "Grep", "NotebookRead", "LS"})
_EDIT_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})


class UnknownToolError(Exception):
    """The tool cannot be mapped to RMACD terms (unregistered MCP/unknown tool)."""

    def __init__(self, tool_name: str, detail: str) -> None:
        super().__init__(f"Tool '{tool_name}' is not governed: {detail}")
        self.tool_name = tool_name
        self.detail = detail


class CapabilityCeilingError(Exception):
    """The registered tool's own capability ceiling forbids the resolved call."""

    def __init__(
        self, tool_name: str, operation: Operation, tier: DataClassification | None
    ) -> None:
        tier_label = tier.value if tier else "any"
        super().__init__(
            f"Tool '{tool_name}' capability ceiling does not permit "
            f"{OP_WORDS[operation]} on {tier_label}"
        )
        self.tool_name = tool_name
        self.operation = operation
        self.tier = tier


@dataclass
class MappedCall:
    """RMACD view of one Claude Code tool call."""

    operation: Operation
    tier: DataClassification | None  # None → the session's default tier applies
    target: str
    rule: str  # which mapping rule / classifier produced this (for reasons)
    egress_destination: str | None = None  # DC2D egress check target, if any


def _first_str(tool_input: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


#: Shells whose ``-c`` argument is a nested script rather than a plain operand.
_SHELL_BINARIES = frozenset({"bash", "sh", "zsh", "dash", "ksh", "ash", "busybox"})

#: Depth cap for the ``-c`` recursion below — ``bash -c "sh -c '...'"`` is
#: worth following, an adversarially nested chain is not.
_MAX_SHELL_NESTING = 4


def _shell_split(command: str) -> list[str]:
    try:
        return shlex.split(command, comments=True)
    except ValueError:
        return command.split()


def _bash_path_candidates(command: str, _depth: int = 0) -> list[str]:
    """Path-like tokens of a shell command, for classification-map matching.

    Recurses into ``sh -c "..."`` / ``bash -c "..."`` payloads: the nested
    script arrives as a *single* quoted token, so without this a command like
    ``bash -c "rm -rf /data/secret"`` exposed no path to the classification map
    and the target silently fell back to the session default tier — turning a
    §12.5 hard deny into an approvable prompt.
    """
    tokens = _shell_split(command)
    candidates = [
        t for t in tokens if t and not t.startswith("-") and ("/" in t or "." in t or "~" in t)
    ]
    if _depth >= _MAX_SHELL_NESTING:
        return candidates
    for i, token in enumerate(tokens):
        if token != "-c" or i == 0:
            continue
        if tokens[i - 1].rsplit("/", 1)[-1] not in _SHELL_BINARIES:
            continue
        nested = tokens[i + 1 : i + 2]
        if nested:
            candidates.extend(_bash_path_candidates(nested[0], _depth + 1))
    return candidates


# Shell metacharacters that disqualify the introspection carve-out below: a
# compound/redirected/substituted command must always take the full classifier
# path, otherwise `rmacd matrix p.json && rm -rf /` would ride the carve-out.
_SHELL_OPERATOR_CHARS = frozenset("|&;<>`$(){}\n")

# Read-only surfaces of the rmacd CLI itself. Deliberately excludes anything
# that writes (`pack sign`), reaches the network/LLM (`classify`), or starts a
# server (`mcp-serve`).
_RMACD_READONLY_SUBCOMMANDS = frozenset(
    {"--version", "--help", "validate", "info", "matrix", "evaluate"}
)
_RMACD_READONLY_GROUPS = frozenset(
    {
        ("pack", "validate"),
        ("pack", "verify"),
        ("pack", "diff"),
        ("pack", "review"),
        ("audit", "summarize"),
    }
)


def _rmacd_introspection(command: str) -> str | None:
    """Detail string when the whole command is a read-only RMACD introspection call.

    The governance layer's own deterministic read surfaces — the session status
    renderer and the read-only rmacd CLI subcommands — classify as Read so a
    bound read-only session can always inspect its own governance state
    (otherwise the fail-closed bash default denies `/rmacd:status` itself).
    """
    if any(ch in _SHELL_OPERATOR_CHARS for ch in command):
        return None
    try:
        tokens = shlex.split(command, comments=True)
    except ValueError:
        return None
    if not tokens:
        return None
    binary = tokens[0].rsplit("/", 1)[-1]
    if binary in ("python", "python3") and len(tokens) >= 3 and tokens[1] == "-m":
        module = tokens[2]
        if module == "rmacd.claude_code.status" or (
            module == "rmacd.claude_code" and tokens[3:4] == ["status"]
        ):
            return "rmacd status renderer"
        if module == "rmacd.cli":
            tokens = ["rmacd", *tokens[3:]]
            binary = "rmacd"
        else:
            return None
    if binary != "rmacd":
        return None
    args = tokens[1:]
    if not args:
        return None
    if args[0] in _RMACD_READONLY_SUBCOMMANDS:
        return f"rmacd {args[0]}"
    if len(args) >= 2 and (args[0], args[1]) in _RMACD_READONLY_GROUPS:
        return f"rmacd {args[0]} {args[1]}"
    return None


def _map_bash(command: str, binding: SessionBinding) -> MappedCall:
    introspection = _rmacd_introspection(command)
    if introspection is not None:
        return MappedCall(
            operation=Operation.READ,
            tier=None,
            target="rmacd:introspection",
            rule=f"rmacd introspection: {introspection}",
        )
    classification = classify_bash_command(command)
    tier: DataClassification | None = None
    matched_path: str | None = None
    for token in _bash_path_candidates(command):
        token_tier = binding.classify_path(token)
        if token_tier is not None and max_tier(tier, token_tier) is token_tier:
            tier, matched_path = token_tier, token
    target = matched_path or f"bash:{classification.binary or command.strip()[:60]}"
    return MappedCall(
        operation=classification.operation,
        tier=tier,
        target=target,
        rule=f"bash classifier: {classification.detail}",
    )


def _map_file_edit(
    tool_name: str, tool_input: dict[str, Any], binding: SessionBinding
) -> MappedCall:
    path = _first_str(tool_input, "file_path", "notebook_path", "path")
    if not path:
        # No path to inspect: treat as Change on an unknown file (conservative).
        return MappedCall(
            operation=Operation.CHANGE,
            tier=None,
            target=f"file:unknown ({tool_name})",
            rule="filesystem semantics: no path argument -> Change (conservative)",
        )
    exists = Path(path).exists()
    operation = Operation.CHANGE if exists else Operation.ADD
    return MappedCall(
        operation=operation,
        tier=binding.classify_path(path),
        target=path,
        rule=(
            "filesystem semantics: existing path -> Change"
            if exists
            else "filesystem semantics: new path -> Add"
        ),
    )


def _map_read(tool_name: str, tool_input: dict[str, Any], binding: SessionBinding) -> MappedCall:
    path = _first_str(tool_input, "file_path", "notebook_path", "path", "pattern")
    target = path or f"session://{tool_name}"
    return MappedCall(
        operation=Operation.READ,
        tier=binding.classify_path(path) if path else None,
        target=target,
        rule=f"{tool_name} -> Read",
    )


def _map_web(tool_name: str, tool_input: dict[str, Any]) -> MappedCall:
    if tool_name == "WebFetch":
        url = _first_str(tool_input, "url")
        destination = urlparse(url).netloc or url or "unknown-host"
        target = url or "web:unknown"
    else:  # WebSearch
        query = _first_str(tool_input, "query")
        destination = "web-search"
        target = f"web-search:{query[:80]}" if query else "web-search"
    return MappedCall(
        operation=Operation.READ,
        tier=None,
        target=target,
        rule=f"{tool_name} -> Read (+ egress check on DC2D profiles)",
        egress_destination=destination,
    )


def _map_mcp(tool_name: str, tool_input: dict[str, Any], binding: SessionBinding) -> MappedCall:
    parts = tool_name.split("__", 2)
    bare_name = parts[2] if len(parts) == 3 and parts[2] else tool_name
    # Prefer a registration under the full namespaced name (e.g. from an
    # MCPRegistryBridge that kept prefixes), then the bare tool name (how
    # governance packs name tools).
    tool = binding.registry.get_tool(tool_name) or binding.registry.get_tool(bare_name)
    if tool is None:
        raise UnknownToolError(
            tool_name,
            f"MCP tool '{bare_name}' is not registered in the session's tools "
            f"registry (packs: {', '.join(binding.pack_sources)})",
        )
    resolved = tool.resolve_call(tool_input)
    # Capability gate (defence in depth): what this tool may ever represent.
    if not tool.permits(resolved.operation, resolved.tier):
        raise CapabilityCeilingError(tool.tool_id, resolved.operation, resolved.tier)
    # Classification-map overlay: path-like arguments may raise the tier
    # (e.g. an MCP filesystem server touching a restricted-mapped path).
    tier = resolved.tier
    for value in tool_input.values():
        if isinstance(value, str) and value:
            tier = max_tier(tier, binding.classify_path(value))
    tier = max_tier(tier, binding.classify_path(resolved.target))
    return MappedCall(
        operation=resolved.operation,
        tier=tier,
        target=resolved.target,
        rule=f"registry tool '{tool.tool_id}' (pack classifier)",
    )


def map_tool_call(
    tool_name: str, tool_input: dict[str, Any], binding: SessionBinding
) -> MappedCall:
    """Map one Claude Code tool call to RMACD terms.

    Raises :class:`UnknownToolError` for tools that cannot be governed and
    :class:`CapabilityCeilingError` when a registered tool's own ceiling
    forbids the resolved call. Both are translated by the hook, not here.
    """
    if tool_name.startswith(MCP_PREFIX):
        return _map_mcp(tool_name, tool_input, binding)
    if tool_name == "Bash":
        return _map_bash(str(tool_input.get("command") or ""), binding)
    if tool_name in _EDIT_TOOLS:
        return _map_file_edit(tool_name, tool_input, binding)
    if tool_name in _READ_TOOLS:
        return _map_read(tool_name, tool_input, binding)
    if tool_name in ("WebFetch", "WebSearch"):
        return _map_web(tool_name, tool_input)
    if tool_name in SESSION_INTERNAL_TOOLS:
        return MappedCall(
            operation=Operation.READ,
            tier=DataClassification.PUBLIC,
            target=f"session://{tool_name}",
            rule="session-internal tool -> Read on public",
        )
    raise UnknownToolError(tool_name, "no mapping rule for this tool")


__all__ = [
    "MCP_PREFIX",
    "OP_WORDS",
    "SESSION_INTERNAL_TOOLS",
    "CapabilityCeilingError",
    "MappedCall",
    "UnknownToolError",
    "map_tool_call",
]
