# RMACD Framework Python SDK

Reference implementation for the RMACD (Read, Move, Add, Change, Delete) Framework — a governance model for autonomous AI agents. The SDK supports all three model variants:

- **3D** (default) — Operations × Data Classification × Autonomy
- **2D Operational** — Operations × Autonomy (no data classification)
- **2D Data-Classification (DC2D)** — Data Classification × Autonomy (no operations axis; for orgs whose primary governance lever is data sensitivity, with operations governed by an upstream IAM/RBAC or DLP layer). See spec Appendix D.

## Installation

```bash
# From PyPI
pip install rmacd-framework

# With optional LLM-assisted tool classification (Anthropic SDK)
pip install "rmacd-framework[llm]"

# With optional governance-pack signing (Ed25519 via cryptography)
pip install "rmacd-framework[sign]"

# With optional YAML-authored governance packs (PyYAML)
pip install "rmacd-framework[yaml]"

# Or from source
git clone https://github.com/rmacdframework/spec.git
cd spec/sdk/python
pip install -e .

# Or using uv
uv pip install rmacd-framework
```

The distribution name on PyPI is `rmacd-framework`; the import name remains `rmacd` (`from rmacd import ...`).

## Quick Start

### Loading and Evaluating Profiles

```python
from rmacd import ProfileLoader, PolicyEvaluator

# Load a profile
loader = ProfileLoader()
profile = loader.load_file("profiles/devops-agent.json")

# Create evaluator
evaluator = PolicyEvaluator(profile)

# Evaluate a policy decision (3D profile)
decision = evaluator.evaluate(
    operation="C",  # Change
    data_classification="internal",
)

print(f"Allowed: {decision.allowed}")
print(f"Autonomy Level: {decision.autonomy_level}")
print(f"Requires Approval: {decision.requires_approval}")
```

### DC2D Profiles (Data-Classification × Autonomy)

```python
from rmacd import (
    AutonomyLevel,
    DataAccess,
    PolicyEvaluator,
    ProfileDC2D,
    TierPolicy,
)

profile = ProfileDC2D(
    profile_id="rmacd-dc2d-support-agent-v1",
    profile_name="Support Agent",
    model="data-classification-2d",
    version="1.0",
    data_access=DataAccess(
        public=TierPolicy(allowed=True, autonomy=AutonomyLevel.AUTONOMOUS),
        internal=TierPolicy(allowed=True, autonomy=AutonomyLevel.LOGGED),
        confidential=TierPolicy(allowed=True, autonomy=AutonomyLevel.APPROVAL),
        restricted=TierPolicy(allowed=False, autonomy=AutonomyLevel.PROHIBITED),
    ),
)
evaluator = PolicyEvaluator(profile)

# DC2D requires data_classification; operation is informational only
decision = evaluator.evaluate(operation="R", data_classification="confidential")
print(decision.allowed)            # True
print(decision.autonomy_level)     # AutonomyLevel.APPROVAL
print(decision.requires_approval)  # True
```

### Validating Profiles

```python
from rmacd import ProfileValidator
from rmacd.validator import SchemaValidationError

# Uses the JSON schemas bundled with the package by default;
# pass schema_dir="path/to/schemas" to validate against other copies.
validator = ProfileValidator()

# Validate a profile file
try:
    validator.validate_file("my-profile.json")
    print("Profile is valid!")
except SchemaValidationError as e:
    print(f"Validation failed: {e.errors}")

# Check validity without exceptions
if validator.is_valid("my-profile.json"):
    print("Valid!")
```

### Emergency Escalation

```python
from rmacd import ProfileLoader, PolicyEvaluator
from rmacd.models import EvaluationContext, TriggerCondition

loader = ProfileLoader()
profile = loader.load_file("incident-responder.json")
evaluator = PolicyEvaluator(profile)

# Evaluate with emergency escalation active
context = EvaluationContext(
    emergency_active=True,
    emergency_trigger=TriggerCondition.SOC_DECLARED_INCIDENT,
)

decision = evaluator.evaluate(
    operation="C",
    data_classification="confidential",
    context=context,
)

print(f"Emergency mode: {decision.emergency_mode}")
```

## CLI Usage

The SDK includes a command-line interface for common operations.

### Validate Profiles

```bash
# Validate single profile
rmacd validate profiles/devops-agent.json

# Validate multiple profiles
rmacd validate profiles/*.json

# Quiet mode (errors only)
rmacd validate -q profiles/*.json
```

### Evaluate Policy Decisions

```bash
# Evaluate operation on 3D profile
rmacd evaluate profiles/devops.json C --classification internal

# With emergency escalation
rmacd evaluate profiles/incident-responder.json C -c confidential --emergency

# JSON output
rmacd evaluate profiles/devops.json R -c public --json
```

