"""Pydantic models for RMACD Framework profiles and policy decisions."""

from datetime import datetime, time
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Operation(str, Enum):
    """RMACD operations that can be performed on data."""

    READ = "R"
    MOVE = "M"
    ADD = "A"
    CHANGE = "C"
    DELETE = "D"


class DataClassification(str, Enum):
    """PICR data classification tiers."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class AutonomyLevel(str, Enum):
    """HITL autonomy levels from most to least autonomous."""

    AUTONOMOUS = "autonomous"
    LOGGED = "logged"
    NOTIFICATION = "notification"
    APPROVAL = "approval"
    ELEVATED_APPROVAL = "elevated_approval"
    PROHIBITED = "prohibited"


class Environment(str, Enum):
    """Supported deployment environments."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    DISASTER_RECOVERY = "disaster-recovery"
    SANDBOX = "sandbox"


class LogLevel(str, Enum):
    """Audit log verbosity levels."""

    STANDARD = "standard"
    ENHANCED = "enhanced"
    VERBOSE = "verbose"
    DEBUG = "debug"


class ProfileStatus(str, Enum):
    """Profile lifecycle status."""

    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class TriggerCondition(str, Enum):
    """Emergency escalation trigger conditions."""

    SOC_DECLARED_INCIDENT = "soc_declared_incident"
    AUTOMATED_THREAT_DETECTION = "automated_threat_detection"
    BUSINESS_CONTINUITY_EVENT = "business_continuity_event"
    COMPLIANCE_EMERGENCY = "compliance_emergency"
    MANUAL_AUTHORIZATION = "manual_authorization"


class ComplianceTag(str, Enum):
    """Supported compliance frameworks."""

    GDPR = "GDPR"
    HIPAA = "HIPAA"
    PCI_DSS = "PCI-DSS"
    SOX = "SOX"
    ISO27001 = "ISO27001"
    CCPA = "CCPA"
    FEDRAMP = "FedRAMP"
    NIST_CSF = "NIST-CSF"


class AlertChannelType(str, Enum):
    """Alert notification channel types."""

    EMAIL = "email"
    SLACK = "slack"
    PAGERDUTY = "pagerduty"
    WEBHOOK = "webhook"
    SIEM = "siem"


class AlertChannel(BaseModel):
    """Alert notification channel configuration."""

    type: AlertChannelType
    target: str = Field(description="Channel-specific target (email, webhook URL, etc.)")


class RateLimits(BaseModel):
    """Rate limiting constraints."""

    queries_per_minute: int | None = Field(
        default=None, ge=1, le=10000, description="Maximum read queries per minute"
    )
    operations_per_hour: int | None = Field(
        default=None, ge=1, le=10000, description="Maximum mutating operations per hour"
    )
    data_volume_mb_per_hour: int | None = Field(
        default=None, ge=1, le=100000, description="Maximum data volume processed per hour in MB"
    )


