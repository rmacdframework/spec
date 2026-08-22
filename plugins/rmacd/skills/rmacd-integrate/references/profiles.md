# Authoring RMACD profiles

Condensed authoring guide. Canonical spec: `docs/RMACD_Framework_v1.4.md` in
https://github.com/rmacdframework/spec. Interactive tools:
https://rmacd-framework.org/generator (build a profile) and
https://rmacd-framework.org/validator (check one).

## Shape decision tree

1. Does the org have a working data classification program (PICR tiers or mappable
   equivalent)?
   - **No** → **2D** (operations × autonomy). Simplest; adopt 3D later.
   - **Yes** → continue.
2. Are the agent's *operational* permissions already governed upstream (IAM/RBAC roles,
   DLP), so only data-tier autonomy needs governing?
   - **Yes** → **DC2D** (data classification × autonomy; spec Appendix D). Adds
     redaction and egress controls.
   - **No** → **3D** (operations × data classification × autonomy). The default.

## Example profiles (`schemas/examples/` in the spec repo)

| File | profile_id | Shape | Summary |
|---|---|---|---|
| `observer-2d.json` | `rmacd-2d-observer-v1` | 2D | Read-only, no data classification |
| `operations-2d.json` | `rmacd-2d-operations-v1` | 2D | R/M/A/C, no Delete |
| `observer-3d.json` | `rmacd-3d-observer-v1` | 3D | Read-only across all tiers |
| `monitoring-3d.json` | `rmacd-3d-monitoring-v1` | 3D | Read-only observability/SRE, alerting |
| `devops-3d.json` | `rmacd-3d-devops-v1` | 3D | CI/CD + infra; full on public, R/M on confidential, R on restricted |
| `incident-responder-3d.json` | `rmacd-3d-incident-responder-v1` | 3D | R/M/A with pre-authorized emergency escalation |
| `administrator-3d.json` | `rmacd-3d-administrator-v1` | 3D | Maximum grants — still no A/C/D on restricted |
| `regulated-data-handler-dc2d.json` | `rmacd-dc2d-regulated-data-handler-v1` | DC2D | Support agent; PII redaction, egress allow-list, restricted tier blocked |

Copy the nearest one and trim; do not start from an empty file.

## Invariants (the validator and runtime both enforce these)

- **§12.5 immutable floor** — Add/Change/Delete on Restricted is prohibited for autonomous
  agents — all three, not just Change and Delete. The profile-3d schema allows only
  `R`/`M` in `permissions.restricted`, and the evaluator applies the same floor at
  runtime regardless of what a profile says. The exception process cannot grant it.
- **Cumulative permissions** — D ⊃ C ⊃ A ⊃ M ⊃ R. Listing `D` for a tier means the
  agent effectively holds every verb there. Grant the lowest verb that does the job.
- **Profile ID patterns** — `^rmacd-2d-[a-z0-9-]+$`, `^rmacd-3d-[a-z0-9-]+$`,
  `^rmacd-dc2d-[a-z0-9-]+$`. Suffix a version (e.g. `-v1`) by convention.
- **PICR tiers** — `public`, `internal`, `confidential`, `restricted` (lowercase in
  JSON). Operations are single letters `R M A C D` (uppercase).
- **Schema `$id` domain** — `https://rmacd-framework.org/schema/v1/profile-{3d,2d,dc2d}.json`.
  Put it in the profile's `$schema` field.

## Autonomy overrides

Defaults come from the built-in matrix (see the table in SKILL.md). Override per cell
with `autonomy_overrides`: 3D keys are `"<tier>.<op>"` (e.g. `"internal.C": "approval"`),
2D keys are operations. Overrides may tighten or loosen within the allowed range but can
never turn a PROHIBITED cell on. DC2D profiles instead set `allowed` + `autonomy` per
tier under `data_access`, plus optional `constraints.redaction` and
`constraints.egress_controls`.

Other useful blocks (see examples): `emergency_escalation` (temporary widened
permissions with triggers, max duration, cooldown, post-incident review) and
`constraints` (environments, rate limits, time windows).

## Check the result

```bash
rmacd validate profiles/agent.json        # schema validation (must print VALID)
rmacd matrix profiles/agent.json          # render the effective autonomy matrix
rmacd info profiles/agent.json            # summary view
rmacd evaluate profiles/agent.json C -c internal      # single-cell decision
```

`rmacd evaluate ... --json` emits the full `PolicyDecision` for scripting;
`--emergency` simulates emergency escalation.

## Keep the model in sync

Generate the agent-facing summary from the same file the runtime enforces, so prompt
and policy cannot drift:

```python
from rmacd import ProfileLoader, build_system_prompt
fragment = build_system_prompt(ProfileLoader().load_file("profiles/agent.json"))
```

The fragment lists granted operations per tier, the per-cell autonomy stance, the hard
prohibitions, and behaviour guidance (prefer the lowest-risk verb, respect denials,
never self-modify the profile). Prepend it to the agent's system prompt.
