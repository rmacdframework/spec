# DC2D customer-support demo

Runnable demonstration of the two DC2D-specific control surfaces:

- **Redaction** — output masking and tokenization applied after access is
  allowed but before the content reaches the agent's response surface.
- **Egress controls** — destination-side check applied before data flows
  to a downstream system.

Both surfaces sit on top of the standard `PolicyEnforcer` access decision
(`enforce()`), which is unchanged between 3D and DC2D profiles. What DC2D
adds is the data-flow plumbing that governs *what leaves* the agent once a
read is allowed.

## What it shows

```
── Reading customer records (post-access, pre-output redaction) ───────
  cust-001 (public      ) → autonomy=autonomous redacted=none
  cust-002 (internal    ) → autonomy=logged     redacted=none
  cust-003 (confidential) → autonomy=approval   redacted=email,ssn,credit_card,phone_us
  cust-004 (restricted  ) → ACCESS DENIED: RMACDProhibitedError

── Egress checks for a Confidential record ────────────────────────────
  ALLOW tenant-hosted-llm
  ALLOW internal-knowledge-base
  BLOCK https://api.openai.com/v1/chat/completions
  BLOCK https://hooks.slack.com/services/T0/B0/xxx
```

- Public / Internal pass through unredacted (they're not in `redact_tiers`).
- Confidential is approved by the `AutoApproveGateway` the demo wires in
  so the script runs deterministically, then PII is tokenized via
  `RegexRedactor`. Deployments substitute a gateway that involves a
  human (ServiceNow, Slack, CLI prompt, webhook).
- Restricted is denied entirely by the profile.
- Egress is allowed to in-profile destinations, blocked to external endpoints.

## Run

```bash
cd spec/examples/dc2d-customer-support
python demo.py
```

No API keys required; the demo is deterministic and doesn't call an LLM.

## Scope of this demo

- **No LLM integration.** The Claude Agent SDK example
  (`../agent-integration-claude-sdk/`) shows how `PreToolUse` hooks wire
  the access decision into an LLM tool loop. The two demos are
  complementary: that one shows access governance inside an LLM agent;
  this one shows data-flow governance under a DC2D profile.
- **`RegexRedactor` covers regular-shape PII** (email, SSN, credit-card,
  US phone, IPv4) and tokenizes matches stably within a process. It
  does not perform entity extraction, language-aware redaction, or
  structured PII detection. Deployments needing those capabilities
  implement `Redactor` against a dedicated engine (Presidio, Microsoft
  Purview, AWS Macie, Cyberhaven) and pass it via `redactor=`.
- **Egress destinations are matched against the profile's allow-list**
  by exact equality or substring. Deployments with richer egress
  regimes (geofencing, per-vendor sub-policies, dynamic threat-intel
  feeds) implement `EgressGate` directly.

## Files

```
.
├── README.md
├── demo.py    # The whole thing — one self-contained script
```

## Profile used

`schemas/examples/regulated-data-handler-dc2d.json` — a regulated-industry
customer-support agent with:

| Tier | Allowed | Autonomy | Redaction |
|---|---|---|---|
| Public | yes | autonomous | none |
| Internal | yes | logged | none |
| Confidential | yes | approval | PII tokenized |
| Restricted | **no** | prohibited | (n/a — access denied) |

Egress: only `tenant-hosted-llm` and `internal-knowledge-base` are
permitted; `block_external_models=true` would also fire for any
sensitive-tier egress to a known external model host.

## See also

- [`docs/runtime-patterns.md`](../../docs/runtime-patterns.md) §8 — the DC2D
  runtime enforcement section
- [`spec/sdk/python/rmacd/redaction.py`](../../sdk/python/rmacd/redaction.py)
- [`spec/sdk/python/rmacd/egress.py`](../../sdk/python/rmacd/egress.py)
- [RMACD spec Appendix D](../../docs/RMACD_Framework_v1.4.md#appendix-d-the-data-classification-two-dimensional-variant-dc2d)
