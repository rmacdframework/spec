---
description: Scaffold label-gated Claude bug triage, auto-fix, and PR-review automation for this repo
---

Set up label-gated bug automation for this repository: Claude triages every `bug` issue
automatically, attempts a fix only when the owner applies the `claude-fix` label, and
auto-reviews the resulting `fix/**` PRs. Work through the steps below in order. Consult
the `rmacd-bug-automation` skill (its `examples/` are the templates, and
`references/claude-code-action.md` holds the verified action facts); do not invent
claude-code-action inputs that are not documented there.

## 1. Preflight

- Confirm this is a git repo with a GitHub remote and that `gh` is authenticated
  (`gh auth status`).
- Detect the parameters:
  ```bash
  gh repo view --json owner,defaultBranchRef,visibility \
    --jq '{owner: .owner.login, branch: .defaultBranchRef.name, visibility}'
  ```
- If the repo is public, tell the user the workflows are designed for that (injection
  posture matters most there); private repos work identically.
- Warn if `.github/workflows/` or `.github/ISSUE_TEMPLATE/bug_report.yml` already has
  files these steps would overwrite — never clobber silently.

## 2. Gather the parameters

Use AskUserQuestion (pre-filling detected defaults) for:

1. **Owner login** (`OWNER_LOGIN`) — the GitHub login that authorizes fixes by applying
   the `claude-fix` label and receives the PR review request. Default: the detected
   repo owner.
2. **Test command** (`TEST_COMMAND`) — the single command that runs the full test suite
   from the repo root, e.g. `cd sdk/python && python -m pytest tests/ --no-cov` or
   `npm test`. Inspect the repo (pyproject/package.json/Makefile/CI workflow) to
   propose a default.
3. **Install command** (`INSTALL_COMMAND`) — what must run first so the test command
   works on a bare `ubuntu-latest` runner, e.g. `pip install -e ".[dev]"` or `npm ci`.
4. **Component list** — the modules for the issue form's Component dropdown. Propose one
   from the repo's top-level packages/directories; keep `other` as the last option.

The default branch needs no substitution: the fix job branches from the checkout HEAD
and `gh pr create` targets the default branch automatically.

## 3. Scaffold the three files

Copy from the `rmacd-bug-automation` skill's `examples/` into the repo, substituting:

- `.github/ISSUE_TEMPLATE/bug_report.yml` ← `examples/bug_report.yml`, with the
  Component dropdown options replaced by the user's component list (keep the RMACD
  profile-shape dropdown only if the repo uses RMACD profiles; otherwise drop that
  field). If the repo has no `.github/ISSUE_TEMPLATE/config.yml`, offer to add one
  (`blank_issues_enabled: true` plus a Discussions contact link).
- `.github/workflows/claude-bug-triage.yml` ← `examples/claude-bug-triage.yml`, with
  `OWNER_LOGIN` (2 occurrences), `TEST_COMMAND` (2 occurrences — prompt and the
  `Bash(TEST_COMMAND:*)` allowed-tool entry must stay identical), and
  `INSTALL_COMMAND` (1 occurrence) substituted.
- `.github/workflows/claude-pr-review.yml` ← `examples/claude-pr-review.yml`, verbatim.

Then validate: parse each file with Python (`python3 -c "import yaml, sys;
yaml.safe_load(open(sys.argv[1]))" <file>`), and confirm no `${{ github.event.* }}`
expression in the workflows interpolates an issue/PR title or body — only numbers, the
repo slug, label names, sender login, and `author_association` are acceptable.

## 4. One-time repo setup (requires the user)

Walk the user through, in this order:

1. **Token** — run locally (requires a Claude Pro/Max subscription):
   ```bash
   claude setup-token
   ```
2. **Secret** — store it in the repo:
   ```bash
   gh secret set CLAUDE_CODE_OAUTH_TOKEN
   ```
   Note: the token expires; it must be regenerated and reset periodically.
3. **GitHub App** — install https://github.com/apps/claude on this repository.
4. **Actions setting** — repo Settings → Actions → General → enable "Allow GitHub
   Actions to create and approve pull requests" (without it, PR creation fails
   silently).
5. **Label** — create the fix-authorization label:
   ```bash
   gh label create claude-fix --color 5319E7 \
     --description "Authorize Claude to attempt an automated fix PR"
   ```

## 5. Commit and push

Show the user the three files, then commit them together with a message like
`Add Claude bug triage/fix/review automation` and push to the default branch (workflows
only trigger once they exist on the default branch).

## 6. Test run

1. Open a dummy issue:
   ```bash
   gh issue create --title "[Bug]: dummy triage test" --label bug \
     --body "Testing the triage workflow. Expected: triage comment. Actual: n/a."
   ```
2. Watch the triage job (`gh run list --workflow claude-bug-triage.yml`, then
   `gh run watch <id>`) and confirm a root-cause comment appears on the issue.
3. Optionally have the user apply `claude-fix` (must be applied by `OWNER_LOGIN`) and
   confirm: branch `fix/issue-N`, a PR linking the issue, the review-request email, and
   a Claude review on the PR.
4. Clean up: close the dummy issue and PR, delete the `fix/issue-N` branch.
