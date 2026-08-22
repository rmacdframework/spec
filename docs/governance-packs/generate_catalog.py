#!/usr/bin/env python3
"""Generate the Governance Pack Catalog markdown from the built-in pack data.

Reads every ``*.json`` pack under ``sdk/python/rmacd/packs/data/`` and renders a
single ``catalog.md`` documenting all built-in packs: the tools each governs,
how operations and data tiers are derived, the target template, and the
capability ceiling. Run after adding or editing a built-in pack:

    python docs/governance-packs/generate_catalog.py

The output is deterministic (packs sorted by name) so re-runs produce minimal
diffs. Hand-edits to ``catalog.md`` will be overwritten — change this script or
the pack data instead.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Repo-relative paths (this file lives in docs/governance-packs/).
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
DATA_DIR = REPO_ROOT / "sdk" / "python" / "rmacd" / "packs" / "data"
OUTPUT = HERE / "catalog.md"

OPERATIONS = ["R", "M", "A", "C", "D"]
OPERATION_NAMES = {
    "R": "Read",
    "M": "Move",
    "A": "Add",
    "C": "Change",
    "D": "Delete",
}

# Curated family grouping (mirrors the README pack catalog table).
FAMILY = {
    "shell": "Shell",
    "aws": "Cloud CLIs",
    "gcloud": "Cloud CLIs",
    "az": "Cloud CLIs",
    "kubectl": "Cloud CLIs",
    "github": "Dev tools",
    "gitlab": "Dev tools",
    "sql": "Dev tools",
    "filesystem": "Dev tools",
    "git": "Developer toolchain",
    "gh": "Developer toolchain",
    "docker": "Developer toolchain",
    "terraform": "Developer toolchain",
    "npm": "Developer toolchain",
    "pip-uv": "Developer toolchain",
    "make": "Developer toolchain",
    "servicenow": "Enterprise operations",
    "helm": "Enterprise operations",
    "ssh-transfer": "Enterprise operations",
    "stripe": "Enterprise operations",
    "vault": "Enterprise operations",
    "slack": "SaaS / collaboration MCPs",
    "google-drive": "SaaS / collaboration MCPs",
    "jira": "SaaS / collaboration MCPs",
    "confluence": "SaaS / collaboration MCPs",
    "postgres": "SaaS / collaboration MCPs",
    "boto3": "Cloud-provider SDKs & MCPs",
    "aws-api-mcp": "Cloud-provider SDKs & MCPs",
    "azure-mcp": "Cloud-provider SDKs & MCPs",
    "gcp-toolbox": "Cloud-provider SDKs & MCPs",
    "ms365": "Microsoft 365 MCP",
    "aws-iam": "Identity & access (focused)",
    "az-identity": "Identity & access (focused)",
    "gcp-iam": "Identity & access (focused)",
}

# Optional one-paragraph preamble printed under a family heading.
FAMILY_BLURB = {
    "Developer toolchain": (
        "The surfaces enterprise coding-agent sessions actually touch: "
        "`load_packs([\"git\", \"gh\", \"docker\", \"terraform\", \"npm\", "
        "\"pip-uv\", \"make\"])` is one line. Each pack governs its CLI both as "
        "a direct tool name and inside shell commands (`bash`/`sh`/... with the "
        "CLI's binary in the command line). Routine development flows normally "
        "(reads are Read on `internal`, installs/commits are Add, builds and "
        "lifecycle changes are Change), while destructive, credential, publish, "
        "and IAM-adjacent operations — force pushes, `terraform apply`/state "
        "surgery, registry publishing, `docker login`/`--privileged`, secret "
        "and token management — land on the **restricted** tier, so the §12.5 "
        "floor makes them structurally impossible to perform autonomously. "
        "Packs that share a shell tool name (`bash`, `sh`, ...) **compose**: "
        "`apply_pack` chains them in load order instead of replacing, and per "
        "call the pack whose rules match governs — with *its own* capability "
        "ceiling, never a union across packs — falling through on no-match to "
        "the next pack and finally to any tool registered before the packs. A "
        "pack's broad tool-name-only fallback rule (e.g. the shell pack's "
        "coreutils table) never shadows another pack's specific claim, so "
        "loading all seven toolchain packs plus `shell` over the same `bash` "
        "tool just works."
    ),
    "Enterprise operations": (
        "One pack per enterprise control domain: change management "
        "(`servicenow` — ITSM/CAB via MCP tool names), Kubernetes deployment "
        "(`helm`), regulated file transfer and remote execution "
        "(`ssh-transfer` — the canonical **Move** pack; an upload is potential "
        "egress, which DC2D deployments should pair with egress controls), "
        "financial rails (`stripe` — payment data is never internal, and money "
        "movement is restricted), and identity/secrets (`vault` — the §12.5 "
        "showcase, where reading a secret is itself the exfiltration risk and "
        "classifies as Read on `restricted`). Restricted-tier *reads* are "
        "profile-gated (they need an explicit Read grant on `restricted`), "
        "while restricted-tier Change/Delete rows are floor-blocked outright. "
        "The CLI-shaped packs (`helm`, `ssh-transfer`, `stripe`, `vault`) "
        "govern their binaries both as direct tools and inside shell commands; "
        "as with the developer-toolchain family, packs sharing a shell tool "
        "name (`bash`, `sh`, ...) **compose** in a single registry — per call, "
        "the pack whose rules match governs with its own capability ceiling, "
        "falling through to the next pack on no-match — so these packs can be "
        "loaded alongside the developer-toolchain (and `shell`) packs on the "
        "same `bash` tool without one overwriting another."
    ),
    "Identity & access (focused)": (
        "Focused, security-hardened variants of the cloud CLI packs. Each is a "
        "drop-in standalone pack (load it *instead of* the general `aws` / `az` / "
        "`gcloud` pack for agents whose role touches identity or secrets): a "
        "general verb-table fallback governs ordinary commands, while scoped "
        "overlays raise the whole identity surface to **confidential** and "
        "privileged identity mutations and secret/credential access to "
        "**restricted**. Because the §12.5 floor makes Add/Change/Delete on "
        "`restricted` *prohibited* for autonomous agents, these packs make "
        "destructive identity and RBAC changes (deleting users/roles, rewriting "
        "policies, purging Key Vault keys) structurally impossible to perform "
        "autonomously — while reads of the identity surface and secret access "
        "require elevated approval rather than running silently."
    ),
}

# Order families appear in the catalog.
FAMILY_ORDER = [
    "Shell",
    "Cloud CLIs",
    "Identity & access (focused)",
    "Dev tools",
    "Developer toolchain",
    "Enterprise operations",
    "SaaS / collaboration MCPs",
    "Cloud-provider SDKs & MCPs",
    "Microsoft 365 MCP",
]


def code(value: str) -> str:
    """Wrap a value in inline code, escaping pipes for Markdown tables."""
    return f"`{value}`".replace("|", "\\|")


def tools_for_when(when: object) -> list[str]:
    """Extract the tool selectors named by a rule's ``when`` clause."""
    if isinstance(when, dict):
        tool = when.get("tool")
        if isinstance(tool, str):
            return [tool]
        if isinstance(tool, list):
            return [str(t) for t in tool]
    return []


