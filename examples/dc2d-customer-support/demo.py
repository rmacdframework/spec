"""DC2D runtime demo: customer-support agent reading mixed-tier records.

Shows the two DC2D-specific control surfaces in action:

1. **Redaction** — when the agent retrieves a Confidential customer
   record, the output is passed through ``PolicyEnforcer.apply_redaction()``
   before being exposed. PII (emails, SSNs, phone numbers, card numbers)
   is tokenized so the record is still useful for support workflows
   without leaking raw identifiers.
2. **Egress controls** — when the agent attempts to forward a record to
   a downstream system (an external LLM, an internal knowledge base), the
   destination is checked against the profile's ``egress_controls`` block.
   External model endpoints are blocked for sensitive tiers; internal
   destinations are permitted.

Unlike the Claude Agent SDK example, this one does not call out to an LLM.
The flows here are deterministic and meant to illustrate the data-flow
plumbing; readers can adapt the same surfaces into any LLM-driven agent.

Run::

    cd spec/examples/dc2d-customer-support
    python demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running from this directory without packaging.
SDK_PATH = Path(__file__).resolve().parent.parent.parent / "sdk" / "python"
if str(SDK_PATH) not in sys.path:
    sys.path.insert(0, str(SDK_PATH))

from rmacd import (  # noqa: E402
    AutoApproveGateway,
    PolicyEnforcer,
    ProfileLoader,
    RMACDEgressBlockedError,
)


PROFILE_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "schemas"
    / "examples"
    / "regulated-data-handler-dc2d.json"
)


# Mock customer record store. In a real integration this is your CRM,
# data warehouse, or customer database.
CUSTOMER_RECORDS: dict[str, dict] = {
    "cust-001": {
        "tier": "public",
        "record": "Acme Co. — public press release: new product launch in Q3.",
    },
    "cust-002": {
        "tier": "internal",
        "record": (
            "Acme Co. — internal note: account manager is Sarah; renewal "
            "discussion scheduled for next quarter."
        ),
    },
    "cust-003": {
        "tier": "confidential",
        "record": (
            "Jane Doe — primary contact jane.doe@acme.example, billing "
            "phone (555) 123-4567, support PIN 4242 4242 4242 4242, "
            "SSN on file 123-45-6789. Renewal discussion in progress."
        ),
    },
    "cust-004": {
        "tier": "restricted",
        "record": "PHI record — protected health information. Not viewable.",
    },
}


# Destinations the agent might try to forward records to.
DESTINATIONS = [
    "tenant-hosted-llm",
    "internal-knowledge-base",
    "https://api.openai.com/v1/chat/completions",
    "https://hooks.slack.com/services/T0/B0/xxx",
]


def divider(label: str = "") -> None:
    if label:
        print(f"\n── {label} " + "─" * (72 - len(label) - 5))
    else:
        print("─" * 72)


def main() -> None:
    profile = ProfileLoader().load_file(PROFILE_PATH)
    # The profile's Confidential tier requires approval. AutoApproveGateway
    # approves every request without human review, which lets this script
    # run deterministically without an interactive prompt and lets the
    # demo flow through to the redaction step. Deployments wire in a
    # gateway that involves a human (CLI prompt, Slack, ServiceNow,
    # webhook); the SDK ships CLIApprovalGateway as a ready-to-use option.
    enforcer = PolicyEnforcer(
        profile=profile,
        agent_id="support-agent-demo",
        approval_gateway=AutoApproveGateway(),
    )

    divider("Profile")
    print(f"  Loaded:    {profile.profile_id}")
    print(f"  Model:     {profile.model}")
    print(f"  Tiers:     ", end="")
    for tier in ("public", "internal", "confidential", "restricted"):
        policy = getattr(profile.data_access, tier)
        flag = "ok" if policy.allowed else "blocked"
        print(f"{tier}={flag}/{policy.autonomy.value} ", end="")
    print()

    # --- Reading records: apply redaction to the output --------------------

    divider("Reading customer records (post-access, pre-output redaction)")
    for cust_id, entry in CUSTOMER_RECORDS.items():
        tier = entry["tier"]
        raw = entry["record"]

        # Step 1: the access decision. enforce() raises if the agent can't
        # read this tier at all (e.g. restricted is denied by this profile).
        try:
            decision = enforcer.enforce(
                operation="R",
                target=f"customer://{cust_id}",
                classification=tier,
            )
        except Exception as exc:
            print(f"  {cust_id} ({tier:12}) → ACCESS DENIED: {type(exc).__name__}")
            continue

        # Step 2: redact the content before exposing it. For tiers not in
        # the profile's redact_tiers list (Public, Internal here), this
        # returns the raw content unchanged.
        redacted = enforcer.apply_redaction(raw, tier=tier)

        autonomy = decision.autonomy_level.value
        applied = ",".join(redacted.redactions_applied) or "none"
        print(f"  {cust_id} ({tier:12}) → autonomy={autonomy:10} redacted={applied}")
        print(f"    {redacted.content}")

    # --- Egress checks: where can a Confidential record flow? --------------

    divider("Egress checks for a Confidential record")
    for dest in DESTINATIONS:
        decision = enforcer.check_egress(tier="confidential", destination=dest)
        verdict = "ALLOW" if decision.allowed else "BLOCK"
        print(f"  {verdict:5} {dest}")
        if not decision.allowed:
            print(f"        reason: {decision.reason}")

    # --- raise_on_deny ergonomics ------------------------------------------

    divider("raise_on_deny=True ergonomics")
    try:
        enforcer.check_egress(
            tier="confidential",
            destination="https://api.openai.com/v1/chat/completions",
            raise_on_deny=True,
        )
    except RMACDEgressBlockedError as exc:
        print(f"  Raised RMACDEgressBlockedError:")
        print(f"    destination:  {exc.destination}")
        print(f"    tier:         {exc.tier}")
        print(f"    matched_rule: {exc.matched_rule}")
        print(f"    message:      {exc}")

    divider()
    print("Done.")


if __name__ == "__main__":
    main()
