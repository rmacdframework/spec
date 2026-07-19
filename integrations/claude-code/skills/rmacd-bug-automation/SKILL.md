---
name: rmacd-bug-automation
description: This skill should be used when the user asks to "set up bug automation", "auto-fix bugs from GitHub issues", "Claude bug triage workflow", "auto-create a PR from an issue", "wire claude-code-action for issues", "label-gated bug fixing", "have Claude triage my bug reports", or wants GitHub Actions that analyze bug reports and open fix PRs with a human approval gate. Also trigger on mentions of the claude-fix label, claude-bug-triage.yml, CLAUDE_CODE_OAUTH_TOKEN, claude setup-token for CI, or the /rmacd:bug-setup command.
---

# Label-gated bug triage and auto-fix with claude-code-action

Set up (or explain) a three-file GitHub automation in which Claude triages incoming bug
reports automatically, but only attempts a fix — and only opens a PR — after a human
maintainer explicitly authorizes it with a label. The flow is a worked example of RMACD
autonomy levels applied to CI: triage is read-only (autonomous), fixing is
**Approval**-gated (a human must act before and after).

## The three files

Copy these from this skill's `examples/` directory (see "Parameterization" below):

1. `.github/ISSUE_TEMPLATE/bug_report.yml` — a GitHub issue **form** that collects
   description, expected/actual behavior, repro steps, SDK version, component, profile
   shape, and logs, and auto-applies the `bug` label.
2. `.github/workflows/claude-bug-triage.yml` — one workflow, two jobs on
   `issues: [labeled]`:
   - **triage** (`label == 'bug'`): read-only tools; posts one comment citing root cause
     as module + file:line, severity, suggested fix, and the next step.
   - **fix** (`label == 'claude-fix'` **and** `sender.login == OWNER_LOGIN`): creates
     branch `fix/issue-N`, implements the smallest fix plus a regression test, runs the
     full test suite as a hard gate, opens a PR that links the issue, and adds the owner
     as reviewer.
3. `.github/workflows/claude-pr-review.yml` — auto-reviews any PR whose head branch
   matches `fix/**` with review-only tools and inline comments. It never approves.

## The label-gated flow, end to end

1. A user files the bug form → `bug` label → triage job runs (read-only) → root-cause
   comment appears on the issue.
2. The maintainer reads the comment in the GitHub notification email. If a fix attempt
   is warranted, they apply the `claude-fix` label — one click, and the only human
   action needed to authorize.
3. The fix job runs: branch `fix/issue-N`, fix + regression test, full test suite must
   pass (no PR is opened on a red suite — Claude comments on the issue instead), PR
   opened with `Fixes #N` and an "RMACD governance" section, owner added as reviewer.
4. The review request emails the owner — **that email is the approval gate**. In RMACD
   terms the automation operates at the **Approval** autonomy level: the change exists
   but is inert until a human reviews and merges. Claude never merges, approves, or
   enables auto-merge.
5. The PR-review workflow independently reviews the diff (correctness, regression-test
   quality, scope, governance invariants) before the human looks at it.

## Security posture (assume a public repo)

Preserve every one of these when scaffolding or editing the workflows:

- **No raw interpolation of attacker-controlled text.** Never put
  `${{ github.event.issue.title }}`, `.body`, or PR title/body into `prompt:` or `run:`.
  Only the issue/PR **number**, repo slug, **label name**, **sender login**, and the
  `author_association` enum may appear in expressions. Claude reads the content itself
  via `gh issue view` / `gh pr diff`, with prompt instructions to treat it as untrusted
  data and refuse embedded instructions.
- **Label gating over author gating.** Triage runs for anyone (read-only, cost-bounded);
  the fix job requires the `claude-fix` label *added by the owner*
  (`github.event.sender.login` guard), so a drive-by attacker can neither trigger writes
  nor self-authorize. `author_association` is passed to the triage prompt as context.
- **Least-privilege tools.** Triage/review get `Read,Glob,Grep` plus narrowly-scoped
  `Bash(gh …:*)` patterns; only the fix job gets `Write,Edit,Bash(git:*)`,
  `Bash(gh pr create:*)` and the exact test command. Never grant blanket `Bash(gh:*)`
  or unscoped `Bash`.
- **Least-privilege permissions.** Triage and review: `contents: read`. Fix only:
  `contents: write, pull-requests: write, issues: write`.
- **Cost bounds.** Every job sets `timeout-minutes` and `--max-turns`; runs consume the
  owner's Claude subscription usage.

## Parameterization

The templates in `examples/` differ from a live deployment only in placeholders:

- `OWNER_LOGIN` — the GitHub login allowed to trigger fixes and assigned as PR reviewer
  (2 occurrences in `claude-bug-triage.yml`).
- `TEST_COMMAND` — the full test-suite command, e.g.
  `cd sdk/python && python -m pytest tests/ --no-cov` (2 occurrences: the prompt's
  quality gate and the matching `Bash(TEST_COMMAND:*)` allowed-tool entry — keep the two
  identical or the gate cannot run).
- `INSTALL_COMMAND` — the dependency-install step that must succeed before the test
  command can, e.g. `pip install -e "sdk/python[dev]"` (1 occurrence).

Also adapt `bug_report.yml`'s component dropdown to the target repo's modules. No
default-branch placeholder is needed: the fix job branches from the checkout HEAD and
`gh pr create` targets the default branch by default.

## One-time repo setup

After scaffolding, walk the owner through (details and sources in
`references/claude-code-action.md`):

1. `claude setup-token` locally (Pro/Max subscription) → copy the OAuth token.
2. `gh secret set CLAUDE_CODE_OAUTH_TOKEN` in the target repo. The token expires;
   regenerate it periodically.
3. Install the Claude GitHub App (https://github.com/apps/claude) on the repo.
4. Repo Settings → Actions → General → enable "Allow GitHub Actions to create and
   approve pull requests".
5. `gh label create claude-fix` (the `bug` label ships with GitHub by default).
6. Test: open a dummy bug issue, watch the triage run, then apply `claude-fix` and
   confirm the PR + review-request email arrive. Close the dummy issue and PR.

## Troubleshooting

- **Branch push or PR creation fails silently** → missing `contents: write` /
  `pull-requests: write`, or the "create and approve pull requests" setting is off.
- **Auth error at job start** → `CLAUDE_CODE_OAUTH_TOKEN` missing or expired; rerun
  `claude setup-token` and reset the secret.
- **Fix PR opened but the review workflow never ran** → GitHub suppresses workflows
  triggered by a workflow's own `GITHUB_TOKEN`; push to the branch or close/reopen the
  PR.
- **Fix job skipped after labeling** → the label was added by someone other than
  `OWNER_LOGIN`, or the label name is misspelled (`claude-fix`, exact).

## Resources

- `examples/bug_report.yml`, `examples/claude-bug-triage.yml`,
  `examples/claude-pr-review.yml` — working templates (placeholders as above).
- `references/claude-code-action.md` — verified claude-code-action v1 facts (inputs,
  auth, permissions, tool syntax, modes) with source URLs. Consult it before changing
  any `with:` or `claude_args:` block; do not use beta-era inputs (`direct_prompt`,
  `custom_instructions`, `mode` are gone in v1).
- The `/rmacd:bug-setup` command automates this scaffold end to end.
