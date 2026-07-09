"""Tests for the CLIApprovalGateway shipped in rmacd.approval.

The gateway prompts on stdin/stderr; tests drive it by monkeypatching the
built-in ``input`` and capturing stderr, so no real terminal is needed.
"""

from __future__ import annotations

import builtins

import pytest

from rmacd import CLIApprovalGateway
from rmacd.approval import ApprovalOutcome, ApprovalRequest
from rmacd.models import AutonomyLevel, DataClassification, Operation


def _request() -> ApprovalRequest:
    return ApprovalRequest(
        agent_id="agent-1",
        profile_id="rmacd-3d-devops-demo-v1",
        operation=Operation.CHANGE,
        target="server://web-01",
        classification=DataClassification.INTERNAL,
        autonomy_level=AutonomyLevel.APPROVAL,
        justification="update config",
    )


def _answer(monkeypatch: pytest.MonkeyPatch, text: str) -> None:
    monkeypatch.setattr(builtins, "input", lambda _prompt="": text)


def test_exported_from_package_root() -> None:
    import rmacd

    assert "CLIApprovalGateway" in rmacd.__all__
    assert rmacd.CLIApprovalGateway is CLIApprovalGateway


def test_yes_approves(monkeypatch: pytest.MonkeyPatch) -> None:
    _answer(monkeypatch, "y")
    decision = CLIApprovalGateway().request(_request())
    assert decision.outcome is ApprovalOutcome.APPROVED
    assert decision.approver == "local-operator"


def test_yes_with_note_captures_note(monkeypatch: pytest.MonkeyPatch) -> None:
    _answer(monkeypatch, "yes approved for the maintenance window")
    decision = CLIApprovalGateway(approver_name="alice").request(_request())
    assert decision.outcome is ApprovalOutcome.APPROVED
    assert decision.approver == "alice"
    assert decision.note == "approved for the maintenance window"


@pytest.mark.parametrize("text", ["n", "no", "", "maybe"])
def test_non_yes_denies(monkeypatch: pytest.MonkeyPatch, text: str) -> None:
    _answer(monkeypatch, text)
    decision = CLIApprovalGateway().request(_request())
    assert decision.outcome is ApprovalOutcome.DENIED


def test_eof_denies_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(_prompt: str = "") -> str:
        raise EOFError

    monkeypatch.setattr(builtins, "input", _raise)
    decision = CLIApprovalGateway().request(_request())
    assert decision.outcome is ApprovalOutcome.DENIED
    assert decision.note == "no stdin available"


def test_request_is_rendered_to_stderr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _answer(monkeypatch, "y")
    CLIApprovalGateway().request(_request())
    err = capsys.readouterr().err
    assert "APPROVAL REQUIRED" in err
    assert "server://web-01" in err
    assert "C  (Change)" in err
    assert "internal" in err
