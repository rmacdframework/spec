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
    "pack.schema.json",
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


def test_built_distribution_ships_its_data_files() -> None:
    """The wheel must carry py.typed, the schemas and every built-in pack.

    Tests run from the source tree, so a mistake in the hatch ``artifacts``
    list is invisible to every other test while shipping a wheel where
    ``load_pack("aws")`` raises FileNotFoundError for every user. PEP 561 also
    requires the ``py.typed`` marker for the strict typing here to reach
    consumers at all.
    """
    from pathlib import Path

    from rmacd.packs import builtin_pack_names

    root = Path(__file__).resolve().parents[1]
    # Parsed as text, not via tomllib: the SDK supports Python 3.10, where
    # tomllib does not exist and tomli is not a dependency.
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    artifacts_block = pyproject.split("artifacts = [", 1)[1].split("]", 1)[0]
    artifacts = [
        line.strip().rstrip(",").strip('"')
        for line in artifacts_block.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    assert "rmacd/py.typed" in artifacts
    assert (root / "rmacd" / "py.typed").is_file()
    assert any("schemas" in a for a in artifacts)
    assert any("packs/data" in a for a in artifacts)

    # Every built-in pack name must have a data file the artifact glob covers.
    data_dir = root / "rmacd" / "packs" / "data"
    for name in builtin_pack_names():
        assert (data_dir / f"{name}.json").is_file(), f"pack data missing for {name!r}"
