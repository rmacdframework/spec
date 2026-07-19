# End-to-end tests (live Claude Code sessions)

`uat.sh` runs real headless Claude Code sessions with an RMACD profile bound and
asserts governance outcomes. Primary assertions are **filesystem truth** (a denied
`rm -rf` leaves the file in place; an approval-gated `git commit` never lands);
transcript greps are secondary corroboration, because model-mediated output wording
can vary.

Scenarios: project-file profile binding + `/rmacd:status`; Read allowed; Delete
denied; Change routed to human approval (headless ⇒ not executed); unbound session
completely untouched.

## Usage

```bash
./tests-e2e/uat.sh                # local dev: plugin from this checkout (--plugin-dir)
./tests-e2e/uat.sh --marketplace  # canary: real marketplace add + install (auto-cleanup;
                                  #   refuses if the marketplace is already registered)
./tests-e2e/uat.sh --sdk-local    # SDK from this checkout instead of PyPI (pre-release)
./tests-e2e/uat.sh --keep         # keep the temp workspace for debugging
```

Requirements: `claude` CLI (logged in, or `CLAUDE_CODE_OAUTH_TOKEN` set), python3,
git. Each run spawns 3 model sessions (~2–4 minutes, small usage cost).

## CI

`.github/workflows/canary-e2e.yml` runs `--marketplace` mode nightly on a clean
runner against the published PyPI wheel and the live marketplace — guarding the
surfaces the unit suite cannot (packaging, install path, and weekly Claude Code
releases changing hook/plugin behavior). It skips with a notice until the
`CLAUDE_CODE_OAUTH_TOKEN` repo secret is configured.
