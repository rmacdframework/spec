"""Egress controls for DC2D profiles.

Egress gating is the second of the two DC2D-specific control surfaces
(redaction is the first). Where redaction shapes *what* leaves an agent,
egress gating governs *where* it can go: external LLM endpoints, vendor
APIs, internal services, customer-facing channels.

The DC2D profile's ``egress_controls`` block declares:

- ``allowed_destinations`` — an explicit allow-list of destination labels
  or patterns. When set, only matching destinations are permitted.
- ``block_external_models`` — a categorical block on Confidential/Restricted
  data flowing to external (non-tenant) model endpoints. Defaults to
  ``True`` per Appendix D.

Callers ask the gate before performing an egress operation:

    decision = enforcer.check_egress(tier="confidential", destination="https://api.openai.com/v1/...")
    if not decision.allowed:
        raise RMACDEgressBlockedError(decision.reason)

The decision is intentionally separate from ``PolicyEnforcer.enforce`` —
egress is checked at the *destination* side of a data flow, often in
different code from the access decision.
"""

from __future__ import annotations

from typing import Protocol
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from rmacd.models import DataClassification, EgressControls


class EgressDecision(BaseModel):
    """Result of an egress check."""

    allowed: bool
    destination: str
    tier: DataClassification
    reason: str | None = Field(
        default=None,
        description="Human-readable explanation when ``allowed`` is False",
    )
    matched_rule: str | None = Field(
        default=None,
        description=(
            "Which rule fired: 'allowlist', 'block_external_models', "
            "'no_constraints', or 'unconfigured'"
        ),
    )


class EgressGate(Protocol):
    """Pluggable egress-decision surface.

    Implementations evaluate the destination against a policy and return
    an ``EgressDecision``. The default ``PolicyDrivenEgressGate`` uses the
    profile's ``EgressControls`` block; integrators with richer policies
    (e.g. a network policy product, an API gateway with allow-listed
    routes) plug in their own.
    """

    def check(
        self,
        destination: str,
        tier: DataClassification,
        controls: EgressControls | None,
    ) -> EgressDecision: ...


# Default external-model host heuristics. Conservative: a deployment that
# uses external models for Public/Internal-only flows should not be flagged
# here; ``block_external_models`` only fires for Confidential/Restricted.
# Production deployments should replace this with their actual external-vs-
# tenant model registry.
_KNOWN_EXTERNAL_MODEL_HOSTS = frozenset(
    {
        "api.openai.com",
        "api.anthropic.com",
        "generativelanguage.googleapis.com",
        "api.mistral.ai",
        "api.cohere.ai",
        "api.together.xyz",
        "api.fireworks.ai",
        "api.perplexity.ai",
    }
)


def _normalize_host(host: str | None) -> str | None:
    """Canonical form of a hostname for comparison.

    DNS hostnames are case-insensitive and a single trailing dot denotes the
    root zone, so ``API.OpenAI.com``, ``api.openai.com`` and
    ``api.openai.com.`` all name the same host. Comparing them literally let
    the first and third bypass ``block_external_models`` and made allow-list
    entries case-sensitive.
    """
    if not host:
        return None
    normalized = host.strip().rstrip(".").lower()
    return normalized or None


