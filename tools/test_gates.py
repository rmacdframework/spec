#!/usr/bin/env python3
"""Mutation test for tools/check_spec.py: inject each failure mode, confirm it is caught.

A gate that cannot fail is not a gate. This injects one fault per invariant into
a throwaway copy of the repo and asserts the matching gate rejects it.

    python tools/test_gates.py
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

SPEC = Path(__file__).resolve().parent.parent
PY = sys.executable

# (label, file, old, new, expected gate, regenerate_first)
FAULTS = [
    ("a requirement renamed in the doc but not the registry", "docs/intent-specification.md",
     "**N-14 (The Monotonicity Rule).**", "**N-14 (The Ratchet Rule).**", "[1]", False),
    ("an anchor deleted", "docs/intent-specification.md",
     '<a id="n-30"></a>', "", "[1]", False),
    ("a citation to a requirement that does not exist", "docs/intent-specification.md",
     "- `docs/audit-evidence.md`", "- (N-99) `docs/audit-evidence.md`", "[1]", False),
    ("a MUST requirement left out of every conformance item", "requirements.yaml",
     "  bundles:\n  - N-11\n", "  bundles:\n  - N-12\n", "[2]", True),
    ("a permissive requirement wrongly claimed as covered", "requirements.yaml",
     "  bundles:\n  - N-42\n", "  bundles:\n  - N-42\n  - N-41\n", "[2]", True),
    ("a normative sentence allowed to sprawl", "docs/intent-specification.md",
     "Revocation **MUST** take effect immediately.",
     "Revocation **MUST** take effect immediately and without any further delay "
     "whatsoever in every single case that the implementation may encounter at "
     "runtime under all possible operating conditions and configurations that "
     "the deploying organization has chosen to put into service anywhere.", "[3]", False),
    ("a double negative reintroduced", "docs/intent-specification.md",
     "The computed level **MUST** be at least as restrictive as the base level.",
     "The computed level **MUST NOT** be less restrictive than the base level.", "[3]", False),
    ("an em-dash in a linkable heading", "docs/intent-specification.md",
     "## Appendix A: Requirement Quick Reference",
     "## Appendix A — Requirement Quick Reference", "[4]", False),
    ("a SHOULD reintroduced into a requirement", "docs/intent-specification.md",
     "an implementation **MUST** propagate `intent_id`",
     "an implementation **SHOULD** propagate `intent_id`", "[5]", False),
    ("an unknown record kind in the registry", "requirements.yaml",
     "- id: C-34\n  kind: conformance", "- id: C-34\n  kind: recommended", "[1]", False),
    ("an RFC 2119 keyword used in explanatory prose", "docs/intent-specification.md",
     "Misdeclaration is then handled by reconciliation (§10) and",
     "Misdeclaration **SHOULD** then be handled by reconciliation (§10) and", "[5]", False),
    ("a binding keyword with no requirement number", "docs/intent-specification.md",
     "Types are an open registry.", "Types **MUST** be an open registry.", "[5]", False),
    ("a retired term reintroduced", "docs/intent-specification.md",
     "the affected action pattern's accrued precedent", "the affected shape's accrued precedent", "[6]", False),
    ("an intent schema rolled back to v1", "schemas/intent-decision.schema.json",
     "schema/v2/intent-decision.json", "schema/v1/intent-decision.json", "[7]", False),
    ("a worked example left on the old schema", "schemas/examples/intents/decision-record.json",
     "schema/v2/intent-decision.json", "schema/v1/intent-decision.json", "[7]", False),
    ("prose naming a field no schema defines", "docs/intent-specification.md",
     "**MUST** declare `valid_until`, an RFC 3339 timestamp",
     "**MUST** declare `expiry_deadline`, an RFC 3339 timestamp", "[8]", False),
    ("a field removed from the schema but still cited in prose", "schemas/intent.schema.json",
     '"valid_until": {', '"valid_until_renamed": {', "[8]", False),
    ("a keyword span broken across a line", "docs/intent-specification.md",
     "An implementation **MUST NOT**\nintroduce a factor",
     "An implementation **MUST\nNOT** introduce a factor", "[5]", False),
    ("a link pointing at a missing anchor", "docs/intent-specification.md",
     "[`intents.md`](intents.md) — the model and its rationale",
     "[the shape key](#n-22-shape-key) — the model and its rationale", "[4]", False),
]


def wrap_tolerant_replace(text: str, old: str, new: str) -> str | None:
    """Replace across the source's hard wrapping, re-wrapping the touched paragraph."""
    if old in text:
        return text.replace(old, new, 1)
    blocks = text.split("\n\n")
    for i, b in enumerate(blocks):
        flat = re.sub(r"\s+", " ", b)
        if old in flat:
            blocks[i] = "\n".join(textwrap.wrap(flat.replace(old, new, 1), 78,
                                                break_long_words=False,
                                                break_on_hyphens=False))
            return "\n\n".join(blocks)
    return None


passed = failed = 0
for label, rel, old, new, tag, regen in FAULTS:
    with tempfile.TemporaryDirectory() as td:
        work = Path(td) / "spec"
        # Ignore by path, not basename: shutil.ignore_patterns("examples") would
        # also drop schemas/examples/, which the vocabulary and schema-family
        # gates read — leaving those gates untested here.
        SKIP_TOP = {".git", "sdk", "node_modules", "__pycache__", "plugins",
                    "examples", "integrations", "tests-e2e", "planning"}

        def _ignore(directory: str, entries: list[str]) -> set[str]:
            rel = Path(directory).relative_to(SPEC)
            if rel == Path("."):
                return {e for e in entries if e in SKIP_TOP}
            return {e for e in entries if e == "__pycache__"}

        shutil.copytree(SPEC, work, ignore=_ignore)
        p = work / rel
        mutated = wrap_tolerant_replace(p.read_text(encoding="utf-8"), old, new)
        if mutated is None:
            print(f"  ERROR  {label}: fault pattern not found"); failed += 1; continue
        p.write_text(mutated, encoding="utf-8")
        tool = str(work / "tools" / "check_spec.py")
        if regen:
            # Regenerate so the derived tables match the mutated registry; this
            # isolates the gate under test from the staleness check.
            subprocess.run([PY, tool, "--regenerate"], capture_output=True, cwd=work)
        r = subprocess.run([PY, tool], capture_output=True, text=True, cwd=work)
        hit = next((l for l in r.stdout.splitlines() if l.startswith("FAIL " + tag)), None)
        if r.returncode != 0 and hit:
            passed += 1
            print(f"  CAUGHT {tag} {label}\n         {hit[5:110]}")
        else:
            failed += 1
            print(f"  MISSED {tag} {label}\n         rc={r.returncode} {r.stdout.strip()[:160]}")

print(f"\n{passed} caught, {failed} missed, of {passed + failed} injected faults")
sys.exit(1 if failed else 0)