class AllowedHours(BaseModel):
    """Time range when operations are permitted."""

    start: str = Field(pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$", description="Start time HH:MM")
    end: str = Field(pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$", description="End time HH:MM")


class MaintenanceWindow(BaseModel):
    """Pre-approved maintenance window."""

    name: str
    start: datetime
    end: datetime
    recurring: Literal["once", "weekly", "monthly"] = "once"


class TimeWindows(BaseModel):
    """Time-based operational restrictions."""

    timezone: str = Field(default="UTC", description="IANA timezone identifier")
    allowed_days: list[
        Literal["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    ] | None = None
    allowed_hours: AllowedHours | None = None
    blackout_dates: list[str] | None = Field(default=None, description="ISO 8601 dates")
    maintenance_windows: list[MaintenanceWindow] | None = None


class ChangeControls(BaseModel):
    """Controls for Change (C) operations."""

    require_backup_before_change: bool = Field(default=True)
    require_rollback_plan: bool = Field(default=True)
    max_blast_radius_percentage: int = Field(default=10, ge=0, le=100)
    canary_deployment_required: bool = Field(default=False)
    change_freeze_periods: list[MaintenanceWindow] | None = None


class DeleteControls(BaseModel):
    """Controls for Delete (D) operations."""

    soft_delete_grace_period_days: int = Field(default=7, ge=1, le=365)
    require_dependency_check: bool = Field(default=True)
    require_legal_hold_check: bool = Field(default=True)
    two_person_rule_for_confidential: bool = Field(
        default=True, description="Require two approvers for Confidential data deletion"
    )
    retention_compliance_check: bool = Field(default=True)


class ResourceQuotas(BaseModel):
    """Resource creation limits for Add (A) operations."""

    max_resources_per_request: int | None = Field(default=None, ge=1, le=1000)
    max_storage_gb_per_request: int | None = Field(default=None, ge=1)
    max_monthly_cost_usd: float | None = Field(default=None, ge=0)
    auto_expiration_days: int | None = Field(default=None, ge=1, le=365)


class Constraints(BaseModel):
    """Operational constraints for the profile."""

    environments: list[Environment] | None = None
    rate_limits: RateLimits | None = None
    time_windows: TimeWindows | None = None
    change_controls: ChangeControls | None = None
    delete_controls: DeleteControls | None = None
    resource_quotas: ResourceQuotas | None = None


class EmergencyEscalation2D(BaseModel):
    """Emergency escalation configuration for 2D profiles."""

    enabled: bool = False
    trigger_conditions: list[TriggerCondition] | None = None
    escalated_permissions: list[Operation] | None = None
    max_duration_minutes: int = Field(default=60, ge=1, le=480)
    require_post_incident_review: bool = True
    notification_targets: list[str] | None = None
    cooldown_minutes: int = Field(default=30, ge=0)


class EmergencyEscalation3D(BaseModel):
    """Emergency escalation configuration for 3D profiles with per-classification permissions."""

    enabled: bool = False
    trigger_conditions: list[TriggerCondition] | None = None
    escalated_permissions: dict[DataClassification, list[Operation]] | None = None
    max_duration_minutes: int = Field(default=60, ge=1, le=480)
    require_post_incident_review: bool = True
    notification_targets: list[str] | None = None
    cooldown_minutes: int = Field(default=30, ge=0)


class AuditRequirements(BaseModel):
    """Audit and logging requirements."""

    log_level: LogLevel = LogLevel.STANDARD
    retention_days: int = Field(default=365, ge=30, le=2555)
    real_time_alerts: list[str] | None = Field(
        default=None, description="Operations or classification.operation combos triggering alerts"
    )
    alert_channels: list[AlertChannel] | None = None
    immutable_logging: bool = Field(
        default=False, description="Require tamper-evident logging (WORM)"
    )
    pii_masking: bool = Field(default=True, description="Automatically mask PII in audit logs")
    compliance_tags: list[ComplianceTag] | None = None


class ApprovalSettings(BaseModel):
    """Settings for approval autonomy level."""

    approvers: list[str] = Field(min_length=1)
    timeout_minutes: int = Field(default=60, ge=1, le=10080)
    escalation_after_minutes: int | None = Field(default=None, ge=1)
    escalation_target: str | None = None


class ElevatedApprovalSettings(BaseModel):
    """Settings for elevated_approval autonomy level."""

    approvers: list[str] = Field(min_length=1)
    timeout_minutes: int = Field(default=240, ge=1, le=10080)
    require_multiple_approvers: bool = False
    minimum_approvers: int = Field(default=2, ge=2)


class ApprovalAuthority(BaseModel):
    """Approval authority configuration."""

    approval: ApprovalSettings | None = None
    elevated_approval: ElevatedApprovalSettings | None = None


class ProfileMetadata(BaseModel):
    """Profile metadata."""

    created: datetime
    updated: datetime | None = None
    author: str
    approved_by: str | None = None
    review_date: str | None = Field(default=None, description="Next review date (ISO 8601)")
    status: ProfileStatus = ProfileStatus.ACTIVE
    deprecation_notice: str | None = None
    tags: list[str] | None = None


class Profile2D(BaseModel):
    """Two-dimensional RMACD profile (operations + autonomy, no data classification)."""

    schema_ref: str | None = Field(
        default=None, alias="$schema", description="JSON Schema reference"
    )
    profile_id: str = Field(pattern=r"^rmacd-2d-[a-z0-9-]+$")
    profile_name: str
    model: Literal["two-dimensional"] = "two-dimensional"
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+(\.[0-9]+)?$")
    description: str | None = None
    permissions: list[Operation] = Field(min_length=1)
    autonomy_overrides: dict[Operation, AutonomyLevel] | None = None
    emergency_escalation: EmergencyEscalation2D | None = None
    constraints: Constraints | None = None
    audit_requirements: AuditRequirements | None = None
    approval_authority: ApprovalAuthority | None = None
    metadata: ProfileMetadata | None = None


class Profile3D(BaseModel):
    """Three-dimensional RMACD profile (operations + data classification + autonomy)."""

    schema_ref: str | None = Field(
        default=None, alias="$schema", description="JSON Schema reference"
    )
    profile_id: str = Field(pattern=r"^rmacd-3d-[a-z0-9-]+$")
    profile_name: str
    model: Literal["three-dimensional"] = "three-dimensional"
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+(\.[0-9]+)?$")
    description: str | None = None
    permissions: dict[DataClassification, list[Operation]]
    autonomy_overrides: dict[str, AutonomyLevel] | None = Field(
        default=None, description="Keys in format 'classification.operation' (e.g., 'internal.C')"
    )
    emergency_escalation: EmergencyEscalation3D | None = None
    constraints: Constraints | None = None
    audit_requirements: AuditRequirements | None = None
    approval_authority: ApprovalAuthority | None = None
    metadata: ProfileMetadata | None = None


class PolicyDecision(BaseModel):
    """Result of a policy evaluation."""

    allowed: bool = Field(description="Whether the operation is permitted")
    operation: Operation
    data_classification: DataClassification | None = None
    autonomy_level: AutonomyLevel = Field(description="Required autonomy level for this operation")
    requires_approval: bool = Field(description="Whether human approval is required")
    requires_notification: bool = Field(description="Whether notification must be sent")
    blocked_reason: str | None = Field(
        default=None, description="Reason if operation is blocked"
    )
    constraints_applied: list[str] = Field(
        default_factory=list, description="List of constraints that were evaluated"
    )
    emergency_mode: bool = Field(
        default=False, description="Whether emergency escalation is active"
    )


class EvaluationContext(BaseModel):
    """Context for policy evaluation."""

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    environment: Environment | None = None
    emergency_active: bool = False
    emergency_trigger: TriggerCondition | None = None
    request_metadata: dict[str, str] | None = None


# --- DC2D (Data-Classification Two-Dimensional) variant ---


class TierPolicy(BaseModel):
    """Per-tier access permission and autonomy stance for DC2D profiles."""

    allowed: bool = Field(description="Whether the agent may interact with data of this tier")
    autonomy: AutonomyLevel = Field(description="Required HITL autonomy level for this tier")
    justification: str | None = Field(
        default=None,
        description="Required when this tier deviates from the recommended default in Appendix D",
    )
    data_categories: list[str] | None = Field(
        default=None,
        description="Optional regulatory/organizational tags scoping this tier (e.g., PII, PHI, PCI)",
    )


class DataAccess(BaseModel):
    """Required per-tier policy block for DC2D profiles. All four tiers must be specified."""

    public: TierPolicy
    internal: TierPolicy
    confidential: TierPolicy
    restricted: TierPolicy

    model_config = {"extra": "forbid"}

    def for_tier(self, tier: DataClassification) -> TierPolicy:
        """Return the TierPolicy for the given classification tier."""
        return getattr(self, tier.value)


class RateLimitsDC2D(BaseModel):
    """Rate limiting constraints for DC2D profiles (no operation-specific limits)."""

    queries_per_minute: int | None = Field(default=None, ge=1, le=10000)
    data_volume_mb_per_hour: int | None = Field(default=None, ge=1, le=100000)
    tokens_per_hour: int | None = Field(
        default=None, ge=1, description="Maximum tokens (prompt + completion) per hour"
    )


class RedactionPolicy(BaseModel):
    """Per-tier output redaction and masking policy. Primary control surface for DC2D."""

    mask_pii: bool = Field(default=True, description="Mask PII in agent outputs")
    redact_tiers: list[DataClassification] = Field(
        default_factory=lambda: [DataClassification.RESTRICTED],
        description="Tiers whose content must be redacted in agent outputs",
    )
    tokenize_identifiers: bool = Field(
        default=False,
        description="Replace direct identifiers with reversible tokens",
    )


class EgressControls(BaseModel):
    """Restrictions on where classified data may flow."""

    allowed_destinations: list[str] | None = Field(
        default=None, description="Permitted egress targets (domains, services, labels)"
    )
    block_external_models: bool = Field(
        default=True,
        description="Prevent confidential/restricted data egress to external model endpoints",
    )


class ConstraintsDC2D(BaseModel):
    """Operational constraints for DC2D profiles. No operation-specific controls."""

    environments: list[Environment] | None = None
    rate_limits: RateLimitsDC2D | None = None
    time_windows: TimeWindows | None = None
    redaction: RedactionPolicy | None = None
    egress_controls: EgressControls | None = None


class EmergencyEscalationDC2D(BaseModel):
    """Emergency escalation for DC2D profiles. Raises permitted data tiers, not operations."""

    enabled: bool = False
    trigger_conditions: list[TriggerCondition] | None = None
    escalated_tiers: list[DataClassification] | None = Field(
        default=None,
        description="Data tiers temporarily made accessible during emergency",
    )
    escalated_autonomy: AutonomyLevel | None = Field(
        default=None,
        description="Autonomy stance applied to escalated tiers during the emergency window",
    )
    max_duration_minutes: int = Field(default=60, ge=1, le=480)
    require_post_incident_review: bool = True
    notification_targets: list[str] | None = None
    cooldown_minutes: int = Field(default=30, ge=0)


class AuditRequirementsDC2D(BaseModel):
    """Audit and logging requirements for DC2D profiles (alerts keyed by tier, not operation)."""

    log_level: LogLevel = LogLevel.STANDARD
    retention_days: int = Field(default=365, ge=30, le=2555)
    real_time_alerts_for_tiers: list[DataClassification] | None = Field(
        default=None, description="Tiers whose access triggers real-time alerts"
    )
    alert_channels: list[AlertChannel] | None = None
    immutable_logging: bool = False
    pii_masking: bool = True
    compliance_tags: list[ComplianceTag] | None = None


class ProfileDC2D(BaseModel):
    """Data-Classification Two-Dimensional RMACD profile (data classification + autonomy).

    For organizations whose primary governance lever is data sensitivity and where
    operational permissions are governed elsewhere (IAM/RBAC, DLP). See Appendix D
    of the RMACD Framework specification.
    """

    schema_ref: str | None = Field(
        default=None, alias="$schema", description="JSON Schema reference"
    )
    profile_id: str = Field(pattern=r"^rmacd-dc2d-[a-z0-9-]+$")
    profile_name: str
    model: Literal["data-classification-2d"] = "data-classification-2d"
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+(\.[0-9]+)?$")
    description: str | None = None
    data_access: DataAccess
    emergency_escalation: EmergencyEscalationDC2D | None = None
    constraints: ConstraintsDC2D | None = None
    audit_requirements: AuditRequirementsDC2D | None = None
    approval_authority: ApprovalAuthority | None = None
    metadata: ProfileMetadata | None = None