class PolicyDrivenEgressGate:
    """Default gate. Reads decisions off the profile's ``EgressControls``.

    Decision order (first match wins):

    1. **No controls configured** — allow (no-op). The caller wired up the
       gate but the profile says nothing; default-allow keeps the gate
       transparent for profiles that don't use this surface.
    2. **Allow-list set and destination doesn't match** — deny. An
       explicit allow-list is treated as exhaustive: if it's set, only
       matches pass.
    3. **``block_external_models`` set and tier is Confidential/Restricted
       and destination is a known external model host** — deny.
    4. Otherwise — allow.

    The class is intentionally simple: it codifies the Appendix D rules
    and nothing more. Integrators with more sophisticated egress regimes
    (geofencing, per-vendor sub-policies, dynamic threat-intel feeds)
    implement ``EgressGate`` directly rather than subclass this.
    """

    def __init__(
        self,
        external_model_hosts: frozenset[str] | None = None,
    ) -> None:
        raw_hosts = (
            external_model_hosts
            if external_model_hosts is not None
            else _KNOWN_EXTERNAL_MODEL_HOSTS
        )
        # Normalize at construction so membership tests below are case- and
        # trailing-dot-insensitive regardless of how the caller spelled them.
        self.external_model_hosts = frozenset(
            normalized
            for normalized in (_normalize_host(host) for host in raw_hosts)
            if normalized is not None
        )

    def check(
        self,
        destination: str,
        tier: DataClassification,
        controls: EgressControls | None,
    ) -> EgressDecision:
        if controls is None:
            return EgressDecision(
                allowed=True,
                destination=destination,
                tier=tier,
                matched_rule="no_constraints",
            )

        # Rule 2: explicit allow-list, if set, is exhaustive.
        if controls.allowed_destinations and not self._matches_allowlist(
            destination, controls.allowed_destinations
        ):
            return EgressDecision(
                    allowed=False,
                    destination=destination,
                    tier=tier,
                    reason=(
                        f"Destination '{destination}' is not in the profile's "
                        f"allowed_destinations list."
                    ),
                    matched_rule="allowlist",
                )

        # Rule 3: external model block for sensitive tiers.
        sensitive_tiers = {DataClassification.CONFIDENTIAL, DataClassification.RESTRICTED}
        if controls.block_external_models and tier in sensitive_tiers:
            host = self._extract_host(destination)
            if host and host in self.external_model_hosts:
                return EgressDecision(
                    allowed=False,
                    destination=destination,
                    tier=tier,
                    reason=(
                        f"Tier '{tier.value}' is blocked from egressing to "
                        f"external model host '{host}' (profile sets "
                        f"block_external_models=true)."
                    ),
                    matched_rule="block_external_models",
                )

        # No rule denied; allow.
        return EgressDecision(
            allowed=True,
            destination=destination,
            tier=tier,
            matched_rule="allowlist" if controls.allowed_destinations else "no_constraints",
        )

    @classmethod
    def _matches_allowlist(cls, destination: str, allowed: list[str]) -> bool:
        # The allow-list entries in the profile schema are free-form labels
        # (e.g. "tenant-hosted-llm") or hostnames rather than full URLs.
        # Matching is intentionally constrained to avoid the substring-bypass
        # class of bug (where an entry "internal" would wrongly admit
        # "evil.internal-breach.com"). An entry matches when it is:
        #   - exactly equal to the destination, OR
        #   - equal to the destination's host, OR
        #   - a parent-domain suffix of the destination's host
        #     (e.g. "example.com" matches "api.example.com").
        host = cls._extract_host(destination)
        for entry in allowed:
            if entry == destination:
                return True
            if host is not None:
                # Both sides are normalized by _extract_host, so an entry
                # spelled "Tenant-Hosted-LLM" or "Example.COM" still matches.
                entry_host = cls._extract_host(entry) or _normalize_host(entry)
                if entry_host is not None and (
                    host == entry_host or host.endswith("." + entry_host)
                ):
                    return True
        return False

    @staticmethod
    def _extract_host(destination: str) -> str | None:
        # Parse the destination as a URL and return the host. urlparse only
        # populates ``hostname`` when a scheme is present, so fall back to
        # treating a scheme-less destination as a bare "host[/path]" — without
        # this, "api.openai.com/v1" would yield no host and the external-model
        # block would silently not fire. Returns a *normalized* host (lower
        # case, no trailing root dot); every comparison in this class is
        # therefore case-insensitive, so "API.OpenAI.com/v1" and
        # "api.openai.com." cannot slip past a rule that "api.openai.com"
        # would trip. Returns None for empty input; non-host-shaped labels
        # (e.g. "internal-kb") come back as themselves, which the allow-list
        # rule handles.
        if "://" in destination:
            return _normalize_host(urlparse(destination).hostname)
        # Bare host or "host/path": take the authority portion before any path.
        candidate = destination.split("/", 1)[0]
        # Strip a port if present (host:port), but not if it's clearly a label.
        host = candidate.rsplit(":", 1)[0] if candidate.count(":") == 1 else candidate
        return _normalize_host(host)


__all__ = [
    "EgressDecision",
    "EgressGate",
    "PolicyDrivenEgressGate",
]
