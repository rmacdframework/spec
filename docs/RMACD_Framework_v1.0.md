**THE RMACD FRAMEWORK**

Read, Move, Add, Change, Delete

A Three-Dimensional Governance Model Integrating
Operational Permissions, Data Classification, and Autonomy Controls
for Governing Autonomous AI Agents in Enterprise IT Operations

*Extending ITIL's MACD Heritage to the Agentic AI Era*

Version 1.0 | January 2026
**Author: Kash Kashyap**

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

Permissions are cumulative: an agent granted 'Change' permissions implicitly possesses 'Add', 'Move', and 'Read' capabilities. This cumulative model reflects the reality that higher-risk operations typically require the lower-risk capabilities as prerequisites.

## **2.3 Dimension 2: Data Classification (PICR)**

The RMACD Framework adopts the industry-standard four-tier data classification model, mapping each tier to specific protection requirements and agent access constraints:

The data classification dimension fundamentally transforms how operational permissions are interpreted. A 'Read' operation against Public data is categorically different from a 'Read' operation against Restricted data, despite being the same operational verb. The integrated RMACD model captures this distinction.

## **2.4 Dimension 3: Autonomy Control (HITL Levels)**

The third dimension specifies the required level of human-in-the-loop (HITL) oversight for any operation. The RMACD Framework defines six autonomy levels:

# **3. The Integrated RMACD Governance Matrix**

## **3.1 The Complete Three-Dimensional Model**

The intersection of RMACD operations and data classification tiers produces a 5×4 matrix, where each cell specifies the required autonomy control level. This matrix serves as the definitive governance reference for AI agent operations:

This matrix represents the default governance posture. Organizations may adjust individual cells based on their risk tolerance, regulatory requirements, and operational maturity, but the matrix provides a sound baseline for initial deployment.

## **3.2 Interpreting the Matrix**

The matrix encodes several fundamental governance principles:

- **Risk Compounds Across Dimensions:** Both higher-risk operations (moving down the RMACD hierarchy) and higher-sensitivity data (moving right across classification tiers) independently increase the required oversight level. The combination of both produces the most restrictive controls.
- **Read Operations Remain Low-Risk Across Classifications:** Even against Restricted data, Read operations require only notification-level oversight because they cannot alter system state. However, enhanced logging ensures accountability and audit capability.
- **Destructive Operations on Sensitive Data Are Prohibited:** Change and Delete operations against Restricted data are marked 'Prohibited' for autonomous agents. These operations require human execution, though agents may recommend or prepare such actions.
- **The 'Approval' Threshold Shifts Left with Risk:** For low-risk operations (Read, Move), approval requirements only appear at higher data classifications. For high-risk operations (Change, Delete), approval is required even for Public data.

## **3.3 Approval Authority Mapping**

Each autonomy level maps to specific approval authorities, enabling integration with existing organizational governance structures:

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

| Data Classification | Autonomy Level | Rationale |
|---------------------|----------------|-----------|
| Public | Autonomous | No state change; freely available information poses zero risk |
| Internal | Logged | Business data access requires audit trail for accountability |
| Confidential | Notification | Sensitive data access requires stakeholder awareness |
| Restricted | Notification | Highest sensitivity requires oversight notification; enhanced logging mandatory |

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

| Data Classification | Autonomy Level | Rationale |
|---------------------|----------------|-----------|
| Public | Autonomous | Low risk relocation; reversible with minimal impact |
| Internal | Logged | Business data movements require audit trail |
| Confidential | Approval | Sensitive data relocation requires explicit authorization |
| Restricted | Approval | Highest sensitivity requires approval; destination validation mandatory |

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

| Data Classification | Autonomy Level | Rationale |
|---------------------|----------------|-----------|
| Public | Logged | Resource creation tracked; template enforcement required |
| Internal | Notification | New business resources require stakeholder awareness |
| Confidential | Approval | Sensitive resource provisioning requires explicit authorization |
| Restricted | Elevated Approval | High-sensitivity resource creation requires CAB/senior approval |

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

| Data Classification | Autonomy Level | Rationale |
|---------------------|----------------|-----------|
| Public | Approval | State modification requires review even for public data |
| Internal | Approval | Business configuration changes require authorization |
| Confidential | Elevated Approval | Sensitive data changes require CAB/senior approval |
| Restricted | Prohibited | No autonomous changes permitted; human execution only |

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

| Data Classification | Autonomy Level | Rationale |
|---------------------|----------------|-----------|
| Public | Approval | Even low-risk deletions require explicit review |
| Internal | Elevated Approval | Business data destruction requires CAB/senior approval |
| Confidential | Elevated Approval | Sensitive data deletion requires two-person rule |
| Restricted | Prohibited | No autonomous deletion permitted; human execution only |

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

