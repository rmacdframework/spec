"""Build an agent self-restriction prompt from a profile.

``build_system_prompt(profile)`` returns a markdown fragment that
summarises the profile's permissions, autonomy stance, and hard
prohibitions for inclusion in the agent's system prompt. Deriving the
prompt mechanically from the profile keeps the model's
self-understanding consistent with the runtime enforcement layer; drift
between a hand-written prompt and the live profile is the most common
source of wasted turns.

The output is intended to be **prepended** to (or referenced by) the
agent's existing system prompt. It is not a complete prompt on its own —
it covers only the parts of agent behaviour that the profile constrains.

Example::

    from rmacd import ProfileLoader, build_system_prompt

    profile = ProfileLoader().load_file("profile.json")
    prompt_fragment = build_system_prompt(profile)
"""

from __future__ import annotations

from typing import cast

from rmacd.evaluator import DEFAULT_AUTONOMY_2D, DEFAULT_AUTONOMY_3D
from rmacd.models import (
    AutonomyLevel,
    DataClassification,
    Operation,
    Profile2D,
    Profile3D,
    ProfileDC2D,
)

# Compact display names for the verbs, in operational order.
_OPS_IN_ORDER: list[Operation] = [
    Operation.READ,
    Operation.MOVE,
    Operation.ADD,
    Operation.CHANGE,
    Operation.DELETE,
]

_OP_FULL_NAMES: dict[Operation, str] = {
    Operation.READ: "Read",
    Operation.MOVE: "Move",
    Operation.ADD: "Add",
    Operation.CHANGE: "Change",
    Operation.DELETE: "Delete",
}

# Compact display names for tiers, ordered low → high sensitivity.
_TIERS_IN_ORDER: list[DataClassification] = [
    DataClassification.PUBLIC,
    DataClassification.INTERNAL,
    DataClassification.CONFIDENTIAL,
    DataClassification.RESTRICTED,
]

_AUTONOMY_SHORT: dict[AutonomyLevel, str] = {
    AutonomyLevel.AUTONOMOUS: "autonomous",
    AutonomyLevel.LOGGED: "logged",
    AutonomyLevel.NOTIFICATION: "notify operator",
    AutonomyLevel.APPROVAL: "approval required",
    AutonomyLevel.ELEVATED_APPROVAL: "elevated approval (CAB/CISO)",
    AutonomyLevel.PROHIBITED: "PROHIBITED",
}


def build_system_prompt(
    profile: Profile2D | Profile3D | ProfileDC2D,
    *,
    title: str | None = None,
) -> str:
    """Produce a markdown prompt fragment derived from ``profile``.

    The fragment describes what the agent can and cannot do under this
    profile, including the autonomy stance per cell (3D), per tier
    (DC2D), or per verb (2D), and the hard prohibitions implied by the
    autonomy matrix.

    Args:
        profile: a loaded ``Profile2D``, ``Profile3D``, or ``ProfileDC2D``.
        title: optional H1 heading. Defaults to the profile name.
    """
    if isinstance(profile, Profile3D):
        return _build_3d(profile, title)
    if isinstance(profile, ProfileDC2D):
        return _build_dc2d(profile, title)
    return _build_2d(profile, title)


# ---------- 3D ---------------------------------------------------------------


def _build_3d(profile: Profile3D, title: str | None) -> str:
    heading = title or profile.profile_name
    lines: list[str] = [
        f"# {heading} — RMACD-governed agent",
        "",
        "You are operating under the RMACD governance framework. Every tool",
        "call is intercepted by a Policy Enforcement Point before it runs.",
        "",
        f"## Your profile (`{profile.profile_id}`)",
        "",
        "Permitted operations per data tier:",
        "",
    ]
    for tier in _TIERS_IN_ORDER:
        perms = profile.permissions.get(tier, [])
        if not perms:
            lines.append(f"- **{tier.value.capitalize()}**: (none)")
            continue
        codes = ", ".join(
            op.value for op in _OPS_IN_ORDER if op in perms
        )
        lines.append(f"- **{tier.value.capitalize()}**: {codes}")
    lines.append("")
    lines.append("Autonomy stance per (operation, tier) — overrides applied:")
    lines.append("")
    lines.append("| Operation | Public | Internal | Confidential | Restricted |")
    lines.append("|---|---|---|---|---|")
    overrides = profile.autonomy_overrides or {}
    for op in _OPS_IN_ORDER:
        row = [f"| **{_OP_FULL_NAMES[op]}**"]
        for tier in _TIERS_IN_ORDER:
            perms = profile.permissions.get(tier, [])
            if op not in perms:
                row.append("not granted")
                continue
            key = f"{tier.value}.{op.value}"
            if key in overrides:
                autonomy = AutonomyLevel(overrides[key])
            else:
                autonomy = DEFAULT_AUTONOMY_3D[tier.value][op.value]
            row.append(_AUTONOMY_SHORT[autonomy])
        lines.append(" | ".join(row) + " |")
    lines.append("")
    prohibitions = _hard_prohibitions_3d(profile)
    if prohibitions:
        lines.append("## Hard prohibitions")
        lines.append("")
        lines.append(
            "These combinations are **prohibited for any agent** by the RMACD"
        )
        lines.append(
            "autonomy matrix (§12.5). The exception process cannot lift them;"
        )
        lines.append("a human must execute them directly:")
        lines.append("")
        for p in prohibitions:
            lines.append(f"- {p}")
        lines.append("")
    lines.extend(_behaviour_block())
    return "\n".join(lines).rstrip() + "\n"


