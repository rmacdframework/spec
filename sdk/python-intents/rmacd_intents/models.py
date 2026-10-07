"""Typed views of the four Intent Specification schemas.

The JSON Schemas bundled in ``rmacd_intents/schemas/`` are authoritative and
every submission is validated against them first (N-1). These models exist for
typed access afterwards; they forbid unknown fields so that a field the schema
does not define can never reach the grading function (N-2, N-8).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from rmacd import AutonomyLevel, DataClassification, Operation

INTENT_ID = r"^int-[a-z0-9][a-z0-9-]*$"
DECISION_ID = r"^dec-[a-z0-9][a-z0-9-]*$"

#: Framework §2.4, in escalation order. Index 4 is where escalation stops (N-14a).
LADDER: tuple[AutonomyLevel, ...] = (
    AutonomyLevel.AUTONOMOUS,
    AutonomyLevel.LOGGED,
    AutonomyLevel.NOTIFICATION,
    AutonomyLevel.APPROVAL,
    AutonomyLevel.ELEVATED_APPROVAL,
    AutonomyLevel.PROHIBITED,
)
ESCALATION_CEILING = 4

PRODUCTION_PLANE = frozenset(
    {
        "change",
        "release",
        "deployment",
        "service_request",
        "decommission",
        "maintenance_window",
        "continuity_invocation",
    }
)
RECORD_PLANE = frozenset({"incident"})
GRANT_PLANE = frozenset({"campaign", "exception"})
BUNDLE_TYPES = frozenset({"release", "decommission"})
DEPENDENT_TYPES = frozenset({"deployment"})


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ActorKind(str, Enum):
    AGENT = "agent"
    PIPELINE = "pipeline"
    HUMAN = "human"


class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    DISASTER_RECOVERY = "disaster-recovery"
    SANDBOX = "sandbox"


class GrantStatus(str, Enum):
    REQUESTED = "requested"
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    CLOSED = "closed"


class Actor(_Strict):
    kind: ActorKind
    id: str = Field(min_length=1)
    authorization: str = Field(min_length=1)
    on_behalf_of: str | None = None


class Reversibility(_Strict):
    rollback_declared: bool | None = None
    rollback_plan: str | None = None
    attested_by: str | None = None


class BlastRadius(_Strict):
    scope_percentage: float | None = Field(default=None, ge=0, le=100)
    affected_count: int | None = Field(default=None, ge=0)


class Declaration(_Strict):
    operation: Operation
    target: str = Field(min_length=1)
    target_class: str | None = None
    data_classification: DataClassification | None = None
    environment: Environment
    reversibility: Reversibility | None = None
    blast_radius: BlastRadius | None = None


class Window(_Strict):
    start: datetime
    end: datetime


class Stage(_Strict):
    name: str
    description: str | None = None
    reversible: bool | None = None


class ClassPredicate(_Strict):
    intent_type: str | None = None
    operation: Operation | None = None
    data_classification: DataClassification | None = None
    environment: Environment | None = None
    target_class: str | None = None
    actor_id: str | None = None
    on_behalf_of: str | None = None


class GrantCaps(_Strict):
    max_children: int = Field(ge=1)
    max_level: AutonomyLevel
    max_blast_radius_percentage: float | None = Field(default=None, ge=0, le=100)


class EscalatedPermissions(_Strict):
    public: list[Operation] | None = None
    internal: list[Operation] | None = None
    confidential: list[Operation] | None = None
    restricted: list[Literal["R", "M"]] | None = None


class Intent(BaseModel):
    """The envelope (spec §2) plus every type-specific field (§4, §7.4)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_url: str | None = Field(default=None, alias="$schema")
    intent_id: str = Field(pattern=INTENT_ID)
    intent_type: str
    submitted_at: datetime
    valid_until: datetime | None = None
    actor: Actor
    declaration: Declaration
    justification: str | None = None
    composes: list[str] | None = None
    requires: list[str] | None = None
    window_ref: str | None = None
    grant_ref: str | None = None
    compliance_tags: list[str] | None = None
    provenance: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    # type-specific
    catalogue_ref: str | None = None
    stages: list[Stage] | None = None
    window: Window | None = None
    service_commitment: str | None = None
    plan_ref: str | None = None
    trigger: str | None = None
    severity: str | None = None
    dedup_key: str | None = None
    class_predicate: ClassPredicate | None = None
    caps: GrantCaps | None = None
    expires_at: datetime | None = None
    base_profile_id: str | None = None
    exception_category: str | None = None
    escalated_permissions: EscalatedPermissions | None = None
    compensating_controls: dict[str, Any] | None = None
    rollback_plan: str | None = None
    status: GrantStatus | None = None

    @property
    def is_grant(self) -> bool:
        return self.intent_type in GRANT_PLANE

    @property
    def is_bundle(self) -> bool:
        return self.intent_type in BUNDLE_TYPES

    @property
    def children(self) -> list[str]:
        """Every intent this one composes or requires (N-11, N-63)."""
        return list(self.composes or []) + list(self.requires or [])


