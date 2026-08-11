"""Claude Code PreToolUse hook: stdin JSON event in, hook JSON decision out.

Invoked as ``python3 -m rmacd.claude_code.hook`` by the plugin's
``hooks/hooks.json`` (PreToolUse, matcher ``"*"``). The process is short-lived:
read one event, bind the session, decide, print, exit 0.

Decision output contract (normative, c2 spec):

- allow → ``{"hookSpecificOutput": {"hookEventName": "PreToolUse",
  "permissionDecision": "allow"}}``
- deny → ``permissionDecision: "deny"`` with a ``permissionDecisionReason``
  that cites the operation, tier, rule, and profile id.
- approval-level autonomy (``approval`` / ``elevated_approval``) →
  ``permissionDecision: "ask"`` — Claude Code's own permission prompt becomes
  the human-in-the-loop step. No ``ApprovalGateway`` is invoked in the hook
  path (there is no interactive stdin in a hook process); the decision is
  computed side-effect-free via ``evaluate_only``.

Fail modes (normative):

- **Unbound** (no profile configured) → passthrough: the hook prints *no*
  decision and exits 0, so Claude Code's own permission flow proceeds
  unchanged, plus a one-time stderr notice per session. Emitting
  ``permissionDecision: "allow"`` here would be wrong — it would suppress
  Claude Code's own prompts and auto-approve everything, turning "not
  configured" into "wide open". The notice cannot corrupt the decision
  protocol, which reads stdout only — but do not assume it is *invisible*:
  since 2026-07-31 Claude Code emits ``{"type": "system", "subtype":
  "hook_response", ...}`` events carrying hook ``stderr`` verbatim under
  ``--output-format stream-json``, where it was previously ``--debug``-only.
  Assume only that stderr stays off the stdout channel.
- **Bound but broken/erroring** → fail closed: deny with a diagnostic reason.
  This covers binding failures (bad profile/pack/map), malformed stdin, and
  any unexpected exception while deciding.
- **Unknown MCP/unmapped tool** → deny by default; ``RMACD_UNKNOWN_TOOL=ask``
  downgrades to Claude Code's own prompt.

Always exits 0: decisions travel in the stdout JSON, never in exit codes
(exit 2 would make Claude Code treat raw stderr as a blocking error, which is
a cruder channel than a structured deny reason).
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import tempfile
from typing import Any, TextIO

from rmacd.audit import compliance_tags_for
from rmacd.claude_code import handoff, mapping, session
from rmacd.claude_code.audit import SessionAuditor, resolve_audit_path, session_context
from rmacd.evaluator import IMMUTABLE_PROHIBITIONS
from rmacd.models import AutonomyLevel, DataClassification, Operation, PolicyDecision

HOOK_EVENT = "PreToolUse"

_UNBOUND_NOTICE = (
    "RMACD: installed but unbound — no profile at .claude/rmacd-profile.json and "
    "RMACD_PROFILE_PATH is not set; tool calls pass through ungoverned. "
    "Run /rmacd:init to create a profile, /rmacd:status for details."
)


def _output(decision: str, reason: str | None = None) -> dict[str, Any]:
    hook_output: dict[str, Any] = {
        "hookEventName": HOOK_EVENT,
        "permissionDecision": decision,
    }
    if reason is not None:
        hook_output["permissionDecisionReason"] = reason
    return {"hookSpecificOutput": hook_output}


def _allow() -> dict[str, Any]:
    return _output("allow")


def _deny(reason: str) -> dict[str, Any]:
    return _output("deny", reason)


def _ask(reason: str) -> dict[str, Any]:
    return _output("ask", reason)


def _tier_label(tier: DataClassification | None) -> str:
    return tier.value if tier is not None else "unclassified"


def _describe(operation: Operation, tier: DataClassification | None, target: str) -> str:
    return f"{mapping.OP_WORDS[operation]} on {_tier_label(tier)} target '{target}'"


def _decision_reason_suffix(rule: str, profile_id: str) -> str:
    return f" Rule: {rule}. Profile: {profile_id}."


def _map_denied_decision(
    decision: PolicyDecision,
    operation: Operation,
    tier: DataClassification | None,
    target: str,
    rule: str,
    binding: session.SessionBinding,
) -> dict[str, Any]:
    described = _describe(operation, tier, target)
    # §12.5 immutable floor first: even when the proximate cause is a profile
    # permission gap, Change/Delete/Add on Restricted is a hard safety
    # boundary that no exception process can lift — say so explicitly.
    if tier is not None and (tier, operation) in IMMUTABLE_PROHIBITIONS:
        return _deny(
            f"RMACD: {described} is prohibited (§12.5 immutable floor — cannot be "
            f"granted by exception; human execution only). Profile: {binding.profile_id}."
        )
    if "constraints" in decision.constraints_applied:
        return _deny(
            f"RMACD: {described} blocked by an operational constraint: "
            f"{decision.blocked_reason or 'constraint check failed'}."
            + _decision_reason_suffix("profile constraints (env/time-window)", binding.profile_id)
        )
    detail = decision.blocked_reason or "not permitted"
    return _deny(
        f"RMACD: {described} denied — {detail}."
        + _decision_reason_suffix(rule, binding.profile_id)
    )


def decide(
    event: dict[str, Any],
    binding: session.SessionBinding,
    auditor: SessionAuditor | None = None,
) -> dict[str, Any]:
    """Produce the hook output for one PreToolUse event under a bound profile.

    Never raises for policy outcomes; unexpected exceptions are the caller's
    signal to fail closed.

    When ``auditor`` is supplied, **every** return path below records a decision
    first. Auditing at the decision point rather than after execution is
    deliberate: a denied call never runs, so it never reaches ``PostToolUse`` —
    a trail built only from executions would omit exactly the denials that
    constitute the evidence.
    """
    tool_name = str(event.get("tool_name") or "")
    raw_input = event.get("tool_input")
    tool_input: dict[str, Any] = raw_input if isinstance(raw_input, dict) else {}
    context = session_context(event)

    def _record(
        result: str,
        operation: Operation,
        target: str,
        tier: DataClassification | None,
        decision: PolicyDecision | None = None,
        blocked_reason: str | None = None,
        autonomy_level: AutonomyLevel | None = None,
    ) -> None:
        if auditor is None:
            return
        auditor.decision(
            agent_id=binding.agent_id,
            profile_id=binding.profile_id,
            operation=operation,
            target=target,
            classification=tier,
            decision=decision,
            result=result,
            blocked_reason=blocked_reason,
            context=context,
        )
        if not auditor.enabled or result not in ("ALLOW", "QUEUED"):
            # A denied call never runs, so it will never reach PostToolUse and
            # needs nothing handed forward. QUEUED does: the user may approve it.
            return
        level = autonomy_level or (
            decision.autonomy_level if decision is not None else AutonomyLevel.APPROVAL
        )
        handoff.store(
            event.get("session_id"),
            event.get("tool_use_id"),
            {
                "v": 1,
                "audit_path": str(auditor.path),
                "agent_id": binding.agent_id,
                "profile_id": binding.profile_id,
                "operation": operation.value,
                "target": target,
                "classification": tier.value if tier is not None else None,
                "autonomy_level": level.value,
                "compliance_tags": compliance_tags_for(binding.profile),
                "requires_approval": bool(
                    decision.requires_approval if decision is not None else result == "QUEUED"
                ),
            },
        )

    try:
        call = mapping.map_tool_call(tool_name, tool_input, binding)
    except mapping.UnknownToolError as exc:
        reason = (
            f"RMACD: {exc.detail}. Unknown tools fail closed while a profile is bound "
            f"(override with RMACD_UNKNOWN_TOOL=ask). Profile: {binding.profile_id}."
        )
        # An unmapped tool has no operation; record it at the most severe so a
        # reader cannot mistake "we could not classify this" for "it was a read".
        if binding.unknown_tool_decision == "ask":
            _record("QUEUED", Operation.DELETE, tool_name, None, blocked_reason=exc.detail)
            return _ask(
                f"RMACD: {exc.detail}. RMACD_UNKNOWN_TOOL=ask routes this to your "
                f"approval. Profile: {binding.profile_id}."
            )
        _record("DENY", Operation.DELETE, tool_name, None, blocked_reason=exc.detail)
        return _deny(reason)
    except mapping.CapabilityCeilingError as exc:
        _record("DENY", exc.operation, tool_name, exc.tier, blocked_reason=str(exc))
        return _deny(
            f"RMACD: {_describe(exc.operation, exc.tier, tool_name)} denied — {exc}."
            + _decision_reason_suffix("tool capability ceiling", binding.profile_id)
        )

    # 3D and DC2D evaluation requires a tier; unmapped targets take the
    # session default (RMACD_DEFAULT_TIER, 'internal' unless overridden).
    # 2D profiles have no classification program — keep whatever the map said
    # (possibly None) so §12.5 still applies to explicitly-mapped targets.
    tier = call.tier
    if tier is None and not binding.is_2d:
        tier = binding.default_tier

    # The decision itself stays side-effect-free: no approval gateway. The hook
    # process cannot host an interactive gateway; approval-level autonomy
    # becomes Claude Code's own "ask" prompt below. The audit write that follows
    # is an append to the session's own sink and never affects the outcome.
    decision = binding.enforcer.evaluate_only(call.operation, call.target, tier)

    if not decision.allowed:
        _record("DENY", call.operation, call.target, tier, decision)
        return _map_denied_decision(decision, call.operation, tier, call.target, call.rule, binding)

    # DC2D data-flow gate: outbound destinations (WebFetch/WebSearch) must
    # clear the profile's egress_controls before the read is allowed.
    if call.egress_destination is not None and binding.is_dc2d:
        egress = binding.enforcer.check_egress(
            tier if tier is not None else binding.default_tier, call.egress_destination
        )
        if not egress.allowed:
            egress_reason = (
                f"egress to '{call.egress_destination}' blocked: "
                f"{egress.reason or 'egress_controls'}"
            )
            _record(
                "DENY", call.operation, call.target, tier, blocked_reason=egress_reason
            )
            return _deny(
                f"RMACD: {_describe(call.operation, tier, call.target)} denied — egress to "
                f"'{call.egress_destination}' blocked: {egress.reason or 'egress_controls'}."
                + _decision_reason_suffix(
                    f"egress_controls ({egress.matched_rule or 'rule'})", binding.profile_id
                )
            )

    if decision.requires_approval:
        _record("QUEUED", call.operation, call.target, tier, decision)
        return _ask(
            f"RMACD: {_describe(call.operation, tier, call.target)} requires "
            f"'{decision.autonomy_level.value}' autonomy — approving this prompt is the "
            f"human-in-the-loop step." + _decision_reason_suffix(call.rule, binding.profile_id)
        )

    _record("ALLOW", call.operation, call.target, tier, decision)
    return _allow()


def _notice_marker_path(event: dict[str, Any] | None) -> str:
    session_id = "nosession"
    if event is not None:
        raw = event.get("session_id")
        if isinstance(raw, str) and raw:
            session_id = "".join(ch for ch in raw if ch.isalnum() or ch in "-_")[:64]
    return os.path.join(tempfile.gettempdir(), f"rmacd-claude-code-unbound-{session_id}")


def _emit_unbound_notice_once(event: dict[str, Any] | None, stderr: TextIO) -> None:
    """Say it once per session, using the marker's creation as the lock.

    ``O_EXCL`` makes "has this session been told?" and "record that it has" one
    atomic step, so concurrent tool calls cannot both slip past a separate
    existence check. ``O_NOFOLLOW`` matters because the marker lives in a shared
    temp directory: without it a symlink planted at this path would redirect the
    write to whatever file the user can write.

    Suppression is closed as well as redirection. Our own marker is always a
    regular file, so anything else occupying the path is not ours and must not
    be allowed to silence the notice — a repeated notice is a nuisance, a
    silently ungoverned session is the failure this exists to prevent.
    """
    marker = _notice_marker_path(event)
    try:
        fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        if not os.path.islink(marker):
            return  # our own marker: already announced for this session
        print(_UNBOUND_NOTICE, file=stderr)
        return
    except OSError:
        # Bookkeeping is unavailable (unwritable temp dir, something in the way).
        # Repeating the notice beats withholding it: the point is that nobody
        # discovers an ungoverned session by accident.
        print(_UNBOUND_NOTICE, file=stderr)
        return
    with contextlib.suppress(OSError), os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write("notified\n")
    print(_UNBOUND_NOTICE, file=stderr)


def run(stdin: TextIO, stdout: TextIO, stderr: TextIO) -> int:
    """Read one PreToolUse event, write at most one JSON decision. Exit 0 always."""
    raw = stdin.read()
    event: dict[str, Any] | None
    try:
        parsed = json.loads(raw)
        event = parsed if isinstance(parsed, dict) else None
    except (json.JSONDecodeError, UnicodeDecodeError):
        event = None

    cwd = None
    if event is not None and isinstance(event.get("cwd"), str):
        cwd = event["cwd"]
    if cwd is None:
        cwd = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()

    try:
        binding = session.bind_session(cwd=cwd)
    except session.SessionBindingError as exc:
        # A profile IS configured but could not be bound: fail closed.
        print(
            json.dumps(
                _deny(
                    f"RMACD: fail-closed — a governance profile is configured for this "
                    f"session but could not be bound: {exc}. Fix the configuration (or "
                    f"unset {session.ENV_PROFILE_PATH} / remove "
                    f"{session.PROJECT_PROFILE_RELPATH}) and retry. Rule: bound-but-broken "
                    f"sessions deny all tool calls."
                )
            ),
            file=stdout,
        )
        return 0

    if binding is None:
        # Unbound: zero-friction passthrough. No stdout output means no
        # permission decision — Claude Code's own flow continues unchanged.
        _emit_unbound_notice_once(event, stderr)
        return 0

    if event is None:
        print(
            json.dumps(
                _deny(
                    f"RMACD: fail-closed — malformed PreToolUse event on stdin while "
                    f"profile '{binding.profile_id}' is bound; refusing the ungoverned "
                    f"call. Rule: bound sessions never pass through on hook errors."
                )
            ),
            file=stdout,
        )
        return 0

    auditor = SessionAuditor(
        resolve_audit_path(binding.profile_path),
        stderr,
        compliance_tags=compliance_tags_for(binding.profile),
    )

    try:
        output = decide(event, binding, auditor)
    except Exception as exc:  # fail closed on any hook/SDK error while bound
        tool_name = event.get("tool_name", "unknown")
        output = _deny(
            f"RMACD: fail-closed — hook error while evaluating tool '{tool_name}': "
            f"{type(exc).__name__}: {exc}. Rule: bound sessions never pass through on "
            f"hook errors. Profile: {binding.profile_id}."
        )
    print(json.dumps(output), file=stdout)
    return 0


def main() -> int:
    return run(sys.stdin, sys.stdout, sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
