#!/usr/bin/env python3
"""Registry gates for the RMACD Intent Specification.

`requirements.yaml` is authoritative for requirement metadata. This tool
regenerates the two artefacts derived from it — Appendix A and the §11
conformance table inside `docs/intent-specification.md`, plus
`requirements.json` — and enforces four invariants:

  1. Document and registry agree, in both directions.
  2. Every MUST/MUST NOT requirement rolls up into a conformance item.
  3. Normative prose stays inside the readability budget.
  4. Every anchor resolves, and every heading slugifies identically under
     GitHub's rules and Python-Markdown's.

    python tools/check_spec.py              # check; non-zero exit on drift
    python tools/check_spec.py --regenerate # rewrite the generated artefacts

Gate 4 exists because the site (Python-Markdown) and GitHub slugify headings
differently: `A — B` becomes `a-b` on the site and `a--b` on GitHub. A heading
that disagrees is a link that silently 404s on one of the two surfaces.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "intent-specification.md"
REGISTRY = ROOT / "requirements.yaml"
JSON_OUT = ROOT / "requirements.json"

# Normative sentences allowed to exceed the budget, with the reason. Each is a
# parallel or enumerated construction where splitting would obscure the rule.
LENGTH_EXEMPT = {
    "N-12": "enumerates the three pinned cells inline",
    "N-36": "enumerates framework §12.5's five prohibitions in one list",
    "N-42": "three parallel MUST NOTs; splitting breaks the parallelism",
}
# `MUST NOT ... unless` reads as a gate on the enumerated list that follows it.
NEGATION_EXEMPT = {
    "N-11": "'MUST NOT lower' is the clearest statement of the composition rule",
    "N-25": "'MUST NOT ... unless' gates the numbered list that follows",
}
MAX_WORDS = 32

# Terms retired in 2.0.0. "Shape" already means a deployment shape (3D / 2D /
# DC2D) everywhere else in the framework, so using it for the equivalence class
# overloaded an established word. "Novelty" named the absence of a thing, which
# made every sentence about it read backwards.
RETIRED_TERMS = {
    "shape": "action pattern",
    "shapes": "action patterns",
    "shape_key": "action_pattern_key",
    "novelty": "precedent",
}

# Sections where a capitalised keyword appears as a quoted token rather than as an
# imperative: the BCP 14 declaration, and the two places that count keywords.
KEYWORD_PROSE_OK = {
    "(preamble)",
    "11. Conformance",
    "Appendix A: Requirement Quick Reference",
}

# Registry-level problems found while loading, surfaced with the other gates.
errors: list[str] = []
# normative id -> the R items that carry its SHOULD-level guidance
advises: dict[str, list[str]] = {}

# The intent schemas track this specification's version; the profile and pack
# schemas track the framework's. They are deliberately on different majors, and
# a stray edit that unifies them is a bug, not a tidy-up.
SCHEMA_FAMILIES = {
    "v2": ("intent.schema.json", "intent-decision.schema.json"),
    "v1": ("profile-2d.schema.json", "profile-3d.schema.json",
           "profile-dc2d.schema.json", "pack.schema.json"),
}

ANCHOR_RE = re.compile(r'<a id="([^"]+)"></a>')
DEF_RE = re.compile(r"^\*\*(N-\d+[a-z]?) \(([^)]+)\)\.\*\* ", re.M)
NORM_RE = re.compile(r"\*\*(MUST NOT|MUST|SHOULD NOT|SHOULD|MAY)\*\*")


# --------------------------------------------------------------------------- slugs
def slug_github(text: str) -> str:
    """GitHub: lowercase, drop all but alphanumerics/space/hyphen/underscore, spaces to hyphens."""
    s = text.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE)
    return s.replace(" ", "-")


def slug_pymarkdown(text: str) -> str:
    """Python-Markdown toc: NFKD to ASCII, then collapse runs of space/hyphen to one hyphen."""
    s = unicodedata.normalize("NFKD", text.strip().lower())
    s = s.encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^\w\s-]", "", s)
    return re.sub(r"[-\s]+", "-", s).strip("-")


# --------------------------------------------------------------------------- registry
def load_registry() -> tuple[dict, dict, dict]:
    errors.clear()
    advises.clear()
    try:
        loaded = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise SystemExit(f"{REGISTRY.name} is not valid YAML:\n{exc}") from None
    if not isinstance(loaded, dict) or "requirements" not in loaded:
        raise SystemExit(f"{REGISTRY.name}: expected a top-level 'requirements:' list")
    data = loaded["requirements"]
    norm = {r["id"]: r for r in data if r["kind"] == "normative"}
    conf = {r["id"]: r for r in data if r["kind"] == "conformance"}
    for r in data:
        if r["kind"] not in ("normative", "conformance"):
            errors.append(f"[1] registry: {r['id']} has unknown kind {r['kind']!r}")
    rec: dict = {}
    rolls: dict[str, list[str]] = {}
    for cid, c in conf.items():
        # An absent or emptied `bundles:` deserializes to None. Normalise it so a
        # malformed registry is reported by the gates, not raised as a traceback.
        bundles = c.get("bundles") or []
        c["bundles"] = bundles
        if not bundles:
            errors.append(f"[1] registry: {cid} bundles no requirement")
        for nid in bundles:
            if nid not in norm:
                errors.append(f"[1] registry: {cid} bundles unknown {nid}")
                continue
            rolls.setdefault(nid, []).append(cid)
    return norm, conf, rolls, rec


def render_conformance_table(conf: dict) -> str:
    rows = [
        f'| <a id="{cid.lower()}"></a>{cid} | {c["name"]} | {c["conformance_text"]} |'
        for cid, c in conf.items()
    ]
    return "| # | Name | Requirement |\n|---|---|---|\n" + "\n".join(rows) + "\n"


def render_appendix(norm: dict, conf: dict, rolls: dict, rec: dict) -> str:
    def link(rid: str) -> str:
        return f"[{rid}](#{rid.lower()})"

    rows_n = "\n".join(
        f'| {link(rid)} | {r["name"]} | {r["gloss"]} | §{r["section"]} | '
        f'{", ".join(link(c) for c in rolls.get(rid, [])) or "—"} |'
        for rid, r in norm.items()
    )
    rows_c = "\n".join(
        f'| {link(cid)} | {c["name"]} | {c["gloss"]} | '
        f'{", ".join(link(n) for n in c["bundles"])} |'
        for cid, c in conf.items()
    )
    permissive = sorted(r for r in norm if r not in rolls)
    return f"""## Appendix A: Requirement Quick Reference

