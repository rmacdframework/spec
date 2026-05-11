"""CLI ApprovalGateway — prompts the operator on stdout / stdin.

Implements the ``ApprovalGateway`` protocol from ``rmacd.approval``. When the
enforcer routes an approval-gated operation through this gateway, the human
running the demo sees a formatted request and types ``y`` / ``n`` (with an
optional note) on the terminal.

Why ship this with the example rather than in the SDK proper: the CLI is one
of many possible approval surfaces (the SDK includes the protocol and the
``RejectAllApprovalGateway`` / ``AutoApproveGateway`` reference impls). Real
deployments will route to ServiceNow, Slack, PagerDuty, or a custom webhook;
the CLI is here purely because the demo runs interactively in a terminal.
"""

from __future__ import annotations

import sys
import threading
from datetime import datetime, timezone

from rmacd.approval import ApprovalDecision, ApprovalOutcome, ApprovalRequest


_PROMPT_LOCK = threading.Lock()


class CLIApprovalGateway:
    """Prompt the local operator for an approval decision.

    The prompt is wrapped in a process-wide lock so concurrent tool calls
    from the agent don't interleave their prompts on the terminal. (Claude's
    tool use is serial in practice, but the lock costs nothing and makes the
    component reusable for multi-agent demos.)
    """

    def __init__(self, approver_name: str = "local-operator") -> None:
        self.approver_name = approver_name

    def request(self, req: ApprovalRequest) -> ApprovalDecision:
        with _PROMPT_LOCK:
            self._render(req)
            answer, note = self._read_response()

        outcome = ApprovalOutcome.APPROVED if answer else ApprovalOutcome.DENIED
        return ApprovalDecision(
            request_id=req.request_id,
            outcome=outcome,
            approver=self.approver_name if answer else self.approver_name,
            decided_at=datetime.now(timezone.utc),
            note=note or None,
        )

    @staticmethod
    def _render(req: ApprovalRequest) -> None:
        bar = "─" * 72
        print(f"\n{bar}", file=sys.stderr)
        print(f"  APPROVAL REQUIRED  ({req.autonomy_level.value})", file=sys.stderr)
        print(bar, file=sys.stderr)
        print(f"  Request:   {req.request_id}", file=sys.stderr)
        print(f"  Agent:     {req.agent_id}", file=sys.stderr)
        print(f"  Profile:   {req.profile_id}", file=sys.stderr)
        print(f"  Operation: {req.operation.value}  ({_op_name(req.operation.value)})", file=sys.stderr)
        print(f"  Target:    {req.target}", file=sys.stderr)
        if req.classification:
            print(f"  Data tier: {req.classification.value}", file=sys.stderr)
        if req.justification:
            print(f"  Reason:    {req.justification}", file=sys.stderr)
        print(bar, file=sys.stderr)

    @staticmethod
    def _read_response() -> tuple[bool, str]:
        try:
            raw = input("  Approve? [y/N] (optional note after a space): ").strip()
        except EOFError:
            return False, "no stdin available"
        if not raw:
            return False, ""
        # Allow "y reason", "yes", "n", "no comment" etc.
        first, _, rest = raw.partition(" ")
        approved = first.lower() in {"y", "yes"}
        return approved, rest.strip()


def _op_name(code: str) -> str:
    return {
        "R": "Read",
        "M": "Move",
        "A": "Add",
        "C": "Change",
        "D": "Delete",
    }.get(code, code)