def _hard_prohibitions_3d(profile: Profile3D) -> list[str]:
    """List (op, tier) pairs that are PROHIBITED in the matrix."""
    del profile  # the matrix is profile-independent for prohibitions
    out: list[str] = []
    for tier in _TIERS_IN_ORDER:
        for op in _OPS_IN_ORDER:
            autonomy = DEFAULT_AUTONOMY_3D[tier.value][op.value]
            if autonomy == AutonomyLevel.PROHIBITED:
                out.append(
                    f"**{_OP_FULL_NAMES[op]} on {tier.value.capitalize()}** "
                    f"— human-only."
                )
    return out


# ---------- 2D ---------------------------------------------------------------


def _build_2d(profile: Profile2D, title: str | None) -> str:
    heading = title or profile.profile_name
    lines: list[str] = [
        f"# {heading} — RMACD-governed agent",
        "",
        "You are operating under the RMACD governance framework. Every tool",
        "call is intercepted by a Policy Enforcement Point before it runs.",
        "",
        f"## Your profile (`{profile.profile_id}`)",
        "",
        "Permitted operations:",
        "",
    ]
    perms = list(profile.permissions)
    perm_codes = ", ".join(op.value for op in _OPS_IN_ORDER if op in perms)
    lines.append(f"- {perm_codes}")
    lines.append("")
    overrides = cast("dict[str, AutonomyLevel]", profile.autonomy_overrides or {})
    lines.append("Autonomy stance per operation:")
    lines.append("")
    lines.append("| Operation | Required oversight |")
    lines.append("|---|---|")
    for op in _OPS_IN_ORDER:
        if op not in perms:
            lines.append(f"| **{_OP_FULL_NAMES[op]}** | not granted |")
            continue
        if op in overrides:
            autonomy = AutonomyLevel(overrides[op])
        else:
            autonomy = DEFAULT_AUTONOMY_2D[op.value]
        lines.append(f"| **{_OP_FULL_NAMES[op]}** | {_AUTONOMY_SHORT[autonomy]} |")
    lines.append("")
    lines.extend(_behaviour_block())
    return "\n".join(lines).rstrip() + "\n"


# ---------- DC2D -------------------------------------------------------------


def _build_dc2d(profile: ProfileDC2D, title: str | None) -> str:
    heading = title or profile.profile_name
    lines: list[str] = [
        f"# {heading} — RMACD-governed agent (DC2D)",
        "",
        "You are operating under an RMACD DC2D profile. Operational",
        "permissions are governed by the upstream IAM/RBAC layer. Your",
        "autonomy depends purely on the **data tier** you access; any",
        "read of Confidential or Restricted data may also be redacted",
        "before reaching you, and any outbound data flow is checked",
        "against the profile's egress controls.",
        "",
        f"## Your profile (`{profile.profile_id}`)",
        "",
        "Access stance per data tier:",
        "",
        "| Tier | Allowed | Autonomy |",
        "|---|---|---|",
    ]
    for tier in _TIERS_IN_ORDER:
        policy = profile.data_access.for_tier(tier)
        allowed = "yes" if policy.allowed else "**no**"
        autonomy = (
            _AUTONOMY_SHORT[policy.autonomy]
            if policy.allowed
            else _AUTONOMY_SHORT[AutonomyLevel.PROHIBITED]
        )
        lines.append(f"| **{tier.value.capitalize()}** | {allowed} | {autonomy} |")
    lines.append("")

    # Surfaces summary
    redaction = (
        profile.constraints.redaction
        if profile.constraints and profile.constraints.redaction
        else None
    )
    egress = (
        profile.constraints.egress_controls
        if profile.constraints and profile.constraints.egress_controls
        else None
    )
    if redaction or egress:
        lines.append("## Data-flow controls applied to your outputs")
        lines.append("")
        if redaction:
            tiers = ", ".join(t.value for t in redaction.redact_tiers) or "(none)"
            lines.append(
                f"- **Redaction**: content from `{tiers}` is masked before "
                f"it reaches you. PII tokens replace direct identifiers."
            )
        if egress:
            if egress.allowed_destinations:
                allowed = ", ".join(egress.allowed_destinations)
                lines.append(
                    f"- **Egress allow-list**: outbound flows are permitted "
                    f"only to: {allowed}."
                )
            if egress.block_external_models:
                lines.append(
                    "- **External model block**: Confidential and Restricted "
                    "data may not egress to external model endpoints."
                )
        lines.append("")
    lines.extend(_behaviour_block(dc2d=True))
    return "\n".join(lines).rstrip() + "\n"


# ---------- shared behaviour guidance ---------------------------------------


def _behaviour_block(dc2d: bool = False) -> list[str]:
    lines = [
        "## Behaviour",
        "",
        "- Prefer the lowest-risk operation that achieves the user's goal.",
        "- Explain your plan before acting on Confidential or Restricted data.",
    ]
    if not dc2d:
        lines.append(
            "- Read before mutate. Move before Add. Add before Delete."
        )
    lines.extend(
        [
            "- Respect denials. If a tool call returns an RMACD error, do not",
            "  retry the same operation; choose a lower-risk alternative or",
            "  tell the user the action requires their direct execution.",
            "- You cannot self-modify your profile. If a task genuinely requires",
            "  permissions you do not have, recommend a §12 exception request.",
        ]
    )
    return lines


__all__ = ["build_system_prompt"]