# ----------------------------------------------------------------- decision record


class EscalationFactor(_Strict):
    factor: Literal[
        "precedent",
        "reversibility",
        "environment",
        "budget_standing",
        "blast_radius",
        "unresolved_authorization",
        "composition_floor",
        "grant_cap",
    ]
    steps: int = Field(ge=0)
    cause: str | None = None


class ImpactBasis(_Strict):
    scheme: str = "data_classification"
    value: str


class ActionPatternFields(_Strict):
    """The six §6.1 fields verbatim, kept by an L1 implementation (N-69)."""

    intent_type: str
    operation: Operation
    data_classification: DataClassification | None = None
    environment: str
    target_class: str
    actor_kind: ActorKind


class Disposition(_Strict):
    outcome: Literal["approved", "approved_with_modifications", "deferred", "denied"]
    approver: str | None = None
    decided_at: datetime
    note: str | None = None

    @property
    def permits(self) -> bool:
        return self.outcome in ("approved", "approved_with_modifications")


class Discrepancy(_Strict):
    field: Literal[
        "operation", "target_class", "data_classification", "environment", "scope", "window"
    ]
    declared: str | None = None
    executed: str | None = None


class Reconciliation(_Strict):
    result: Literal["matched", "divergent", "undeclared", "unexecuted"]
    reconciled_at: datetime | None = None
    audit_record_id: str | None = None
    discrepancies: list[Discrepancy] | None = None


class DecisionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_url: str | None = Field(default=None, alias="$schema")
    decision_id: str = Field(pattern=DECISION_ID)
    intent_id: str = Field(pattern=INTENT_ID)
    decided_at: datetime
    action_pattern_key: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    action_pattern_fields: ActionPatternFields | None = None
    base_level: AutonomyLevel
    computed_level: AutonomyLevel
    escalation_factors: list[EscalationFactor]
    impact_basis: ImpactBasis
    profile_id: str
    implementation_level: Literal["L1", "L2", "L3"] | None = None
    matrix_version: str
    likelihood_weights_version: str
    policy_version: str
    log_epoch: str = Field(pattern=r"^seq-[0-9]+$")
    grant_ref: str | None = None
    disposition: Disposition | None = None
    prohibition_source: Literal["pinned", "extended"] | None = None
    reconciliation: Reconciliation | None = None

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)


# ------------------------------------------------------------------------- logs


class IntentLogEntry(BaseModel):
    """One line of the intent log (spec §9.1)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_url: str | None = Field(default=None, alias="$schema")
    seq: int = Field(ge=1)
    logged_at: datetime
    kind: Literal["submission", "rejection", "transition"]
    intent_id: str | None = Field(default=None, pattern=INTENT_ID)
    document: dict[str, Any] | None = None
    raw: str | None = None
    failure: str | None = None
    from_status: GrantStatus | None = None
    to_status: GrantStatus | None = None
    changed_by: str | None = None

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)


class AdjudicationLogEntry(BaseModel):
    """One line of the adjudication log (spec §9.2)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_url: str | None = Field(default=None, alias="$schema")
    seq: int = Field(ge=1)
    logged_at: datetime
    kind: Literal["decision", "disposition", "reconciliation"]
    decision_id: str = Field(pattern=DECISION_ID)
    record: DecisionRecord | None = None
    disposition: Disposition | None = None
    reconciliation: Reconciliation | None = None

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)


class Rejection(_Strict):
    """What a submission that failed validation becomes (N-1, N-59)."""

    intent_id: str | None = None
    failure: str
    document: dict[str, Any] | None = None
    raw: str | None = None
