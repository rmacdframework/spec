"""Tests for PolicyEnforcer, approval gateways, and audit emission.

These cover the decision-to-action layer added in SDK 0.4.0. The
``PolicyEvaluator`` itself has separate coverage in ``test_evaluator.py``;
the goal here is to verify that the enforcer wraps the evaluator with
the correct side effects (approval routing, audit records, exception
mapping) and surfaces the right exception subclass for each failure
mode.
"""

from __future__ import annotations

import asyncio
import inspect
import io
import json
from pathlib import Path

import pytest

from rmacd import (
    ApprovalDecision,
    ApprovalGateway,
    ApprovalOutcome,
    ApprovalRequest,
    AutoApproveGateway,
    DataClassification,
    JSONLAuditLogger,
    Operation,
    PolicyEnforcer,
    Profile3D,
    ProfileLoader,
    RejectAllApprovalGateway,
    RMACDApprovalDeniedError,
    RMACDApprovalTimeoutError,
    RMACDPermissionDeniedError,
    RMACDProhibitedError,
)

FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "schemas" / "examples"


@pytest.fixture
def admin_profile() -> Profile3D:
    """Administrator profile — broadest permissions, hits the matrix prohibition cases."""
    profile = ProfileLoader().load_file(FIXTURE_DIR / "administrator-3d.json")
    assert isinstance(profile, Profile3D)
    return profile


@pytest.fixture
def observer_profile() -> Profile3D:
    """Observer profile — R only, useful for testing profile-denied paths."""
    profile = ProfileLoader().load_file(FIXTURE_DIR / "observer-3d.json")
    assert isinstance(profile, Profile3D)
    return profile


@pytest.fixture
def buf() -> io.StringIO:
    return io.StringIO()


def make_enforcer(
    profile: Profile3D,
    *,
    gateway: ApprovalGateway | None = None,
    audit_sink: io.StringIO | None = None,
) -> PolicyEnforcer:
    return PolicyEnforcer(
        profile=profile,
        agent_id="test-agent",
        approval_gateway=gateway or AutoApproveGateway(),
        audit_logger=JSONLAuditLogger(audit_sink) if audit_sink else None,
    )


def audit_results(buf: io.StringIO) -> list[str]:
    return [json.loads(line)["policy_decision"]["result"] for line in buf.getvalue().splitlines()]


# ---- ALLOW path ------------------------------------------------------------


def test_autonomous_operation_allowed_and_audited(admin_profile, buf):
    enforcer = make_enforcer(admin_profile, audit_sink=buf)
    decision = enforcer.enforce("R", "doc://public/readme", "public")
    assert decision.allowed
    assert decision.autonomy_level.value == "autonomous"
    assert audit_results(buf) == ["ALLOW"]


# ---- Approval flow ---------------------------------------------------------


def test_approval_flow_emits_queued_approved_allow(admin_profile, buf):
    # A on confidential → elevated_approval per profile override
    enforcer = make_enforcer(
        admin_profile, gateway=AutoApproveGateway(), audit_sink=buf
    )
    enforcer.enforce("A", "server://prod/db-01", "confidential")
    # Three records: QUEUED, APPROVED, ALLOW
    assert audit_results(buf) == ["QUEUED", "APPROVED", "ALLOW"]


def test_approval_denied_raises_and_audits_rejected(admin_profile, buf):
    enforcer = make_enforcer(
        admin_profile, gateway=RejectAllApprovalGateway(), audit_sink=buf
    )
    with pytest.raises(RMACDApprovalDeniedError):
        enforcer.enforce("A", "server://prod/db-01", "confidential")
    assert audit_results(buf) == ["QUEUED", "REJECTED"]


def test_approval_timeout_raises_correct_subclass(admin_profile):
    class TimeoutGateway:
        def request(self, req: ApprovalRequest) -> ApprovalDecision:
            return ApprovalDecision(
                request_id=req.request_id,
                outcome=ApprovalOutcome.TIMEOUT,
                approver=None,
            )

    enforcer = make_enforcer(admin_profile, gateway=TimeoutGateway())
    with pytest.raises(RMACDApprovalTimeoutError):
        enforcer.enforce("A", "server://prod/db-01", "confidential")


# ---- Denial subclasses -----------------------------------------------------


