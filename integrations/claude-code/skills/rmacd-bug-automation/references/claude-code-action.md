# claude-code-action v1 — verified facts

Verified against the claude-code-action v1 GA docs and `action.yml` on 2026-07-19.
Re-verify against the source URLs below before relying on anything not listed here.

## Action and inputs

- Action: `anthropics/claude-code-action@v1`.
- v1 input names: `prompt`, `claude_args`, `track_progress`.
- Beta-era inputs are **gone** in v1 — do not use `direct_prompt`,
  `custom_instructions`, or `mode`.
- Modes: a `prompt:` input present → **automation mode** (event/schedule driven, no
  mention needed). `prompt:` absent → interactive @claude-mention mode. Use automation
  mode for issue triage and fixes; either works for review.

## Authentication

- Subscription auth: input `claude_code_oauth_token`, fed from secret
  `CLAUDE_CODE_OAUTH_TOKEN`, generated locally with `claude setup-token` (requires a
  Pro/Max subscription). The token **expires** — regenerate periodically; there is no
  documented refresh flow.
- API-key alternative: `ANTHROPIC_API_KEY`.
- Runs consume the owner's subscription usage — bound every job with `timeout-minutes`
  and `--max-turns`.

## Repository prerequisites

- Install the Claude GitHub App: https://github.com/apps/claude
- Enable Settings → Actions → General → "Allow GitHub Actions to create and approve
  pull requests".
- Workflow permissions: `contents: write`, `pull-requests: write`, `issues: write` for
  jobs that push branches or open PRs. A review-only job can drop to `contents: read`.
  Missing permissions cause **silent** branch-push failures.

## Tools and PR creation

- Constrain tools via `claude_args: --allowedTools "..."` — comma-separated; MCP tools
  as `mcp__<namespace>__<tool>`; Bash patterns as `Bash(prefix:*)`.
- Review-only set: `mcp__github_inline_comment__create_inline_comment,Read,Glob,Grep`
  plus narrowly-scoped `Bash(gh …:*)` entries.
- Fix set: `Bash(gh pr create:*),Write,Edit,Bash(git:*),Read,Glob,Grep` plus the exact
  test-runner command.
- The action opens PRs itself via `Bash(gh pr create:*)` when allowed.

## Injection mitigation (public repos)

- Never interpolate `${{ github.event.issue.body }}` (or title, or PR body/title) into
  `prompt:` or `run:`. Have Claude read the issue via `gh issue view` and treat the
  content as untrusted data.
- Gate write-capable jobs on a maintainer-applied label (recommended: auto-triage on
  `bug`, fix only on `claude-fix` added by the owner — checked via
  `github.event.sender.login`), and/or on `github.event.issue.author_association` in
  OWNER/MEMBER/COLLABORATOR.

## Source URLs

- https://github.com/anthropics/claude-code-action
- https://github.com/anthropics/claude-code-action/blob/main/action.yml
- https://github.com/anthropics/claude-code-action/blob/main/docs/setup.md
- https://github.com/anthropics/claude-code-action/blob/main/docs/solutions.md
- https://github.com/anthropics/claude-code-action/blob/main/docs/security.md
- https://github.com/anthropics/claude-code-action/blob/main/docs/migration-guide.md
- https://code.claude.com/docs/en/github-actions.md
