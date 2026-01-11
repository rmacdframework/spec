# Changelog

All notable changes to the RMACD Framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

### Planned for v1.1

- Additional permission profile templates
- Platform-specific integration guides
- Enhanced compliance mappings

### Planned for v2.0

- Multi-agent coordination patterns
- Delegation and escalation workflows
- Runtime policy evaluation SDK

---

[1.0.0]: https://github.com/rmacdframework/spec/releases/tag/v1.0.0
