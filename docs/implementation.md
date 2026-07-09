# Implementation Guide

This guide provides step-by-step instructions for implementing the RMACD Framework in your organization.

## Prerequisites

Before implementing RMACD, ensure you have:

1. **Inventory of AI agents** — Document all deployed or planned autonomous agents
2. **Identified stakeholders** — Change management, security, compliance teams
3. **Approval workflow infrastructure** — Ticketing system, notification capabilities

## Step 1: Choose Your Implementation Model

### Two-Dimensional Model (RMACD + HITL)

Choose this if:
- Your organization does not have formal data classification
- You need rapid adoption
- You're piloting with a limited scope

### Three-Dimensional Model (RMACD + HITL + Data Classification)

Choose this if:
- You have an established data classification scheme
- You operate in a regulated industry
- Your agents access data across multiple sensitivity levels

### Data-Classification Two-Dimensional Model (DC2D: Data Classification + HITL)

Choose this if:
- Your primary governance lever is data sensitivity, not operation type
- Operational permissions are already governed upstream (IAM/RBAC, DLP, gateway)
- You need redaction and egress controls as the enforcement surface

See spec Appendix D for the full DC2D variant.

## Step 2: Define Permission Profiles

Start with the provided templates:

- **Observer** — Read-only agents
- **Logistics** — Read + Move agents
- **Provisioning** — Read + Move + Add agents
- **Operations** — Read + Move + Add + Change agents
- **Administrator** — Full RMACD (with restrictions on Restricted data)

Customize as needed for your agent types.

## Step 3: Configure Policy Enforcement

Integrate RMACD with your agent runtime:

1. Load permission profiles from your policy store
2. Intercept agent operation requests
3. Evaluate against the governance matrix
4. Enforce autonomy requirements (allow, notify, queue for approval, deny)
5. Log all decisions for audit

## Step 4: Integrate Approval Workflows

Map autonomy levels to your existing systems:

| Autonomy Level | Integration |
|----------------|-------------|
| Autonomous | No integration needed |
| Logged | Enhanced logging pipeline |
| Notification | Email, Slack, Teams alerts |
| Approval | ServiceNow, Jira, custom ticketing |
| Elevated Approval | CAB workflow, senior management queue |
| Prohibited | Block with explanation |

## Step 5: Test and Validate

Before production enforcement:

