from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from rmacd_intents import MemoryStore, StaticActorResolver
from rmacd_intents.grading import Engine

REPO = Path(__file__).resolve().parents[3]
PROFILES = REPO / "schemas" / "examples"
EXAMPLES = REPO / "schemas" / "examples" / "intents"

#: authorization -> profile, matching the actors used by the worked examples.
BINDINGS = {
    "spiffe://corp/ns/agents/devops-agent-007": PROFILES / "devops-3d.json",
    "spiffe://corp/ns/ci/release-pipeline": PROFILES / "devops-3d.json",
    "spiffe://corp/ns/agents/monitoring-agent-002": PROFILES / "monitoring-3d.json",
    "okta://company.com/users/j.smith": PROFILES / "administrator-3d.json",
    "spiffe://corp/ns/agents/observer": PROFILES / "observer-3d.json",
    "spiffe://corp/ns/agents/ops-2d": PROFILES / "operations-2d.json",
    "spiffe://corp/ns/agents/handler-dc2d": PROFILES / "regulated-data-handler-dc2d.json",
}


class Clock:
    def __init__(self, start: datetime | None = None) -> None:
        self.now = start or datetime(2026, 8, 15, 10, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def resolver() -> StaticActorResolver:
    return StaticActorResolver.from_paths(BINDINGS)


@pytest.fixture
def store() -> MemoryStore:
    return MemoryStore()


@pytest.fixture
def engine(store: MemoryStore, resolver: StaticActorResolver, clock: Clock) -> Engine:
    return Engine(store, resolver, policy_version="test-policy-1", clock=clock)


def example(name: str) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((EXAMPLES / name).read_text(encoding="utf-8"))
    return loaded


def intent(**overrides: Any) -> dict[str, Any]:
    """A valid production change by the devops agent, with overrides applied shallowly."""
    doc = example("change-production.json")
    doc.update(overrides)
    return doc
