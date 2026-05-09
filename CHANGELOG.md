# Changelog

All notable changes to the RMACD Framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0] - 2026-05-09

### Added

- **Data-Classification Two-Dimensional variant (DC2D)** — A second 2D projection of the
  governance model that pairs Data Classification with HITL Autonomy, dropping the
  operations axis. Intended for organizations whose primary governance lever is data
  sensitivity and whose operational permissions are governed by an upstream IAM/RBAC or
  DLP layer (e.g., regulated industries, AI-DLP product deployments).
- **Specification Appendix D: The Data-Classification Two-Dimensional Variant (DC2D)** —
  Motivation, relationship to 2D and 3D models, governance matrix with recommended
  defaults, schema identifier, intentional omissions, and prior-art positioning
  (CSA capability-control matrix as nearest framework analogue, AI-DLP vendors as
  implementation analogue).
- **`schemas/profile-dc2d.schema.json`** — JSON Schema (Draft 2020-12) for DC2D profiles.
  Required `data_access` block with per-tier `allowed` + `autonomy` policy. Adds
  `redaction` and `egress_controls` constraint blocks; emergency escalation operates on
  data tiers (`escalated_tiers` + `escalated_autonomy`) rather than operations.
- **`schemas/examples/regulated-data-handler-dc2d.json`** — Worked example: customer-support
  agent with public→autonomous, internal→logged, confidential→approval (DPO),
  restricted→denied with justification.

### Changed

- **Python SDK to v0.3.0** — Adds `ProfileDC2D`, `DataAccess`, `TierPolicy`, and supporting
  models. `ProfileLoader`, `ProfileValidator`, `PolicyEvaluator`, and the `rmacd` CLI all
  recognize `model: "data-classification-2d"`. CLI `info` and `matrix` commands render
  per-tier output for DC2D profiles. Operation argument to `evaluator.evaluate()` is
  preserved as decision metadata for DC2D but does not affect the autonomy decision.
- **`DEFAULT_AUTONOMY_DC2D`** matrix added to evaluator: public→autonomous,
  internal→logged, confidential→approval, restricted→elevated_approval.
- **Specification document renamed** — `docs/RMACD_Framework_v1.2.{md,docx}` →
  `docs/RMACD_Framework_v1.3.{md,docx}`, following the existing convention of bumping
  the filename on every minor release. Internal version line bumped to v1.3.0
  (May 2026). All references in `README.md`, `tools-registry/README.md`, and
  `CITATION.cff` updated.

### Tests

- 11 new tests in `tests/test_evaluator.py` covering DC2D evaluation paths, the
  operation-is-metadata-only invariant, emergency tier escalation with selective
  coverage, and end-to-end loader + schema validator round-trip.

---

## [1.2.1] - 2026-04-27

### Fixed

- **Governance matrix bug** — `DEFAULT_AUTONOMY_3D` in Python SDK `evaluator.py` did not match the
  specification matrix; corrected six cells: `public.M`, `public.C`, `internal.R`,
  `confidential.R`, `confidential.D`, and `restricted.R`
- **Python SDK `DeleteControls` model** — Added missing `two_person_rule_for_confidential` field
  and corrected `retention_compliance_check` default (`false` → `true`) to match JSON schema
- **CLI version string** — Hardcoded `0.1.0` in `cli.py` updated to `0.2.1`
- **Appendix B profile schemas** — Fixed wrong domain (`rmacd.io` → `rmacd-framework.org`),
  missing `"model": "three-dimensional"` field, and missing `rmacd-3d-` ID prefix across all
  six example profiles; runtime example records in Appendix C updated to match
- **Test coverage** — Added `test_default_autonomy_matrix_matches_spec` covering all 20 cells
  of the governance matrix

---

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

### Planned for v1.4

- Platform-specific integration guides (Kubernetes, AWS/Azure/GCP)
- LangChain / AutoGen / CrewAI integration modules
- GraphQL API for registry management

### Planned for v2.0

- Multi-agent coordination patterns
- Delegation and escalation workflows
- Web UI for registry management

---

[1.3.0]: https://github.com/rmacdframework/spec/releases/tag/v1.3.0
[1.2.1]: https://github.com/rmacdframework/spec/releases/tag/v1.2.1
[1.2.0]: https://github.com/rmacdframework/spec/releases/tag/v1.2.0
[1.1.0]: https://github.com/rmacdframework/spec/releases/tag/v1.1.0
[1.0.2]: https://github.com/rmacdframework/spec/releases/tag/v1.0.2
[1.0.1]: https://github.com/rmacdframework/spec/releases/tag/v1.0.1
[1.0.0]: https://github.com/rmacdframework/spec/releases/tag/v1.0.0