### Display Profile Information

```bash
# Show profile info
rmacd info profiles/devops.json

# JSON output
rmacd info profiles/devops.json --json
```

### View Autonomy Matrix

```bash
# Display effective autonomy matrix
rmacd matrix profiles/devops.json

# JSON output
rmacd matrix profiles/devops.json --json
```

## Policy Enforcement

`PolicyEnforcer` is the runtime Policy Enforcement Point: it evaluates a call
against the profile, routes approval-gated operations through an
`ApprovalGateway`, writes an `AuditRecord` per decision, and raises a typed
`RMACDError` subclass on any non-allowed outcome.

```python
from rmacd import PolicyEnforcer
from rmacd.exceptions import RMACDPolicyError

enforcer = PolicyEnforcer(profile, agent_id="devops-agent-01", registry=registry)

# Direct enforcement (you already classified the action)
enforcer.enforce(operation="C", target="server://web-01", classification="internal")

# Registry-backed tool-call enforcement — the integration point for an agent
# framework's tool hook (Claude PreToolUse, OpenAI needs_approval, ...).
# Classifies (tool_name, args) via the registry, applies the tool's capability
# ceiling, then enforces profile ∩ tool. Unknown tools fail closed.
try:
    enforcer.enforce_tool_call("Bash", {"command": "rm -rf build/"})
except RMACDPolicyError as exc:
    print(f"Blocked: {exc}")

# Dry-run variant (no approval, no audit, no raise)
decision = enforcer.evaluate_tool_call("Bash", {"command": "kubectl get pods"})
```

See [framework adapters](../../docs/framework-adapters.md) for wiring this
into Claude Agent SDK, OpenAI Agents SDK, Microsoft Agent Framework, LangChain,
AutoGen, and CrewAI, and [runtime patterns](../../docs/runtime-patterns.md)
for the surrounding architecture.

## Governance Packs (SDK 0.11.0)

Instead of hand-writing a classifier for each tool, get classification from a
**governance pack** (`rmacd.packs`) — a declarative, reusable, signable artifact
that maps a tool call to RMACD terms `(operation, data tier, target)` as data.
Build the enforcer's registry from packs in one line:

```python
from rmacd import PolicyEnforcer
from rmacd.packs import load_packs

enforcer = PolicyEnforcer(
    profile, agent_id="agent-1",
    registry=load_packs(["aws", "kubectl", "github", "sql", "jira"]),
)
enforcer.enforce_tool_call("kubectl", {"command": "delete pod web -n prod"})
```

22 built-in packs ship with the SDK (`shell`, `aws`, `gcloud`, `az`, `kubectl`,
`github`, `gitlab`, `sql`, `filesystem`, `jira`, `confluence`, `slack`,
`google-drive`, `postgres`, `boto3`, `aws-api-mcp`, `azure-mcp`, `gcp-toolbox`,
`ms365`, `aws-iam`, `az-identity`, `gcp-iam`) and load by name. Runtime stays deterministic — packs only feed the
evaluator; the §12.5 floor, profile, and capability ceiling still gate.

Author, review, and sign a pack for a new server (the LLM runs only here, never
at enforcement time):

```bash
rmacd classify tools.json -n my-server -o my-server.yaml  # AI-compile a draft
rmacd pack review my-server.yaml                           # eyeball the uncertain tail
rmacd pack sign  my-server.yaml -k signing.pem            # freeze + Ed25519 sign ([sign] extra)
rmacd pack verify my-server.yaml -k signing.pub           # gate trust in CI/prod
rmacd pack diff  my-server.yaml tools.json                # detect drift later
```

Built-in packs are **AI-drafted starting points** — review and sign before
production use. In production, refuse anything unsigned/untrusted:

```python
registry = load_packs(["my-org/devops"], require_signed=True, trusted_keys=PUBLIC_PEM)
```

Full guide: [docs/governance-packs/](../../docs/governance-packs/).

## Tools Registry

The SDK includes a Tools Registry for managing and validating AI agent tool access.

### Creating a Registry

```python
from rmacd.registry import ToolsRegistry, quick_register

# Create registry
registry = ToolsRegistry("my-organization")

# Register tools
quick_register(
    registry,
    tool_id="database_query",
    tool_name="Database Query",
    rmacd_level="R",
    description="Execute read-only database queries",
    data_access="confidential",
    required_hitl="logged"
)

# Validate agent access
is_allowed, reason = registry.validate_tool_access(
    tool_id="database_query",
    allowed_levels=["R", "M"],
    data_tier="confidential"
)

print(f"Allowed: {is_allowed} - {reason}")
```

### Risk Assessment

```python
# Calculate workflow risk
workflow_tools = ["github_commit", "kubernetes_deploy", "slack_notify"]
risk = registry.calculate_workflow_risk(workflow_tools)

print(f"Total Risk: {risk['total_risk']}/10")
print(f"Highest RMACD: {risk['highest_rmacd']}")
```