def describe_tier(tier: object) -> str:
    """Render a human-readable description of a tier specification."""
    if isinstance(tier, str):
        return code(tier)
    if not isinstance(tier, dict):
        return "—"

    parts: list[str] = []
    pattern_map = tier.get("pattern_map")
    if isinstance(pattern_map, list):
        for entry in pattern_map:
            arg_regex = entry.get("arg_regex", {})
            arg = arg_regex.get("arg", "?")
            pattern = arg_regex.get("pattern", "")
            parts.append(
                f"{code(entry.get('tier', '?'))} when "
                f"`{arg}` matches `{pattern}`"
            )

    resolver = tier.get("resolver")
    if resolver:
        frm = tier.get("from")
        from_txt = f" from `{frm}`" if frm else ""
        parts.append(f"resolver `{resolver}`{from_txt}")

    default = tier.get("default")
    if default:
        parts.append(f"otherwise {code(default)}")

    return "; ".join(parts) if parts else "—"


def render_verb_rule(rule: dict[str, Any]) -> list[str]:
    """Render a CLI/verb-table style rule (parse + verb_table)."""
    lines: list[str] = []
    tools = tools_for_when(rule.get("when"))
    lines.append(f"**Matches tools:** {', '.join(code(t) for t in tools)}  ")

    parse = rule.get("parse", {})
    parsed_arg = parse.get("arg")
    if parsed_arg:
        wrappers = parse.get("strip_wrappers") or []
        wrap_txt = (
            f" (strips wrappers: {', '.join(code(w) for w in wrappers)})"
            if wrappers
            else ""
        )
        lines.append(f"**Parses argument:** `{parsed_arg}`{wrap_txt}  ")

    # Group verbs by operation, preserving R→M→A→C→D order.
    verb_table = rule.get("verb_table", {})
    by_op: dict[str, list[str]] = {op: [] for op in OPERATIONS}
    for verb, op in verb_table.items():
        by_op.setdefault(op, []).append(verb)

    lines.append("")
    lines.append("| Operation | Verbs |")
    lines.append("|-----------|-------|")
    for op in OPERATIONS:
        verbs = by_op.get(op) or []
        if verbs:
            verb_txt = ", ".join(code(v) for v in verbs)
            lines.append(f"| **{op}** {OPERATION_NAMES[op]} | {verb_txt} |")
    default_op = rule.get("default")
    if default_op:
        lines.append(
            f"| *(unrecognised verb)* | defaults to **{default_op}** "
            f"{OPERATION_NAMES.get(default_op, '')} |"
        )
    lines.append("")

    lines.append(f"**Data tier:** {describe_tier(rule.get('tier'))}  ")
    if rule.get("target"):
        lines.append(f"**Target template:** {code(rule['target'])}  ")
    capability = rule.get("capability")
    if capability:
        lines.append(
            f"**Capability ceiling:** {', '.join(code(c) for c in capability)}  "
        )
    return lines


