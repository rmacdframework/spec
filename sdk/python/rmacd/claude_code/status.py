"""Session governance status for ``/rmacd:status``.

``python3 -m rmacd.claude_code.status`` renders, for the current directory's
session: the bound profile (id, shape, source path), the effective autonomy
matrix, bound governance packs, the classification map, and how approvals and
unknown tools are routed.

The matrix table mirrors ``rmacd matrix`` (``rmacd.cli.cmd_matrix``). That CLI
code path is an ``argparse`` command that loads its own file and prints
directly, so it is not cleanly importable for an in-memory profile; the small
formatting loop is reimplemented here (per c2: reuse if cleanly importable,
otherwise reimplement small) on the same ``get_effective_autonomy_matrix()``
data, so both surfaces render identical values.
"""

from __future__ import annotations

import sys

from rmacd.claude_code import session
from rmacd.evaluator import AnyProfile, PolicyEvaluator

_TIERS = ["public", "internal", "confidential", "restricted"]
_OPS = ["R", "M", "A", "C", "D"]


def _render_matrix(profile: AnyProfile) -> list[str]:
    """Effective autonomy matrix table (same data/format as ``rmacd matrix``)."""
    matrix = PolicyEvaluator(profile).get_effective_autonomy_matrix()
    lines: list[str] = []
    if profile.model == "data-classification-2d":
        lines.append(f"{'Classification':<15} {'Autonomy Level':<20}")
        lines.append("-" * 35)
        for tier in _TIERS:
            value = matrix.get(tier)
            if isinstance(value, str):
                lines.append(f"{tier:<15} {value:<20}")
    elif profile.model == "three-dimensional":
        header = f"{'Classification':<15}" + "".join(f" {op:<12}" for op in _OPS)
        lines.append(header)
        lines.append("-" * 75)
        for tier in _TIERS:
            row = matrix.get(tier)
            if not isinstance(row, dict):
                continue
            cells = "".join(f" {row.get(op, 'N/A'):<12}" for op in _OPS)
            lines.append(f"{tier:<15}{cells}")
    else:
        lines.append(f"{'Operation':<12} {'Autonomy Level':<20}")
        lines.append("-" * 35)
        for op in _OPS:
            value = matrix.get(op)
            if isinstance(value, str):
                lines.append(f"{op:<12} {value:<20}")
    return lines


def render_status(cwd: str | None = None) -> str:
    """Human-readable governance status for the session rooted at *cwd*."""
    lines: list[str] = ["RMACD session governance status", "=" * 33, ""]

    try:
        binding = session.bind_session(cwd=cwd)
    except session.SessionBindingError as exc:
        lines += [
            "State: BOUND BUT BROKEN — the hook is FAILING CLOSED (all tool calls denied).",
            f"Cause: {exc}",
            "",
            "Fix the configuration, or unbind by unsetting RMACD_PROFILE_PATH / removing",
            f"{session.PROJECT_PROFILE_RELPATH}. Restart the Claude Code session afterwards.",
        ]
        return "\n".join(lines)

    if binding is None:
        lines += [
            "State: UNBOUND — RMACD is installed but no profile is bound.",
            "Tool calls pass through ungoverned (Claude Code's own permission flow only).",
            "",
            "Bind a profile by either:",
            f"  - setting {session.ENV_PROFILE_PATH}=/path/to/profile.json, or",
            f"  - creating {session.PROJECT_PROFILE_RELPATH} in the project root",
            "    (run /rmacd:init to scaffold one).",
        ]
        return "\n".join(lines)

    lines += [
        "State:      BOUND (fail-closed on hook errors)",
        f"Profile:    {binding.profile_id} — {binding.profile.profile_name}",
        f"Shape:      {binding.shape} ({binding.profile.model})",
        f"Source:     {binding.profile_path}",
        f"Agent id:   {binding.agent_id}",
        "",
        "Effective autonomy matrix (defaults + overrides, §12.5 floor applied):",
        *_render_matrix(binding.profile),
        "",
        f"Bound packs:        {', '.join(binding.pack_sources)}",
        f"Registry:           {len(binding.registry)} governed tool(s)",
    ]

    if binding.classification_rules:
        lines.append(
            f"Classification map: {len(binding.classification_rules)} rule(s) "
            f"({session.ENV_CLASSIFICATION_MAP}):"
        )
        for rule in binding.classification_rules:
            lines.append(f"  {rule.pattern}  ->  {rule.tier.value}")
    else:
        lines.append(f"Classification map: none ({session.ENV_CLASSIFICATION_MAP} not set)")
    lines += [
        f"Default tier:       {binding.default_tier.value} "
        f"(unmapped targets; {session.ENV_DEFAULT_TIER})",
        f"Unknown tools:      {binding.unknown_tool_decision} "
        f"({session.ENV_UNKNOWN_TOOL}=ask|deny)",
        "",
        "Approval routing:   approval-level autonomy returns permissionDecision \"ask\" —",
        "                    Claude Code's own permission prompt is the human-in-the-loop",
        "                    step. No ApprovalGateway runs inside the hook process.",
    ]
    return "\n".join(lines)


def main() -> int:
    print(render_status())
    return 0


if __name__ == "__main__":
    sys.exit(main())
