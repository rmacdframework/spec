"""Output redaction for DC2D profiles.

The DC2D variant (Appendix D) drops the operations axis on the assumption
that the IAM/DLP layer governs *what* an agent can do, leaving redaction as
the primary control surface for governing *what data flows back out* once an
operation is allowed. This module makes that control surface concrete.

The flow:

1. The agent calls a tool that reads Confidential or Restricted data.
2. The enforcer's access decision (``PolicyEnforcer.enforce``) allows the
   read because the profile's ``data_access[tier].allowed`` is true and the
   autonomy stance is satisfied (e.g. ``logged`` or ``approval``-approved).
3. **Before** the tool's output reaches the agent's response surface, the
   caller passes it through ``PolicyEnforcer.apply_redaction()``. That
   method delegates to a ``Redactor`` which masks PII, tokenizes
   identifiers, or replaces the content entirely, depending on the
   profile's ``RedactionPolicy``.

This module ships two ``Redactor`` implementations:

- ``NullRedactor`` — pass-through. Default when no redactor is configured.
  Suitable for tests and for 3D profiles where redaction isn't part of the
  enforcement surface.
- ``RegexRedactor`` — pattern-based redaction covering email, US SSN,
  credit-card-shaped numbers, US phone numbers, and IPv4 addresses, with
  optional stable tokenization. It does not perform entity extraction,
  language-aware redaction, or structured PII detection. Deployments
  requiring those capabilities implement ``Redactor`` against a
  dedicated PII engine (Presidio, Microsoft Purview, AWS Macie,
  Cyberhaven) and pass it to ``PolicyEnforcer`` via ``redactor=``.
"""

from __future__ import annotations

import re
from typing import Protocol

from pydantic import BaseModel, Field

from rmacd.models import DataClassification, RedactionPolicy


class RedactionResult(BaseModel):
    """Result of redacting a string.

    Carries both the redacted content and a structured account of what was
    redacted so the audit pipeline can record the action without leaking
    the original sensitive value into the log.
    """

    content: str = Field(description="The redacted output")
    redactions_applied: list[str] = Field(
        default_factory=list,
        description=(
            "Names of the patterns that fired (e.g. 'email', 'ssn'). The "
            "matched values themselves are intentionally not retained."
        ),
    )
    tier: DataClassification | None = Field(
        default=None,
        description="The data tier this redaction was performed against",
    )


class Redactor(Protocol):
    """Pluggable content redactor.

    Implementations transform the input content according to the
    ``RedactionPolicy`` and return a ``RedactionResult``. The transform must
    be idempotent: running redaction twice on the same content should
    produce the same output.
    """

    def redact(
        self,
        content: str,
        tier: DataClassification,
        policy: RedactionPolicy,
    ) -> RedactionResult: ...


class NullRedactor:
    """No-op redactor. Pass-through.

    The default when no redactor is configured. Returns the input unchanged
    and records no redactions. Use only for non-DC2D profiles or in tests
    where the redaction interface is exercised but no actual masking is
    desired.
    """

    def redact(
        self,
        content: str,
        tier: DataClassification,
        policy: RedactionPolicy,
    ) -> RedactionResult:
        del policy
        return RedactionResult(content=content, redactions_applied=[], tier=tier)


# Default PII patterns. Deliberately conservative: better to under-match
# than to corrupt non-PII content. Deployments needing entity extraction
# or structured PII detection (e.g. addresses, names, custom record IDs)
# implement ``Redactor`` against a dedicated engine rather than extending
# this pattern set.
_DEFAULT_PATTERNS: dict[str, tuple[re.Pattern[str], str]] = {
    "email": (
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        "[REDACTED_EMAIL]",
    ),
    "ssn": (
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "[REDACTED_SSN]",
    ),
    "credit_card": (
        # 13-19 digit sequences with optional separators; matches Visa,
        # Mastercard, Amex, Discover shapes. Will produce false positives
        # for long numeric IDs — acceptable for a default pattern.
        re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
        "[REDACTED_CARD]",
    ),
    "phone_us": (
        re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
        "[REDACTED_PHONE]",
    ),
    "ipv4": (
        re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
        "[REDACTED_IP]",
    ),
}


class RegexRedactor:
    """Pattern-based redactor.

    Replaces matches of a configured pattern set with named tokens. The
    default pattern set covers common PII shapes (email, SSN, credit
    card, US phone, IPv4). Callers can add or replace patterns via
    ``patterns=``.

    Tokenization (``policy.tokenize_identifiers``) replaces the match with
    a stable hash-prefix token (e.g. ``[TOKEN_email_a1b2c3]``) so the
    same value redacts to the same token within one process — useful for
    keeping outputs internally consistent without leaking the original.
    """

    def __init__(
        self,
        patterns: dict[str, tuple[re.Pattern[str], str]] | None = None,
    ) -> None:
        self.patterns = patterns if patterns is not None else dict(_DEFAULT_PATTERNS)

    def redact(
        self,
        content: str,
        tier: DataClassification,
        policy: RedactionPolicy,
    ) -> RedactionResult:
        # Honour the policy's tier scoping: if this tier isn't on the
        # redact_tiers list, return the content unchanged. Callers should
        # still route through the redactor so the audit pipeline sees a
        # consistent shape — RedactionResult with an empty applied list.
        if tier not in policy.redact_tiers:
            return RedactionResult(content=content, redactions_applied=[], tier=tier)

        # If the policy has mask_pii disabled, we treat that as "redaction
        # is policy-disabled for this tier" and pass through. The tier-
        # scoped redact_tiers list is the primary lever; mask_pii is the
        # global switch.
        if not policy.mask_pii:
            return RedactionResult(content=content, redactions_applied=[], tier=tier)

        applied: list[str] = []
        out = content
        for name, (pattern, replacement) in self.patterns.items():
            new_out, count = pattern.subn(
                self._make_replacement(name, replacement, policy.tokenize_identifiers),
                out,
            )
            if count > 0:
                applied.append(name)
                out = new_out
        return RedactionResult(content=out, redactions_applied=applied, tier=tier)

    @staticmethod
    def _make_replacement(name: str, default: str, tokenize: bool):
        if not tokenize:
            return lambda _m: default

        # When tokenization is on, replace each unique match with a stable
        # token within the process so the same value redacts to the same
        # token consistently. Using a content-hash keeps it deterministic
        # per process without retaining the original.
        def _repl(match: re.Match[str]) -> str:
            import hashlib

            digest = hashlib.sha256(match.group(0).encode("utf-8")).hexdigest()[:8]
            return f"[TOKEN_{name}_{digest}]"

        return _repl


__all__ = [
    "NullRedactor",
    "RedactionResult",
    "Redactor",
    "RegexRedactor",
]
