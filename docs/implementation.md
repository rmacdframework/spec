# Implementation Guide

This guide provides step-by-step instructions for implementing the RMACD Framework in your organization.

## Prerequisites

Before implementing RMACD, ensure you have:

1. **Inventory of AI agents** — Document all deployed or planned autonomous agents
2. **Identified stakeholders** — Change management, security, compliance teams
3. **Approval workflow infrastructure** — Ticketing system, notification capabilities

## Step 1: Choose Your Implementation Model

Pick the shape that matches the governance lever you actually control. The
decision is not about ambition — it is about which axis your organization can
already populate with trustworthy values. A 3D profile whose classification
tiers are guesses is weaker than a 2D profile whose operations are exact.

| | Three-Dimensional (default) | Two-Dimensional (Operational) | DC2D (Data-Classification 2D) |
|---|---|---|---|
| **Dimensions** | RMACD × HITL × Data Classification | RMACD × HITL | Data Classification × HITL |
| **Schema** | `profile-3d` | `profile-2d` | `profile-dc2d` |
| **Profile ID pattern** | `rmacd-3d-*` | `rmacd-2d-*` | `rmacd-dc2d-*` |
| **Choose it when** | You have an established classification scheme; you're in a regulated industry; agents span multiple sensitivity levels | You have no formal classification tiers; you need rapid adoption; you're piloting with a limited scope | Data sensitivity, not operation type, is your primary lever |
| **Assumes governed upstream** | Nothing | Data sensitivity | Operational permissions (IAM/RBAC, DLP, gateway) |
| **Primary enforcement surface** | The full operation × tier matrix, including the §12.5 immutable floor | The operation × autonomy matrix | Redaction and egress controls |
| **Example profile** | `schemas/examples/devops-3d.json` | `schemas/examples/observer-2d.json` | `schemas/examples/regulated-data-handler-dc2d.json` |

See spec Appendix D for the full DC2D variant. Shapes are per-profile, not
per-organization: a 2D pilot can coexist with 3D profiles for the agents whose
data you have classified.

## Step 2: Define Permission Profiles

The cumulative permission model (D ⊃ C ⊃ A ⊃ M ⊃ R) gives a natural ladder of
roles (spec §9.4). These are conceptual templates, not identifiers the SDK
resolves:

| Ladder role | Permissions | Typical agent |
|---|---|---|
| **Observer** | `R` | Monitoring, reporting, read-only analysis |
| **Logistics** | `R`, `M` | Data movement and transfer |
| **Provisioning** | `R`, `M`, `A` | Resource creation |
| **Operations** | `R`, `M`, `A`, `C` | Day-to-day change execution |
| **Administrator** | `R`, `M`, `A`, `C`, `D` | Full RMACD |

**Administrator is not unlimited.** Add, Change and Delete on Restricted stay
prohibited for every autonomous agent — all three operations, not just Change
and Delete — and §12.5 makes that boundary non-grantable: no exception
request, and no profile field, can lift it. The SDK enforces it twice, in the
`profile-3d` schema and again as a runtime floor in the evaluator.

Worked examples ship in `schemas/examples/`, named for the deployment shape
rather than the ladder. Start from the nearest one and customize:

| Shape | Examples |
|---|---|
| 2D | `observer-2d`, `operations-2d` |
| 3D | `observer-3d`, `monitoring-3d`, `devops-3d`, `incident-responder-3d`, `administrator-3d` |
| DC2D | `regulated-data-handler-dc2d` |

### Profiles as code

Treat profiles like any other reviewed, versioned artifact — not
configuration edited by hand in a console.

**Repository layout.** Keep profiles as JSON in the agent's repository,
one file per profile:

```
rmacd/
  profiles/
    observer-3d.json
    devops-3d.json
    support-dc2d.json
```

**PR review.** A permission change is a governance change: it arrives as a
profile diff in a pull request, reviewed by the profile owner (and, for
autonomy or classification changes, whoever your governance process names —
e.g. change management or security). The JSON diff shows exactly which
cell of the matrix moved.

**CI validation.** Gate every push/PR with the
[RMACD Validate action](../integrations/github-action/README.md):

```yaml
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: rmacdframework/spec/integrations/github-action@main
        with:
          profiles: "rmacd/profiles/*.json"
```

