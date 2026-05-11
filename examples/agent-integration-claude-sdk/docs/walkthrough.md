# Walkthrough: code-to-concern map

This document maps each runtime concern this example handles to the
concrete code that handles it. Other framework integrations (LangChain,
AutoGen, CrewAI, raw Anthropic SDK) follow the same playbook — only the
dispatch surface differs.

## Profile binding

`PolicyEnforcer` accepts the agent identity and profile explicitly at
construction:

```python
PolicyEnforcer(
    profile=ProfileLoader().load_file(PROFILE_PATH),
    agent_id="devops-agent-demo",
    ...
)
```

`PolicyEnforcer.from_env()` reads `RMACD_PROFILE_PATH` and
`RMACD_AGENT_ID` from the environment for 12-factor deployments. This
demo uses the explicit form so it runs without prior environment setup.

The binding is one-shot at startup: a process holds a single
`PolicyEnforcer` for the life of the agent. Multi-agent runtimes that
host several profiles in one process instantiate one enforcer per agent.

## Resource classification lookup

`rmacd_demo/classifier.py` implements `classify_tool_call(tool_name, tool_input)`
and returns `(operation, target, classification)` by:

1. Looking up the static RMACD operation for the tool (a property of the
   *tool*, not the *resource*).
2. Resolving the target from the tool's arguments
   (`server_id="db-prod-01"` → `target="server://db-prod-01"`).
3. Reading the resource's classification from the mock infra. Production
   integrations swap this lookup for a data catalog, tag registry, or
   DLP product API.

The lookup runs colocated with the PEP — classifier and enforcer in the
same process — so the classification is authoritative at the moment of
the call. A cache-miss or stale tag elsewhere in the pipeline cannot let
a Confidential resource through as Internal.

## Dynamic operation classification

The classifier resolves the tier dynamically from the resource the LLM
picked at call time, not from a static tag on the tool definition.
`update_config(server_id="web-stage-01")` and
`update_config(server_id="db-prod-01")` produce different
classifications (Internal vs. Confidential) and therefore go through
different autonomy gates.

For tools whose operation verb is also dynamic (`kubectl apply` is Add
when the resource doesn't exist, Change when it does), the classifier
performs a pre-flight existence check and returns the appropriate verb.
The pattern generalizes — the classifier is a function, not a static
table.

## Approval-wait semantics

The `ApprovalGateway` Protocol returns when the gateway says so, not
when the enforcer decides to give up. Implementations can:

- Prompt on stdin (this demo's `CLIApprovalGateway`)
- Suspend on an event loop while a webhook awaits an answer
- Poll a ticketing system every few seconds
- Spawn a Slack message and `await` a button click

The CLI gateway blocks the tool call until the operator answers.
Deployments needing agent operation to span hours implement a gateway
that suspends the agent process (not just the tool call) and resumes
when the approval arrives. The SDK contract is that `gateway.request()`
returns an `ApprovalDecision`; how it gets one is up to the gateway.

`ApprovalOutcome.TIMEOUT` is the third return value: gateways that
cannot reach an approver within `request.timeout_seconds` return it
rather than raise.

## Framework integration surface (Claude Agent SDK)

The integration surface is the `PreToolUse` hook in `rmacd_demo/hook.py`:

```python
options = ClaudeAgentOptions(
    mcp_servers={"rmacd_demo": server},
    hooks={"PreToolUse": [HookMatcher(matcher="*", hooks=[pretool_hook])]},
)
```

The hook returns one of:

- `{"permissionDecision": "allow"}` — enforcer approved.
- `{"permissionDecision": "deny", "permissionDecisionReason": "..."}` — enforcer denied.

The reason string is what the LLM sees as the tool error. The hook
includes the denial subclass in the reason (Prohibited, Permission
Denied, Approval Denied, Timeout, Constraint) so the agent can adapt
its next move accordingly.

## Agent-side self-restriction

`rmacd_demo/system_prompt.md` tells the model:

- Which profile it's bound to.
- The permitted operations per tier.
- The autonomy stance per cell.
- The hard prohibitions.
- How to behave when a tool returns a denial.

The model still doesn't have full visibility (the operator can deny an
approval-gated call), but it has enough context to plan sensibly: read
before mutate, avoid proposing Change/Delete on Restricted, and
communicate clearly when an action requires the operator's direct
execution.

## DC2D runtime enforcement

This example uses a 3D profile, so redaction and egress controls do not
apply here. See the separate
[`examples/dc2d-customer-support/`](../../dc2d-customer-support/) demo
for redaction (`PolicyEnforcer.apply_redaction`) and egress
(`PolicyEnforcer.check_egress`) in action.

## SDK error contract

`rmacd/exceptions.py` defines the hierarchy:

```
RMACDError
└── RMACDPolicyError
    ├── RMACDPermissionDeniedError    profile does not grant this (op, tier)
    ├── RMACDProhibitedError          autonomy matrix prohibits — never granted
    ├── RMACDConstraintError          env / time window / quota blocked it
    ├── RMACDApprovalRequiredError    approval needed and no gateway was wired up
    ├── RMACDApprovalDeniedError      human approver said no
    └── RMACDApprovalTimeoutError     approval request timed out
RMACDEgressBlockedError               (DC2D) destination blocked by egress_controls
```

Every exception carries the underlying `PolicyDecision` so callers can
inspect `autonomy_level`, `blocked_reason`, and `constraints_applied`. The
hook uses the split to translate each subclass into a distinct
`permissionDecisionReason` string for the LLM.