def describe_when(when: object) -> str:
    """Render a rule's selector condition (for scoped overlay rules)."""
    if not isinstance(when, dict):
        return "—"
    arg_regex = when.get("arg_regex")
    if isinstance(arg_regex, dict):
        return f"`{arg_regex.get('arg', '?')}` matches `{arg_regex.get('pattern', '')}`"
    arg_equals = when.get("arg_equals")
    if isinstance(arg_equals, dict):
        return "; ".join(f"`{k}` = {code(str(v))}" for k, v in arg_equals.items())
    tools = tools_for_when(when)
    return ", ".join(code(t) for t in tools) if tools else "any call"


def render_classify_rules(rules: list[dict[str, Any]]) -> list[str]:
    """Render MCP/per-tool style rules (when + classify) as a table."""
    lines = [
        "| Operation | Tools | Data tier | Target |",
        "|-----------|-------|-----------|--------|",
    ]
    for rule in rules:
        classify = rule.get("classify", {})
        op = classify.get("operation", "?")
        op_label = f"**{op}** {OPERATION_NAMES.get(op, '')}"
        tools = tools_for_when(rule.get("when"))
        tools_txt = ", ".join(code(t) for t in tools) if tools else "—"
        tier_txt = describe_tier(classify.get("tier"))
        target = classify.get("target")
        target_txt = code(target) if target else "—"
        lines.append(f"| {op_label} | {tools_txt} | {tier_txt} | {target_txt} |")
    return lines


def render_overlay_rules(rules: list[dict[str, Any]]) -> list[str]:
    """Render scoped tier-overlay rules (when + classify.tier, no operation).

    These don't assert an operation — they raise the data tier when their
    selector matches, combining with the base rule via most-sensitive-wins.
    """
    lines = [
        "**Tier overlays** (raise the data tier when the command matches; "
        "operation comes from the base rule):",
        "",
        "| Applies when | Raises tier to |",
        "|--------------|----------------|",
    ]
    for rule in rules:
        classify = rule.get("classify", {})
        cond = describe_when(rule.get("when"))
        tier_txt = describe_tier(classify.get("tier"))
        lines.append(f"| {cond} | {tier_txt} |")
    return lines


