# Governance Packs & AI-Compile Authoring

> Make agent onboarding *configuration, not code.* Governance Packs turn the
> work of mapping a tool call to RMACD terms into a declarative, reusable,
> signed artifact — and the AI-compile workflow drafts those packs for you,
> subject to human review.

**Status:** Shipped in `rmacd-framework` 0.11.0 as the `rmacd.packs` package.
Normative specification status deferred to a later spec revision.

---

## Quickstart

```python
from rmacd import PolicyEnforcer
from rmacd.packs import load_packs

# Off-the-shelf governance for an agent's tool surface — no classifier code.
enforcer = PolicyEnforcer(
    profile, agent_id="agent-1",
    registry=load_packs(["aws", "kubectl", "github", "jira"]),
)
enforcer.enforce_tool_call("kubectl", {"command": "delete pod web -n prod"})
```

Author a pack for a new MCP server, review it, and sign it:

```bash
rmacd classify tools.json -n my-server -o my-server.yaml   # AI-compile a draft
rmacd pack review my-server.yaml                            # eyeball the uncertain tail
rmacd pack sign  my-server.yaml -k signing.pem             # freeze + Ed25519 sign
rmacd pack verify my-server.yaml -k signing.pub            # gate trust in CI/prod
rmacd pack diff  my-server.yaml tools.json                 # detect drift later
```

Built-in packs ship as data and are loadable by name (`load_pack("aws")`); they
are **AI-drafted starting points** — review and sign them before relying on them
in production. Signing needs the optional extra: `pip install rmacd-framework[sign]`;
the LLM authoring path needs `pip install rmacd-framework[llm]`.

---

## Why this exists

RMACD's decision engine is already deterministic, fast, and well-tested. The
barrier to adopting it across an enterprise agent fleet is not the enforcement
hooks — those are thin and several already work today. The barrier is
**classification**: the step that translates a concrete tool call into the three
terms RMACD reasons about.

```
kubectl("delete pod payments-api -n prod")
        │
        ▼  classification
operation = Delete · tier = confidential · target = pod://prod/payments-api
        │
        ▼  enforcement (deterministic)
§12.5 floor + agent profile + tool capability ceiling  →  allow / approve / deny
```

Today that translation is **hand-written Python**, re-implemented per integration
and per team. It cannot be shipped as data — the SDK literally drops a tool's
dynamic classifier when serializing it. The result is duplicated effort,
inconsistent governance across teams, and ~60–105 lines of brittle glue for
every new agent.

Governance Packs remove that tax.

## What ships

1. **A declarative classification language** — express what a hand-written
   classifier expresses, as data. Three primitives cover the real cases:
   `verb_table` (operation from a verb in an argument), `pattern_map` (tier from
   a resource pattern), and `resolver` (a named hook for live lookups).
2. **Packs** — versioned, signable bundles of classification rules for an
   ecosystem (e.g. `kubectl`, `aws`, `jira`). Authored once, reused everywhere.
3. **AI-compile authoring** — point the tooling at a tool source (an MCP server,
   an OpenAPI spec, a CLI surface); the LLM proposes a pack with rationale and
   confidence; a human reviews the uncertain tail; the result is frozen and
   signed. **The LLM never runs at enforcement time.**

## Enterprise value

- **Unblocks adoption.** A standard, signed governance artifact is what gets an
  agent project through security review.
- **Seamless onboarding.** New-agent integration drops from ~60–105 LoC of
  classifier code to ~0 — pick packs off the shelf (or compile one and review
  it). The same `kubectl` pack governs a LangChain, OpenAI, and Claude agent
  identically.
- **Audit-grade.** The runtime source of truth is a signed, human-approved data
  file. Every decision — including live resolver lookups — is reconstructable
  from the pack version plus the audit record.

## Pack catalog (planned)

| Family | Packs |
|--------|-------|
| Shell | `shell` (reference; ports the existing `bash.py`) |
| Cloud CLIs | `aws`, `gcloud`, `az`, `kubectl` |
| Dev tools | `github`, `gitlab`, `sql`, `filesystem` |
| SaaS / collab MCPs | `slack`, `google-drive`, `jira`, `confluence`, `postgres` |
| Cloud-provider MCPs | AWS `awslabs/mcp` suite (incl. AWS API MCP), Azure MCP Server, Google Cloud MCP Toolbox for Databases + Cloud Run MCP |
| Microsoft 365 MCPs | Microsoft Graph / Work IQ — Outlook, Teams, SharePoint, OneDrive, Word, Dataverse |

Together these govern the agentic surface of all three major cloud providers
plus the dominant enterprise productivity suite, out of the box.

## Document map

- **[design.md](design.md)** — technical design: the pack format, the rule
  language, the runtime engine, SDK integration, the security model.
- **[roadmap.md](roadmap.md)** — phased delivery plan, scope, and success
  metrics.
- **[authoring-guide.md](authoring-guide.md)** — how to write a pack, with a
  fully worked example, including CLI-style vs MCP-style packs and the rules for
  "passthrough" tools that execute arbitrary APIs/SQL.

## Relationship to the rest of the framework

Governance Packs are additive and change nothing about how enforcement
works. They produce the `(operation, tier, target)` *input* to the evaluator —
exactly what classifiers produce today. The §12.5 immutable floor, the agent
profile, and the tool capability ceiling remain the authoritative runtime gates.
Existing hand-written classifiers continue to work unchanged.