def test_profile_denied_when_matrix_would_otherwise_allow(observer_profile, buf):
    # Observer profile only grants R. C on internal would be approval-gated
    # under the default matrix, not prohibited — so we should see a profile
    # denial, not a matrix prohibition.
    enforcer = make_enforcer(observer_profile, audit_sink=buf)
    with pytest.raises(RMACDPermissionDeniedError):
        enforcer.enforce("C", "server://web-01", "internal")
    assert audit_results(buf) == ["DENY"]


def test_matrix_prohibited_wins_over_profile_gap(observer_profile):
    # D on restricted: both the profile lacks it AND the matrix prohibits.
    # The prohibition message is the more informative one — we must surface
    # that subclass so the agent knows this isn't a candidate for an
    # exception request.
    enforcer = make_enforcer(observer_profile)
    with pytest.raises(RMACDProhibitedError):
        enforcer.enforce("D", "vault://secret", "restricted")


def test_matrix_prohibited_via_admin_profile(admin_profile):
    # Administrator profile actively grants R/M on restricted but not C/D.
    # C/D on restricted is matrix-prohibited.
    enforcer = make_enforcer(admin_profile)
    with pytest.raises(RMACDProhibitedError):
        enforcer.enforce("C", "vault://secret", "restricted")
    with pytest.raises(RMACDProhibitedError):
        enforcer.enforce("D", "vault://secret", "restricted")


# ---- @guard decorator ------------------------------------------------------


def test_guard_decorator_blocks_before_function_runs(observer_profile):
    enforcer = make_enforcer(observer_profile)
    calls: list[str] = []

    @enforcer.guard(
        operation="C",
        classifier=lambda *, server_id, **_: (f"server://{server_id}", "internal"),
    )
    def update_config(*, server_id: str, value: int) -> None:
        del value
        calls.append(server_id)

    with pytest.raises(RMACDPermissionDeniedError):
        update_config(server_id="web-01", value=8)
    assert calls == []  # function body never ran


def test_guard_decorator_runs_function_when_allowed(admin_profile, buf):
    enforcer = make_enforcer(admin_profile, audit_sink=buf)
    calls: list[str] = []

    @enforcer.guard(
        operation="R",
        classifier=lambda *, doc_id, **_: (f"doc://{doc_id}", "public"),
    )
    def read_doc(*, doc_id: str) -> str:
        calls.append(doc_id)
        return f"contents of {doc_id}"

    result = read_doc(doc_id="readme")
    assert result == "contents of readme"
    assert calls == ["readme"]
    # An ALLOW record and an EXECUTED record should be present.
    results = audit_results(buf)
    assert "ALLOW" in results
    assert "EXECUTED" in results


def audit_executions(buf: io.StringIO) -> list[dict]:
    """The ``execution`` block of every record that carries one."""
    return [
        json.loads(line)["execution"]
        for line in buf.getvalue().splitlines()
        if json.loads(line).get("execution")
    ]


def test_guard_on_async_tool_records_failure_not_success(admin_profile, buf):
    """A guarded async tool that raises must not be audited as SUCCESS.

    Regression: the wrapper used to be a plain ``def``, so ``fn(...)`` returned
    an un-awaited coroutine, the SUCCESS record fired immediately with
    ``duration_ms≈0``, and the ``except`` arm could never see a failure raised
    inside the coroutine. That is forged evidence in an audit-evidence product.
    """
    enforcer = make_enforcer(admin_profile, audit_sink=buf)

    @enforcer.guard(
        operation="R",
        classifier=lambda **_: ("doc://boom", "public"),
    )
    async def failing_tool() -> str:
        await asyncio.sleep(0.01)
        raise RuntimeError("tool blew up")

    with pytest.raises(RuntimeError, match="tool blew up"):
        asyncio.run(failing_tool())

    executions = audit_executions(buf)
    assert len(executions) == 1
    assert executions[0]["status"] == "FAILURE"
    assert executions[0]["error"] == "tool blew up"
    assert "EXECUTED" in audit_results(buf)


def test_guard_on_async_tool_records_success_and_real_duration(admin_profile, buf):
    """A successful async tool is audited once, after it actually completes."""
    enforcer = make_enforcer(admin_profile, audit_sink=buf)

    @enforcer.guard(
        operation="R",
        classifier=lambda **_: ("doc://slow", "public"),
    )
    async def slow_tool() -> str:
        await asyncio.sleep(0.05)
        return "done"

    assert asyncio.run(slow_tool()) == "done"

    executions = audit_executions(buf)
    assert len(executions) == 1
    assert executions[0]["status"] == "SUCCESS"
    assert executions[0]["error"] is None
    # The old wrapper reported ~0 because it never waited for the coroutine.
    assert executions[0]["duration_ms"] >= 40