### MCP Integration

```python
from rmacd.registry import MCPTool, MCPRegistryBridge

# Bridge into the same registry your PolicyEnforcer uses (or omit registry=
# to let the bridge create its own)
bridge = MCPRegistryBridge(registry=registry)

# Register MCP tools with auto-classification — accepts MCPTool objects or
# raw MCP tools/list entries; each gets a capability ceiling at its inferred
# operation and classification provenance in metadata["classification"]
tool = bridge.register_mcp_tool(MCPTool(
    name="filesystem-read",
    description="Read files from the filesystem",
    inputSchema={"type": "object", "properties": {"path": {"type": "string"}}},
    operations=["read", "list"]
))
bridge.register_mcp_tools(tools_list_response["tools"])  # bulk, raw dicts OK

# Tools the keyword heuristic could not classify confidently
for t in bridge.low_confidence_tools():
    print(t.tool_id, t.metadata["classification"])

# Check agent access
allowed, reason = bridge.can_agent_use_tool(
    "filesystem-read",
    agent_permissions=["R", "M"],
    agent_data_tier="internal"
)
```

#### LLM-assisted classification (optional)

The keyword heuristic only sees surface strings. With the `llm` extra
(`pip install rmacd-framework[llm]`), a Claude model reads the whole tool
definition and returns a structured classification with a rationale and
confidence score:

```python
from rmacd.registry import MCPRegistryBridge
from rmacd.registry.llm import LLMToolClassifier

bridge = MCPRegistryBridge(
    registry=registry,
    llm_classifier=LLMToolClassifier(),  # reads ANTHROPIC_API_KEY; default model claude-fable-5
    llm_mode="fallback",  # LLM only for tools the keywords can't classify ("always" for all)
)
```

LLM failures degrade gracefully to the keyword result — registration is never
blocked. The LLM classification is advisory input to governance: the §12.5
safety floor, the agent profile, and the tool capability ceiling are still
enforced deterministically.

### Bash Command Classification

`bash` is the hard governance case: one tool, an opaque command string, any
action. The bundled classifier parses a command line — binaries, subcommands,
flags, pipes, redirects, sub-shells, shell control keywords — into the
**maximum** RMACD operation, failing closed (Change) on unknown binaries:

```python
from rmacd.models import Operation
from rmacd.registry import ToolDefinition, classify_bash_command, make_bash_classifier

classify_bash_command("git log --oneline").operation        # Operation.READ
classify_bash_command("sed -i s/a/b/ conf").operation       # Operation.CHANGE
classify_bash_command("for f in *; do rm $f; done").operation  # Operation.DELETE

# As a dynamic classifier on a registered Bash tool:
registry.register_tool(ToolDefinition(
    "Bash", "Shell", "C",  # nominal level for indexing
    classifier=make_bash_classifier(),
))
enforcer.enforce_tool_call("Bash", {"command": "rm -rf build/"})  # → Delete
```

### Export/Import

```python
# Export registry to JSON
registry.export_to_json("tools_catalog.json")

# Import tools from JSON
new_registry = ToolsRegistry("imported")
new_registry.import_from_json("tools_catalog.json")
```

---

## Models

### Profile Types

- **Profile2D**: Two-dimensional profile (operations + autonomy, no data classification)
- **Profile3D**: Three-dimensional profile (operations + data classification + autonomy)
- **ProfileDC2D**: Data-classification 2D profile (data classification + autonomy, no operations axis)

### Core Enums

- **Operation**: `R` (Read), `M` (Move), `A` (Add), `C` (Change), `D` (Delete)
- **DataClassification**: `public`, `internal`, `confidential`, `restricted`
- **AutonomyLevel**: `autonomous`, `logged`, `notification`, `approval`, `elevated_approval`, `prohibited`

### Policy Decision

The `PolicyDecision` Pydantic model contains:

```python
class PolicyDecision(BaseModel):
    allowed: bool                    # Whether operation is permitted
    operation: Operation             # The evaluated operation
    data_classification: DataClassification | None
    autonomy_level: AutonomyLevel    # Required autonomy level
    requires_approval: bool          # Whether human approval needed
    requires_notification: bool      # Whether notification required
    blocked_reason: str | None       # Reason if blocked
    constraints_applied: list[str]   # Constraints that were checked
    emergency_mode: bool             # Whether emergency escalation active
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy rmacd

# Linting
ruff check rmacd
```

## License

This work is licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](../../LICENSE).

## Links

- [RMACD Framework Specification](https://github.com/rmacdframework/spec)
- [JSON Schemas](../../schemas/)
- [Example Profiles](../../schemas/examples/)
