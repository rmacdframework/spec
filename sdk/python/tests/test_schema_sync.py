"""Guard against the bundled schemas drifting from the authoritative copies.

The authoritative schemas live in <repo>/schemas/. The package bundles
byte-identical copies under rmacd/schemas/ so a wheel install can validate
profiles without the repo checkout. If this test fails, re-copy the
authoritative files:

    cp ../../schemas/profile-*.schema.json rmacd/schemas/
"""

from pathlib import Path

import pytest

SCHEMA_NAMES = [
    "profile-2d.schema.json",
    "profile-3d.schema.json",
    "profile-dc2d.schema.json",
]

BUNDLED_DIR = Path(__file__).parent.parent / "rmacd" / "schemas"
AUTHORITATIVE_DIR = Path(__file__).parent.parent.parent.parent / "schemas"


@pytest.mark.skipif(
    not AUTHORITATIVE_DIR.exists(),
    reason="authoritative schemas not available (running outside the repo checkout)",
)
@pytest.mark.parametrize("name", SCHEMA_NAMES)
def test_bundled_schema_matches_authoritative(name: str) -> None:
    bundled = BUNDLED_DIR / name
    authoritative = AUTHORITATIVE_DIR / name

    assert bundled.exists(), f"bundled schema missing: {bundled}"
    assert authoritative.exists(), f"authoritative schema missing: {authoritative}"
    assert bundled.read_bytes() == authoritative.read_bytes(), (
        f"{name} has drifted from the authoritative copy in {AUTHORITATIVE_DIR}; "
        f"re-copy it into rmacd/schemas/"
    )
