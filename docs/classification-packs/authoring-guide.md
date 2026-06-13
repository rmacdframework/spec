# Classification Packs — Authoring Guide

How to write a classification pack. Companion documents:
[README](README.md), [design](design.md), [roadmap](roadmap.md).

> A pack maps a tool call `(tool_name, args)` to RMACD terms
> `(operation, data_tier, target)` — as data, not code. This guide covers the
> anatomy of a pack, the two pack styles, the three classification primitives,
> a fully worked example, and the required treatment of high-risk "passthrough"
> tools.

---

## 1. Anatomy of a pack

```yaml
pack: <name>                    # ecosystem identifier (e.g. kubectl, jira)
version: <semver>
description: <one line>
default_operation: <R|M|A|C|D>  # fail-closed default when no rule/verb matches
provenance:                     # who/what authored and reviewed this
  authored_by: <person/team>
  llm_assisted: <bool>
  reviewed_by: <person>
  source_hash: <sha256:…>       # hash of the tool defs this was compiled from
content_hash: <sha256:…>        # set by `rmacd pack sign`
signature: <…>                  # set by `rmacd pack sign`
resolvers:                      # optional named live-lookup hooks (see §4.3)
  - name: <resolver-name>
    description: <one line>
    fail_closed_default: <tier>
rules:                          # the classification rules (see §3)
  - id: <rule-id>
    when: { … }                 # selector
    parse: { … }                # optional extraction
    classify: { … }             # or verb_table + default
    confidence: <high|low>
```

A rule that does not set every field falls back to the pack/tool defaults; any
field a rule omits is filled from `default_operation`, the resolver/pattern_map
default, or the rendered target template.

## 2. Two pack styles

The verb that determines the operation lives in different places depending on the
tool surface. Knowing which style you are writing is the first decision.

### CLI-style (verb is inside a string argument)

Shells and cloud CLIs pass the whole command as one string:
`kubectl("delete pod …")`. Parse the string and match the verb with a
`verb_table`.

```yaml
- id: kubectl
  when: { tool: kubectl }
  parse: { arg: command, strip_wrappers: [sudo, env] }
  verb_table: { get: R, describe: R, apply: C, scale: C, create: A, delete: D }
  default: C
  tier:
    pattern_map:
      - { arg_regex: { arg: command, pattern: "-n\\s+prod" }, tier: confidential }
    default: internal
```

### MCP-style (verb is in the tool name)

MCP servers expose each capability as its own named tool: `jira_delete_issue`,
`jira_create_issue`. Match the tool name and assign a literal operation.

```yaml
- id: jira-delete
  when: { tool: jira_delete_issue }
  classify: { operation: D, tier: { resolver: jira_project_tier, from: project_key, default: confidential }, target: "jira://{project_key}/{issue_key}" }
```

## 3. The three primitives

| Primitive | Produces | Use when |
|-----------|----------|----------|
| `verb_table` | operation | the verb is a token in a parsed argument (CLI-style) |
| `pattern_map` | tier | the tier follows from a pattern in an argument |
| `resolver` | tier | the tier requires a live lookup (CMDB, tag store) |

Plus two literals — `operation:` and `target:` (a template with `{arg}` /
`{capture}` substitution).

### 3.1 `verb_table` (operation)

A token → operation map applied to a parsed command. **The result is the MAX
operation over every matched token**, so a compound command
(`get pods && delete pod x`) classifies as the most dangerous thing it contains.
Unmatched → the rule's `default` (fail-closed).

### 3.2 `pattern_map` (tier)

An ordered list of `regex on an argument → tier`. First match wins; if several
could apply, the most sensitive tier is taken. Falls back to `default`.

### 3.3 `resolver` (tier, live data)

A named hook declared in the pack and implemented once in the deployment:

```python
from rmacd.classification import register_resolver

@register_resolver("jira_project_tier")
def jira_project_tier(value: str, ctx) -> str:
    return cmdb.tier_for_project(value)   # "internal" | "confidential" | …
```

The engine guarantees fail-closed behavior: if the resolver raises or times out,
the pack's `fail_closed_default` is used, and the resolved value is recorded in
the audit record so the decision stays reconstructable. Write **one resolver per
concept**, not one per tool.

## 4. Worked example — the `jira` pack

Jira is an MCP server, so this is an MCP-style pack. The same shape applies to
`confluence` (they ship from the same Atlassian MCP server).

