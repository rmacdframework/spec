# RMACD Framework Python SDK

Reference implementation for the RMACD (Read, Move, Add, Change, Delete) Framework - a three-dimensional governance model for autonomous AI agents.

## Installation

```bash
# From source
git clone https://github.com/rmacdframework/spec.git
cd spec/sdk/python
pip install -e .

# Or using uv
uv pip install -e .
```

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

### Validating Profiles

```python
from rmacd import ProfileValidator

validator = ProfileValidator(schema_dir="../../schemas")

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

# Create MCP bridge
bridge = MCPRegistryBridge("mcp-demo")

# Register MCP tool with auto-classification
mcp_tool = MCPTool(
    name="filesystem-read",
    description="Read files from the filesystem",
    inputSchema={"type": "object", "properties": {"path": {"type": "string"}}},
    operations=["read", "list"]
)
bridge.register_mcp_tool(mcp_tool)

# Check agent access
allowed, reason = bridge.can_agent_use_tool(
    "filesystem-read",
    agent_permissions=["R", "M"],
    agent_data_tier="internal"
)
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

### Core Enums

- **Operation**: `R` (Read), `M` (Move), `A` (Add), `C` (Change), `D` (Delete)
- **DataClassification**: `public`, `internal`, `confidential`, `restricted`
- **AutonomyLevel**: `autonomous`, `logged`, `notification`, `approval`, `elevated_approval`, `prohibited`

### Policy Decision

The `PolicyDecision` model contains:

```python
@dataclass
class PolicyDecision:
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