Note: Even Administrator agents do not receive full RMACD permissions on Restricted data. Change and Delete operations on Restricted data remain human-only in the default model.

## **9.2 Environment-Based Differentiation**

The same agent should have different permission profiles across environments. Production environments warrant stricter controls than development or staging:

## **9.3 Integration with Change Management**

RMACD integrates naturally with existing ITIL change management processes. The combination of operation type and data classification determines the appropriate change category:

# **10. Regulatory Compliance Mapping**

## **10.1 Framework Alignment**

The RMACD Framework's three-dimensional model provides natural alignment with major regulatory frameworks. The data classification dimension directly maps to regulatory data categories, while the operation and autonomy dimensions address required controls:

- **GDPR (General Data Protection Regulation):** Personal data maps to Confidential tier; special categories (Article 9) map to Restricted. Read operations enable data subject access rights; Change enables rectification; Delete enables erasure ('right to be forgotten'). Consent workflows map to HITL approval requirements.
- **HIPAA (Health Insurance Portability and Accountability Act):** Protected Health Information (PHI) maps to Restricted tier. The RMACD model enforces minimum necessary access (R-only default), audit logging requirements, and approval controls for any mutative operation.
- **PCI-DSS (Payment Card Industry Data Security Standard):** Cardholder data maps to Restricted tier. RMACD's prohibition on autonomous Change/Delete operations aligns with PCI requirements for privileged access management and change control.
- **SOX (Sarbanes-Oxley Act):** Financial data maps to Confidential tier. Separation of duties is enforced through differentiated agent profiles; audit requirements are addressed through the logging framework.

## **10.2 Compliance Matrix**

| Regulatory Framework | Data Classification Mapping | Key RMACD Controls | Audit Requirements |
|---------------------|----------------------------|-------------------|-------------------|
| GDPR | Personal Data → Confidential; Special Categories → Restricted | Read enables access rights; Change enables rectification; Delete enables erasure | Enhanced logging for all personal data operations |
| HIPAA | PHI → Restricted | R-only default; approval required for mutative operations | Minimum necessary access; comprehensive audit trails |
| PCI-DSS | Cardholder Data → Restricted | Prohibited autonomous Change/Delete; elevated approval for Move | Real-time monitoring; quarterly access reviews |
| SOX | Financial Data → Confidential | Separation of duties via differentiated profiles | Retention minimum 7 years; tamper-evident logs |
| ISO 27001 | Based on organization classification | Full RMACD matrix alignment | Annual audits; continuous monitoring |
| NIST CSF | Risk-based classification | Graduated autonomy controls | Risk assessment documentation |

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

# **12. Conclusion: ITIL for the Agentic Era**

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

*RMACD Framework v1.0*
*Conceived and authored by Kash, January 2026*
*Released under Creative Commons Attribution 4.0 (CC BY 4.0)*

# **Appendix A: Quick Reference Card**

The following condensed reference captures the essential RMACD governance matrix for rapid consultation:

**RMACD GOVERNANCE MATRIX - QUICK REFERENCE**

**Autonomy Level Key:** AUTO = Autonomous (no human required) | LOG = Autonomous + Enhanced Logging | NOTIFY = Human Notified | APPROVE = Approval Required | ELEVATED = CAB/Senior Approval | PROHIBIT = Human Only

**Operation Risk Hierarchy (Low → High):** Read → Move → Add → Change → Delete
**Data Sensitivity Hierarchy (Low → High):** Public → Internal → Confidential → Restricted

# **Appendix B: Permission Profile Templates (JSON)**

The following JSON templates define machine-readable permission profiles that can be consumed by AI agentic platforms. These profiles encode the RMACD governance model in a format suitable for runtime policy enforcement.

## **B.1 Profile Schema Definition**

Each permission profile follows a standardized schema that defines the agent's operational boundaries across data classifications:

