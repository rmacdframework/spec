# Changelog

All notable changes to the RMACD Framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2026-01-18

### Added

- **Python Tools Registry** — Reference implementation for automated tool governance
  - Core registry with tool registration and RMACD classification
  - Permission validation against agent profiles
  - Risk scoring algorithm combining all three RMACD dimensions
  - Audit logging for compliance tracking
  - MCP (Model Context Protocol) auto-classification bridge
  - 27 pre-configured tools across all RMACD levels
  - 5 standard permission profiles (Observer, Coordinator, Contributor, Developer, Administrator)
  - Comprehensive test suite (43 tests)
  - JSON export/import for tool catalogs

### Changed

- Added Section 9.4 "Python Tools Registry Implementation" to framework specification
- Updated implementation guide with tools-registry reference
- Documentation links updated to reference tools-registry directory

---

## [1.1.0] - 2026-01-13

### Added

- All 15 governance tables now present in Markdown specification
- Tables 1-5: RMACD Hierarchy, Data Classification Tiers, Autonomy Levels, Governance Matrix (3D), Governance Matrix (2D)
- Tables 11-13: GDPR Alignment, HIPAA Alignment, PCI-DSS Alignment
- Table 15: Adoption Roadmap

### Changed

- Updated Tables 6-10 and Table 14 to match DOCX 4-column format with full content
- Renamed specification files from v1.0 to v1.1
- Version updated to 1.1 in both DOCX and Markdown documents

### Fixed

- Markdown formatting: proper code fences for pseudocode, Python, and JSON blocks
- Markdown formatting: blank lines before bullet lists
- Full parity between DOCX and Markdown versions (15 tables, 16 H1, 64 H2 headings)

---

## [1.0.2] - 2026-01-11

### Added

- Framework diagram (`docs/RMACD_Framework_Diagram.drawio.png`)
- Editable draw.io source file (`docs/RMACD_Framework_Diagram.drawio`)
- Embedded diagram in README for visual overview

### Changed

- Updated Documentation section with diagram links

---

## [1.0.1] - 2026-01-11

### Added

- Markdown version of full specification (`docs/RMACD_Framework_v1.0.md`)
- Improved documentation section in README with better organization

### Changed

- Updated README to prioritize markdown documentation for GitHub readability

---

## [1.0.0] - 2026-01-11

### Added

- **RMACD Operational Hierarchy**: Five graduated permission tiers
  - Read (R): Observe, query, analyze — no state change
  - Move (M): Relocate, transfer — reversible operations
  - Add (A): Create, provision — additive impact
  - Change (C): Modify, update — state mutation
  - Delete (D): Remove, destroy — potentially irreversible

- **Human-in-the-Loop (HITL) Autonomy Levels**
  - Autonomous: No human oversight required
  - Logged: Autonomous with enhanced audit trail
  - Notification: Human notified, no approval required
  - Approval: Human approval required before execution
  - Elevated Approval: Senior/CAB approval required
  - Prohibited: Operation not permitted for agents

- **Two Implementation Models**
  - Two-Dimensional Model: RMACD × HITL (no data classification required)
  - Three-Dimensional Model: RMACD × HITL × Data Classification

- **Data Classification Integration (PICR)**
  - Public: Freely shareable
  - Internal: Business use only
  - Confidential: Sensitive information
  - Restricted: Maximum protection required

- **Permission Profile Templates**
  - Observer (Read-only)
  - Logistics (Read + Move)
  - Provisioning (Read + Move + Add)
  - Operations (Read + Move + Add + Change)
  - Administrator (Full RMACD)

- **JSON Schema Definitions**
  - Two-dimensional profile schema
  - Three-dimensional profile schema
  - Example profiles for common agent types

- **Compliance Mappings**
  - GDPR alignment
  - HIPAA alignment
  - PCI-DSS alignment
  - SOX alignment
  - ISO 27001 alignment

- **Implementation Guidance**
  - Environment-based differentiation
  - Approval authority mapping
  - ITIL change management integration
  - Adoption roadmap

### Notes

- Initial public release
- Created by Kash Kashyap
- Licensed under CC BY 4.0

---

## Future Roadmap

### Planned for v1.3

- Platform-specific integration guides (Kubernetes, AWS/Azure/GCP)
- LangChain / AutoGen / CrewAI integration modules
- GraphQL API for registry management

### Planned for v2.0

- Multi-agent coordination patterns
- Delegation and escalation workflows
- Web UI for registry management

---

[1.2.0]: https://github.com/rmacdframework/spec/releases/tag/v1.2.0
[1.1.0]: https://github.com/rmacdframework/spec/releases/tag/v1.1.0
[1.0.2]: https://github.com/rmacdframework/spec/releases/tag/v1.0.2
[1.0.1]: https://github.com/rmacdframework/spec/releases/tag/v1.0.1
[1.0.0]: https://github.com/rmacdframework/spec/releases/tag/v1.0.0
