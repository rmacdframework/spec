# Implementation Guide

This guide provides step-by-step instructions for implementing the RMACD Framework in your organization.

## Prerequisites

Before implementing RMACD, ensure you have:

1. **Inventory of AI agents** — Document all deployed or planned autonomous agents
2. **Identified stakeholders** — Change management, security, compliance teams
3. **Approval workflow infrastructure** — Ticketing system, notification capabilities

## Step 1: Choose Your Implementation Model

### Two-Dimensional Model (RMACD + HITL)

Choose this if:
- Your organization does not have formal data classification
- You need rapid adoption
- You're piloting with a limited scope

### Three-Dimensional Model (RMACD + HITL + Data Classification)

Choose this if:
- You have an established data classification scheme
- You operate in a regulated industry
- Your agents access data across multiple sensitivity levels

## Step 2: Define Permission Profiles

Start with the provided templates:

- **Observer** — Read-only agents
- **Logistics** — Read + Move agents
- **Provisioning** — Read + Move + Add agents
- **Operations** — Read + Move + Add + Change agents
- **Administrator** — Full RMACD (with restrictions on Restricted data)

Customize as needed for your agent types.

## Step 3: Configure Policy Enforcement

Integrate RMACD with your agent runtime:

1. Load permission profiles from your policy store
2. Intercept agent operation requests
3. Evaluate against the governance matrix
4. Enforce autonomy requirements (allow, notify, queue for approval, deny)
5. Log all decisions for audit

## Step 4: Integrate Approval Workflows

Map autonomy levels to your existing systems:

| Autonomy Level | Integration |
|----------------|-------------|
| Autonomous | No integration needed |
| Logged | Enhanced logging pipeline |
| Notification | Email, Slack, Teams alerts |
| Approval | ServiceNow, Jira, custom ticketing |
| Elevated Approval | CAB workflow, senior management queue |
| Prohibited | Block with explanation |

## Step 5: Test and Validate

Before production enforcement:

1. Run in audit-only mode (log decisions, don't enforce)
2. Review logs for unexpected denials or approvals
3. Adjust profiles and matrix as needed
4. Gradually enable enforcement

## Step 6: Monitor and Iterate

Ongoing operations:

1. Review agent behavior patterns
2. Adjust permissions based on demonstrated trustworthiness
3. Respond to incidents and update profiles
4. Conduct periodic compliance audits

---

## Platform-Specific Guides

*Coming soon:*

- Kubernetes / Container orchestration
- AWS / Azure / GCP agent integration
- LangChain / AutoGPT integration
- ServiceNow integration

---

## Need Help?

- Email: contact@rmacd-framework.org
- Web: [rmacd-framework.org](https://rmacd-framework.org)
- GitHub Discussions: [rmacdframework/spec/discussions](https://github.com/rmacdframework/spec/discussions)