```json
{
  "$schema": "https://rmacd.io/schema/v1/profile.json",
  "profile_id": "string",
  "profile_name": "string",
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
  "$schema": "https://rmacd.io/schema/v1/profile.json",
  "profile_id": "rmacd-observer-v1",
  "profile_name": "Observer",
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
  "$schema": "https://rmacd.io/schema/v1/profile.json",
  "profile_id": "rmacd-logistics-v1",
  "profile_name": "Logistics",
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
  "$schema": "https://rmacd.io/schema/v1/profile.json",
  "profile_id": "rmacd-provisioning-v1",
  "profile_name": "Provisioning",
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
  "$schema": "https://rmacd.io/schema/v1/profile.json",
  "profile_id": "rmacd-operations-v1",
  "profile_name": "Operations",
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

Maximum agent permissions with appropriate controls. Note: Restricted data C/D remains prohibited.

```json
{
  "$schema": "https://rmacd.io/schema/v1/profile.json",
  "profile_id": "rmacd-administrator-v1",
  "profile_name": "Administrator",
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
  "$schema": "https://rmacd.io/schema/v1/profile.json",
  "profile_id": "rmacd-security-ir-v1",
  "profile_name": "Security Incident Response",
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

The RMACD enforcement architecture consists of four primary components that work together to govern agent operations:

- **Policy Store:** Central repository for RMACD permission profiles, governance matrices, and organizational customizations. Profiles are versioned and cryptographically signed to ensure integrity.
- **Policy Decision Point (PDP):** Runtime engine that evaluates agent operation requests against loaded profiles. The PDP determines the required autonomy level and whether the operation can proceed.
- **Policy Enforcement Point (PEP):** Integration layer that intercepts agent operations and enforces PDP decisions. The PEP can block, queue for approval, or allow operations based on policy.
- **Audit and Compliance Engine:** Logging infrastructure that captures all policy decisions, agent actions, and approval workflows for compliance reporting and forensic analysis.

## **C.2 Runtime Evaluation Flow**

When an AI agent attempts an operation, the following evaluation sequence occurs:

- Agent requests operation (e.g., 'CHANGE configuration on server-prod-01')
- PEP intercepts request and extracts: operation type, target resource, data classification
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
# Python SDK Example
from rmacd import PolicyEnforcer, Profile

enforcer = PolicyEnforcer(
policy_store_url="https://policies.internal/rmacd",
agent_id="devops-agent-001"
)

@enforcer.guard  # Decorator intercepts and evaluates
def modify_config(server_id: str, config: dict):
"""Agent function to modify server configuration."""
return infrastructure_api.update_config(server_id, config)

# Enforcement happens automatically:
# - If ALLOW: function executes normally
# - If DENY: RMACDPermissionError raised
# - If QUEUE: function blocks until approval received
```

- **API Gateway Integration:** Deploy RMACD as a policy layer in the API gateway. All agent requests pass through the gateway, which evaluates permissions before forwarding to backend services.
- **Service Mesh Sidecar:** Deploy RMACD policy enforcement as a sidecar proxy alongside agent containers. The sidecar intercepts all outbound requests and applies policy decisions.
- **Event-Driven Integration:** For asynchronous agent operations, integrate RMACD with the message queue. The policy enforcer evaluates operations before messages are processed.

## **C.5 Approval Workflow Integration**

When operations require human approval, RMACD integrates with existing workflow systems:

```json
{
  "approval_request": {
    "request_id": "apr-20260110-001",
    "agent_id": "devops-agent-001",
    "profile_id": "rmacd-operations-v1",
    "operation": {
      "type": "CHANGE",
      "target": "config://prod/app-server-01/nginx.conf",
      "classification": "internal",
      "description": "Update nginx worker_connections from 1024 to 2048"
    },
    "required_autonomy": "approval",
    "approvers": ["change-manager@company.com"],
    "timeout_minutes": 60,
    "created_at": "2026-01-10T14:30:00Z",
    "context": {
      "reason": "Performance optimization for increased traffic",
      "rollback_plan": "Revert to backup nginx.conf.bak",
      "impact_assessment": "Low - affects single server"
    }
  }
}
```

Approval requests can be routed to ServiceNow, Jira, Slack, Microsoft Teams, or custom workflow systems via webhooks and API integrations.

## **C.6 Audit Log Format**

All policy decisions and agent operations generate structured audit logs for compliance:

```json
{
  "audit_record": {
    "record_id": "aud-20260110-143022-001",
    "timestamp": "2026-01-10T14:30:22.456Z",
    "agent_id": "devops-agent-001",
    "profile_id": "rmacd-operations-v1",
    "operation": {
      "type": "CHANGE",
      "target": "config://prod/app-server-01/nginx.conf",
      "classification": "internal"
    },
    "policy_decision": {
      "result": "ALLOW",
      "autonomy_level": "approval",
      "approval_id": "apr-20260110-001",
      "approved_by": "john.smith@company.com",
      "approved_at": "2026-01-10T14:28:00Z"
    },
    "execution": {
      "status": "SUCCESS",
      "duration_ms": 1250,
      "rollback_available": true
    },
    "compliance_tags": ["SOX", "ISO27001"]
  }
}
```

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

*— End of Document —*