def test_guard_preserves_coroutine_function_identity(admin_profile):
    """The wrapper must still look async to frameworks that introspect it.

    Adapters branch on ``inspect.iscoroutinefunction`` to decide whether to
    await a tool; a sync wrapper around an async tool silently breaks them.
    """
    enforcer = make_enforcer(admin_profile)

    @enforcer.guard(operation="R", classifier=lambda **_: ("doc://x", "public"))
    async def async_tool() -> str:
        return "x"

    @enforcer.guard(operation="R", classifier=lambda **_: ("doc://y", "public"))
    def sync_tool() -> str:
        return "y"

    assert inspect.iscoroutinefunction(async_tool)
    assert not inspect.iscoroutinefunction(sync_tool)


def test_guard_on_async_tool_blocks_before_awaiting(observer_profile):
    """Denial still happens before the coroutine body runs."""
    enforcer = make_enforcer(observer_profile)
    calls: list[str] = []

    @enforcer.guard(
        operation="C",
        classifier=lambda *, server_id, **_: (f"server://{server_id}", "internal"),
    )
    async def update_config(*, server_id: str) -> None:
        calls.append(server_id)

    with pytest.raises(RMACDPermissionDeniedError):
        asyncio.run(update_config(server_id="web-01"))
    assert calls == []


# ---- from_env() ------------------------------------------------------------


def test_from_env_loads_profile_and_agent_id(monkeypatch):
    monkeypatch.setenv("RMACD_AGENT_ID", "env-agent")
    monkeypatch.setenv(
        "RMACD_PROFILE_PATH", str(FIXTURE_DIR / "observer-3d.json")
    )
    enforcer = PolicyEnforcer.from_env()
    assert enforcer.agent_id == "env-agent"
    assert enforcer.profile.profile_id.startswith("rmacd-3d-")


def test_from_env_raises_clear_error_when_unset(monkeypatch):
    monkeypatch.delenv("RMACD_AGENT_ID", raising=False)
    with pytest.raises(ValueError, match="RMACD_AGENT_ID"):
        PolicyEnforcer.from_env()


# ---- evaluate_only does not audit -----------------------------------------


def test_evaluate_only_is_side_effect_free(admin_profile, buf):
    enforcer = make_enforcer(admin_profile, audit_sink=buf)
    decision = enforcer.evaluate_only("R", "doc://public/readme", "public")
    assert decision.allowed
    assert buf.getvalue() == ""  # no audit emitted


def test_execution_record_carries_the_decision_autonomy(admin_profile, buf):
    """A human-approved call must not be filed as having run autonomously.

    `_audit_execution` used to synthesise its own decision with
    `autonomy_level=AUTONOMOUS, requires_approval=False`, so the EXECUTED row
    contradicted the QUEUED/APPROVED rows it sits beside. An execution row read
    on its own is how "what did this agent do without being asked?" gets
    answered, so it asserted precisely the wrong thing. Same defect the session
    hooks had; this is the `@guard` path.
    """
    enforcer = make_enforcer(admin_profile, gateway=AutoApproveGateway(), audit_sink=buf)

    @enforcer.guard(
        operation=Operation.CHANGE,
        classifier=lambda *a, **k: ("cfg.yaml", DataClassification.INTERNAL),
    )
    def change_config() -> str:
        return "done"

    change_config()

    records = [json.loads(line) for line in buf.getvalue().splitlines() if line.strip()]
    executed = [r for r in records if r["policy_decision"]["result"] == "EXECUTED"]
    assert len(executed) == 1
    # internal.C is approval-gated in the default matrix; the gateway approved it.
    assert executed[0]["policy_decision"]["autonomy_level"] == "approval"
    assert executed[0]["execution"]["status"] == "SUCCESS"


def test_execution_record_of_an_autonomous_call_still_says_autonomous(admin_profile, buf):
    """The counterpart: the fix must not relabel genuinely autonomous work."""
    enforcer = make_enforcer(admin_profile, audit_sink=buf)

    @enforcer.guard(
        operation=Operation.READ,
        classifier=lambda *a, **k: ("doc://public/readme", DataClassification.PUBLIC),
    )
    def read_doc() -> str:
        return "ok"

    read_doc()

    executed = [
        json.loads(line)
        for line in buf.getvalue().splitlines()
        if line.strip() and json.loads(line)["policy_decision"]["result"] == "EXECUTED"
    ]
    assert executed[0]["policy_decision"]["autonomy_level"] == "autonomous"