def render_pack(pack: dict[str, Any]) -> list[str]:
    """Render the full section for one pack."""
    name = pack["pack"]
    lines: list[str] = []
    lines.append(f"### `{name}`")
    lines.append("")
    lines.append(f"> {pack.get('description', '').strip()}")
    lines.append("")

    prov = pack.get("provenance", {})
    meta_bits = [
        f"**Version** {pack.get('version', '—')}",
        f"**Family** {FAMILY.get(name, '—')}",
        f"**Default operation** {pack.get('default_operation', '—')}",
        f"**Review status** {prov.get('review_status', '—')}",
    ]
    if prov.get("llm_assisted"):
        meta_bits.append("**LLM-assisted** yes")
    lines.append(" · ".join(meta_bits))
    lines.append("")

    resolvers = pack.get("resolvers")
    if resolvers:
        lines.append("**Resolvers** (live tier lookups, fail-closed):")
        lines.append("")
        for res in resolvers:
            failclosed = res.get("fail_closed_default", "—")
            desc = res.get("description", "").strip()
            lines.append(
                f"- `{res.get('name', '?')}` — {desc} "
                f"(fail-closed default: {code(failclosed)})"
            )
        lines.append("")

    rules = pack.get("rules", [])
    verb_rules = [r for r in rules if "verb_table" in r]
    classify_rules = [r for r in rules if "classify" in r]
    # An overlay raises tier without asserting an operation; a full classify
    # rule (operation set) is a per-tool mapping rendered as its own table.
    op_rules = [r for r in classify_rules if r.get("classify", {}).get("operation")]
    overlay_rules = [r for r in classify_rules if not r.get("classify", {}).get("operation")]

    for rule in verb_rules:
        lines.extend(render_verb_rule(rule))
        lines.append("")
    if op_rules:
        lines.extend(render_classify_rules(op_rules))
        lines.append("")
    if overlay_rules:
        lines.extend(render_overlay_rules(overlay_rules))
        lines.append("")

    return lines


def load_packs() -> list[dict[str, Any]]:
    packs = []
    for path in sorted(DATA_DIR.glob("*.json")):
        packs.append(json.loads(path.read_text()))
    return packs


def render_catalog(packs: list[dict[str, Any]]) -> str:
    by_name = {p["pack"]: p for p in packs}
    lines: list[str] = []

    lines.append("# Governance Pack Catalog")
    lines.append("")
    lines.append(
        "> The built-in governance packs that ship with `rmacd-framework` "
        f"({len(packs)} packs). Each maps a tool call to RMACD terms "
        "**(operation, data tier, target)** as data — no hand-written "
        "classifier. Load one by name with `load_pack(\"aws\")` or several "
        "with `load_packs([\"aws\", \"kubectl\", \"github\"])`."
    )
    lines.append("")
    lines.append(
        "> [!IMPORTANT]\n"
        "> Built-in packs are **AI-drafted starting points** "
        "(`review_status: ai-drafted`). Review and sign them before relying on "
        "them in production — see the [authoring guide](authoring-guide.md) and "
        "the [overview](README.md). Runtime classification is always "
        "deterministic: the §12.5 floor, agent profile, and tool capability "
        "ceiling remain the authoritative gates, and the LLM never runs at "
        "enforcement time."
    )
    lines.append("")

    # Summary table.
    lines.append("## At a glance")
    lines.append("")
    lines.append("| Pack | Family | Tools / selectors | Rules | Summary |")
    lines.append("|------|--------|-------------------|-------|---------|")
    for name in sorted(by_name):
        pack = by_name[name]
        rules = pack.get("rules", [])
        selectors: list[str] = []
        for rule in rules:
            selectors.extend(tools_for_when(rule.get("when")))
        n_selectors = len(set(selectors))
        summary = pack.get("description", "").strip().rstrip(".")
        # Trim the boilerplate prefix for a tighter table cell.
        summary = summary.replace("RMACD classification for the ", "")
        summary = summary.replace("RMACD classification for ", "")
        if len(summary) > 80:
            summary = summary[:77].rstrip() + "…"
        lines.append(
            f"| [`{name}`](#{name}) | {FAMILY.get(name, '—')} "
            f"| {n_selectors} | {len(rules)} | {summary} |"
        )
    lines.append("")

    # Per-family detailed sections.
    for family in FAMILY_ORDER:
        members = sorted(n for n in by_name if FAMILY.get(n) == family)
        if not members:
            continue
        lines.append(f"## {family}")
        lines.append("")
        if family in FAMILY_BLURB:
            lines.append(FAMILY_BLURB[family])
            lines.append("")
        for name in members:
            lines.extend(render_pack(by_name[name]))

    lines.append("---")
    lines.append("")
    lines.append(
        "*Generated by `docs/governance-packs/generate_catalog.py` from the "
        "built-in pack data in `sdk/python/rmacd/packs/data/`. "
        "Do not edit by hand — re-run the script after changing a pack.*"
    )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    packs = load_packs()
    OUTPUT.write_text(render_catalog(packs))
    print(f"Wrote {OUTPUT} ({len(packs)} packs)")


if __name__ == "__main__":
    main()
