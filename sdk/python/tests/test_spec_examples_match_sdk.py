"""The spec's normative JSON examples must match what the SDK actually emits.

Appendix C.5 and C.6 are the shapes an integrator builds an approval gateway and
a SIEM pipeline against. They had drifted badly — C.6 wrapped the record in an
``audit_record`` envelope the SDK never emits, spelled the operation
``"CHANGE"`` where the SDK emits ``"C"``, and carried a phantom
``execution.rollback_available``; C.5 used ``timeout_minutes`` for
``timeout_seconds``, ``required_autonomy`` for ``autonomy_level``, and nested
the operation that the SDK keeps flat.

Prose drifts silently. These tests parse the JSON straight out of the spec
markdown and compare it against a live record, so it cannot drift again.
"""

from __future__ import annotations

import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from rmacd import ApprovalRequest
from rmacd.audit import AuditExecution, JSONLAuditLogger, build_audit_record
from rmacd.models import (
    AutonomyLevel,
    DataClassification,
    Operation,
    PolicyDecision,
)

SPEC = Path(__file__).resolve().parents[3] / "docs" / "RMACD_Framework_v1.4.md"


def _json_block_after(heading: str) -> dict:
    """The first ```json fenced block following a heading in the spec."""
    text = SPEC.read_text(encoding="utf-8")
    idx = text.find(heading)
    assert idx != -1, f"heading {heading!r} not found in the spec"
    match = re.search(r"```json\n(.*?)\n```", text[idx:], re.DOTALL)
    assert match, f"no json block after {heading!r}"
    return json.loads(match.group(1))


@pytest.fixture
def live_audit_record() -> dict:
    """A real record, serialized exactly as JSONLAuditLogger writes it."""
    decision = PolicyDecision(
        allowed=True,
        operation=Operation.CHANGE,
        data_classification=DataClassification.INTERNAL,
        autonomy_level=AutonomyLevel.APPROVAL,
        requires_approval=True,
        requires_notification=False,
    )
    record = build_audit_record(
        agent_id="devops-agent-001",
        profile_id="rmacd-3d-operations-v1",
        operation=Operation.CHANGE,
        target="config://prod/app-server-01/nginx.conf",
        classification=DataClassification.INTERNAL,
        decision=decision,
        result="ALLOW",
        approval_id="apr-20260110-001",
        approver="john.smith@company.com",
        approved_at=datetime(2026, 1, 10, 14, 28, tzinfo=timezone.utc),
        execution=AuditExecution(status="SUCCESS", duration_ms=1250),
        compliance_tags=["SOX", "ISO27001"],
    )
    buf = io.StringIO()
    JSONLAuditLogger(buf).log(record)
    return json.loads(buf.getvalue().strip())


def test_appendix_c6_audit_record_keys_match(live_audit_record: dict) -> None:
    """C.6's example has exactly the SDK's top-level keys — no envelope."""
    spec_example = _json_block_after("## **C.6 Audit Log Format**")

    assert "audit_record" not in spec_example, (
        "C.6 re-introduced the audit_record envelope; the SDK emits the record "
        "at the top level"
    )
    assert set(spec_example) == set(live_audit_record), (
        f"key mismatch\n  spec-only: {sorted(set(spec_example) - set(live_audit_record))}"
        f"\n  sdk-only:  {sorted(set(live_audit_record) - set(spec_example))}"
    )


@pytest.mark.parametrize("block", ["operation", "policy_decision", "execution"])
def test_appendix_c6_nested_blocks_match(live_audit_record: dict, block: str) -> None:
    """Nested blocks match field-for-field, catching phantom fields."""
    spec_example = _json_block_after("## **C.6 Audit Log Format**")
    assert set(spec_example[block]) == set(live_audit_record[block]), (
        f"{block} mismatch\n"
        f"  spec-only: {sorted(set(spec_example[block]) - set(live_audit_record[block]))}\n"
        f"  sdk-only:  {sorted(set(live_audit_record[block]) - set(spec_example[block]))}"
    )


def test_appendix_c6_operation_type_is_the_enum_code() -> None:
    """`"C"`, not `"CHANGE"` — the value an integrator filters a SIEM on."""
    spec_example = _json_block_after("## **C.6 Audit Log Format**")
    op_type = spec_example["operation"]["type"]
    assert op_type == Operation.CHANGE.value == "C", f"got {op_type!r}"


def test_appendix_c5_approval_request_keys_match() -> None:
    """C.5's example has exactly the fields of a real ApprovalRequest."""
    spec_example = _json_block_after("## **C.5 Approval Workflow Integration**")

    assert "approval_request" not in spec_example, "C.5 re-introduced the envelope"

    request = ApprovalRequest(
        request_id="apr-20260110-001",
        agent_id="devops-agent-001",
        profile_id="rmacd-3d-operations-v1",
        operation=Operation.CHANGE,
        target="config://prod/app-server-01/nginx.conf",
        classification=DataClassification.INTERNAL,
        autonomy_level=AutonomyLevel.APPROVAL,
        justification="Performance optimization for increased traffic",
    )
    live_keys = set(vars(request))

    assert set(spec_example) == live_keys, (
        f"key mismatch\n  spec-only: {sorted(set(spec_example) - live_keys)}"
        f"\n  sdk-only:  {sorted(live_keys - set(spec_example))}"
    )


def test_appendix_c5_uses_seconds_and_flat_operation() -> None:
    """The three fields C.5 previously got wrong."""
    spec_example = _json_block_after("## **C.5 Approval Workflow Integration**")

    assert "timeout_seconds" in spec_example
    assert "timeout_minutes" not in spec_example
    assert "autonomy_level" in spec_example
    assert "required_autonomy" not in spec_example
    # `operation` is the flat enum code, not a nested object.
    assert spec_example["operation"] == "C"


def test_audit_evidence_doc_example_matches_the_spec_shape() -> None:
    """docs/audit-evidence.md tells readers its records are Appendix C.6.

    That claim is only true if its own worked example has the same shape.
    """
    doc = SPEC.parent / "audit-evidence.md"
    match = re.search(r"```json\n(.*?)\n```", doc.read_text(encoding="utf-8"), re.DOTALL)
    assert match, "no json block in audit-evidence.md"
    example = json.loads(match.group(1))

    spec_example = _json_block_after("## **C.6 Audit Log Format**")
    assert set(example) == set(spec_example)
    assert set(example["policy_decision"]) == set(spec_example["policy_decision"])