For local feedback before CI, the same check is available as a
[pre-commit](https://pre-commit.com) hook (`id: rmacd-validate`) — see the
action README for the `.pre-commit-config.yaml` snippet.

**Inject at agent startup.** The profile the repo reviews is the profile
the agent runs: load it at startup and inject it into the agent's system
prompt with `build_system_prompt` (from `rmacd.prompts`) so the model knows
its own boundaries, while `PolicyEnforcer` bound to the same profile
enforces them deterministically:

```python
from rmacd import PolicyEnforcer, ProfileLoader
from rmacd.prompts import build_system_prompt

profile = ProfileLoader().load_file("rmacd/profiles/devops-3d.json")
system_prompt = base_prompt + "\n\n" + build_system_prompt(profile)
enforcer = PolicyEnforcer(profile, agent_id="devops-agent")
```

**Visual path.** For authoring or reviewing profiles outside the editor,
the website's Generator and Validator at
[rmacd-framework.org](https://rmacd-framework.org) build and check the same
JSON — generate visually, then commit the file through the PR flow above.

## Step 3: Configure Policy Enforcement

Integrate RMACD with your agent runtime. Each step below has a corresponding
SDK surface, so the sequence maps onto code rather than staying an abstraction:

| # | Step | SDK surface |
|---|---|---|
| 1 | Load permission profiles from your policy store | `ProfileLoader().load_file(...)` / `.load_dict(...)`, or `PolicyEnforcer.from_env()` |
| 2 | Intercept agent operation requests | Your runtime's tool-call hook (`PreToolUse`, middleware, wrapper) |
| 3 | Evaluate against the governance matrix | `PolicyEvaluator.evaluate(...)` for a pure decision |
| 4 | Enforce autonomy requirements (allow, notify, queue for approval, deny) | `PolicyEnforcer.enforce(...)` or `enforce_tool_call(...)` |
| 5 | Log all decisions for audit | `AuditLogger` — `JSONLAuditLogger` out of the box, your SIEM sink in production |

The evaluator/enforcer split matters here: use the evaluator wherever a
decision must have no side effects (dry runs, profile linters, "would this be
allowed?" UIs), and the enforcer everywhere a real call is about to happen.
See [`runtime-patterns.md`](runtime-patterns.md) §1.

## Step 4: Integrate Approval Workflows

Map autonomy levels to your existing systems. The left column is the
`AutonomyLevel` value the decision carries, so this table is also the routing
table for your `ApprovalGateway` implementation:

| Autonomy Level | `AutonomyLevel` value | Runtime behaviour | Integration |
|----------------|----------------------|-------------------|-------------|
| Autonomous | `autonomous` | Proceeds immediately | No integration needed |
| Logged | `logged` | Proceeds; decision recorded | Enhanced logging pipeline |
| Notification | `notification` | Proceeds; operator informed | Email, Slack, Teams alerts |
| Approval | `approval` | Blocks on `ApprovalGateway.request(...)` | ServiceNow, Jira, custom ticketing |
| Elevated Approval | `elevated_approval` | Blocks on the gateway, routed to a higher authority | CAB workflow, senior management queue |
| Prohibited | `prohibited` | `RMACDProhibitedError` — never reaches a gateway | Block with explanation |

Choose the gateway shape by how long an approver realistically takes:

| Expected latency | Gateway shape |
|---|---|
| Seconds to about a minute | Synchronous — Slack button, CLI prompt; the tool call waits |
| Minutes to hours | Asynchronous handoff — persist the request, return `ApprovalOutcome.TIMEOUT`, resume on a later agent turn |
| Days | Not an agent-session concern at all; route through a workflow system |

If no gateway is configured, the enforcer uses `RejectAllApprovalGateway` and
denies every approval-gated call. That default is deliberate: an unwired
approval surface is a deployment bug, and failing closed costs blocked work,
while failing open costs unreviewed change. See
[`runtime-patterns.md`](runtime-patterns.md) §5 for the full protocol.

## Step 5: Test and Validate

Before production enforcement:

1. **Run in audit-only mode** — evaluate and log decisions without enforcing
   them (`PolicyEvaluator` rather than `PolicyEnforcer`, or an enforcer whose
   exceptions your wrapper only records).
2. **Review the logs** for unexpected denials and unexpected allows. Both are
   findings: a denial storm means the profile is too tight for the agent's real
   work; a quiet log on a mutating agent usually means the classifier is
   under-reporting the operation.
3. **Adjust profiles and the matrix** — as reviewed diffs, not console edits.
4. **Gradually enable enforcement**, starting with the lowest-blast-radius
   environment and the highest-confidence tools.

## Step 6: Monitor and Iterate

Ongoing operations:

1. **Review agent behavior patterns** — `rmacd audit summarize` turns the
   JSONL trail into a per-operation, per-tier report.
2. **Adjust permissions** based on demonstrated trustworthiness.
3. **Respond to incidents** and update profiles.
4. **Conduct periodic compliance audits** — see
   [`audit-evidence.md`](audit-evidence.md) for SIEM shipping and the
   SOC 2 / ISO 27001 / GDPR control mapping.

---

## Python SDK

The `rmacd-framework` package on PyPI ships the enforcement plumbing
that turns a profile decision into an action. Install with:

```bash
pip install "rmacd-framework>=0.14"
```

The distribution name is `rmacd-framework`; the import name is `rmacd`.
Optional extras: `[mcp]` (policy MCP server), `[llm]` (Claude-assisted tool
classification), `[sign]` (Ed25519 pack signing), `[yaml]` (YAML packs and
tool-source files).

Core components:

| Component | Role | Shipped implementations |
|---|---|---|
| `PolicyEvaluator` | Pure decision function, no side effects | — |
| `PolicyEnforcer` | Decision + approval routing + audit emission + typed exceptions; plus DC2D `apply_redaction()` and `check_egress()` | — |
| `ApprovalGateway` | Pluggable approval surface | `RejectAllApprovalGateway` (default, fail-closed), `AutoApproveGateway`, `CLIApprovalGateway` |
| `AuditLogger` | Pluggable audit sink | `JSONLAuditLogger`, `NullAuditLogger` |
| `Redactor` (DC2D) | Output PII masking | `NullRedactor`, `RegexRedactor` |
| `EgressGate` (DC2D) | Destination allow-listing and external-model blocking | `PolicyDrivenEgressGate` |
| `RMACDError` hierarchy | Typed exception per non-allow outcome | Permission-denied, prohibited, constraint, tool-capability, approval-required, approval-denied, approval-timeout, egress-blocked |

Integrators supply the production versions of the pluggable pieces — a
ServiceNow/Slack/PagerDuty/webhook gateway, a SIEM audit sink, a real PII
engine as a `Redactor`. The SDK's own implementations are reference-grade:
enough to run the examples and the tests, not a substitute for your
enterprise systems.

Source: `sdk/python/rmacd/`. Schema validation, profile loading, and the
Tools Registry are also available under the same package
(`from rmacd import ...`, `from rmacd.registry import ...`).

### CLI

Installing the package puts an `rmacd` command on `PATH`:

| Command | What it does |
|---|---|
| `rmacd validate <profile.json>...` | Validate one or more profiles against the 2D / 3D / DC2D schema |
| `rmacd evaluate <profile.json> <R\|M\|A\|C\|D> [-c <tier>]` | Evaluate a single decision against a profile |
| `rmacd info <profile.json>` | Print a profile's identity, permissions and constraints |
| `rmacd matrix <profile.json>` | Print the *effective* autonomy matrix for that profile |
| `rmacd classify <tools.json> -n <pack-name>` | AI-compile a tool surface into a draft governance pack |
| `rmacd pack validate\|review\|sign\|verify\|diff` | Pack lifecycle: schema check, human-review queue, Ed25519 signing, verification, drift detection |
| `rmacd audit summarize <log.jsonl>` | Turn an audit trail into an auditor-facing report (`--format text\|json\|md`, `--since`/`--until`/`--agent`/`--denials-only`) |
| `rmacd mcp-serve [--profile <profile.json>]` | Serve RMACD as an MCP policy server on stdio (needs the `[mcp]` extra) |

## Reference integrations

Runnable end-to-end examples in `examples/`:

| Directory | What it shows |
|---|---|
| `agent-integration-claude-sdk/` | Claude Agent SDK with `PreToolUse` hook → `PolicyEnforcer.enforce_tool_call` (registry-backed). |
| `agent-integration-anthropic-sdk/` | Raw Anthropic SDK manual tool-use loop; the most portable template. |
| `dc2d-customer-support/` | DC2D redaction and egress controls demonstrated without an LLM. |
| `governance-packs-quickstart/` | Building an enforcer's registry from governance packs. |

## Companion runtime docs

| Document | What it adds to this guide |
|---|---|
| [`docs/runtime-patterns.md`](runtime-patterns.md) | Profile binding, classification lookup, approval-wait, error contract, DC2D runtime, end-to-end integration checklist |
| [`docs/framework-adapters.md`](framework-adapters.md) | Registry-backed `enforce_tool_call`, plus OpenAI Agents SDK, Microsoft Agent Framework, LangChain, AutoGen and CrewAI snippets, and RMACD as an MCP server |
| [`docs/claude-code.md`](claude-code.md) | Governing a Claude Code session itself — the `rmacd` plugin, its `SessionStart` / `PreToolUse` / `PostToolUse` hooks, the session audit trail, and enterprise managed-settings rollout |
| [`docs/audit-evidence.md`](audit-evidence.md) | `rmacd audit summarize`, SIEM shipping recipes, and the SOC 2 / ISO 27001 / GDPR control mapping |

## Tools registry

`from rmacd.registry import ToolsRegistry` is the first-class tool→RMACD
classifier and capability ceiling that `PolicyEnforcer.enforce_tool_call`
consults to enforce *profile ∩ tool*. The previously-standalone
`tools-registry/` directory has been removed; its content lives in
`rmacd.registry`.

Classification engines available at tool-registration time:

| Engine | How to use it | Notes |
|---|---|---|
| **Manual** | `ToolDefinition(rmacd_level=..., data_access=...)` | Optionally add a dynamic `classifier=` that resolves `(operation, tier, target)` from the call's arguments — e.g. `make_bash_classifier()` for shell commands |
| **Keyword heuristic** | `MCPRegistryBridge` over an MCP `tools/list` response | Every auto-classified tool gets a capability ceiling at its inferred operation plus provenance metadata; `bridge.low_confidence_tools()` surfaces the human-review queue |
| **LLM-assisted** (optional, `pip install "rmacd-framework[llm]"`) | `LLMToolClassifier`, as `llm_mode="fallback"` (only when keywords are unsure) or `"always"` | Has a Claude model classify ambiguous tool definitions |

All three are advisory inputs at *registration* time only. Whatever an engine
concludes, the §12.5 floor, the agent's profile, and the tool's capability
ceiling remain deterministically enforced at call time — a misclassification
can make a tool harder to use, never easier.

---

## Governance Packs (recommended)

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

**34 built-in packs** load by name:

| Family | Packs |
|---|---|
| Cloud CLIs | `aws`, `az`, `gcloud`, `kubectl` |
| Cloud-provider SDKs & MCPs | `aws-api-mcp`, `azure-mcp`, `boto3`, `gcp-toolbox` |
| Identity & access (focused) | `aws-iam`, `az-identity`, `gcp-iam` |
| Developer toolchain | `docker`, `gh`, `git`, `make`, `npm`, `pip-uv`, `terraform` |
| Dev tools | `filesystem`, `github`, `gitlab`, `sql` |
| Enterprise operations | `helm`, `servicenow`, `ssh-transfer`, `stripe`, `vault` |
| SaaS / collaboration MCPs | `confluence`, `google-drive`, `jira`, `postgres`, `slack` |
| Microsoft 365 MCP | `ms365` |
| Shell | `shell` (advisory only — `rmacd.registry.bash` remains the enforcing shell classifier) |

The [pack catalog](governance-packs/catalog.md) documents every rule each pack
compiles to.

**Author your own** with the AI-compile workflow:

| Step | Command | Purpose |
|---|---|---|
| 1 | `rmacd classify <tools.json> -n <name>` | Draft a pack from a tool surface (`--llm` for the ambiguous tail) |
| 2 | `rmacd pack review <pack>` | Surface the rules that need a human decision |
| 3 | `rmacd pack sign <pack> -k <key.pem>` | Freeze and Ed25519-sign it (`[sign]` extra) |
| 4 | `rmacd pack verify <pack> -k <pub.pem>` | Verify a signature before trusting a pack |
| 5 | `rmacd pack diff <pack> <tools.json>` | Detect drift when the tool surface changes |

The LLM runs only at authoring time; runtime classification is fully
deterministic. Built-in packs ship as `review_status: ai-drafted` — they are
starting points, so **review and sign** them before granting production trust.
Composition never weakens a classification: adding a pack can only make a call
look more dangerous, never less.

See [docs/governance-packs/](governance-packs/) for the full design, roadmap, and
authoring guide, and the runnable
[`examples/governance-packs-quickstart/`](../examples/governance-packs-quickstart/).

---

## Need Help?

- Email: contact@rmacd-framework.org
- Web: [rmacd-framework.org](https://rmacd-framework.org)
- GitHub Discussions: [rmacdframework/spec/discussions](https://github.com/rmacdframework/spec/discussions)
