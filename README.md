# RMACD: Agent Governance Framework

**ITIL for the Agentic Era**

[![License: CC BY 4.0](https://img.shields.io/badge/License-CC_BY_4.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![Version](https://img.shields.io/badge/version-1.0-blue.svg)](https://github.com/rmacdframework/spec/releases)

---

## Overview

The **RMACD Framework** (Read, Move, Add, Change, Delete) is a governance model for autonomous AI agents in enterprise IT operations. It integrates:

- **Operational Permissions** — Five graduated tiers (R→M→A→C→D) based on risk
- **Human-in-the-Loop Controls** — Six autonomy levels from fully autonomous to prohibited
- **Data Classification** — Optional integration with enterprise data sensitivity tiers

RMACD answers the fundamental governance question: *"What can this agent do, to what data, with what oversight?"*

---

## Quick Start

### The Five Operations

| Operation | Risk Level | Description |
|-----------|------------|-------------|
| **R**ead | Near-Zero | Observe, query, analyze — no state change |
| **M**ove | Low-Medium | Relocate, transfer — reversible |
| **A**dd | Medium | Create, provision — additive impact |
| **C**hange | High | Modify, update — state mutation |
| **D**elete | Critical | Remove, destroy — potentially irreversible |

### Two Implementation Models

| Model | Dimensions | Best For |
|-------|-----------|----------|
| **Two-Dimensional** | RMACD × HITL | Organizations without formal data classification |
| **Three-Dimensional** | RMACD × HITL × Data Classification | Regulated industries, mature data governance |

---

## Governance Matrix (Three-Dimensional Model)

|  | Public | Internal | Confidential | Restricted |
|--|--------|----------|--------------|------------|
| **Read** | Auto | Auto | Logged | Notify |
| **Move** | Auto | Notify | Approve | Elevated |
| **Add** | Notify | Approve | Elevated | Elevated |
| **Change** | Approve | Approve | Elevated | **Prohibited** |
| **Delete** | Approve | Elevated | Elevated | **Prohibited** |

---

## Documentation

- [Full Specification (Word)](docs/RMACD_Framework_v1.0.docx)
- [Website](https://rmacd-framework.org)
- [JSON Schema Templates](schemas/)

---

## Installation

RMACD is a governance specification, not a software package. To implement:

1. **Assess** your organization's data classification maturity
2. **Select** the Two-Dimensional or Three-Dimensional model
3. **Define** permission profiles for your agent types
4. **Integrate** with your agent runtime/orchestration platform

See the [Implementation Guide](docs/implementation.md) for details.

---

## JSON Permission Profiles

Example profile for a read-only monitoring agent:

```json
{
  "$schema": "https://rmacd-framework.org/schema/v1/profile-2d.json",
  "profile_id": "rmacd-2d-observer-v1",
  "profile_name": "Observer",
  "model": "two-dimensional",
  "version": "1.0",
  "permissions": ["R"],
  "constraints": {
    "environments": ["development", "staging", "production"],
    "rate_limits": {
      "queries_per_minute": 100
    }
  }
}
```

See [schemas/examples/](schemas/examples/) for more profiles.

---

## Citation

If you use the RMACD Framework in your work, please cite:

```bibtex
@misc{rmacd2026,
  author = {Kash Kashyap},
  title = {RMACD: Agent Governance Framework},
  year = {2026},
  url = {https://rmacd-framework.org},
  note = {Version 1.0}
}
```

Or see [CITATION.cff](CITATION.cff) for machine-readable citation.

---

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

This work is licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](LICENSE).

You are free to share and adapt this material with appropriate attribution.

---

## Author

**Created by Kash Kashyap** — January 2026

Email: kash@rmacd-framework.org  
Web: [rmacd-framework.org](https://rmacd-framework.org)  
ORCID: [0009-0005-0127-6265](https://orcid.org/0009-0005-0127-6265)
LinkedIn: [linkedin.com/in/kashkashyap](https://linkedin.com/in/kashkashyap)

---

*RMACD: Agent Governance Framework — ITIL for the Agentic Era*
