# RMACD Validate — GitHub Action

Composite action that validates RMACD permission profiles (and optionally
governance packs) against the official JSON Schemas on every push and pull
request. Profiles are code: this action gives them the same CI gate as any
other artifact in your repository.

Under the hood it installs the [`rmacd-framework`](https://pypi.org/project/rmacd-framework/)
SDK and runs `rmacd validate` on every matched profile, and
`rmacd pack validate` (plus `rmacd pack verify` when signatures are required)
on every matched pack. Any failure exits non-zero and fails the job, with the
schema errors surfaced in grouped log output.

## Quick start

Add `.github/workflows/rmacd-validate.yml` to your repository:

```yaml
name: RMACD Validate

on:
  push:
    branches: [main]
  pull_request:

permissions:
  contents: read

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Validate RMACD profiles
        uses: rmacdframework/spec/integrations/github-action@main
        with:
          profiles: "rmacd/profiles/*.json"
```

## Inputs

| Input | Default | Description |
|---|---|---|
| `profiles` | `**/rmacd*/**/*.json` | Glob(s) of profile JSON files to validate (bash `globstar`; multiple space-separated globs allowed). The default matches any `*.json` under a directory whose name starts with `rmacd` — e.g. `rmacd/profiles/observer-3d.json`. Override it to match your layout (`policies/**/*.json`, `schemas/examples/*.json`, ...). No matches produces a warning, not a failure. |
| `packs` | *(empty)* | Optional glob(s) of governance pack files (`.json`/`.yaml`) to check with `rmacd pack validate`. Empty skips the pack step. |
| `require-signed-packs` | `false` | When `true`, also run `rmacd pack verify` on every matched pack. Requires `pack-public-key`. |
| `pack-public-key` | *(empty)* | Workspace path to the Ed25519 public key PEM used by `rmacd pack verify`. Required when `require-signed-packs` is `true`. |
| `version` | `>=0.13` | pip version specifier for the SDK, appended verbatim (`>=0.13`, `==0.13.0`, ...). |

### Packs example (with signature verification)

```yaml
      - name: Validate RMACD profiles and packs
        uses: rmacdframework/spec/integrations/github-action@main
        with:
          profiles: "rmacd/profiles/*.json"
          packs: "rmacd/packs/*.yaml"
          require-signed-packs: "true"
          pack-public-key: "rmacd/keys/packs-ed25519.pub.pem"
```

The action automatically installs the SDK extras it needs: `[yaml]` when a
`packs` glob is set (YAML pack support) and `[sign]` when
`require-signed-packs` is `true` (Ed25519 verification).

## pre-commit hook

The same validation is available as a [pre-commit](https://pre-commit.com)
hook, so broken profiles never reach CI in the first place. Add to your
`.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/rmacdframework/spec
    rev: main  # pin a tag/SHA in real use
    hooks:
      - id: rmacd-validate
```

The hook's default `files` pattern matches JSON files inside a directory
whose name starts with `rmacd` (the `rmacd/profiles/*.json` layout) as well
as files named `*-2d.json`, `*-3d.json`, or `*-dc2d.json`. Override `files`
in your config if your profiles live elsewhere:

```yaml
      - id: rmacd-validate
        files: ^policies/.*\.json$
```

## Notes

- **Marketplace listing is deferred.** GitHub Marketplace requires
  `action.yml` at the repository root; this action lives at
  `integrations/github-action/` inside the spec repo, so referencing it via
  `uses: rmacdframework/spec/integrations/github-action@main` works, but a
  Marketplace listing would need a dedicated action repository. Pin a tag or
  commit SHA instead of `@main` for reproducible builds.
- **Exit behavior:** any invalid profile or pack fails the step non-zero;
  the `rmacd` CLI prints `INVALID: <file>` plus per-error detail to stderr,
  wrapped in a log group per step (per pack for the packs step).
- **Runner requirements:** `ubuntu-latest`/any runner with bash; Python 3.12
  is provisioned by the action via `actions/setup-python`.
