**THE RMACD FRAMEWORK**

Read, Move, Add, Change, Delete

A Three-Dimensional Governance Model Integrating
Operational Permissions, Data Classification, and Autonomy Controls
for Governing Autonomous AI Agents in Enterprise IT Operations

*Extending ITIL's MACD Heritage to the Agentic AI Era*

Version 1.4.1 | August 2026
**Author: Kash Kashyap** ([ORCID: 0009-0005-0127-6265](https://orcid.org/0009-0005-0127-6265))

## **Revision history**

| Spec | Change |
|------|--------|
| 1.2 | Added the Python Tools Registry reference implementation for automated tool governance. |
| 1.2.1 | Corrected the governance-matrix defaults in the SDK; fixed the Appendix B profile schemas. |
| 1.3.0 | Added **Appendix D**, the Data-Classification 2D variant (DC2D), with schema, example profile and SDK support. |
| 1.3.1 | Published the SDK enforcement layer and the DC2D runtime controls; added `runtime-patterns.md`, `framework-adapters.md` and the runtime-architecture diagram. |
| 1.3.2 | Hardened the **§12.5** boundary: Add/Change/Delete on Restricted is now rejected both at authoring time by `profile-3d.schema.json` and at decision time by an immutable evaluator floor, closing a gap where an `autonomy_overrides` entry could raise a prohibited cell. |
| 1.4.0 | Made the Tools Registry a first-class policy layer (§9.4–9.5); added **session governance** (§9.7), **audit evidence** (§9.8) and the **MCP policy server** (§9.9). Renamed v1.3 → v1.4 per the minor-release convention. |
| 1.4.1 | Introduced **RMACD Intents** (`docs/intents.md`, `docs/intent-specification.md`): declarative pre-execution adjudication complementing runtime interception. Restated the §12.4 exception template as an `exception` intent, resolving a schema URL advertised since v1.0 but never published. Corrected the Appendix A quick-reference card, where Add on Restricted still read *Elevated Approval* after the 1.4.0 correction to §3.1 — as did the §6.3 Add-operations table. Restated the §9.1, §10 and Appendix B notes that still described the §12.5 floor as Change and Delete only; it is all three. |

### SDK releases behind this revision

| SDK | Added |
|-----|-------|
| 0.4.0–0.6.0 | `PolicyEnforcer`, `ApprovalGateway`, `AuditLogger` and the `RMACDError` hierarchy; DC2D `Redactor` / `EgressGate`; `build_system_prompt`; runnable reference integrations. |
| 0.7.0 | The immutable §12.5 runtime floor (see spec 1.3.2); time-window, egress and redaction fixes. |
| 0.8.0 | **Tools Registry as a policy layer.** Each tool registers an operation, an optional dynamic classifier (args → operation/tier/target) and an optional capability ceiling; `enforce_tool_call(tool, args)` enforces **profile ∩ tool capability** with the §12.5 floor. The standalone `tools-registry/` was folded into `rmacd.registry`. |
| 0.9.1 | Single-sourced the package version; bundled the three profile schemas into the wheel. |
| 0.10.0 | Optional **LLM-assisted tool classification** (`LLMToolClassifier`, extra `[llm]`) wired into `MCPRegistryBridge`; capability ceilings and provenance on auto-classified MCP tools; a `low_confidence_tools()` review queue. |
| 0.11.0 | **Governance Packs** (`rmacd.packs`) — declarative, reusable, signable tool → `(operation, tier, target)` mappings as data; AI-compile authoring (`rmacd classify`); Ed25519 signing and drift detection. 19 built-in packs. |
| 0.12.0 | Three cloud-identity packs (`aws-iam`, `az-identity`, `gcp-iam`); `CLIApprovalGateway` promoted into the SDK. 22 packs. |
| 0.13.0 | **Session governance** (§9.7): a deterministic `PreToolUse` hook binding a Claude Code session to a profile, plus the `plugins/rmacd/` plugin. **Audit evidence** (§9.8, `rmacd audit summarize`). Read-only **MCP policy server** (§9.9, `rmacd mcp-serve`, extra `[mcp]`). Pack composition. 34 packs. |
| 0.14.0 | Security release closing nine under-enforcement bypasses; corrected §3.1 — **Add on Restricted is Prohibited**, not Elevated Approval. |
| 0.14.1 | Closed the remaining session fail-open: a bound session whose SDK cannot be imported now denies every tool call instead of running ungoverned. |

Standing constraints, unchanged by any release above:

- **LLM classification is advisory**, at authoring and registration time only.
  Runtime enforcement — the §12.5 floor, the agent profile, the capability
  ceiling — is deterministic, with no model in the decision path.
- **Governance Packs are an SDK capability, not normative.**
- Every addition above is **additive**: the runtime gates are unchanged.

# **Abstract**

As autonomous AI agents increasingly permeate enterprise IT operations, organizations face a critical governance challenge: how to grant AI systems the operational freedom necessary for productivity while maintaining the control required for compliance, security, and business continuity. Existing frameworks address autonomy levels, permission scopes, or data classification in isolation, but none provide an integrated, operationally-focused model that enterprise IT teams can immediately understand and implement.
This paper introduces the RMACD Framework (Read, Move, Add, Change, Delete), a three-dimensional governance model that integrates operational permissions from ITIL's MACD heritage, enterprise data classification tiers (Public, Internal, Confidential, Restricted), and graduated human-in-the-loop autonomy controls. This integration creates a comprehensive matrix that answers the fundamental governance question: 'What can this agent do, to what data, with what oversight?'
By unifying these three dimensions into a single coherent model, RMACD provides enterprise operations teams with a familiar vocabulary, proven mental models, and implementation-ready governance controls for managing AI agents alongside traditional IT assets. The framework bridges forty years of IT service management best practices with the emerging requirements of autonomous AI governance, creating what may be termed 'ITIL for the Agentic Era.'

# **1. Origins: The MACD Heritage in IT Service Management**

## **1.1 The Birth of Operational Verbs in IT**

The management of IT infrastructure has always required a standardized vocabulary for describing operational actions. Long before the advent of ITIL, IT organizations recognized that systematic change control demanded clear categorization of the types of modifications that could be made to systems, networks, and services.
The term MACD (Move, Add, Change, Delete) emerged from the telecommunications industry in the 1980s, where service providers needed a consistent framework for processing customer orders. As defined by industry practice, MACD represents the four fundamental actions that can be taken against any IT asset or service:

- **Move:** Relocating an asset or service from one location, network segment, or logical position to another
- **Add:** Creating, provisioning, or deploying new assets, services, or configurations
- **Change:** Modifying, updating, or reconfiguring existing assets or services
- **Delete:** Removing, decommissioning, or disposing of assets or services (also termed 'Disconnect' or 'Disposal')

## **1.2 Evolution Through ITIL and Service Management**

The Information Technology Infrastructure Library (ITIL), first developed by the UK Government's Central Computer and Telecommunications Agency in the 1980s, formalized change management as a core IT service management discipline. ITIL's Change Management process established that 'the addition, modification, or removal of anything that could have an effect on IT services' requires controlled handling.
ITIL introduced the concept of change categorization based on risk and impact, distinguishing between Standard Changes (pre-authorized, low-risk, repeatable), Normal Changes (require full assessment and CAB approval), and Emergency Changes (expedited approval for urgent situations). This risk-based approach to operational permissions directly informs the RMACD Framework's graduated autonomy model.

## **1.3 The Parallel Evolution of Data Classification**

Concurrent with the development of operational change management, enterprises developed data classification frameworks to categorize information by sensitivity and required protection levels. The industry-standard four-tier model emerged across government, military, and commercial sectors:

- **Public:** Information freely shareable with no restrictions; disclosure poses no risk
- **Internal:** Business information for internal use only; not sensitive but requires access controls
- **Confidential:** Sensitive information whose exposure could cause legal, financial, or reputational harm
- **Restricted:** Highly sensitive information requiring maximum protection; unauthorized access could be catastrophic

These two frameworks, operational verbs (MACD) and data classification, evolved independently yet are fundamentally complementary. The RMACD Framework unifies them for the first time in the context of autonomous AI agent governance.

## **1.4 From Physical Assets to Autonomous Agents**

For four decades, MACD operations were performed by human agents: technicians, engineers, and administrators who received requests, assessed impacts, obtained approvals, and executed changes. The human operator served as both the executor and the implicit control mechanism, applying judgment, context, and institutional knowledge to every action.
The emergence of autonomous AI agents fundamentally disrupts this model. AI agents can perceive their environment, reason about objectives, plan multi-step actions, and execute operations without continuous human oversight. They are, in effect, the new 'agents' performing MACD operations, but without the implicit safeguards that human judgment provided.
This paradigm shift demands a new framework that explicitly encodes the risk assessment, data sensitivity awareness, and approval workflows that were previously implicit in human-mediated operations. The RMACD Framework addresses this need by creating a three-dimensional governance model that integrates operational permissions, data classification, and autonomy controls.

# **2. The Three-Dimensional RMACD Governance Model**

## **2.1 Framework Overview**

The RMACD Framework is built on the integration of three orthogonal dimensions, each of which contributes essential information to the governance decision:

- **Dimension 1 - Operational Permission (RMACD):** What action is the agent attempting to perform? The five operational verbs (Read, Move, Add, Change, Delete) form a graduated hierarchy of risk, from observation-only operations to potentially irreversible destructive actions.
- **Dimension 2 - Data Classification (PICR):** What is the sensitivity of the data being acted upon? The four-tier classification (Public, Internal, Confidential, Restricted) determines the potential impact of any operational action.
- **Dimension 3 - Autonomy Control (HITL):** What level of human oversight is required? The autonomy spectrum ranges from fully autonomous operation through various levels of notification and approval to complete prohibition.

The intersection of these three dimensions creates a comprehensive governance matrix that provides clear, unambiguous guidance for any agent-data-operation combination. This three-dimensional approach resolves the ambiguities present in frameworks that address only one or two dimensions.

## **2.2 Dimension 1: Operational Permissions (RMACD)**

The RMACD operational hierarchy extends traditional MACD with an explicit Read tier, creating five graduated permission levels:

| Level | Operation | Risk Profile | Agent Capability |
|---|---|---|---|
| R | Read | Near-Zero (no state change) | Observe, query, analyze, report, recommend |
| M | Move | Low-Medium (reversible) | Relocate, transfer, migrate, reassign |
| A | Add | Medium (additive, auditable) | Create, provision, deploy, install |
| C | Change | High (state mutation) | Modify, update, reconfigure, patch |
| D | Delete | Critical (potentially irreversible) | Remove, decommission, terminate, purge |

Permissions are cumulative: an agent granted 'Change' permissions implicitly possesses 'Add', 'Move', and 'Read' capabilities. This cumulative model reflects the reality that higher-risk operations typically require the lower-risk capabilities as prerequisites.

## **2.3 Dimension 2: Data Classification (PICR)**

The RMACD Framework adopts the industry-standard four-tier data classification model, mapping each tier to specific protection requirements and agent access constraints:

| Classification | Description | Examples |
|---|---|---|
| Public | Freely shareable; no impact from disclosure | Marketing materials, press releases, public documentation |
| Internal | Business use only; low impact from disclosure | Internal memos, org charts, non-sensitive procedures |
| Confidential | Sensitive; significant harm from disclosure | Customer PII, financial data, contracts, HR records |
| Restricted | Highly sensitive; severe/catastrophic harm | Trade secrets, PHI, payment card data, credentials |

The data classification dimension fundamentally transforms how operational permissions are interpreted. A 'Read' operation against Public data is categorically different from a 'Read' operation against Restricted data, despite being the same operational verb. The integrated RMACD model captures this distinction.

## **2.4 Dimension 3: Autonomy Control (HITL Levels)**

The third dimension specifies the required level of human-in-the-loop (HITL) oversight for any operation. The RMACD Framework defines six autonomy levels:

| Autonomy Level | Description | Use Case |
|---|---|---|
| Autonomous | No human oversight required | Low-risk operations on non-sensitive data |
| Logged | Autonomous with enhanced audit trail | Moderate-risk operations requiring traceability |
| Notification | Human notified; no approval required | Operations requiring awareness but not blocking |
| Approval | Human approval required before execution | Significant operations requiring explicit consent |
| Elevated Approval | Senior/CAB approval required | High-risk operations on sensitive data |
| Prohibited | Operation not permitted for agents | Catastrophic-risk operations; human-only |

# **3. The Integrated RMACD Governance Matrix**

## **3.1 The Complete Three-Dimensional Model**

The intersection of RMACD operations and data classification tiers produces a 5×4 matrix, where each cell specifies the required autonomy control level. This matrix serves as the definitive governance reference for AI agent operations:

| Operation | Public | Internal | Confidential | Restricted |
|---|---|---|---|---|
| Read | Autonomous | Autonomous | Logged | Notification |
| Move | Autonomous | Notification | Approval | Elevated Approval |
| Add | Notification | Approval | Elevated Approval | Prohibited |
| Change | Approval | Approval | Elevated Approval | Prohibited |
| Delete | Approval | Elevated Approval | Elevated Approval | Prohibited |

This matrix represents the default governance posture. Organizations may adjust individual cells based on their risk tolerance, regulatory requirements, and operational maturity, but the matrix provides a sound baseline for initial deployment.

## **3.2 Interpreting the Matrix**

The matrix encodes several fundamental governance principles:

- **Risk Compounds Across Dimensions:** Both higher-risk operations (moving down the RMACD hierarchy) and higher-sensitivity data (moving right across classification tiers) independently increase the required oversight level. The combination of both produces the most restrictive controls.
- **Read Operations Remain Low-Risk Across Classifications:** Even against Restricted data, Read operations require only notification-level oversight because they cannot alter system state. However, enhanced logging ensures accountability and audit capability.
- **State-Changing Operations on Sensitive Data Are Prohibited:** Add, Change and Delete operations against Restricted data are all marked 'Prohibited' for autonomous agents. These operations require human execution, though agents may recommend or prepare such actions. This is the §12.5 immutable floor: unlike every other cell, these three cannot be relaxed by an organization's own matrix adjustments, by an autonomy override, or through the exception process.
- **The 'Approval' Threshold Shifts Left with Risk:** For low-risk operations (Read, Move), approval requirements only appear at higher data classifications. For high-risk operations (Change, Delete), approval is required even for Public data.

## **3.3 Approval Authority Mapping**

Each autonomy level maps to specific approval authorities, enabling integration with existing organizational governance structures:

| Autonomy Level | Approval Authority | Audit Requirement |
|---|---|---|
| Autonomous | Pre-authorized (no approval) | Standard operational logging |
| Logged | Pre-authorized (no approval) | Enhanced logging with retention |
| Notification | Agent Owner / Operator | Action logging + notification record |
| Approval | Team Lead / Change Manager | RFC documentation + approval chain |
| Elevated Approval | CAB / Senior Management / CISO | Full RFC + impact assessment + PIR |
| Prohibited | Human execution only | N/A for agents; human audit applies |

# **4. Read Operations: The Foundation of Safe Autonomy**

## **4.1 Definition and Scope**

Read operations encompass all agent activities that observe, query, or analyze system state without modifying it. The Read tier is the foundational layer of the RMACD hierarchy, representing the lowest-risk operational capability that can be granted to an autonomous agent.

- **Core Read Capabilities:** Query databases and APIs, access file contents, retrieve configuration states, monitor system metrics, analyze logs, scan network states, examine user activity, and synthesize information from multiple sources.
- **Read Outputs:** Dashboards, reports, alerts, recommendations, anomaly notifications, compliance assessments, and knowledge artifacts. Critically, Read operations produce information but do not execute changes.

## **4.2 Why Read as a Distinct Tier**

Traditional MACD frameworks assume Read operations as a prerequisite rather than a distinct operational category. Before any Move, Add, Change, or Delete can occur, the operator must first observe the current state. In human-mediated workflows, this implicit Read operation carries near-zero risk because the human operator serves as a natural filter between observation and action.
However, when an autonomous AI agent performs Read operations, the distinction becomes critical for several reasons:

- **Safe Onboarding:** New AI agents can be deployed with Read-only permissions, allowing observation and learning without operational risk. Organizations can evaluate agent behavior before granting mutative permissions.
- **Separation of Concerns:** Read-only agents can perform continuous monitoring, analysis, and recommendation generation while separate agents (or humans) execute approved changes.
- **Evidence Integrity:** In compliance and forensic contexts, Read-only access ensures the agent cannot alter the data it examines, maintaining evidentiary chain of custody.
- **Progressive Trust:** The Read tier enables a graduated trust model where agents earn expanded permissions over time based on demonstrated reliable behavior.

## **4.3 Read Operations Across Data Classifications**

| Data Tier | Autonomy | Logging Requirement | Rationale |
|---|---|---|---|
| Public | Autonomous | Standard operational logs | Zero harm from disclosure |
| Internal | Autonomous | Standard operational logs | Low harm; business context only |
| Confidential | Logged | Enhanced audit trail; 90-day retention | Compliance; breach notification prep |
| Restricted | Notification | Real-time alerts; 1-year retention | Human awareness of sensitive access |

## **4.4 Read-Only Agent Patterns**

Several valuable enterprise use cases can be addressed entirely with Read-only (R-level) agents:

- **Monitoring Agents:** Continuous observation of system health, performance metrics, and security events. These agents can alert humans to anomalies without the ability to remediate, ensuring human judgment remains in the response loop.
- **Compliance Auditors:** Automated scanning of configurations, access logs, and data handling practices against policy baselines. Read-only access ensures the audit agent cannot alter the evidence it examines.
- **Recommendation Engines:** Analysis of system state and generation of optimization recommendations. Humans review and approve recommendations before execution by separate agents or manual processes.
- **Knowledge Extractors:** Scanning documents, configurations, and logs to build organizational knowledge bases. Read-only ensures source data integrity while enabling knowledge synthesis.
- **Anomaly Detectors:** Continuous analysis of patterns across logs, metrics, and events to identify deviations from baselines. Alert generation without response capability.

## **4.5 Read Operation Best Practices**

- **Scope Read Access Narrowly:** Grant access only to the specific data sources required for the agent's function, even within the Read tier.
- **Implement Query Boundaries:** Define limits on query scope, frequency, and result set sizes to prevent resource exhaustion and data exfiltration patterns.
- **Log All Restricted Access:** Any Read operation against Confidential or Restricted data must generate an immutable audit record.
- **Separate Read from Execute:** Ensure Read-only agents cannot invoke execution capabilities through indirect mechanisms such as writing to command queues.
- **Monitor for Escalation Attempts:** Detect patterns suggesting a Read-only agent is attempting to circumvent its permission boundaries.

## **4.6 Anti-Patterns to Avoid**

- **Read-to-Write Leakage:** Granting a Read-only agent the ability to write to locations that trigger automated workflows effectively grants execution capability.
- **Unbounded Data Access:** Allowing Read access to 'everything' rather than specific, justified data sources creates unnecessary exposure risk.
- **Missing Classification Awareness:** Treating all Read operations identically regardless of underlying data classification undermines the three-dimensional model.
- **Credential Exposure:** Read access to configuration stores that contain embedded credentials effectively grants privilege escalation.

# **5. Move Operations: Controlled Relocation**

## **5.1 Definition and Scope**

Move operations encompass all agent activities that relocate assets, data, or services from one location to another without fundamentally altering their content or configuration. Move is the first mutative tier in the RMACD hierarchy, introducing the ability to change system state while maintaining reversibility.

- **Core Move Capabilities:** Transfer files between storage locations, migrate workloads between hosts or clusters, reassign resources between projects or teams, relocate network assets between segments, move data between geographic regions, and rebalance loads across infrastructure.
- **Key Characteristic - Reversibility:** Move operations are distinguished from higher-risk operations by their inherent reversibility. A moved asset can typically be moved back to its original location, making Move operations lower-risk than Add, Change, or Delete.

## **5.2 Risk Profile**

Move operations carry a Low-to-Medium risk profile depending on the context:

- **Low Risk:** Moving non-production assets, relocating non-sensitive data between equivalent storage tiers, or rebalancing loads within a single environment.
- **Medium Risk:** Moving production workloads, transferring data across security boundaries, or relocating assets that affect service availability.
- **Elevated Risk:** Moving data across geographic boundaries (compliance implications), transferring between cloud providers, or relocating assets in regulated environments.

The data classification of the asset being moved significantly impacts the risk assessment. Moving Public data between storage locations is near-zero risk; moving Restricted data across network boundaries requires elevated controls.

## **5.3 Move Operations Across Data Classifications**

| Data Tier | Autonomy | Pre-Conditions | Post-Conditions |
|---|---|---|---|
| Public | Autonomous | None | Audit log entry |
| Internal | Notification | Destination validation | Notify asset owner; rollback plan ready |
| Confidential | Approval | Security assessment; DLP check | Verification; compliance attestation |
| Restricted | Elevated Approval | CAB review; legal/compliance sign-off | Chain of custody; encryption verification |

## **5.4 Move Operation Agent Patterns**

- **Load Balancing Agents:** Autonomously redistribute workloads across infrastructure to optimize performance. Limited to Public/Internal data; requires notification for anything else.
- **Data Lifecycle Agents:** Move aging data to lower-cost storage tiers based on retention policies. Must respect classification: can autonomously tier Public data but requires approval for Confidential.
- **Disaster Recovery Agents:** Relocate workloads to failover sites during incidents. Pre-authorized Move permissions for DR scenarios with post-incident reporting.
- **Containment Agents:** Move compromised assets to isolation networks during security incidents. Move-only permissions enable rapid response without modification capability.

## **5.5 Move Operation Safeguards**

- **Destination Validation:** Before any Move, verify the destination meets the same or higher security classification as the source.
- **Rollback Capability:** Maintain the ability to reverse the Move operation for a defined period after execution.
- **Data Residency Compliance:** For data subject to geographic restrictions, validate that the destination meets residency requirements.
- **Integrity Verification:** Verify that moved assets are intact and uncorrupted after the operation completes.
- **Source Cleanup:** Define whether the source copy should be retained, deleted, or tombstoned after the Move.

## **5.6 Anti-Patterns to Avoid**

- **Move-as-Exfiltration:** Moving data to less-secured locations as a method of bypassing access controls. Destination must meet source classification.
- **Unrestricted Destination:** Allowing Move operations to any destination rather than pre-approved target locations.
- **Missing Rollback:** Executing Move operations without maintaining the ability to reverse them.
- **Classification Downgrade:** Moving data to locations with lower security controls without explicit reclassification approval.

# **6. Add Operations: Governed Creation**

## **6.1 Definition and Scope**

Add operations encompass all agent activities that create new assets, provision new resources, deploy new configurations, or introduce new data into the environment. Add is a medium-risk tier that increases system state complexity and resource consumption.

- **Core Add Capabilities:** Provision virtual machines or containers, create user accounts or service identities, deploy applications or services, generate new data records, establish new network configurations, create storage volumes, and instantiate new monitoring or alerting rules.
- **Key Characteristic - Additive Impact:** Add operations increase system complexity and resource consumption. While they don't modify or destroy existing state, they create new state that must be managed, secured, and eventually retired.

## **6.2 Risk Profile**

Add operations carry a Medium risk profile with several considerations:

- **Resource Consumption:** Uncontrolled Add operations can exhaust capacity, increase costs, and create sprawl that becomes difficult to manage.
- **Attack Surface Expansion:** Each new resource, account, or service represents additional attack surface that must be secured and monitored.
- **Configuration Drift:** Added resources may not conform to organizational standards, creating inconsistencies that complicate operations.
- **Orphan Risk:** Added resources may become orphaned if not properly tracked, creating security and cost risks.

The data classification for Add operations relates to what data the new resource will handle or create, not just existing data sensitivity.

## **6.3 Add Operations Across Data Classifications**

| Data Tier | Autonomy | Pre-Conditions | Post-Conditions |
|---|---|---|---|
| Public | Notification | Template compliance check | Asset registration; owner assignment |
| Internal | Approval | Budget verification; standard config | CMDB update; monitoring enabled |
| Confidential | Elevated Approval | Security review; hardened config | Security scan; compliance attestation |
| Restricted | PROHIBITED | Human execution only | Agent may prepare; human executes |

Note: Add operations against Restricted data are Prohibited for autonomous agents. Creating a resource that will hold Restricted data is itself a Restricted-tier mutation, so it sits behind the same §12.5 safety boundary as Change and Delete: the agent may prepare or recommend the change, but a human executes it.

## **6.4 Add Operation Agent Patterns**

- **Auto-Scaling Agents:** Provision additional compute resources in response to demand. Pre-approved templates with notification; budget guardrails prevent runaway scaling.
- **Self-Service Provisioning:** Create development environments or test resources on demand. Approval required; automatic expiration dates to prevent orphaning.
- **Onboarding Agents:** Provision new user accounts and standard resources for new employees. Elevated approval due to identity creation; must follow identity governance policies.
- **Incident Response Agents:** Spin up forensic environments or additional monitoring during incidents. Pre-authorized Add for IR scenarios with post-incident cleanup requirements.

## **6.5 Add Operation Safeguards**

- **Template Enforcement:** All Add operations should use pre-approved templates that enforce security baselines and organizational standards.
- **Budget Guardrails:** Implement cost limits that prevent agents from creating resources beyond approved budgets.
- **Expiration Policies:** Added resources should have default expiration dates that require explicit renewal to prevent orphaning.
- **Automatic Registration:** All added resources must be automatically registered in asset inventories (CMDB) with assigned owners.
- **Security Baseline Verification:** Added resources must pass security configuration checks before becoming operational.

## **6.6 Anti-Patterns to Avoid**

- **Unconstrained Creation:** Allowing unlimited Add operations without budget, quota, or approval constraints.
- **Shadow Resources:** Adding resources that bypass inventory systems, creating untracked assets.
- **Configuration Drift:** Adding resources with non-standard configurations that create security or operational inconsistencies.
- **Privilege Accumulation:** Creating new service accounts or roles with excessive permissions as a way to escalate privileges.
- **Orphan Creation:** Adding resources without clear ownership, making future lifecycle management impossible.

# **7. Change Operations: Managed Mutation**

## **7.1 Definition and Scope**

Change operations encompass all agent activities that modify the state, configuration, or content of existing assets. Change is a high-risk tier that directly alters production state, potentially affecting system behavior, security posture, and service availability.

- **Core Change Capabilities:** Modify configuration files and settings, update application code or deployments, alter database records, change network rules and policies, update user permissions and roles, patch operating systems and applications, and reconfigure service parameters.
- **Key Characteristic - State Mutation:** Change operations modify existing state rather than creating or removing it. This makes them particularly sensitive because the original state may be lost or difficult to recover without explicit versioning and backup mechanisms.

## **7.2 Risk Profile**

Change operations carry a High risk profile with critical considerations:

- **Service Impact:** Changes to production systems can cause outages, performance degradation, or unexpected behavior affecting users and business operations.
- **Security Impact:** Configuration changes can inadvertently create vulnerabilities, weaken access controls, or expose sensitive data.
- **Cascade Effects:** Changes in interconnected systems can trigger unexpected cascading effects across dependent services.
- **Recovery Complexity:** Unlike Add operations (which can be deleted) or Move operations (which can be reversed), Change operations may be difficult to undo without explicit rollback capabilities.

## **7.3 Change Operations Across Data Classifications**

| Data Tier | Autonomy | Pre-Conditions | Post-Conditions |
|---|---|---|---|
| Public | Approval | Backup created; rollback tested | Verification; smoke test; monitoring |
| Internal | Approval | Impact assessment; change window | PIR scheduled; rollback window defined |
| Confidential | Elevated Approval | CAB review; security assessment | Security scan; compliance check; PIR |
| Restricted | PROHIBITED | Human execution only | Agent may recommend; human executes |

Note: Change operations against Restricted data are Prohibited for autonomous agents. This represents a fundamental safety boundary: the combination of high-risk operations with highly sensitive data creates unacceptable risk for autonomous execution.

## **7.4 Change Operation Agent Patterns**

- **Configuration Management Agents:** Apply approved configuration baselines and remediate drift. Pre-approved standard changes; requires approval for non-standard modifications.
- **Patch Management Agents:** Deploy security patches and updates. Approval required; must operate within defined change windows; automatic rollback on failure.
- **Optimization Agents:** Tune performance parameters based on observed behavior. Approval required; changes must stay within defined parameter ranges.
- **Self-Healing Agents:** Automatically remediate known issues by applying pre-approved fixes. Pre-authorized for specific, well-tested remediation patterns only.

## **7.5 Change Operation Safeguards**

- **Mandatory Backup:** Before any Change operation, create a backup or snapshot that enables rollback.
- **Change Windows:** Restrict Change operations to defined maintenance windows for production systems.
- **Canary Deployment:** For changes affecting multiple systems, implement staged rollout with monitoring between stages.
- **Automatic Rollback:** Implement automatic rollback triggers based on health checks and error thresholds.
- **Two-Phase Execution:** Implement propose-then-apply patterns where the agent proposes changes and awaits confirmation before execution.
- **Blast Radius Limits:** Constrain the scope of any single Change operation to prevent widespread impact from errors.

## **7.6 Anti-Patterns to Avoid**

- **Unapproved Production Changes:** Allowing Change operations against production without appropriate approval workflow.
- **Missing Rollback:** Executing changes without maintaining the ability to restore previous state.
- **Unlimited Scope:** Allowing agents to change any configuration parameter without boundaries on sensitive settings.
- **Change-as-Bypass:** Using Change operations to modify access controls or security settings as a privilege escalation technique.
- **Silent Failures:** Executing changes without verification and alerting on failures.

# **8. Delete Operations: Protected Destruction**

## **8.1 Definition and Scope**

Delete operations encompass all agent activities that remove, decommission, or destroy assets, data, or configurations. Delete is the highest-risk tier in the RMACD hierarchy, representing potentially irreversible actions that can cause permanent data loss or service termination.

- **Core Delete Capabilities:** Remove files and data records, decommission virtual machines and containers, delete user accounts and service identities, terminate services and applications, purge database tables, remove network configurations, and destroy storage volumes.
- **Key Characteristic - Potential Irreversibility:** Delete operations may be irreversible, particularly for data destruction. Even with backups, recovery can be time-consuming, incomplete, or impossible depending on backup coverage and retention policies.

## **8.2 Risk Profile**

Delete operations carry a Critical risk profile with severe considerations:

- **Data Loss:** Deleted data may be permanently lost if backups are inadequate or non-existent, causing irreparable harm.
- **Service Termination:** Deleting active resources can cause immediate service outages affecting users and business operations.
- **Compliance Violations:** Premature deletion of regulated data can trigger legal penalties and compliance failures.
- **Cascade Failures:** Deleting resources that other systems depend upon can cause widespread cascading failures.
- **Malicious Exploitation:** Delete capabilities are high-value targets for attackers seeking to cause maximum damage.

## **8.3 Delete Operations Across Data Classifications**

| Data Tier | Autonomy | Pre-Conditions | Post-Conditions |
|---|---|---|---|
| Public | Approval | Dependency check; backup verified | Inventory update; retention log |
| Internal | Elevated Approval | Owner confirmation; retention check | Deletion certificate; audit record |
| Confidential | Elevated Approval | Legal/compliance review; hold check | Secure destruction cert; compliance attestation |
| Restricted | PROHIBITED | Human execution only | Agent may identify; human executes |

Note: Delete operations against Restricted data are Prohibited for autonomous agents. Additionally, Delete operations generally require the highest autonomy controls at every data classification level compared to other operations.

## **8.4 Delete Operation Agent Patterns**

- **Retention Policy Agents:** Identify data eligible for deletion based on retention schedules. Agent identifies candidates; human approves batch deletion; agent executes approved deletions.
- **Resource Cleanup Agents:** Remove orphaned or expired resources to control costs and reduce sprawl. Pre-approved for resources past expiration with no recent activity; notification to owners before deletion.
- **Decommissioning Agents:** Coordinate the removal of systems being retired. Orchestrate the deletion workflow; require approval at each stage; maintain audit trail.
- **Secure Disposal Agents:** Ensure data is securely destroyed according to compliance requirements. For Confidential data only; requires elevated approval; generates destruction certificates.

## **8.5 Delete Operation Safeguards**

- **Soft Delete First:** Implement soft deletion (mark as deleted) before hard deletion, with a grace period for recovery.
- **Dependency Analysis:** Before any deletion, analyze and report dependencies that would be affected.
- **Legal Hold Check:** Verify that data is not subject to legal holds or litigation preservation requirements.
- **Retention Compliance:** Confirm that minimum retention periods have been satisfied before deletion.
- **Owner Notification:** Require explicit owner acknowledgment before deleting any resource with an assigned owner.
- **Destruction Certification:** Generate auditable certificates of destruction for compliance-regulated data.
- **Two-Person Rule:** For Confidential data deletion, require approval from two independent approvers.

## **8.6 Anti-Patterns to Avoid**

- **Immediate Hard Delete:** Deleting data without a soft-delete grace period that allows recovery.
- **Bypassing Retention:** Deleting data before retention requirements are satisfied, creating compliance violations.
- **Ignoring Dependencies:** Deleting resources without checking for dependent systems or data.
- **Silent Destruction:** Deleting resources without audit trails or owner notification.
- **Delete-as-Attack:** Insufficient controls allowing compromised agents to execute mass deletion attacks.
- **Orphan Creation:** Deleting parent resources while leaving dependent resources orphaned.

# **9. Implementation: Guardrails for Agentic Platforms**

## **9.1 Permission Profile Templates**

RMACD permissions can be expressed as profiles that define an agent's operational boundaries across data classifications. The following templates provide starting points for common agent roles:

| Agent Profile | Public | Internal | Confidential | Restricted |
|---|---|---|---|---|
| Observer | R | R | R | R (notify) |
| Logistics | RM | RM | R | — |
| Provisioning | RMA | RMA | RM | R |
| Operations | RMAC | RMAC | RMA | R |
| Administrator | RMACD | RMACD | RMAC | RM |

Note: Even Administrator agents do not receive full RMACD permissions on Restricted data. Add, Change and Delete operations on Restricted data all remain human-only in the default model.

## **9.2 Environment-Based Differentiation**

The same agent should have different permission profiles across environments. Production environments warrant stricter controls than development or staging:

| Environment | DevOps Agent | Security Agent | Data Scope |
|---|---|---|---|
| Development | RMACD (all tiers) | RMAC | Synthetic only |
| Staging | RMAC (to Confid.) | RMA | Anonymized |
| Production | RM (to Internal) | R only | Full classification |

## **9.3 Integration with Change Management**

RMACD integrates naturally with existing ITIL change management — termed **change enablement** in ITIL 4. ITIL 4 recognizes three change types: **Standard** (pre-authorized, low-risk, repeatable), **Normal** (risk-assessed, authorized by the appropriate change authority), and **Emergency** (expedited for urgent situations). The combination of RMACD operation and data classification determines which change type applies and the change authority required:

| RMACD Operation | Public/Internal | Confidential | Restricted |
|---|---|---|---|
| Read | No RFC required | No RFC required | Standard change |
| Move | Standard change | Normal change | Normal change (CAB) |
| Add | Standard change | Normal change | Normal change (CAB) |
| Change | Normal change | Normal change (CAB) | Human authority only¹ |
| Delete | Normal change | Normal change (CAB) | Human authority only¹ |

¹ Add/Change/Delete on Restricted is **prohibited for autonomous agents** by the §12.5 immutable safety floor — these are never issued as an automated change and always require a human change authority.

Higher-risk cells escalate the **change authority** — from delegated or automated approval for low-risk normal changes up to the Change Advisory Board (CAB) for high-risk ones — consistent with ITIL 4's risk-based authorization model. RMACD's **emergency-escalation** controls correspond directly to ITIL's **Emergency change** type: a time-boxed, expedited path with heightened logging and mandatory post-hoc review.

## **9.4 Python Tools Registry**

The Tools Registry (`rmacd.registry`, SDK 0.8.0+) is the first-class **tool→RMACD classifier and capability layer**. For each tool it declares: the RMACD operation it represents; an optional dynamic classifier that resolves `(operation, data tier, target)` from a call's arguments (so a Delete on a prod resource resolves to Confidential while the same tool on staging resolves to Internal); and an optional **capability ceiling** bounding what the tool may ever do. This is the component that closes the resource-classification gap — mapping a concrete tool call to RMACD terms — without hand-written per-integration glue.

It binds directly to the enforcement layer (§9.5): `PolicyEnforcer.enforce_tool_call(tool_name, args)` looks the tool up in the registry, classifies the call, checks the tool's capability ceiling, then evaluates the resolved `(operation, tier)` against the agent's profile. Enforcement is the **intersection** — the agent profile must allow it **and** the tool's capability must allow it — with the §12.5 safety floor always applied. The registry also computes aggregate risk for multi-tool workflows and auto-classifies MCP servers.

### Core Capabilities

The Tools Registry provides:

- **Tool Registration and Classification** — Register tools with their RMACD level, data classification requirements, and HITL controls
- **Permission Validation** — Validate tool access against agent permission profiles before execution
- **Risk Scoring** — Automatically calculate risk scores for individual tools and multi-tool workflows
- **Audit Logging** — Track all tool registrations, access validations (allows *and* denials), and policy decisions
- **MCP Integration** — Auto-classify Model Context Protocol (MCP) tools, with a capability ceiling at the inferred operation, classification provenance metadata, and a human-review queue for low-confidence results
- **LLM-Assisted Classification** (optional) — A Claude model classifies tool definitions the keyword heuristic cannot, returning a structured `(operation, tier, HITL)` with rationale and confidence; advisory only — runtime enforcement remains deterministic. At authoring time this is the compiler that produces a Governance Pack (§9.6)

### Risk Scoring Algorithm

The registry calculates risk scores using a weighted formula that combines all three RMACD dimensions:

```
risk_score = (rmacd_risk × 0.6 + data_risk × 0.4) × hitl_modifier × 10

Where:
  - rmacd_risk: 0.0 (Read) to 1.0 (Delete)
  - data_risk: 0.0 (Public) to 1.0 (Restricted)
  - hitl_modifier: 0.0 (Prohibited) to 1.0 (Autonomous)
```

This produces a 0-10 scale where higher scores indicate greater operational risk.

### Basic Usage

```python
from rmacd.registry import ToolsRegistry, quick_register

# Create a registry for your organization
registry = ToolsRegistry("my-organization")

# Register a tool with RMACD classification
quick_register(
    registry,
    tool_id="database_query",
    tool_name="Database Query",
    rmacd_level="R",
    description="Execute read-only database queries",
    data_access="confidential",
    required_hitl="logged"
)

# Validate agent access before execution
is_allowed, reason = registry.validate_tool_access(
    tool_id="database_query",
    allowed_levels=["R", "M"],      # Agent's RMACD permissions
    data_tier="confidential"         # Agent's data access tier
)

if is_allowed:
    # Execute the tool
    pass
else:
    # Deny access, log violation
    print(f"Access denied: {reason}")
```

### Workflow Risk Assessment

The registry can analyze multi-tool workflows to identify risk concentrations:

```python
# Every tool in the workflow must be registered first — the registry ships
# empty, and unregistered ids are reported in `missing_tools` rather than
# raising, which would otherwise yield a silent all-zero risk score.
for tool_id, name, level, tier in [
    ("github_commit", "GitHub Commit", "C", "internal"),
    ("kubernetes_deploy", "Kubernetes Deploy", "A", "internal"),
    ("slack_notify", "Slack Notify", "A", "public"),
]:
    quick_register(
        registry,
        tool_id=tool_id,
        tool_name=name,
        rmacd_level=level,
        description=name,
        data_access=tier,
        required_hitl="approval",
    )

# Calculate aggregate risk
risk_analysis = registry.calculate_workflow_risk(
    ["github_commit", "kubernetes_deploy", "slack_notify"]
)

print(f"Total Risk: {risk_analysis['total_risk']}/10")       # 5.26/10
print(f"Highest RMACD Level: {risk_analysis['highest_rmacd']}")  # C
print(f"Highest Risk Tool: {risk_analysis['highest_risk_tool']}")
```

> Risk scoring is **advisory** — a prioritisation aid for review, not part of
> the enforcement path. No decision in §9.5 or §12.5 consults it.

### Pre-Classified Tool Coverage: Governance Packs

A `ToolsRegistry` starts **empty**. Tool coverage is not a fixed catalogue baked
into the registry; it is supplied by **Governance Packs** — declarative,
versionable, signable documents that map a tool call to
`(operation, classification, target)` as data rather than code. Load them and
the registry is populated:

```python
from rmacd.packs import load_packs

registry = load_packs(["shell", "filesystem", "git", "kubectl"])
```

The SDK ships **34 built-in packs**, covering shells, cloud CLIs and their
identity surfaces, developer toolchains, databases, and SaaS/MCP servers:

| Family | Packs |
|--------|-------|
| Shell and filesystem | `shell`, `filesystem` |
| Cloud CLIs | `aws`, `az`, `gcloud`, `kubectl`, `boto3` |
| Cloud identity | `aws-iam`, `az-identity`, `gcp-iam` |
| Cloud-provider MCPs | `aws-api-mcp`, `azure-mcp`, `gcp-toolbox` |
| Developer toolchain | `git`, `gh`, `github`, `gitlab`, `docker`, `terraform`, `helm`, `npm`, `pip-uv`, `make` |
| Data | `sql`, `postgres` |
| SaaS and collaboration | `slack`, `jira`, `confluence`, `google-drive`, `ms365`, `servicenow`, `stripe` |
| Secrets and transfer | `vault`, `ssh-transfer` |

The authoritative, generated list — including per-pack tool and rule counts —
is `docs/governance-packs/catalog.md`. Packs carry a `content_hash` and an
optional Ed25519 signature so a deployment can pin exactly the classification
logic it reviewed; see §9.6.

> **Note.** The `shell` pack is **advisory**. The hand-tuned
> `rmacd.registry.bash` engine remains the enforcing classifier for shell
> commands — the pack under-classifies constructs the declarative language
> cannot yet express (shell redirects, `-c`/`eval` payloads, flag-elevated
> commands such as `find -delete`). See `docs/governance-packs/design.md` §8.

### Standard Permission Profiles

The cumulative permission model (§3) yields a natural ladder of agent roles.
These are **conceptual templates**, not identifiers the SDK resolves — a
profile is whatever its JSON declares:

| Template | Permissions | Use Cases |
|----------|-------------|-----------|
| Observer | R | Monitoring, reporting, analytics |
| Logistics | R, M | File organization, data migration |
| Provisioning | R, M, A | Content creation, resource provisioning |
| Operations | R, M, A, C | Development, configuration management |
| Administrator | R, M, A, C, D | System administration, data cleanup |

Note that even Administrator cannot perform Add, Change, or Delete on
Restricted data — that boundary is immutable (§12.5) and is enforced beneath
any permission grant.

Worked example profiles ship in `schemas/examples/`:
`observer-2d`, `observer-3d`, `operations-2d`, `monitoring-3d`, `devops-3d`,
`incident-responder-3d`, `administrator-3d`, and `regulated-data-handler-dc2d`.

### Enforcement bridge

Bind a tool to the enforcement layer by registering it with a classifier and a
capability ceiling, then gating every call through `enforce_tool_call`:

```python
from rmacd import PolicyEnforcer, ProfileLoader
from rmacd.registry import ToolsRegistry, ToolDefinition, ToolCapability
from rmacd.models import Operation

registry = ToolsRegistry("my-organization")
registry.register_tool(ToolDefinition(
    "update_config", "Update Config", Operation.CHANGE,
    classifier=lambda args: (
        "C",
        "confidential" if str(args.get("server_id", "")).startswith("prod-") else "internal",
        f"server://{args.get('server_id')}",
    ),
    capability=ToolCapability(operations={Operation.CHANGE}),  # may never delete
))

enforcer = PolicyEnforcer(
    profile=ProfileLoader().load_file("profiles/agent.json"),
    agent_id="agent-1",
    registry=registry,
)
enforcer.enforce_tool_call("update_config", {"server_id": "prod-db-01"})
# → classify → capability gate → profile gate (§12.5 floor) → allow / raise
```

### Integration Points

The Tools Registry integrates with agent platforms through:

- **`PolicyEnforcer.enforce_tool_call`** — the single registry-backed gate for a
  framework's tool-call hook (Claude Agent SDK `PreToolUse`, OpenAI Agents SDK
  tool guardrail / `needs_approval`, Microsoft Agent Framework
  `FunctionMiddleware`); see `docs/framework-adapters.md`.
- **JSON Export/Import** — Exchange tool catalogs between systems
- **MCP Bridge** (`MCPRegistryBridge`) — Auto-classify an MCP server's
  `tools/list` response (raw dicts accepted, bulk registration supported) into
  the same registry the enforcer consults. Two classification engines: a
  deterministic keyword heuristic, and an optional Claude-backed
  `LLMToolClassifier` (`pip install rmacd-framework[llm]`) used in `fallback`
  mode (only for tools the keywords cannot classify confidently) or `always`
  mode. LLM failures degrade to the keyword result — registration is never
  blocked. Every auto-classified tool carries a capability ceiling at its
  inferred operation and provenance in `metadata["classification"]`;
  `low_confidence_tools()` surfaces the human-review queue.
- **Bash command classifier** (`classify_bash_command` / `make_bash_classifier`)
  — for the opaque `bash` tool, parse a shell command into the maximum RMACD
  operation (honouring switch-level distinctions such as `sed -n` vs `sed -i`,
  `nslookup` vs `nsupdate`, `>` redirects, shell control keywords so
  `for f in *; do rm "$f"; done` resolves to Delete, and process substitution),
  failing closed on unknown binaries. Operation-level; pair with a 2D profile
  or a path→tier resolver.

### Module Location

The implementation lives in the SDK at `sdk/python/rmacd/registry/`
(`tools.py`, `mcp.py`, `bash.py`, `llm.py`). Import via
`from rmacd.registry import ...`. The previously-standalone `tools-registry/`
directory was removed in v1.4.0; its content is now `rmacd.registry`.

## **9.5 Python SDK Enforcement Layer**

The `rmacd-framework` Python package on PyPI ships the enforcement
plumbing that turns a profile decision into an action: approval routing,
audit emission, exception classification, and the DC2D data-flow
controls. The package is the integration point every agent runtime
(Claude Agent SDK, raw Anthropic SDK, LangChain, AutoGen, CrewAI) hits
when wiring RMACD into a tool-call site.

### Core components

- **`PolicyEvaluator`** — pure decision function. Given a profile and an
  (operation, classification), returns a `PolicyDecision`. No side
  effects. Suitable for offline analysis, profile linters, and dry-run
  UX.
- **`PolicyEnforcer`** — decision + side effects on top of
  `PolicyEvaluator`. Routes approval-gated operations through an
  `ApprovalGateway`, emits `AuditRecord`s through an `AuditLogger`, and
  raises a typed subclass of `RMACDPolicyError` on any non-allow path.
  Also exposes `apply_redaction()` and `check_egress()` for DC2D
  profiles. `from_env()` constructs the enforcer from
  `RMACD_PROFILE_PATH` and `RMACD_AGENT_ID` for 12-factor deployments.
- **`ApprovalGateway` Protocol** — pluggable approval surface returning
  `APPROVED`, `DENIED`, or `TIMEOUT`. Ships `RejectAllApprovalGateway`
  (fail-closed default) and `AutoApproveGateway` (deterministic
  scripted use). Production integrations implement against ServiceNow,
  Jira, Slack, PagerDuty, or webhooks.
- **`AuditLogger` Protocol** — pluggable audit sink. Ships
  `JSONLAuditLogger` (file or stream) and `NullAuditLogger` (default).
  `AuditRecord` shape matches Appendix C.6.
- **`Redactor` Protocol** (DC2D) — output redaction for tiers in the
  profile's `redact_tiers`. Ships `NullRedactor` and `RegexRedactor`
  (email, SSN, credit-card, US phone, IPv4; stable tokenization).
- **`EgressGate` Protocol** (DC2D) — destination check applied before
  classified data leaves the agent. Ships `PolicyDrivenEgressGate`
  (allowlist + `block_external_models` rules).
- **`RMACDError` hierarchy** — typed exceptions for each non-allow
  outcome: `RMACDPermissionDeniedError`, `RMACDProhibitedError`,
  `RMACDConstraintError`, `RMACDApprovalRequiredError`,
  `RMACDApprovalDeniedError`, `RMACDApprovalTimeoutError`,
  `RMACDEgressBlockedError`.
- **Immutable safety floor** — the evaluator enforces the §12.5 prohibitions
  (Add/Change/Delete on Restricted) as a hard runtime floor that no profile
  permission, `autonomy_overrides` entry, or emergency escalation can raise.
  This complements the schema-level rejection of such profiles and guarantees
  the boundary holds even for profiles built in code rather than loaded from a
  validated file.

### Reference integrations

Runnable end-to-end examples live in `spec/examples/`:

| Directory | What it shows |
|---|---|
| `agent-integration-claude-sdk/` | Claude Agent SDK with `PreToolUse` hook → `PolicyEnforcer.enforce`. Seven DevOps tools exercising all five RMACD verbs across all four data tiers. |
| `agent-integration-anthropic-sdk/` | Raw Anthropic SDK manual tool-use loop with prompt caching; `dispatch_tool()` is the single integration site that any framework adapts. |
| `dc2d-customer-support/` | Self-contained DC2D demo (no LLM) showing redaction and egress controls on customer records across all four tiers. |

### Companion documentation

- **`docs/runtime-patterns.md`** — profile binding, resource
  classification lookup, dynamic operation classification, approval-wait
  semantics, SDK error contract, agent self-restriction prompt, DC2D
  runtime, and an end-to-end integration checklist with the
  SDK-provides-vs-integrator-provides boundary.
- **`docs/framework-adapters.md`** — registry-backed `enforce_tool_call`
  (including bash-command and MCP auto-classification), plus copy-pasteable
  integration code for the OpenAI Agents SDK (tool guardrail +
  `needs_approval`), Microsoft Agent Framework (`FunctionMiddleware`),
  LangChain (callback handler + per-tool decorator), AutoGen v0.4+
  (function-tool wrapper), CrewAI (`BaseTool` mixin), and a generic
  dispatch-site pattern.

### Relationship to the Tools Registry

Section 9.4 describes the Tools Registry (`rmacd.registry`), which the
enforcer consults via `enforce_tool_call` to classify a call and apply the
tool capability ceiling. The registry answers "what does this tool call
*mean* in RMACD terms, and what may this tool ever do?"; `PolicyEnforcer`
answers "may *this agent* do that, right now?" — and enforces the
intersection. The previously-standalone `tools-registry/` directory was
folded into `rmacd.registry` and removed in v1.4.0.

## **9.6 Governance Packs**

A **Governance Pack** is a declarative, versionable document that maps tool
calls to `(operation, classification, target)`. Packs move classification out
of code and into reviewable data, so onboarding a tool surface becomes
configuration rather than a code change.

A pack declares:

- **Selectors** — which tool a rule applies to (exact name, glob, or regex),
  optionally narrowed by argument predicates.
- **Extraction** — how to reach the meaningful argument: wrapper stripping,
  tokenization, and recursion into `$(...)` substitution.
- **A `verb_table`** — token-to-operation mapping, combined by **MAX
  operation**, with a fail-closed `default_operation`.
- **A `pattern_map`** — target-to-classification mapping, resolved
  most-sensitive-wins, plus a `target` template.
- **A capability ceiling** — the most a tool may *ever* do, independent of the
  calling profile.

### Normative requirements

1. **Determinism.** Pack evaluation MUST be a pure function of the pack set and
   the tool call. An LLM MAY assist at *authoring* time; it MUST NOT
   participate in a runtime decision.
2. **Composition never weakens.** When multiple packs match a call, the result
   is the **most severe asserted operation** and the **most sensitive tier**.
   Severity is applied as a floor *before* specificity ranking, so a more
   specific rule can never lower an operation asserted by a less specific one.
   A rule asserting no operation MUST contribute no operation claim.
3. **Segment independence.** A compound shell command is resolved per segment
   (split on `;`, `&&`, `||`, `|`, and bare `&`); the result is the maximum
   across segments. `git log; shred x` is a Delete.
4. **Binary anchoring.** A rule naming both shell tools and real binaries MUST
   require one of those binaries as a command token, so an overlay cannot claim
   an unrelated binary's invocation.
5. **The pack layer is subordinate.** Classification is *input* to enforcement.
   The profile, the tool capability ceiling, and the §12.5 immutable floor
   always gate the resulting call.

### Integrity

Each pack carries a canonical `content_hash`; packs MAY carry a detached
Ed25519 signature over it. A deployment SHOULD pin the packs it has reviewed
and load with signature verification required. `source_hash` capture supports
drift detection: when an upstream tool surface changes, affected tools are
flagged for re-review rather than silently reclassified.

The reference SDK ships **34 built-in packs** (§9.4) and the CLI verbs
`rmacd classify`, `rmacd pack validate|review|sign|verify|diff`. Design
rationale and the authoring workflow are in `docs/governance-packs/`.

## **9.7 Session Governance**

Sections 9.4–9.6 govern an agent *an integrator builds*. Session governance
covers the other case: a general-purpose coding agent, run by a human, whose
tool calls should be subject to the same profile.

The reference implementation governs Claude Code through its `PreToolUse`
hook. The model generalizes to any agent runtime offering a synchronous
pre-execution interception point.

### Binding

A session is **bound** when a profile resolves, searched in this order:

1. `RMACD_PROFILE_PATH` (explicit, wins outright).
2. `<cwd>/.claude/rmacd-profile.json`, then each parent directory —
   nearest wins, so a subproject may bind a stricter profile than its root.
3. `$CLAUDE_PROJECT_DIR/.claude/rmacd-profile.json`.

The upward walk is required, not optional: session working directories change
during normal use, and resolving only the exact cwd silently unbinds the
session.

### Normative fail modes

| State | Required behavior |
|-------|-------------------|
| No profile bound | Passthrough. Emit no decision; the host's own permission flow is unchanged. Notify once. |
| Bound, hook errors | **Deny**, with a diagnostic reason. Covers invalid profile, malformed input, and unexpected exceptions. |
| Bound, unknown tool | Deny by default; MAY be configured to route to the host's approval prompt instead. |
| Bound, governance layer unavailable | **Deny.** See below. |

The last row is the one most easily missed. If the host treats a failed hook as
non-blocking — as Claude Code does — then a missing or unimportable SDK yields
an **ungoverned session with no error surfaced to the user**. A conforming
implementation MUST therefore detect "a profile is configured but governance
cannot run" and deny, rather than relying on the hook process itself to be
present and healthy.

One residual fail-open cannot be closed from inside the hook: if the host
imposes a **timeout** and the hook exceeds it, a host that treats a failed hook
as non-blocking proceeds ungoverned. Fail-closed logic covers everything the
hook can observe; it cannot cover never returning an answer. Implementations
SHOULD keep the decision path free of network and disk latency — it needs only
the profile and an in-memory evaluation — and deployments SHOULD set the
timeout with margin for cold caches and loaded hosts. Conforming
implementations MUST document this gap rather than claim fail-closed is total.

Where autonomy resolves to approval, the hook SHOULD surface the host's own
permission prompt rather than blocking on an out-of-band gateway: the hook
process is short-lived and has no interactive input.

Tool calls made inside **subagents** are governed identically — the hook fires
for them as it does in the main conversation.

## **9.8 Audit Evidence**

§9.5 emits audit records; this section covers turning them into evidence.

Records are JSON Lines in the Appendix C.6 shape, one per decision, appended in
decision order. An implementation MUST NOT rewrite or reorder emitted records.

### Where the record is written

An implementation MUST record the **decision**, not merely the execution. A
denied operation never runs, so a trail assembled from completed operations
omits every denial — the exact evidence that demonstrates the boundary held.
Where a runtime offers separate pre- and post-execution interception (§9.7),
the decision is recorded before the call and the outcome after it, joined by a
call identifier.

The outcome record MUST carry forward the classification and autonomy level the
**decision** computed. It MUST NOT recompute them. Two failures follow from
recomputing, both observed in the reference implementation before this rule was
stated:

- **The classification is not a pure function of the call.** Whether writing to
  a path is an Add or a Change depends on whether the path exists — which the
  call itself has just changed. Re-deriving after execution filed every file
  creation as `Add` in its decision and `Change` in its outcome: two records
  that join on the same identifier and disagree about what the agent did.
- **The autonomy level is a property of the decision, not the execution.** An
  outcome record that asserts its own autonomy will claim `autonomous` for a
  call a human explicitly approved. The decision row holds the truth, but an
  outcome row read on its own — which is how "what did this agent do without
  asking?" is answered — then states the opposite.

Carrying the decision forward also keeps the post-execution path cheap: it needs
no profile, no registry, and no re-evaluation.

Records MAY carry an `extra` block for context outside the C.6 shape — session
and call identifiers, and the agent identity when the call originated in a
subagent. Consumers MUST tolerate its absence.

The reference SDK provides `rmacd audit summarize`, which produces an
operation × classification matrix of decisions, denial counts by cause, and
explicit identification of §12.5 floor denials — the evidence an auditor asks
for when the question is "prove the boundary held". Records carry the profile
id and, where applicable, the approval id and approver, so a decision can be
traced to the policy that produced it and the human who authorized it.

`immutable_logging` in a profile's audit requirements signals a WORM
destination. **Conformance note (SDK ≤ 0.14.1):** the reference
`JSONLAuditLogger` writes plain lines with no hash chain, sequence number, or
signature, and `pii_masking` is not applied to audit fields. An implementation
claiming tamper-evidence MUST supply it at the sink.

**Conformance note (session governance):** the reference implementation writes
the session trail best-effort — an unwritable sink emits a diagnostic and the
governance decision stands unchanged. This is deliberate: an audit failure must
not take down a working session. It does mean the trail is not itself evidence
of completeness, so a deployment that must prove no gaps MUST monitor the sink.

## **9.9 MCP Policy Server**

RMACD policy is itself exposed over the Model Context Protocol, so a model can
*consult* governance without being able to alter it. The reference server
(`rmacd mcp-serve`, `[mcp]` extra) offers read-only tools:

| Tool | Purpose |
|------|---------|
| `rmacd_evaluate` | Evaluate an operation/classification against a profile |
| `rmacd_matrix` | Effective autonomy matrix for a profile |
| `rmacd_validate_profile` | Validate a profile against its schema |
| `rmacd_list_packs` / `rmacd_pack_info` | Inspect available governance packs |
| `rmacd_classify_bash` | Classify a shell command in RMACD terms |

Every tool is **advisory and side-effect-free**. Nothing here is an enforcement
path: a model consulting the server cannot grant itself permission, and an
answer from it is not a decision. Enforcement remains §9.5 at the call site.

# **10. Regulatory Compliance Mapping**

## **10.1 Framework Alignment**

The RMACD Framework's three-dimensional model provides natural alignment with major regulatory frameworks. The data classification dimension directly maps to regulatory data categories, while the operation and autonomy dimensions address required controls:

- **GDPR (General Data Protection Regulation):** Personal data maps to Confidential tier; special categories (Article 9) map to Restricted. Read operations enable data subject access rights; Change enables rectification; Delete enables erasure ('right to be forgotten'). Consent workflows map to HITL approval requirements.
- **HIPAA (Health Insurance Portability and Accountability Act):** Protected Health Information (PHI) maps to Restricted tier. The RMACD model enforces minimum necessary access (R-only default), audit logging requirements, and approval controls for any mutative operation.
- **PCI-DSS (Payment Card Industry Data Security Standard):** Cardholder data maps to Restricted tier. RMACD's prohibition on autonomous Add, Change and Delete operations against Restricted data aligns with PCI requirements for privileged access management and change control.
- **SOX (Sarbanes-Oxley Act):** Financial data maps to Confidential tier. Separation of duties is enforced through differentiated agent profiles; audit requirements are addressed through the logging framework.

## **10.2 Compliance Matrix**

| Regulation | Data Classification | Key RMACD Control | Audit Requirement |
|---|---|---|---|
| GDPR | Confidential/Restricted | HITL for C/D operations | Processing activity logs |
| HIPAA | Restricted | R-only default; prohibit A/C/D | 6-year retention |
| PCI-DSS | Restricted | Prohibit autonomous A/C/D | 1-year online, archive |
| SOX | Confidential | Elevated approval for C | 7-year retention |
| ISO 27001 | All tiers | Classification-based controls | As per risk assessment |

## **10.3 Additional Regulatory Frameworks**

### **CCPA/CPRA (California Consumer Privacy Act / California Privacy Rights Act)**

The California Consumer Privacy Act, as amended by the California Privacy Rights Act, establishes consumer rights over personal information for California residents.

**RMACD Mapping:**

| CCPA/CPRA Requirement | RMACD Implementation |
|----------------------|---------------------|
| **Right to Know** | Read operations on Confidential data with `logged` autonomy; audit trails demonstrate what data was accessed |
| **Right to Delete** | Delete operations require `approval` or `elevated_approval`; soft-delete grace periods enable request fulfillment |
| **Right to Correct** | Change operations on personal data require `approval` with documented justification |
| **Right to Opt-Out (Sale/Sharing)** | Move operations involving data transfer require `approval`; prohibited destinations prevent unauthorized sharing |
| **Data Minimization** | Permission profiles enforce minimum necessary access; Read-only profiles for agents that don't need mutation |
| **Sensitive Personal Information** | Maps to Restricted tier; autonomous Add/Change/Delete prohibited |

**Key Controls:**
- Consumer personal information: Confidential tier
- Sensitive personal information (precise geolocation, race, health, etc.): Restricted tier
- 45-day response window maps to approval workflow timeouts
- Audit retention: Minimum 24 months per CPRA

### **FedRAMP (Federal Risk and Authorization Management Program)**

FedRAMP provides a standardized approach to security assessment for cloud products and services used by U.S. federal agencies.

**RMACD Mapping:**

| FedRAMP Requirement | RMACD Implementation |
|--------------------|---------------------|
| **Access Control (AC)** | RMACD profiles enforce least privilege; autonomy levels implement separation of duties |
| **Audit and Accountability (AU)** | `audit_requirements` object mandates log retention (minimum 90 days online, 1 year archive) |
| **Configuration Management (CM)** | Change operations require `approval`; `change_controls` enforce backup and rollback requirements |
| **Incident Response (IR)** | `emergency_escalation` enables pre-authorized incident response with mandatory post-review |
| **System and Information Integrity (SI)** | Read-only monitoring profiles enable continuous monitoring without mutation risk |
| **Personnel Security (PS)** | `approval_authority` maps to authorized personnel; multi-approver support for elevated actions |

**Impact Level Mapping:**

| FedRAMP Impact | RMACD Data Classification | Autonomy Constraints |
|----------------|--------------------------|---------------------|
| **Low** | Public, Internal | Standard governance matrix |
| **Moderate** | Internal, Confidential | Approval required for C/D; enhanced logging |
| **High** | Confidential, Restricted | Elevated approval for all mutations; prohibited A/C/D on Restricted |

**Key Controls:**
- Continuous monitoring agents: Observer profile with `logged` autonomy
- Configuration management agents: Operations profile with `approval` for changes
- All profiles must include `compliance_tags: ["FedRAMP"]` in audit_requirements
- Immutable logging required for High impact systems

### **NIST Cybersecurity Framework (NIST CSF)**

The NIST Cybersecurity Framework provides a policy framework of computer security guidance for organizations to assess and improve their ability to prevent, detect, and respond to cyber attacks.

**RMACD Mapping to CSF Core Functions:**

| CSF Function | CSF Category | RMACD Implementation |
|--------------|--------------|---------------------|
| **IDENTIFY** | Asset Management | Profiles define agent-asset relationships; data classification aligns with asset inventory |
| **IDENTIFY** | Risk Assessment | Governance matrix codifies risk-based autonomy decisions |
| **PROTECT** | Access Control | Three-dimensional model enforces least privilege across operations and data tiers |
| **PROTECT** | Data Security | PICR classification directly maps to data security requirements |
| **DETECT** | Anomalies and Events | Monitoring profiles with real-time alerts; audit logging enables anomaly detection |
| **DETECT** | Continuous Monitoring | Observer profiles enable 24/7 monitoring without mutation risk |
| **RESPOND** | Response Planning | Incident Responder profiles with emergency escalation |
| **RESPOND** | Mitigation | Move operations enable containment; pre-authorized IR actions |
| **RECOVER** | Recovery Planning | Rollback requirements in change_controls; soft-delete grace periods |

**CSF Implementation Tiers:**

| CSF Tier | RMACD Maturity |
|----------|----------------|
| **Tier 1 - Partial** | Basic 2D profiles; manual approval workflows |
| **Tier 2 - Risk Informed** | 3D profiles with data classification; documented governance matrix |
| **Tier 3 - Repeatable** | Automated policy enforcement; integrated approval workflows; audit logging |
| **Tier 4 - Adaptive** | Continuous monitoring; graduated autonomy based on behavior; automated incident response |

**Key Controls:**
- Implement profiles aligned with CSF Protect function categories
- Use `audit_requirements.compliance_tags: ["NIST-CSF"]` for framework alignment
- Emergency escalation supports CSF Respond function
- Monitoring profiles support CSF Detect function

## **10.4 Multi-Regulation Compliance**

Organizations subject to multiple regulatory frameworks should:

1. **Identify overlapping requirements** - Map each regulation to RMACD dimensions
2. **Apply the most restrictive control** - When regulations conflict, use the stricter autonomy level
3. **Maintain unified audit trails** - Configure `compliance_tags` array with all applicable frameworks
4. **Document compliance mapping** - Create organization-specific crosswalk between regulations and profiles

**Example: Healthcare Organization (HIPAA + SOX + NIST CSF)**

```json
{
  "audit_requirements": {
    "retention_days": 2555,
    "immutable_logging": true,
    "compliance_tags": ["HIPAA", "SOX", "NIST-CSF"],
    "pii_masking": true
  }
}
```

# **11. Adoption Roadmap**

## **11.1 Phase 1: Assessment (Weeks 1-4)**

- **Inventory existing AI agents:** Document all deployed agents, their current permissions, and data access patterns
- **Map data classifications:** Ensure all data stores have current classification labels (Public, Internal, Confidential, Restricted)
- **Identify gaps:** Compare current agent permissions against the RMACD governance matrix; identify over-permissioned agents
- **Assess HITL capabilities:** Evaluate existing approval workflow infrastructure and notification systems

## **11.2 Phase 2: Policy Development (Weeks 5-8)**

- **Customize the governance matrix:** Adjust default autonomy levels based on organizational risk tolerance and regulatory requirements
- **Define permission profiles:** Create agent role templates based on organizational needs
- **Establish approval authorities:** Map autonomy levels to specific roles and governance bodies
- **Document exception procedures:** Define processes for handling operations that require elevated permissions

## **11.3 Phase 3: Implementation (Weeks 9-16)**

- **Deploy policy enforcement:** Implement technical controls that enforce RMACD permissions at runtime
- **Configure audit logging:** Ensure all agent operations are logged with appropriate retention
- **Integrate approval workflows:** Connect HITL requirements to ticketing, change management, and notification systems
- **Train operations teams:** Ensure staff understand the RMACD model and their approval responsibilities

## **11.4 Phase 4: Optimization (Ongoing)**

- **Monitor and adjust:** Review agent behavior patterns and adjust permissions based on demonstrated trustworthiness
- **Graduated autonomy expansion:** Increase permissions for agents that demonstrate reliable behavior
- **Incident analysis:** Use any agent-related incidents to refine the governance matrix
- **Compliance validation:** Regular audits to ensure ongoing regulatory alignment

# **12. Exception Handling and Escalation**

## **12.1 Overview**

Even the most comprehensive governance framework must accommodate legitimate exceptions. Business continuity, emergency response, and evolving operational requirements create scenarios where agents may need temporary permission escalations beyond their standard profiles. This section defines the formal exception handling process that maintains governance integrity while enabling operational flexibility.

## **12.2 Exception Categories**

RMACD recognizes four categories of exceptions, each with distinct approval requirements and durations:

| Category | Description | Max Duration | Approval Authority | Example |
|----------|-------------|--------------|-------------------|---------|
| **Emergency** | Imminent threat to business continuity or security | 4 hours | On-call Manager + Security | Active security incident requiring immediate containment |
| **Urgent** | Time-sensitive business requirement | 24 hours | Department Head | Critical production fix outside change window |
| **Planned** | Scheduled activity requiring elevated permissions | 7 days | CAB or Governance Board | Quarterly maintenance, migration projects |
| **Extended** | Long-term operational requirement | 30 days | CISO + Business Owner | New agent capability pilot program |

## **12.3 Exception Request Process**

### Step 1: Request Submission

Exception requests must include:

- **Requesting agent identifier** and current profile
- **Requested permissions** (specific RMACD operations and data classifications)
- **Business justification** with impact assessment
- **Duration requested** with specific start/end timestamps
- **Rollback plan** if exception causes issues
- **Monitoring commitments** during exception period

### Step 2: Risk Assessment

The approving authority must evaluate:

- **Necessity**: Can the objective be achieved within current permissions?
- **Scope**: Is the request minimally scoped to achieve the objective?
- **Duration**: Is the requested timeframe appropriate?
- **Compensating controls**: What additional monitoring or restrictions apply?
- **Precedent**: Does this indicate a need for permanent profile adjustment?

### Step 3: Approval Decision

| Decision | Action |
|----------|--------|
| **Approved** | Exception profile activated with automatic expiration |
| **Approved with Modifications** | Reduced scope/duration granted |
| **Deferred** | Additional information required |
| **Denied** | Justification provided; alternative approach suggested |

### Step 4: Exception Activation

Upon approval:

1. Exception profile is created with explicit expiration timestamp
2. Enhanced audit logging is automatically enabled
3. Notification sent to Security Operations Center (SOC)
4. Monitoring dashboard updated with active exception indicator
5. Automatic calendar reminder set for exception review

### Step 5: Exception Closure

At expiration or upon completion:

1. Exception permissions automatically revoked
2. Post-exception audit report generated
3. Review conducted: Was exception necessary? Were boundaries respected?
4. Recommendation made: Close, extend, or convert to permanent profile change

## **12.4 Exception Profile Template**

An exception request is a declared, justified, time-bounded ask submitted for
adjudication before it takes effect — which is precisely an RMACD Intent. It is
therefore expressed as the `exception` intent type rather than as a separate
record shape, so the framework carries one request path rather than two. See
`docs/intent-specification.md` §7.4.

```json
{
  "$schema": "https://rmacd-framework.org/schema/v1/intent.json",
  "intent_id": "int-exc-20260115-001",
  "intent_type": "exception",
  "submitted_at": "2026-01-15T10:15:00Z",
  "actor": {
    "kind": "agent",
    "id": "devops-agent-007",
    "authorization": "spiffe://corp/ns/agents/devops-agent-007",
    "on_behalf_of": "dba-team@company.com"
  },
  "declaration": {
    "operation": "A",
    "target": "db://prod/payments/migration",
    "data_classification": "confidential",
    "environment": "production",
    "reversibility": {
      "rollback_declared": true,
      "rollback_plan": "Restore from snapshot db-snap-20260115-pre-migration",
      "attested_by": "dba-team@company.com"
    }
  },
  "base_profile_id": "rmacd-3d-observer-v1",
  "exception_category": "urgent",
  "escalated_permissions": {
    "confidential": ["R", "M", "A"],
    "restricted": ["R"]
  },
  "expires_at": "2026-01-16T11:00:00Z",
  "compensating_controls": {
    "enhanced_logging": true,
    "real_time_alerts": true,
    "human_shadow": "dba-team@company.com",
    "restricted_targets": ["db-prod-migration-*"]
  },
  "rollback_plan": "Restore from snapshot db-snap-20260115-pre-migration",
  "status": "requested",
  "justification": "Emergency database migration required due to storage failure"
}
```

Two points of shape are deliberate. The **approval fields are absent from the
request**: who approved, when, and from what effective time are recorded as the
*disposition* on the adjudication's decision record (`intent-decision.schema.json`),
not asserted by the requester — an actor declares facts and never records its own
approval. And `restricted` is capped at `R` and `M` by the schema itself, so the
§12.5 prohibition below is enforced at authoring time and not only by process.

## **12.5 Prohibited Exceptions**

Certain permission escalations are **never** granted through the exception process:

| Prohibition | Rationale |
|-------------|-----------|
| Add, Change or Delete on Restricted data | Fundamental safety boundary; requires human execution |
| Removal of audit logging | Compliance and forensic requirements are non-negotiable |
| Cross-environment exceptions (prod profile in dev) | Environment isolation must be maintained |
| Indefinite or open-ended duration | All exceptions must have explicit expiration |
| Blanket "all operations" grants | Exceptions must be specifically scoped |

For these scenarios, the operation must be performed by a human operator with appropriate authorization, with the agent potentially preparing or recommending the action.

**Enforcement (rmacd 0.7.0+):** The Change/Delete-on-Restricted prohibition — together with Add on Restricted — is enforced mechanically, not merely by convention. `schemas/profile-3d.schema.json` rejects any profile that lists A, C, or D under `permissions.restricted` or sets a `restricted.(A|C|D)` autonomy override to anything other than `prohibited`. Independently, the SDK evaluator applies an immutable runtime floor (`IMMUTABLE_PROHIBITIONS`) that returns `PROHIBITED` for these cells before any permission, override, or emergency-escalation path is consulted, so a hand-built or programmatically-constructed profile cannot bypass the boundary even if it sidesteps schema validation.

## **12.6 Exception Metrics and Governance**

Organizations should track and review:

| Metric | Target | Action if Exceeded |
|--------|--------|-------------------|
| Exception frequency per agent | < 2 per month | Review if profile needs permanent adjustment |
| Average exception duration | < 24 hours | Investigate extended exceptions |
| Exception denial rate | 20-40% | Too low suggests rubber-stamping; too high suggests overly restrictive profiles |
| Post-exception incidents | 0 | Any incident triggers immediate review |
| Exceptions converted to permanent | < 10% | High conversion suggests inadequate initial profiling |

Monthly exception reports should be reviewed by the governance board to identify patterns requiring systematic profile adjustments.

# **13. Incident Response and Violation Management**

## **13.1 Overview**

When an AI agent violates its RMACD profile—whether through malfunction, compromise, or misconfiguration—organizations need a structured response process. This section defines the incident classification, response workflow, and remediation procedures for RMACD policy violations.

## **13.2 Violation Categories**

| Category | Severity | Description | Example |
|----------|----------|-------------|---------|
| **Attempt** | Low | Agent requested operation beyond permissions; blocked by PEP | Observer agent attempted Move operation |
| **Bypass** | High | Agent circumvented policy controls | Agent wrote to command queue to trigger action |
| **Breach** | Critical | Unauthorized operation executed on protected data | Change operation on Confidential data without approval |
| **Compromise** | Critical | Agent behavior indicates external manipulation | Unusual operation patterns suggesting hijacking |

## **13.3 Detection Mechanisms**

RMACD policy enforcement should include multiple detection layers:

| Layer | Mechanism | Response |
|-------|-----------|----------|
| **Prevention** | Policy Enforcement Point (PEP) blocks unauthorized operations | Log attempt, continue monitoring |
| **Detection** | Anomaly detection on operation patterns | Alert SOC, flag for investigation |
| **Audit** | Post-hoc analysis of audit logs | Identify policy gaps, update profiles |
| **Correlation** | Cross-agent behavior analysis | Detect coordinated violations |

## **13.4 Incident Response Workflow**

### Phase 1: Detection and Triage (0-15 minutes)

1. **Alert received** from PEP, SIEM, or anomaly detection
2. **Initial classification** based on violation category and data sensitivity
3. **Severity assignment** using matrix:

| Violation Type | Public Data | Internal Data | Confidential Data | Restricted Data |
|----------------|-------------|---------------|-------------------|-----------------|
| Attempt | P4-Low | P4-Low | P3-Medium | P2-High |
| Bypass | P3-Medium | P2-High | P1-Critical | P1-Critical |
| Breach | P2-High | P1-Critical | P1-Critical | P1-Critical |
| Compromise | P1-Critical | P1-Critical | P1-Critical | P1-Critical |

### Phase 2: Containment (15-60 minutes)

Based on severity:

| Severity | Containment Action |
|----------|-------------------|
| **P4-Low** | Log and monitor; no immediate action required |
| **P3-Medium** | Reduce agent to Read-only profile; notify agent owner |
| **P2-High** | Suspend agent operations; isolate from sensitive systems |
| **P1-Critical** | Immediate termination; network isolation; preserve forensic state |

### Phase 3: Investigation (1-24 hours)

Investigation must determine:

- **Root cause**: Misconfiguration, bug, compromise, or intentional abuse?
- **Scope**: What data/systems were affected?
- **Impact**: Was data exfiltrated, modified, or destroyed?
- **Attribution**: If compromise, what was the attack vector?

### Phase 4: Remediation (24-72 hours)

| Root Cause | Remediation |
|------------|-------------|
| **Misconfiguration** | Correct profile; add validation; update deployment process |
| **Software bug** | Patch agent; add regression tests; review similar agents |
| **Policy gap** | Update governance matrix; add new constraints |
| **Compromise** | Rotate credentials; patch vulnerability; forensic review |
| **Intentional abuse** | Revoke agent; escalate to management/legal |

### Phase 5: Recovery and Restoration

1. **Validate remediation** through testing
2. **Restore agent** with corrected profile (if appropriate)
3. **Enhanced monitoring** for 30-day observation period
4. **Stakeholder communication** on incident and resolution

### Phase 6: Post-Incident Review

Within 7 days of resolution:

- **Incident report** documenting timeline, impact, and response
- **Lessons learned** identifying process improvements
- **Governance updates** if matrix or profiles need adjustment
- **Training needs** if human error contributed

## **13.5 Incident Response Profiles**

For security incident response, pre-authorized escalation profiles enable rapid containment:

```json
{
  "$schema": "https://rmacd-framework.org/schema/v1/profile-3d.json",
  "profile_id": "rmacd-3d-incident-responder-v1",
  "profile_name": "Incident Responder",
  "model": "three-dimensional",
  "version": "1.0",
  "description": "Pre-authorized IR agent for security incident containment",
  "permissions": {
    "public": ["R", "M", "A"],
    "internal": ["R", "M", "A"],
    "confidential": ["R", "M"],
    "restricted": ["R"]
  },
  "autonomy_overrides": {
    "internal.M": "autonomous",
    "confidential.M": "notification"
  },
  "emergency_escalation": {
    "enabled": true,
    "trigger_conditions": ["soc_declared_incident", "automated_threat_detection"],
    "escalated_permissions": {
      "confidential": ["R", "M", "A"],
      "restricted": ["R", "M"]
    },
    "max_duration_minutes": 60,
    "require_post_incident_review": true,
    "notification_targets": ["soc@company.com", "ciso@company.com"]
  },
  "constraints": {
    "environments": ["production"],
    "allowed_actions": [
      "isolate_network_segment",
      "block_ip_address",
      "disable_user_account",
      "capture_memory_dump",
      "snapshot_disk",
      "quarantine_file"
    ]
  },
  "metadata": {
    "created": "2026-01-15T00:00:00Z",
    "author": "security-operations",
    "approved_by": "ciso"
  }
}
```

## **13.6 Violation Metrics and Continuous Improvement**

Track these metrics to improve governance effectiveness:

| Metric | Purpose | Target |
|--------|---------|--------|
| Mean Time to Detect (MTTD) | How quickly violations are identified | < 5 minutes |
| Mean Time to Contain (MTTC) | How quickly agents are isolated | < 15 minutes |
| Mean Time to Remediate (MTTR) | How quickly normal operations resume | < 24 hours |
| Violation rate per agent | Identifies problematic agents | < 1 per quarter |
| False positive rate | Detection system accuracy | < 5% |
| Recurring violations | Same agent, same violation type | 0 (should not recur) |

## **13.7 Communication Templates**

### Initial Notification (Internal)

```
RMACD POLICY VIOLATION DETECTED
Severity: [P1-Critical | P2-High | P3-Medium | P4-Low]
Agent: [agent-id]
Violation: [category] - [brief description]
Data Classification: [Public | Internal | Confidential | Restricted]
Containment Status: [Contained | In Progress | Monitoring]
Incident Lead: [name]
Bridge/Channel: [link]
```

### Stakeholder Update

```
RMACD INCIDENT UPDATE - [incident-id]
Status: [Investigating | Contained | Remediated | Closed]
Impact Summary: [brief description]
Affected Systems: [list]
Current Actions: [what's being done]
ETA to Resolution: [timeframe]
Next Update: [time]
```

# **14. Conclusion: ITIL for the Agentic Era**

The RMACD Framework represents the natural evolution of IT service management principles into the age of autonomous AI agents. By integrating three essential dimensions—operational permissions (RMACD), data classification (PICR), and autonomy controls (HITL)—the framework provides enterprise IT organizations with a comprehensive, implementable, and universal governance model.
The framework's three-dimensional approach resolves critical gaps in existing governance approaches. Where security frameworks address permissions without operational specificity, where data classification schemes ignore agent autonomy, and where autonomy frameworks neglect data sensitivity, RMACD provides an integrated model that addresses all three concerns simultaneously.
The detailed treatment of each operational tier—Read, Move, Add, Change, and Delete—provides practitioners with specific guidance on risk profiles, data classification considerations, safeguards, and anti-patterns. This operational depth transforms RMACD from a conceptual model into an implementation-ready governance framework.
The key innovations of the RMACD Framework include:

- **The Read Foundation:** Adding Read as an explicit operational tier enables safe agent onboarding, continuous monitoring use cases, and progressive trust building
- **Three-Dimensional Integration:** The combination of operations, data classification, and autonomy controls provides unambiguous governance guidance for any agent-data-operation scenario
- **Operational Depth:** Detailed guidance for each RMACD tier (Read, Move, Add, Change, Delete) including risk profiles, safeguards, agent patterns, and anti-patterns
- **ITIL Heritage:** Building on forty years of MACD operational vocabulary ensures enterprise IT teams can immediately understand and implement the framework
- **Compliance Alignment:** Natural mapping to GDPR, HIPAA, PCI-DSS, SOX, and other regulatory frameworks simplifies compliance demonstration
As AI agents become increasingly prevalent in enterprise operations, the need for standardized governance frameworks will only intensify. Organizations that adopt RMACD gain immediate benefits: a common vocabulary for discussing agent permissions, clear mapping to existing change management processes, natural compliance alignment, and a pathway for gradually increasing agent autonomy as trust is established.
The agentic AI era demands that we reconsider how we govern operational permissions. RMACD provides the answer: graduated autonomy control through operational verb classification, data-sensitivity-aware permission profiles, and human-in-the-loop requirements matched to risk profiles. It is, in essence, ITIL for the Agentic Era.

* * *

*RMACD Framework v1.2.1*
*Conceived and authored by Kash, January 2026*
*Released under Creative Commons Attribution 4.0 (CC BY 4.0)*

# **Appendix A: Quick Reference Card**

The following condensed reference captures the essential RMACD governance matrix for rapid consultation:

**RMACD GOVERNANCE MATRIX - QUICK REFERENCE**

|  | PUBLIC | INTERNAL | CONFIDENTIAL | RESTRICTED |
|---|---|---|---|---|
| READ | AUTO | AUTO | LOG | NOTIFY |
| MOVE | AUTO | NOTIFY | APPROVE | ELEVATED |
| ADD | NOTIFY | APPROVE | ELEVATED | PROHIBIT |
| CHANGE | APPROVE | APPROVE | ELEVATED | PROHIBIT |
| DELETE | APPROVE | ELEVATED | ELEVATED | PROHIBIT |

**Autonomy Level Key:** AUTO = Autonomous (no human required) | LOG = Autonomous + Enhanced Logging | NOTIFY = Human Notified | APPROVE = Approval Required | ELEVATED = CAB/Senior Approval | PROHIBIT = Human Only

**Operation Risk Hierarchy (Low → High):** Read → Move → Add → Change → Delete
**Data Sensitivity Hierarchy (Low → High):** Public → Internal → Confidential → Restricted

# **Appendix B: Permission Profile Templates (JSON)**

The following JSON templates define machine-readable permission profiles that can be consumed by AI agentic platforms. These profiles encode the RMACD governance model in a format suitable for runtime policy enforcement.

## **B.1 Profile Schema Definition**

Each permission profile follows a standardized schema that defines the agent's operational boundaries across data classifications:

```json
{
  "$schema": "https://rmacd-framework.org/schema/v1/profile-3d.json",
  "profile_id": "rmacd-3d-<name>-v1",
  "profile_name": "string",
  "model": "three-dimensional",
  "version": "1.0",
  "description": "string",
  "permissions": {
    "public": ["R", "M", "A", "C", "D"],
    "internal": ["R", "M", "A", "C", "D"],
    "confidential": ["R", "M", "A", "C"],
    "restricted": ["R", "M"]
  },
  "autonomy_overrides": {
    "<classification>.<operation>": "<autonomy_level>"
  },
  "constraints": {
    "environments": ["development", "staging", "production"],
    "time_windows": { "..." },
    "rate_limits": { "..." },
    "resource_quotas": { "..." }
  },
  "metadata": {
    "created": "ISO-8601",
    "author": "string",
    "approved_by": "string"
  }
}
```

## **B.2 Observer Profile**

Read-only access across all data classifications. Ideal for monitoring, compliance auditing, and recommendation agents.

```json
{
  "$schema": "https://rmacd-framework.org/schema/v1/profile-3d.json",
  "profile_id": "rmacd-3d-observer-v1",
  "profile_name": "Observer",
  "model": "three-dimensional",
  "version": "1.0",
  "description": "Read-only monitoring and analysis agent",
  "permissions": {
    "public": ["R"],
    "internal": ["R"],
    "confidential": ["R"],
    "restricted": ["R"]
  },
  "autonomy_overrides": {
    "confidential.R": "logged",
    "restricted.R": "notification"
  },
  "constraints": {
    "environments": ["development", "staging", "production"],
    "rate_limits": {
      "queries_per_minute": 100,
      "data_volume_mb_per_hour": 500
    }
  },
  "metadata": {
    "created": "2026-01-10T00:00:00Z",
    "author": "rmacd-framework",
    "approved_by": "security-team"
  }
}
```

## **B.3 Logistics Profile**

Read and Move permissions for data transfer and workload balancing operations.

```json
{
  "$schema": "https://rmacd-framework.org/schema/v1/profile-3d.json",
  "profile_id": "rmacd-3d-logistics-v1",
  "profile_name": "Logistics",
  "model": "three-dimensional",
  "version": "1.0",
  "description": "Data transfer and workload balancing agent",
  "permissions": {
    "public": ["R", "M"],
    "internal": ["R", "M"],
    "confidential": ["R"],
    "restricted": []
  },
  "autonomy_overrides": {
    "public.M": "autonomous",
    "internal.M": "notification",
    "confidential.R": "logged"
  },
  "constraints": {
    "environments": ["development", "staging", "production"],
    "allowed_destinations": [
      "storage-tier-*",
      "backup-region-*",
      "dr-site-*"
    ],
    "prohibited_destinations": [
      "external-*",
      "public-*"
    ]
  },
  "metadata": {
    "created": "2026-01-10T00:00:00Z",
    "author": "rmacd-framework",
    "approved_by": "operations-team"
  }
}
```

## **B.4 Provisioning Profile**

Read, Move, and Add permissions for resource provisioning and deployment operations.

```json
{
  "$schema": "https://rmacd-framework.org/schema/v1/profile-3d.json",
  "profile_id": "rmacd-3d-provisioning-v1",
  "profile_name": "Provisioning",
  "model": "three-dimensional",
  "version": "1.0",
  "description": "Resource provisioning and deployment agent",
  "permissions": {
    "public": ["R", "M", "A"],
    "internal": ["R", "M", "A"],
    "confidential": ["R", "M"],
    "restricted": ["R"]
  },
  "autonomy_overrides": {
    "public.A": "notification",
    "internal.A": "approval",
    "confidential.M": "approval",
    "restricted.R": "notification"
  },
  "constraints": {
    "environments": ["development", "staging"],
    "resource_quotas": {
      "max_vms_per_request": 10,
      "max_storage_gb_per_request": 500,
      "max_monthly_cost_usd": 5000
    },
    "required_templates": [
      "approved-vm-template-*",
      "hardened-container-*"
    ],
    "auto_expiration_days": 30
  },
  "metadata": {
    "created": "2026-01-10T00:00:00Z",
    "author": "rmacd-framework",
    "approved_by": "cloud-governance"
  }
}
```

## **B.5 Operations Profile**

Full operational capabilities except Delete for production change management.

```json
{
  "$schema": "https://rmacd-framework.org/schema/v1/profile-3d.json",
  "profile_id": "rmacd-3d-operations-v1",
  "profile_name": "Operations",
  "model": "three-dimensional",
  "version": "1.0",
  "description": "Production operations and change management agent",
  "permissions": {
    "public": ["R", "M", "A", "C"],
    "internal": ["R", "M", "A", "C"],
    "confidential": ["R", "M", "A"],
    "restricted": ["R"]
  },
  "autonomy_overrides": {
    "public.C": "approval",
    "internal.C": "approval",
    "confidential.A": "elevated_approval",
    "restricted.R": "notification"
  },
  "constraints": {
    "environments": ["development", "staging", "production"],
    "time_windows": {
      "production_changes": {
        "allowed_days": ["tuesday", "wednesday", "thursday"],
        "allowed_hours_utc": { "start": "06:00", "end": "14:00" },
        "blackout_dates": ["2026-12-24", "2026-12-25", "2026-12-31"]
      }
    },
    "change_controls": {
      "require_backup_before_change": true,
      "require_rollback_plan": true,
      "max_blast_radius_percentage": 10,
      "canary_deployment_required": true
    }
  },
  "metadata": {
    "created": "2026-01-10T00:00:00Z",
    "author": "rmacd-framework",
    "approved_by": "cab-committee"
  }
}
```

## **B.6 Administrator Profile**

Maximum agent permissions with appropriate controls. Note: Restricted data A/C/D remains prohibited.

```json
{
  "$schema": "https://rmacd-framework.org/schema/v1/profile-3d.json",
  "profile_id": "rmacd-3d-administrator-v1",
  "profile_name": "Administrator",
  "model": "three-dimensional",
  "version": "1.0",
  "description": "Full administrative agent with maximum permissions",
  "permissions": {
    "public": ["R", "M", "A", "C", "D"],
    "internal": ["R", "M", "A", "C", "D"],
    "confidential": ["R", "M", "A", "C"],
    "restricted": ["R", "M"]
  },
  "autonomy_overrides": {
    "public.D": "approval",
    "internal.D": "elevated_approval",
    "confidential.C": "elevated_approval",
    "restricted.M": "elevated_approval"
  },
  "constraints": {
    "environments": ["development", "staging", "production"],
    "delete_controls": {
      "soft_delete_grace_period_days": 7,
      "require_dependency_check": true,
      "require_legal_hold_check": true,
      "two_person_rule_for_confidential": true
    },
    "audit_requirements": {
      "enhanced_logging": true,
      "real_time_alerts": ["confidential.*", "restricted.*"],
      "retention_days": 365
    }
  },
  "metadata": {
    "created": "2026-01-10T00:00:00Z",
    "author": "rmacd-framework",
    "approved_by": "ciso"
  }
}
```

## **B.7 Custom Profile Example: Security Incident Response**

Specialized profile for security incident response with pre-authorized emergency permissions.

```json
{
  "$schema": "https://rmacd-framework.org/schema/v1/profile-3d.json",
  "profile_id": "rmacd-3d-security-ir-v1",
  "profile_name": "Security Incident Response",
  "model": "three-dimensional",
  "version": "1.0",
  "description": "Emergency response agent for security incidents",
  "permissions": {
    "public": ["R", "M", "A"],
    "internal": ["R", "M", "A"],
    "confidential": ["R", "M"],
    "restricted": ["R"]
  },
  "autonomy_overrides": {
    "public.M": "autonomous",
    "internal.M": "autonomous",
    "confidential.M": "notification"
  },
  "emergency_escalation": {
    "enabled": true,
    "trigger_conditions": ["active_incident", "soc_declared_emergency"],
    "escalated_permissions": {
      "confidential": ["R", "M", "A"],
      "restricted": ["R", "M"]
    },
    "escalation_duration_minutes": 60,
    "require_post_incident_review": true
  },
  "constraints": {
    "environments": ["production"],
    "allowed_actions": [
      "isolate_compromised_asset",
      "block_ip_address",
      "disable_user_account",
      "capture_forensic_snapshot",
      "deploy_additional_monitoring"
    ]
  },
  "metadata": {
    "created": "2026-01-10T00:00:00Z",
    "author": "security-operations",
    "approved_by": "ciso"
  }
}
```

# **Appendix C: Implementation Workflow**

This appendix describes how RMACD permission profiles are consumed by AI agentic platforms at runtime. The workflow covers profile loading, policy evaluation, execution control, and audit logging.

## **C.1 High-Level Architecture**

![RMACD Runtime Architecture](RMACD_Runtime_Architecture.drawio.png)

*Source: [`RMACD_Runtime_Architecture.drawio`](RMACD_Runtime_Architecture.drawio). SDK class names are overlaid on each component.*

The RMACD enforcement architecture consists of four primary components that work together to govern agent operations:

- **Policy Store:** Central repository for RMACD permission profiles, governance matrices, and organizational customizations. Profiles are versioned and cryptographically signed to ensure integrity.
- **Policy Decision Point (PDP):** Runtime engine that evaluates agent operation requests against loaded profiles. The PDP determines the required autonomy level and whether the operation can proceed.
- **Policy Enforcement Point (PEP):** Integration layer that intercepts agent operations and enforces PDP decisions. The PEP can block, queue for approval, or allow operations based on policy.
- **Audit and Compliance Engine:** Logging infrastructure that captures all policy decisions, agent actions, and approval workflows for compliance reporting and forensic analysis.

## **C.2 Runtime Evaluation Flow**

When an AI agent attempts an operation, the following evaluation sequence occurs:

- Agent requests operation (e.g., 'CHANGE configuration on server-prod-01')
- PEP intercepts request and extracts: operation type, target resource, data classification (in the reference SDK this extraction is the Tools Registry, §9.4 — static tool metadata plus an optional per-call dynamic classifier)
- PEP queries PDP with: agent_id, profile_id, operation, resource_classification
- PDP loads agent's assigned permission profile from Policy Store
- PDP evaluates: Does profile grant this operation for this classification?
- PDP determines required autonomy level from governance matrix
- PDP checks constraints: environment, time window, rate limits, quotas
- PDP returns decision: ALLOW, DENY, QUEUE_FOR_APPROVAL, or NOTIFY
- PEP enforces decision and logs outcome to Audit Engine
- If approval required: operation queued; approver notified; agent waits or times out

## **C.3 Policy Decision Logic (Pseudocode)**

The following pseudocode illustrates the core policy evaluation algorithm:

```text
function evaluateOperation(agent, operation, resource):
profile = loadProfile(agent.profile_id)
classification = resource.data_classification

# Step 1: Check if operation is permitted at all
if operation not in profile.permissions[classification]:
return DENY("Operation not permitted for classification")

# Step 2: Determine autonomy level
override_key = f"{classification}.{operation}"
if override_key in profile.autonomy_overrides:
autonomy = profile.autonomy_overrides[override_key]
else:
autonomy = DEFAULT_GOVERNANCE_MATRIX[operation][classification]

# Step 3: Check if operation is prohibited
if autonomy == "prohibited":
return DENY("Operation prohibited for agents")

# Step 4: Validate constraints
constraint_result = validateConstraints(profile, operation, resource)
if constraint_result.failed:
return DENY(constraint_result.reason)

# Step 5: Return decision based on autonomy level
switch autonomy:
case "autonomous":
return ALLOW(log_level="standard")
case "logged":
return ALLOW(log_level="enhanced")
case "notification":
notifyStakeholders(agent, operation, resource)
return ALLOW(log_level="enhanced")
case "approval":
return QUEUE_FOR_APPROVAL(approver="change_manager")
case "elevated_approval":
return QUEUE_FOR_APPROVAL(approver="cab_committee")
```

## **C.4 Integration Patterns**

RMACD enforcement can be integrated with agentic platforms through several patterns:

- **SDK Integration:** Embed the RMACD SDK directly into the agent runtime. The SDK intercepts tool calls and API requests, evaluating each against the assigned profile before execution.

```python
# Python SDK Example (rmacd-framework)
from rmacd import PolicyEnforcer, ProfileLoader

enforcer = PolicyEnforcer(
    profile=ProfileLoader().load_file("profiles/operations.json"),
    agent_id="devops-agent-001",
)

@enforcer.guard(  # Decorator intercepts and evaluates before the body runs
    operation="C",
    classifier=lambda *, server_id, **_: (
        f"server://{server_id}",
        "confidential" if server_id.startswith("prod-") else "internal",
    ),
)
def modify_config(*, server_id: str, config: dict):
    """Agent function to modify server configuration."""
    return infrastructure_api.update_config(server_id, config)

# Enforcement happens automatically:
# - If ALLOW: function executes normally
# - If DENY: a typed RMACDPolicyError subclass is raised
# - If approval-gated: routed through the ApprovalGateway first

# Alternatively, gate a framework's tool-call hook through the Tools
# Registry (§9.4) with a single call — no per-function decorators:
#   enforcer.enforce_tool_call(tool_name, tool_args)
```

- **API Gateway Integration:** Deploy RMACD as a policy layer in the API gateway. All agent requests pass through the gateway, which evaluates permissions before forwarding to backend services.
- **Service Mesh Sidecar:** Deploy RMACD policy enforcement as a sidecar proxy alongside agent containers. The sidecar intercepts all outbound requests and applies policy decisions.
- **Event-Driven Integration:** For asynchronous agent operations, integrate RMACD with the message queue. The policy enforcer evaluates operations before messages are processed.

## **C.5 Approval Workflow Integration**

When operations require human approval, RMACD integrates with existing workflow
systems. This is the `ApprovalRequest` an `ApprovalGateway` receives, verbatim
as the SDK constructs it:

```json
{
  "request_id": "apr-20260110-001",
  "agent_id": "devops-agent-001",
  "profile_id": "rmacd-3d-operations-v1",
  "operation": "C",
  "target": "config://prod/app-server-01/nginx.conf",
  "classification": "internal",
  "autonomy_level": "approval",
  "justification": "Performance optimization for increased traffic",
  "timeout_seconds": 300,
  "metadata": null,
  "created_at": "2026-01-10T14:30:00Z"
}
```

Note the shape: `operation` is the single-letter RMACD code at the top level
(not a nested object), the required autonomy is `autonomy_level`, and the
timeout is `timeout_seconds`. Free-form context belongs in `metadata`.

**Approver routing is the gateway's responsibility, not the request's.** The
request carries no `approvers` list: the profile's `approval_authority` block
declares who may approve and how many are required, and the integrator's
`ApprovalGateway` implementation reads it. Requests can be routed to
ServiceNow, Jira, Slack, Microsoft Teams, or custom workflow systems via
webhooks and API integrations.

> **Conformance note (SDK ≤ 0.14.0).** `approval_authority` — `approvers`,
> `timeout_minutes`, `require_multiple_approvers`, `minimum_approvers` — is
> schema-validated but **not yet enforced by the reference SDK**: it does not
> reach the gateway, and `timeout_seconds` is currently fixed at 300. An
> implementation claiming conformance must enforce it or document the gap.

## **C.6 Audit Log Format**

All policy decisions and agent operations generate structured audit logs for
compliance. Each record is one line of JSONL, emitted exactly as shown — the
object is **top-level**, with no `audit_record` envelope:

```json
{
  "record_id": "aud-a21511787fe6416a",
  "timestamp": "2026-01-10T14:30:22.456Z",
  "agent_id": "devops-agent-001",
  "profile_id": "rmacd-3d-operations-v1",
  "operation": {
    "type": "C",
    "target": "config://prod/app-server-01/nginx.conf",
    "classification": "internal"
  },
  "policy_decision": {
    "result": "ALLOW",
    "autonomy_level": "approval",
    "blocked_reason": null,
    "approval_id": "apr-20260110-001",
    "approved_by": "john.smith@company.com",
    "approved_at": "2026-01-10T14:28:00Z",
    "constraints_applied": [],
    "emergency_mode": false
  },
  "execution": {
    "status": "SUCCESS",
    "duration_ms": 1250,
    "error": null
  },
  "compliance_tags": ["SOX", "ISO27001"]
}
```

Points where a reader is most likely to get this wrong:

- `operation.type` is the **single-letter RMACD code** (`"C"`), not a word
  (`"CHANGE"`). It is the value of the `Operation` enum.
- `policy_decision.result` is one of `ALLOW`, `DENY`, `QUEUED`, `APPROVED`,
  `REJECTED`, `EXECUTED`. `EXECUTED` records are emitted by `@guard` after a
  tool runs and are the only ones carrying an `execution` block; on every other
  record `execution` is `null`. *(Known gap in SDK ≤ 0.14.0:
  `rmacd.audit_report` omits `EXECUTED` from its result table, so `@guard`
  execution records fall into that report's "other" bucket.)*
- `blocked_reason`, `constraints_applied` and `emergency_mode` are always
  present. `constraints_applied` names the constraint families that
  participated in the decision — `immutable_prohibition` identifies a §12.5
  floor denial.
- Timestamps are RFC 3339 with a `Z` suffix and are **timezone-aware UTC**.
- There is no `rollback_available` field.

## **C.7 Deployment Checklist**

Organizations implementing RMACD should complete the following deployment steps:

- **Profile Assignment:** Map each AI agent to an appropriate RMACD permission profile based on its intended function and risk tolerance.
- **Data Classification Tagging:** Ensure all data sources, APIs, and resources are tagged with their data classification (Public, Internal, Confidential, Restricted).
- **Policy Store Deployment:** Deploy the central policy store with high availability and access controls appropriate for security infrastructure.
- **PDP/PEP Integration:** Integrate policy decision and enforcement points with agent runtimes using the appropriate integration pattern.
- **Approval Workflow Configuration:** Configure approval routing to appropriate stakeholders and integrate with existing ticketing systems.
- **Audit Pipeline Setup:** Establish audit log collection, retention, and alerting according to compliance requirements.
- **Testing and Validation:** Test all permission profiles in non-production environments before enabling enforcement in production.
- **Monitoring and Alerting:** Configure dashboards and alerts for policy violations, approval backlogs, and unusual agent behavior patterns.

## **C.8 Companion Runtime Documentation**

The architecture and pseudocode in this Appendix describe *what* the
enforcement layer does. The companion documents in `docs/` describe *how* an
integrator wires it together at the call site:

- **`docs/implementation.md`** — step-by-step adoption: choosing a deployment
  shape, defining profiles, classifying resources, and rolling out enforcement.
- **`docs/runtime-patterns.md`** — profile binding, resource
  classification lookup, dynamic operation classification, approval-wait
  semantics for LLM tool calls, SDK error contract, agent self-restriction
  prompts, and DC2D runtime enforcement.
- **`docs/framework-adapters.md`** — copy-pasteable integration code for
  the OpenAI Agents SDK, Microsoft Agent Framework, LangChain, AutoGen and
  CrewAI, plus a generic dispatch-site pattern for any other framework.
- **`docs/governance-packs/`** (§9.6) — pack format, design rationale, the
  AI-compile authoring workflow, signing and drift detection, and the
  generated `catalog.md` of built-in packs.
- **`docs/claude-code.md`** (§9.7) — session governance: binding, the
  normative fail-mode table, tool mapping, and the plugin.
- **`docs/audit-evidence.md`** (§9.8) — the audit record field reference and
  `rmacd audit summarize`.
- **`docs/intents.md`** (§12.4) — the intent model: adjudication as a second,
  out-of-band enforcement mode complementing runtime interception; the intent
  ladder, the production and record planes, the type registry, and how
  likelihood escalates the §3.1 matrix without introducing a second one.
- **`docs/intent-specification.md`** — the normative companion to the above:
  the intent envelope, the actor model, the adjudication contract, grants and
  campaigns, the decision record, and conformance requirements.

# **Appendix D: The Data-Classification Two-Dimensional Variant (DC2D)**

## **D.1 Motivation**

The Three-Dimensional model (Operations × Data Classification × Autonomy) and the operational Two-Dimensional model (Operations × Autonomy, see schema `profile-2d.json`) cover the majority of enterprise deployments. A third deployment shape exists in practice but has not previously been articulated as a named framework variant: organizations whose **primary governance lever is data sensitivity**, where operational permissions are already governed elsewhere — typically by IAM/RBAC, DLP, or platform-native policy.

Indicators that an organization is a candidate for the DC2D variant include:

- Mature data classification programme (ISO/IEC 27001 Annex A.5.12, NIST SP 800-60) is already authoritative.
- AI agent operational permissions are bounded by an existing identity layer (e.g., Microsoft Entra, Okta, Salesforce profiles) and are not re-litigated at the agent governance layer.
- Inline enforcement is delivered by an AI-DLP, gateway, or trust-layer product (e.g., Microsoft Purview, Salesforce Einstein Trust Layer, AWS Bedrock Guardrails + Macie, Cloudflare AI Gateway, Databricks Unity Catalog) for which the missing artefact is a *named, versioned policy profile*, not an enforcement engine.
- Regulatory drivers (HIPAA, PCI-DSS, GDPR Art. 9) are framed in terms of *what data the agent touches*, not *what verbs it issues*.

The DC2D variant makes the Data Classification × Autonomy pairing explicit and portable, so that organizations with this deployment shape can express agent governance in a single profile rather than composing it ad hoc across multiple products.

## **D.2 Relationship to the 2D and 3D Models**

| Variant | Axes | Best For |
|---|---|---|
| **3D** | Operations × Data Classification × Autonomy | Default. Organizations with both formal classification and granular operational governance needs. |
| **2D (Operational)** | Operations × Autonomy | Organizations without formal data classification tiers. |
| **2D (Data-Classification, DC2D)** | Data Classification × Autonomy | Organizations whose primary governance lever is data sensitivity; operations are governed by an upstream identity or DLP layer. |

DC2D is not a replacement for the 3D model; it is a deliberate projection that drops the operations axis when that axis is being enforced elsewhere. Organizations should select 3D where feasible.

## **D.3 The DC2D Governance Matrix**

The DC2D matrix collapses to a single row because autonomy is determined solely by the classification of data accessed:

| Data Tier | Recommended Default | Acceptable Range | Typical Coverage |
|---|---|---|---|
| Public | Autonomous | Autonomous → Logged | Marketing copy, public documentation, open data |
| Internal | Logged | Logged → Notification | Internal wikis, non-sensitive operational data |
| Confidential | Approval | Notification → Approval | PII, customer records, financial data |
| Restricted | Elevated Approval | Approval → Prohibited | PHI, PCI, secrets, GDPR Article 9 special categories |

**Defaults rationale.** The recommended defaults represent the middle of the acceptable range, calibrated to match the autonomy stance most commonly observed in production deployments of AI-DLP and trust-layer products. They are deliberately more conservative than a Read-only collapse of the 3D matrix and less conservative than a worst-case (Change/Delete) collapse, on the assumption that DC2D is used precisely when the operation mix is heterogeneous and bounded externally.

**Deviation discipline.** Any tier whose autonomy stance falls outside the acceptable range, or where `allowed: false` is set for tiers below Restricted, must include a written `justification` in the profile and be reviewed by the same authority that approves 3D profile exceptions (see Section 12).

## **D.4 Profile Schema Identifier**

DC2D profiles are validated against the schema at:

```
https://rmacd-framework.org/schema/v1/profile-dc2d.json
```

Profile IDs follow the pattern `^rmacd-dc2d-[a-z0-9-]+$` to disambiguate them from operational 2D profiles (`rmacd-2d-*`) and 3D profiles (`rmacd-3d-*`).

## **D.5 What DC2D Intentionally Omits**

The following fields from the 3D and operational 2D models are **absent by design** in DC2D, because they are operation-specific:

- `permissions` (the RMACD verb set)
- `change_controls` (backup/rollback/blast-radius for Change operations)
- `delete_controls` (soft-delete grace, dependency check, legal-hold for Delete operations)
- `resource_quotas` (creation limits for Add operations)

DC2D adds, in their place:

- `redaction` — per-tier output masking and tokenization (the primary control surface when the operation axis is dropped).
- `egress_controls` — restrictions on where classified data may flow, including a default block on external (non-tenant) model endpoints for Confidential and Restricted tiers.
- `escalated_tiers` (within `emergency_escalation`) — emergency expansion of permitted data tiers, replacing the `escalated_permissions` field used in operational profiles.

## **D.6 Example Profile**

A worked example (`schemas/examples/regulated-data-handler-dc2d.json`) accompanies this appendix. It models a customer-support agent in a regulated industry with the following stance: Public autonomous, Internal logged, Confidential gated by per-action DPO approval, Restricted denied entirely with explicit justification pointing to a separate authorized profile.

## **D.7 Prior Art and Positioning**

The DC2D pairing is best characterized as **making explicit a control composition the industry already performs ad hoc**, rather than introducing a wholly new conceptual axis. The two axes individually are mainstream:

- Sensitivity-tier gating has been standard practice in DLP since the 2000s and is the operating model of contemporary AI-DLP products (Cyberhaven, Strac, MIND, Cloudflare AI Gateway, Symantec + Google Agent Gateway, Lakera).
- Tiered HITL autonomy taxonomies have been popularized by the Cloud Security Alliance (Agentic NIST AI RMF Profile; *Levels of Autonomy*, January 2026), TM Forum's AI Autonomy Governance, and Inteq's decision-tier model.

The closest framework-level prior art is the CSA capability-control matrix, which uses *capability type* rather than *data sensitivity* as its second axis. DC2D substitutes data sensitivity for capability, yielding a model directly aligned with regulated-industry compliance vocabulary (HIPAA PHI, PCI cardholder data, GDPR Article 9 special categories) and the policy surfaces of mainstream AI-DLP products.

*— End of Document —*
