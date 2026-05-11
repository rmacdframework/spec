"""Tests for the DC2D runtime surfaces added in SDK 0.5.0.

These cover the redaction and egress-control plumbing layered on top of
``PolicyEnforcer``. The DC2D *access decision* itself is already covered
by ``test_evaluator.py``; the focus here is on the data-flow surfaces
that only DC2D profiles activate.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rmacd import (
    DataClassification,
    NullRedactor,
    PolicyDrivenEgressGate,
    PolicyEnforcer,
    ProfileLoader,
    Profile3D,
    ProfileDC2D,
    RegexRedactor,
    RMACDEgressBlockedError,
)
from rmacd.models import EgressControls, RedactionPolicy


FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "schemas" / "examples"


# ---- fixtures --------------------------------------------------------------


@pytest.fixture
def dc2d_profile() -> ProfileDC2D:
    profile = ProfileLoader().load_file(FIXTURE_DIR / "regulated-data-handler-dc2d.json")
    assert isinstance(profile, ProfileDC2D)
    return profile


@pytest.fixture
def three_d_profile() -> Profile3D:
    profile = ProfileLoader().load_file(FIXTURE_DIR / "observer-3d.json")
    assert isinstance(profile, Profile3D)
    return profile


@pytest.fixture
def dc2d_enforcer(dc2d_profile) -> PolicyEnforcer:
    return PolicyEnforcer(profile=dc2d_profile, agent_id="dc2d-test")


@pytest.fixture
def three_d_enforcer(three_d_profile) -> PolicyEnforcer:
    return PolicyEnforcer(profile=three_d_profile, agent_id="3d-test")


# ---- redaction -------------------------------------------------------------


def test_dc2d_profile_redacts_confidential_pii(dc2d_enforcer):
    content = "Customer: jane.doe@example.com, SSN 123-45-6789"
    result = dc2d_enforcer.apply_redaction(content, "confidential")
    assert "jane.doe@example.com" not in result.content
    assert "123-45-6789" not in result.content
    assert "email" in result.redactions_applied
    assert "ssn" in result.redactions_applied


def test_dc2d_profile_does_not_redact_public_tier(dc2d_enforcer):
    # The reference profile only redacts Confidential/Restricted; Public
    # and Internal should pass through unchanged.
    content = "Customer: jane.doe@example.com"
    result = dc2d_enforcer.apply_redaction(content, "public")
    assert result.content == content
    assert result.redactions_applied == []


def test_dc2d_tokenization_is_stable_for_same_value(dc2d_enforcer):
    content = "Email A: jane@x.com, Email B: jane@x.com, Email C: john@x.com"
    result = dc2d_enforcer.apply_redaction(content, "confidential")
    # Each unique email should map to a unique token; same email → same token
    tokens = [
        part for part in result.content.split() if part.startswith("[TOKEN_email_")
    ]
    assert len(tokens) >= 2
    # The two "jane@x.com" tokens should match each other; "john@x.com"
    # produces a different token.
    jane_tokens = {t for t in tokens if "[TOKEN_email_" in t}
    assert len(jane_tokens) == 2  # jane gets one token, john another


def test_three_d_profile_redaction_is_pass_through(three_d_enforcer):
    # 3D profiles have no redaction block, so apply_redaction should be
    # a no-op that returns the content unchanged.
    content = "SSN 123-45-6789"
    result = three_d_enforcer.apply_redaction(content, "confidential")
    assert result.content == content
    assert result.redactions_applied == []


def test_redactor_respects_mask_pii_off():
    policy = RedactionPolicy(
        mask_pii=False,
        redact_tiers=[DataClassification.CONFIDENTIAL],
        tokenize_identifiers=False,
    )
    redactor = RegexRedactor()
    result = redactor.redact(
        "SSN 123-45-6789", DataClassification.CONFIDENTIAL, policy
    )
    # mask_pii=False is the global off-switch; content should pass through.
    assert result.content == "SSN 123-45-6789"
    assert result.redactions_applied == []


def test_null_redactor_never_modifies():
    redactor = NullRedactor()
    policy = RedactionPolicy(
        mask_pii=True,
        redact_tiers=[DataClassification.CONFIDENTIAL],
        tokenize_identifiers=True,
    )
    out = redactor.redact("anything goes", DataClassification.CONFIDENTIAL, policy)
    assert out.content == "anything goes"
    assert out.redactions_applied == []


# ---- egress ----------------------------------------------------------------


def test_dc2d_egress_blocks_destinations_off_allowlist(dc2d_enforcer):
    # The reference profile's allow-list is ["tenant-hosted-llm",
    # "internal-knowledge-base"]. OpenAI is not on it.
    decision = dc2d_enforcer.check_egress(
        "confidential", "https://api.openai.com/v1/chat/completions"
    )
    assert decision.allowed is False
    assert decision.matched_rule == "allowlist"


def test_dc2d_egress_permits_allowlist_destination(dc2d_enforcer):
    decision = dc2d_enforcer.check_egress("confidential", "tenant-hosted-llm")
    assert decision.allowed is True


def test_egress_raise_on_deny_raises_correct_exception(dc2d_enforcer):
    with pytest.raises(RMACDEgressBlockedError) as ei:
        dc2d_enforcer.check_egress(
            "confidential",
            "https://api.openai.com/v1/chat/completions",
            raise_on_deny=True,
        )
    assert ei.value.destination is not None
    assert "openai" in ei.value.destination


def test_block_external_models_without_allowlist():
    # Build a profile-driven gate directly so we can isolate the
    # block_external_models rule from the allowlist rule.
    gate = PolicyDrivenEgressGate()
    controls = EgressControls(block_external_models=True, allowed_destinations=None)

    # Confidential → known external model host → blocked
    decision = gate.check(
        "https://api.anthropic.com/v1/messages",
        DataClassification.CONFIDENTIAL,
        controls,
    )
    assert decision.allowed is False
    assert decision.matched_rule == "block_external_models"

    # Public → same host → allowed (rule only fires on sensitive tiers)
    decision = gate.check(
        "https://api.anthropic.com/v1/messages",
        DataClassification.PUBLIC,
        controls,
    )
    assert decision.allowed is True


def test_egress_with_no_controls_is_pass_through(three_d_enforcer):
    # 3D profiles carry no egress_controls block; the gate should see
    # None and allow everything.
    decision = three_d_enforcer.check_egress(
        "confidential", "https://api.openai.com/v1/anything"
    )
    assert decision.allowed is True
    assert decision.matched_rule == "no_constraints"