Every normative requirement and conformance item carries a short plain-English
name. A name is a reading aid, not an identifier: `N-14` and `C-5` are the
stable references external documents cite, and they never change. A name can be
revised; a number cannot.

Anchors are keyed to the identifier rather than the name, for the same reason:
`#n-14` resolves to N-14 whatever it comes to be called.

This appendix is generated from `requirements.yaml` by `tools/check_spec.py`.
Edit the registry, not the tables.

### A.1 Normative requirements

| # | Name | What it says | Section | Rolls up to |
|---|---|---|---|---|
{rows_n}

Every **MUST** and **MUST NOT** above rolls up into a conformance item. The
entries showing — are permissive ({", ".join(permissive)}): they grant latitude
rather than impose an obligation, so §11 has nothing to assert about them.

### A.2 Conformance checklist

| # | Name | What it says | Bundles |
|---|---|---|---|
{rows_c}

---

"""


def regenerate(doc: str, norm: dict, conf: dict, rolls: dict, rec: dict) -> str:
    # Inline names come from the registry too, so renaming a requirement is a
    # one-line edit there rather than an edit plus a hunt through the prose.
    def _inline(m: re.Match[str]) -> str:
        rid = m.group(1)
        return f'**{rid} ({norm[rid]["name"]}).**' if rid in norm else m.group(0)

    doc = re.sub(r"\*\*(N-\d+[a-z]?) \([^)]+\)\.\*\*", _inline, doc)
    doc = re.sub(
        r"\| # \| Name \| Requirement \|\n\|---\|---\|---\|\n(?:\|.*\n)+",
        lambda _: render_conformance_table(conf),
        doc,
        count=1,
    )
    doc = re.sub(
        r"## Appendix A: Requirement Quick Reference\n.*?---\n\n(?=## See also)",
        lambda _: render_appendix(norm, conf, rolls, rec),
        doc,
        count=1,
        flags=re.S,
    )
    return doc


def build_json(norm: dict, conf: dict, rolls: dict, rec: dict) -> str:
    recs = [
        {
            "id": rid, "kind": "normative", "name": r["name"], "gloss": r["gloss"],
            "section_anchor": f"#{rid.lower()}", "rolls_up_to": rolls.get(rid, []),
        }
        for rid, r in norm.items()
    ] + [
        {
            "id": cid, "kind": "conformance", "name": c["name"], "gloss": c["gloss"],
            "section_anchor": f"#{cid.lower()}", "rolls_up_to": [],
        }
        for cid, c in conf.items()
    ] + [
        {
            "id": rid, "kind": "recommended", "name": r["name"], "gloss": r["gloss"],
            "section_anchor": f"#{rid.lower()}", "rolls_up_to": [],
        }
        for rid, r in rec.items()
    ]
    return json.dumps(recs, indent=2, ensure_ascii=False) + "\n"


# --------------------------------------------------------------------------- gates
def requirement_bodies(doc: str) -> dict[str, str]:
    """Text of each requirement, from its definition site to the next block boundary."""
    bodies, marks = {}, list(DEF_RE.finditer(doc))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(doc)
        chunk = doc[m.start():end]
        cut = re.search(r"\n#{2,3} ", chunk)
        bodies[m.group(1)] = chunk[: cut.start()] if cut else chunk
    return bodies


def sentences(text: str) -> list[str]:
    """Prose sentences only.

    Tables, fences and list items are not prose. Removing them must not splice
    the prose on either side into one run-on "sentence", so each contiguous
    prose block is split independently.
    """
    runs: list[list[str]] = [[]]
    in_fence = False
    for ln in text.split("\n"):
        if ln.lstrip().startswith("```"):
            in_fence = not in_fence
            runs.append([])
            continue
        non_prose = (
            in_fence
            or ln.lstrip().startswith(("|", ">", "- ", "* "))
            or re.match(r"\s*\d+\. ", ln)
            or (ln.startswith("   ") and ln.strip())  # list continuation
            or not ln.strip()
        )
        if non_prose:
            runs.append([])
        else:
            runs[-1].append(ln)

    out: list[str] = []
    for run in runs:
        if not run:
            continue
        flat = re.sub(r"\s+", " ", ANCHOR_RE.sub("", " ".join(run)))
        flat = re.sub(r"^\*\*N-\d+[a-z]? \([^)]+\)\.\*\* ", "", flat)
        out += [x.strip() for x in re.split(r"(?<=[.:]) (?=[A-Z`*])", flat) if x.strip()]
    return out


def run_gates(doc: str, norm: dict, conf: dict, rolls: dict, rec: dict) -> list[str]:
    fail: list[str] = []
    anchors = set(ANCHOR_RE.findall(doc))
    found = {m.group(1): m.group(2) for m in DEF_RE.finditer(doc)}

    # -- 1. document <-> registry, both directions
    for rid, r in norm.items():
        if rid not in found:
            fail.append(f"[1] {rid} in registry but has no definition site")
        elif found[rid] != r["name"]:
            fail.append(f"[1] {rid} name drift: doc={found[rid]!r} registry={r['name']!r}")
        if rid.lower() not in anchors:
            fail.append(f"[1] {rid} has no anchor")
    for rid in found:
        if rid not in norm:
            fail.append(f"[1] {rid} defined in document but absent from registry")
    for cid in conf:
        if cid.lower() not in anchors:
            fail.append(f"[1] {cid} has no anchor")
    for rid in rec:
        if rid.lower() not in anchors:
            fail.append(f"[1] {rid} has no anchor")
    for ref in set(re.findall(r"\b([NCR]-\d+[a-z]?)\b", doc)):
        if ref not in norm and ref not in conf and ref not in rec:
            fail.append(f"[1] document cites unknown {ref}")

    # -- 2. every obligation rolls up
    bodies = requirement_bodies(doc)
    for rid in norm:
        verbs = set(NORM_RE.findall(bodies.get(rid, "")))
        obligated = bool(verbs & {"MUST", "MUST NOT"})
        if obligated and not rolls.get(rid):
            fail.append(f"[2] {rid} carries a MUST but rolls up into no conformance item")
        if not obligated and rolls.get(rid):
            fail.append(f"[2] {rid} is permissive but is claimed by {rolls[rid]}")
        # This specification states obligations and latitude, never advice: a
        # SHOULD an implementer may decline would break N-21's requirement that
        # the same intent grade the same way across implementations.
        if verbs & {"SHOULD", "SHOULD NOT"}:
            fail.append(f"[5] {rid} uses SHOULD; this specification states MUST or MAY only")

    # -- 3. readability budget
    for rid, body in bodies.items():
        for s in sentences(body):
            if not NORM_RE.search(s):
                continue
            words = len(re.sub(r"[*`]", "", s).split())
            if words > MAX_WORDS and rid not in LENGTH_EXEMPT:
                fail.append(f"[3] {rid} normative sentence is {words} words (max {MAX_WORDS}): {s[:70]}...")
            if rid not in NEGATION_EXEMPT and re.search(
                r"\*\*MUST NOT\*\*.{0,140}?\b(less restrictive|anything other than|"
                r"absence of|nothing other than|no\b[^.]{0,40}\bother than)", s
            ):
                fail.append(f"[3] {rid} MUST NOT carries a second negative: {s[:70]}...")

    # -- 6. Retired vocabulary must not come back, in the spec or anything it ships.
    scanned = [("docs/intent-specification.md", doc)]
    companion = ROOT / "docs" / "intents.md"
    if companion.exists():
        scanned.append(("docs/intents.md", companion.read_text(encoding="utf-8")))
    for ex in sorted((ROOT / "schemas" / "examples" / "intents").glob("*.json")):
        scanned.append((f"schemas/examples/intents/{ex.name}", ex.read_text(encoding="utf-8")))
    for label, text in scanned:
        for term, replacement in RETIRED_TERMS.items():
            for m in re.finditer(rf"(?i)\b{re.escape(term)}\b", text):
                line = text[:m.start()].count("\n") + 1
                fail.append(f"[6] {label}:{line} retired term {m.group(0)!r}; use {replacement!r}")

    # -- 7. The two schema families stay on their own majors, and every worked
    # intent example cites the current one.
    for version, names in SCHEMA_FAMILIES.items():
        for name in names:
            path = ROOT / "schemas" / name
            if not path.exists():
                fail.append(f"[7] missing schema {name}")
                continue
            sid = json.loads(path.read_text(encoding="utf-8")).get("$id", "")
            if f"/schema/{version}/" not in sid:
                fail.append(f"[7] {name} should be on schema/{version}, found {sid!r}")
    for ex in sorted((ROOT / "schemas" / "examples" / "intents").glob("*.json")):
        declared = json.loads(ex.read_text(encoding="utf-8")).get("$schema", "")
        if declared and "/schema/v2/" not in declared:
            fail.append(f"[7] {ex.name} cites {declared!r}, not the current schema/v2")

    # -- 5. RFC 2119 §6: capitalised keywords belong inside numbered requirements.
    # Anywhere else they are either rhetoric or a binding rule with no identifier
    # (and so no conformance item). Prose that must mention a keyword as a token
    # is allowlisted by section, deliberately, one section at a time.
    spans = []
    marks = list(DEF_RE.finditer(doc))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(doc)
        chunk = doc[m.start():end]
        cut = re.search(r"\n#{2,3} ", chunk)
        spans.append((m.start(), m.start() + (cut.start() if cut else len(chunk))))
    for m in NORM_RE.finditer(doc):
        if any(a <= m.start() < b for a, b in spans):
            continue
        section = doc.rfind("\n## ", 0, m.start())
        title = doc[section + 4: doc.find("\n", section + 4)].strip() if section > 0 else "(preamble)"
        if title not in KEYWORD_PROSE_OK:
            line = doc[:m.start()].count("\n") + 1
            fail.append(f"[5] L{line} {m.group(1)} used outside a numbered requirement, in {title!r}")

    # -- 4. anchors resolve; headings agree across renderers
    headings = re.findall(r"^#{1,6} (.+)$", doc, re.M)
    slugs = set()
    for h in headings:
        g, p = slug_github(h), slug_pymarkdown(h)
        if g != p:
            fail.append(f"[4] heading slug differs (GitHub {g!r} vs site {p!r}): {h}")
        slugs.update({g, p})
    for target in set(re.findall(r"\]\(#([^)]+)\)", doc)):
        if target not in anchors and target not in slugs:
            fail.append(f"[4] internal link #{target} has no target")
    return fail


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--regenerate", action="store_true")
    args = ap.parse_args()

    norm, conf, rolls, rec = load_registry()
    doc = DOC.read_text(encoding="utf-8")
    rebuilt = regenerate(doc, norm, conf, rolls, rec)
    js = build_json(norm, conf, rolls, rec)

    fail: list[str] = []
    if args.regenerate:
        DOC.write_text(rebuilt, encoding="utf-8")
        JSON_OUT.write_text(js, encoding="utf-8")
        doc = rebuilt
        print(f"regenerated: Appendix A, §11 table, requirements.json "
              f"({len(norm)} normative, {len(conf)} conformance)")
    else:
        # Staleness is reported but never short-circuits: one stale table must not
        # hide a coverage or readability failure elsewhere in the document.
        if rebuilt != doc:
            fail.append("[0] generated sections are stale; run: tools/check_spec.py --regenerate")
        if not JSON_OUT.exists() or JSON_OUT.read_text(encoding="utf-8") != js:
            fail.append("[0] requirements.json is stale; run: tools/check_spec.py --regenerate")

    fail += errors + run_gates(doc, norm, conf, rolls, rec)
    for f in fail:
        print("FAIL " + f)
    covered = sum(1 for r in norm if rolls.get(r))
    print(f"\n{len(norm)} normative, {len(conf)} conformance, {covered} obligations covered, "
          f"{len(set(ANCHOR_RE.findall(doc)))} anchors")
    print("GATES PASS" if not fail else f"GATES FAIL ({len(fail)})")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
