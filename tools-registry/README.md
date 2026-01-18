# RMACD Tools Registry

**A Python-based tool governance system for the RMACD Framework**

[![License: CC BY 4.0](https://img.shields.io/badge/License-CC_BY_4.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

> **Note:** This functionality is now integrated into the [RMACD Python SDK](../sdk/python/).
> For new projects, use `from rmacd.registry import ToolsRegistry` after installing the SDK.
> This standalone version remains for reference and backward compatibility.

---

## Overview

The RMACD Tools Registry maps tools to RMACD operational levels and provides:

- **Automated Tool Classification** — Map tools to R/M/A/C/D levels based on risk
- **Permission Validation** — Verify tool access against permission profiles
- **Risk Scoring** — Calculate risk scores for tools and workflows
- **Audit Logging** — Track all tool registrations and access attempts
- **JSON Import/Export** — Portable registry format
- **MCP Integration** — Auto-classify Model Context Protocol tools

---

## Quick Start

```python
from rmacd_tools_registry import ToolsRegistry, quick_register

# Create registry
registry = ToolsRegistry("my-registry")

# Register a tool
quick_register(
    registry,
    tool_id="file_reader",
    tool_name="File Reader",
    rmacd_level="R",
    description="Read file contents",
    data_access="internal"
)

# Validate access
is_allowed, reason = registry.validate_tool_access(
    tool_id="file_reader",
    allowed_levels=["R", "M"],
    data_tier="internal"
)

print(f"Access: {is_allowed} - {reason}")
```

---

## Architecture

```
+-------------------------------------------------------------+
|                    RMACD Tools Registry                      |
+-------------------------------------------------------------+
|                                                             |
|  +---------------+  +--------------+  +----------------+    |
|  | Tool          |  | Permission   |  | Risk           |    |
|  | Definition    |  | Validation   |  | Scoring        |    |
|  +---------------+  +--------------+  +----------------+    |
|                                                             |
|  +---------------+  +--------------+  +----------------+    |
|  | RMACD         |  | HITL         |  | Data           |    |
|  | Levels        |  | Controls     |  | Classification |    |
|  +---------------+  +--------------+  +----------------+    |
|                                                             |
|  +-------------------------------------------------------+  |
|  |            Audit Log & Statistics                     |  |
|  +-------------------------------------------------------+  |
+-------------------------------------------------------------+
```

---

## RMACD Levels

| Level | Code | Risk | Description |
|-------|------|------|-------------|
| **Read** | R | Near-Zero | Observe, query, analyze — no state change |
| **Move** | M | Low-Medium | Relocate, transfer — reversible |
| **Add** | A | Medium | Create, provision — additive impact |
| **Change** | C | High | Modify, update — state mutation |
| **Delete** | D | Critical | Remove, destroy — potentially irreversible |

---

## HITL Controls

| Level | Code | Description |
|-------|------|-------------|
| **Autonomous** | auto | Execute without human involvement |
| **Logged** | logged | Execute and log for audit |
| **Notify** | notify | Execute and notify human |
| **Approve** | approve | Require approval before execution |
| **Elevated** | elevated | Require senior approval |
| **Prohibited** | prohibited | Cannot be executed |

---

## Data Classification

| Tier | Code | Description |
|------|------|-------------|
| **Public** | public | Publicly available information |
| **Internal** | internal | Internal use only |
| **Confidential** | confidential | Sensitive business information |
| **Restricted** | restricted | Highly sensitive, regulated data |

---

## Risk Scoring

The registry automatically calculates risk scores based on:

```
risk_score = (rmacd_risk * 0.6 + data_risk * 0.4) * hitl_modifier * 10

Where:
  - rmacd_risk: 0.0 (R) to 1.0 (D)
  - data_risk: 0.0 (public) to 1.0 (restricted)
  - hitl_modifier: 0.0 (prohibited) to 1.0 (autonomous)
```

---

## File Structure

```
tools-registry/
├── rmacd_tools_registry.py      # Core registry implementation
├── example_usage.py             # Comprehensive examples
├── test_registry.py             # Test suite (43 tests)
├── mcp_integration.py           # MCP bridge
├── rmacd_tools_catalog.json     # Pre-configured tool catalog
├── rmacd_permission_profiles.json  # Standard permission profiles
├── mcp_tools_catalog.json       # MCP tools with classifications
└── README.md                    # This file
```

---

## Use Cases

### AI Agent Governance

```python
# Define agent capabilities
agent_profile = {
    "permissions": ["R", "M", "A"],
    "data_tier": "internal"
}

# Validate each tool the agent wants to use
for tool_id in agent_requested_tools:
    is_allowed, reason = registry.validate_tool_access(
        tool_id,
        agent_profile["permissions"],
        agent_profile["data_tier"]
    )
```

### Workflow Risk Assessment

```python
# Assess risk before deploying new workflow
workflow_tools = ["github_commit", "kubernetes_deploy", "slack_notify"]
risk = registry.calculate_workflow_risk(workflow_tools)

print(f"Total Risk: {risk['total_risk']}/10")
print(f"Highest RMACD: {risk['highest_rmacd']}")
```

### Compliance Auditing

```python
# Get complete audit trail
audit_log = registry.get_audit_log()

# Export for compliance review
registry.export_to_json("audit_export.json")
```

---

## Running Tests

```bash
python test_registry.py
```

Expected output:
```
Tests run: 43
Successes: 43
Failures: 0
Errors: 0

ALL TESTS PASSED!
```

---

## Integration Roadmap

- [x] Core registry implementation
- [x] MCP auto-classification
- [ ] LangChain integration
- [ ] AutoGen integration
- [ ] CrewAI integration
- [ ] GraphQL API
- [ ] Web UI for registry management

---

## Related Documentation

- [RMACD Framework Specification](../docs/RMACD_Framework_v1.2.md)
- [Implementation Guide](../docs/implementation.md)
- [JSON Schema Templates](../schemas/)

---

## License

This work is licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](../LICENSE).

---

## Author

**Created by Kash Kashyap** — January 2026

Email: kash@rmacd-framework.org
ORCID: [0009-0005-0127-6265](https://orcid.org/0009-0005-0127-6265)
LinkedIn: [linkedin.com/in/kashkashyap](https://linkedin.com/in/kashkashyap)

---

*RMACD Tools Registry — Governance for the Agentic Era*