```yaml
pack: jira
version: 1.0.0
description: RMACD classification for the Jira MCP server
default_operation: C            # unknown future tool → treat as risky

provenance:
  authored_by: platform-sec@acme
  llm_assisted: true
  reviewed_by: jdoe@acme
  source_hash: sha256:…
content_hash: sha256:…
signature: …

resolvers:
  - name: jira_project_tier
    description: Resolve a Jira project key to its data classification
    fail_closed_default: confidential

rules:
  - id: jira-read
    when: { tool: ["jira_search", "jira_get_*", "jira_list_*"] }
    classify:
      operation: R
      tier: { resolver: jira_project_tier, from: project_key, default: internal }
      target: "jira://{project_key}/{issue_key}"
    confidence: high

  - id: jira-add
    when: { tool: ["jira_create_issue", "jira_add_comment", "jira_add_attachment"] }
    classify:
      operation: A
      tier: { resolver: jira_project_tier, from: project_key, default: internal }
      target: "jira://{project_key}"
    confidence: high

  - id: jira-move
    when: { tool: jira_move_issue }
    classify:
      operation: M
      tier: { resolver: jira_project_tier, from: target_project_key, default: internal }
      target: "jira://{issue_key}->{target_project_key}"
    confidence: high

  - id: jira-change
    when: { tool: ["jira_update_issue", "jira_transition_issue", "jira_assign_issue"] }
    classify:
      operation: C
      tier:
        pattern_map:
          - { arg_regex: { arg: project_key, pattern: "^(SEC|HR|LEGAL)$" }, tier: confidential }
        resolver: jira_project_tier
        from: project_key
        default: internal
      target: "jira://{project_key}/{issue_key}"
    confidence: high

  - id: jira-delete
    when: { tool: jira_delete_issue }
    classify:
      operation: D
      tier: { resolver: jira_project_tier, from: project_key, default: confidential }
      target: "jira://{project_key}/{issue_key}"
    confidence: high
```

### How a call flows

`jira_delete_issue(project_key="SEC", issue_key="SEC-42")`:

1. `jira-delete` matches → operation **Delete**; the `jira_project_tier` resolver
   returns **restricted** for `SEC`; target `jira://SEC/SEC-42`.
2. The evaluator sees Delete on restricted → the §12.5 immutable floor →
   **hard denied** (no exception possible).

`jira_search(project_key="ENG")` → Read on internal → allowed and logged. Same
pack, opposite outcomes, no hand-written classifier code.

## 5. Passthrough tools (mandatory treatment)

A tool that executes arbitrary commands, SQL, or APIs has no fixed operation —
its risk lives in the argument. Examples: a shell tool, a SQL `query` tool, the
AWS API MCP server, the Google Cloud DB toolbox, Azure CLI generation.

Required treatment:

1. **Arg-aware operation.** Use a `verb_table` over the action/verb in the
   argument (e.g. SQL `DROP`/`DELETE`/`TRUNCATE` → D; `UPDATE`/`INSERT` → C;
   `SELECT` → R). Never assign a flat literal operation.
2. **Worst-case capability ceiling.** Cap the tool at the most destructive
   operation it could perform, so an over-broad profile cannot be exploited
   through it.
3. **Fail-closed default.** Unrecognized input classifies at the pack default
   (typically C).
4. **Human review.** The AI-compile workflow flags every passthrough tool;
   review each one explicitly before signing.

## 6. Validate, review, sign

```bash
rmacd pack validate jira.yaml          # schema + ReDoS/lint checks
rmacd classify <mcp-server> -o draft.yaml   # AI-compile a first draft
rmacd pack review draft.yaml           # inspect low-confidence + passthrough tail
rmacd pack sign jira.yaml              # freeze: content_hash + ed25519 signature
rmacd pack verify jira.yaml            # confirm signature/trust before production use
rmacd pack diff jira.yaml <mcp-server> # detect drift when the tool surface changes
```

Once signed, a pack is immutable; a change is a new version (`name@version`).
Use `pack diff` periodically (or in CI) to catch tools whose definitions have
changed and re-review only those.

## 7. Checklist for a good pack

- [ ] Correct style chosen (CLI-style `verb_table` vs MCP-style name match).
- [ ] `default_operation` set to a safe (high) value.
- [ ] Every passthrough tool classified arg-aware with a worst-case ceiling.
- [ ] Tiers default to the most sensitive plausible value, not the least.
- [ ] Resolvers declared with a `fail_closed_default`; one resolver per concept.
- [ ] Golden fixtures cover the riskiest calls (every Delete/Change path).
- [ ] Validated, reviewed, and signed before production use.