1. Run in audit-only mode (log decisions, don't enforce)
2. Review logs for unexpected denials or approvals
3. Adjust profiles and matrix as needed
4. Gradually enable enforcement

## Step 6: Monitor and Iterate

Ongoing operations:

1. Review agent behavior patterns
2. Adjust permissions based on demonstrated trustworthiness
3. Respond to incidents and update profiles
4. Conduct periodic compliance audits

---

## Python SDK

The `rmacd-framework` package on PyPI ships the enforcement plumbing
that turns a profile decision into an action. Install with:

```bash
pip install rmacd-framework
```

Core components:

- **`PolicyEvaluator`** — pure decision function (no side effects).
- **`PolicyEnforcer`** — decision + approval routing + audit emission +
  typed exceptions, plus DC2D `apply_redaction()` and `check_egress()`.
- **`ApprovalGateway`** — pluggable approval surface
  (`RejectAllApprovalGateway`, `AutoApproveGateway`; integrators
  implement against ServiceNow, Slack, PagerDuty, webhooks).
- **`AuditLogger`** — pluggable audit sink (`JSONLAuditLogger`,
  `NullAuditLogger`).
- **`Redactor`** (DC2D) — `NullRedactor` and `RegexRedactor` for
  output PII masking.
- **`EgressGate`** (DC2D) — `PolicyDrivenEgressGate` for destination
  allow-listing and external-model blocking.
- **`RMACDError` hierarchy** — typed exceptions for each non-allow
  outcome (denied, prohibited, constraint, approval-required,
  approval-denied, approval-timeout, egress-blocked).

Source: `sdk/python/rmacd/`. Schema validation, profile loading, and the
Tools Registry are also available under the same package
(`from rmacd import ...`, `from rmacd.registry import ...`).

## Reference integrations

Runnable end-to-end examples in `examples/`:

| Directory | What it shows |
|---|---|
| `agent-integration-claude-sdk/` | Claude Agent SDK with `PreToolUse` hook → `PolicyEnforcer.enforce_tool_call` (registry-backed). |
| `agent-integration-anthropic-sdk/` | Raw Anthropic SDK manual tool-use loop; the most portable template. |
| `dc2d-customer-support/` | DC2D redaction and egress controls demonstrated without an LLM. |

## Companion runtime docs

- [`docs/runtime-patterns.md`](runtime-patterns.md) — profile binding,
  classification lookup, approval-wait, error contract, DC2D runtime,
  end-to-end integration checklist.
- [`docs/framework-adapters.md`](framework-adapters.md) — registry-backed
  `enforce_tool_call`, plus OpenAI Agents SDK, Microsoft Agent Framework,
  LangChain, AutoGen, and CrewAI integration snippets.

## Tools registry

`from rmacd.registry import ToolsRegistry` is the first-class tool→RMACD
classifier and capability ceiling that `PolicyEnforcer.enforce_tool_call`
consults to enforce *profile ∩ tool*. The previously-standalone
`tools-registry/` directory has been removed; its content lives in
`rmacd.registry`.

Classification engines available at tool-registration time:

- **Manual** — `ToolDefinition(rmacd_level=..., data_access=...)`, optionally
  with a dynamic `classifier=` that resolves `(operation, tier, target)` from
  the call's arguments (e.g. `make_bash_classifier()` for shell commands).
- **Keyword heuristic** — `MCPRegistryBridge` auto-classifies MCP
  `tools/list` entries; every auto-classified tool gets a capability ceiling
  at its inferred operation plus provenance metadata, and
  `bridge.low_confidence_tools()` surfaces the human-review queue.
- **LLM-assisted** (optional, `pip install rmacd-framework[llm]`) —
  `LLMToolClassifier` has a Claude model classify ambiguous tool definitions;
  used as `llm_mode="fallback"` (only when keywords are unsure) or
  `"always"`. Advisory only: the §12.5 floor, profile, and capability
  ceiling remain deterministically enforced.

---

## Governance Packs (SDK 0.11.0, recommended)

Rather than hand-writing classification per integration, populate the enforcer's
registry from **governance packs** (`rmacd.packs`) — declarative, reusable,
signable artifacts that map a tool call to RMACD terms as data:

```python
from rmacd import PolicyEnforcer
from rmacd.packs import load_packs

enforcer = PolicyEnforcer(
    profile, agent_id="agent-1",
    registry=load_packs(["aws", "kubectl", "github", "sql", "jira"]),
)
```

- **22 built-in packs** load by name (cloud CLIs, cloud IAM/identity, dev tools,
  and MCP servers for Slack/Drive/Jira/Confluence/Postgres/Microsoft 365 + AWS/Azure/GCP).
- **Author your own** with the AI-compile workflow: `rmacd classify <tools.json>`
  → `rmacd pack review` → `rmacd pack sign` (Ed25519, `[sign]` extra) →
  `rmacd pack verify` / `rmacd pack diff` (drift). The LLM runs only at authoring
  time; runtime classification is fully deterministic.
- Built-in packs are AI-drafted starting points — **review and sign** before
  production trust.

See [docs/governance-packs/](governance-packs/) for the full design, roadmap, and
authoring guide, and the runnable
[`examples/governance-packs-quickstart/`](../examples/governance-packs-quickstart/).

---

## Need Help?

- Email: contact@rmacd-framework.org
- Web: [rmacd-framework.org](https://rmacd-framework.org)
- GitHub Discussions: [rmacdframework/spec/discussions](https://github.com/rmacdframework/spec/discussions)
