"""Actor resolution (spec §3).

The engine does not know who ``spiffe://corp/ns/agents/devops-agent-007`` is;
a deployment does. ``ActorResolver`` is the seam: given the actor block it
returns whether the authorization resolved, whether ``on_behalf_of`` names an
accountable human or team, and which profile the actor is bound to. An
unresolvable authorization fails closed (N-6); a non-human actor with no
accountable human is rejected (N-5).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from rmacd import ProfileLoader
from rmacd.evaluator import AnyProfile

from .models import Actor, ActorKind


@dataclass(frozen=True)
class Resolution:
    authorized: bool
    profile: AnyProfile | None
    accountable: bool = True  # whether on_behalf_of resolved; irrelevant for humans


class ActorResolver(Protocol):
    def resolve(self, actor: Actor) -> Resolution: ...


@dataclass
class ResolvedActor:
    profile: AnyProfile
    #: Resolvable ``on_behalf_of`` values; empty means any value resolves.
    accountable: set[str] = field(default_factory=set)


class StaticActorResolver:
    """A map from ``authorization`` to a bound profile.

    This is the shipped resolver: enough for a pipeline, a file-based deployment
    and every test. A SPIFFE or OIDC resolver implements the same one-method
    protocol.
    """

    def __init__(self, bindings: dict[str, ResolvedActor]) -> None:
        self._bindings = bindings

    @classmethod
    def from_paths(
        cls,
        bindings: dict[str, str | Path],
        accountable: dict[str, set[str]] | None = None,
    ) -> StaticActorResolver:
        loader = ProfileLoader()
        resolved = {
            auth: ResolvedActor(
                profile=loader.load_file(Path(path)),
                accountable=set((accountable or {}).get(auth, set())),
            )
            for auth, path in bindings.items()
        }
        return cls(resolved)

    def resolve(self, actor: Actor) -> Resolution:
        bound = self._bindings.get(actor.authorization)
        if bound is None:
            return Resolution(authorized=False, profile=None, accountable=False)
        if actor.kind is ActorKind.HUMAN:
            return Resolution(authorized=True, profile=bound.profile, accountable=True)
        accountable = bool(actor.on_behalf_of) and (
            not bound.accountable or actor.on_behalf_of in bound.accountable
        )
        return Resolution(authorized=True, profile=bound.profile, accountable=accountable)
