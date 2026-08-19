from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from modules.platform.models import TenantOwnedModel


class RuntimeEnvironment(TenantOwnedModel):
    class EnvironmentType(models.TextChoices):
        LOCAL = "local", "Local"
        DEVELOPMENT = "development", "Development"
        STAGING = "staging", "Staging"
        PRODUCTION = "production", "Production"
        DISASTER_RECOVERY = "disaster_recovery", "Disaster recovery"

    code = models.CharField(max_length=60)
    name = models.CharField(max_length=160)
    environment_type = models.CharField(max_length=24, choices=EnvironmentType.choices)
    base_url = models.URLField(blank=True)
    region = models.CharField(max_length=100, blank=True)
    data_residency = models.CharField(max_length=100, blank=True)
    production_data_allowed = models.BooleanField(default=False)
    requires_change_approval = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "adminops_runtime_environment"
        ordering = ["environment_type", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="adm_env_code_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "environment_type", "is_active"],
                name="adm_env_type_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.environment_type == self.EnvironmentType.PRODUCTION and not self.base_url:
            raise ValidationError("A production environment requires a base URL")
        if self.production_data_allowed and self.environment_type not in {
            self.EnvironmentType.PRODUCTION,
            self.EnvironmentType.DISASTER_RECOVERY,
        }:
            raise ValidationError(
                "Production data is allowed only in production or disaster-recovery environments"
            )


class ReleaseRecord(TenantOwnedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        VALIDATED = "validated", "Validated"
        APPROVED = "approved", "Approved"
        DEPLOYED = "deployed", "Deployed"
        FAILED = "failed", "Failed"
        ROLLED_BACK = "rolled_back", "Rolled back"

    environment = models.ForeignKey(
        RuntimeEnvironment,
        on_delete=models.PROTECT,
        related_name="releases",
    )
    version_label = models.CharField(max_length=80)
    release_name = models.CharField(max_length=180)
    source_revision = models.CharField(max_length=160)
    artifact_sha256 = models.CharField(max_length=64)
    migration_plan_sha256 = models.CharField(max_length=64, blank=True)
    change_summary = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    requested_by_public_id = models.UUIDField()
    validated_by_public_id = models.UUIDField(null=True, blank=True)
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    deployed_by_public_id = models.UUIDField(null=True, blank=True)
    validated_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    deployed_at = models.DateTimeField(null=True, blank=True)
    rollback_reference = models.CharField(max_length=240, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "adminops_release_record"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "environment", "version_label"],
                name="adm_release_env_ver_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "environment", "status", "created_at"],
                name="adm_release_status_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.environment_id and self.environment.company_id != self.company_id:
            raise ValidationError("A release cannot target another company's environment")
        for field_name in ("artifact_sha256", "migration_plan_sha256"):
            value = getattr(self, field_name)
            invalid_digest = value and (
                len(value) != 64
                or any(char not in "0123456789abcdef" for char in value.lower())
            )
            if invalid_digest:
                raise ValidationError(
                    {field_name: "A lowercase or uppercase SHA-256 digest is required"}
                )
        if self.status == self.Status.ROLLED_BACK and not self.rollback_reference:
            raise ValidationError("A rolled-back release requires rollback evidence")


class ReleaseCheck(TenantOwnedModel):
    class Category(models.TextChoices):
        SECURITY = "security", "Security"
        DATABASE = "database", "Database"
        API = "api", "API"
        FRONTEND = "frontend", "Frontend"
        RECOVERY = "recovery", "Recovery"
        OBSERVABILITY = "observability", "Observability"
        GOVERNANCE = "governance", "Governance"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PASSED = "passed", "Passed"
        FAILED = "failed", "Failed"
        WAIVED = "waived", "Waived"

    release = models.ForeignKey(
        ReleaseRecord,
        on_delete=models.PROTECT,
        related_name="checks",
    )
    code = models.CharField(max_length=100)
    name = models.CharField(max_length=180)
    category = models.CharField(max_length=24, choices=Category.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    is_critical = models.BooleanField(default=True)
    target_value = models.CharField(max_length=160, blank=True)
    measured_value = models.CharField(max_length=160, blank=True)
    evidence = models.CharField(max_length=1000, blank=True)
    waiver_reason = models.CharField(max_length=500, blank=True)
    checked_by_public_id = models.UUIDField(null=True, blank=True)
    checked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "adminops_release_check"
        ordering = ["category", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["release", "code"],
                name="adm_release_check_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "status", "is_critical"],
                name="adm_check_status_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.release_id and self.release.company_id != self.company_id:
            raise ValidationError("A release check cannot cross companies")
        if self.status == self.Status.WAIVED and not self.waiver_reason:
            raise ValidationError("A waived check requires a reason")
        completed_statuses = {
            self.Status.PASSED,
            self.Status.FAILED,
            self.Status.WAIVED,
        }
        if self.status in completed_statuses and not self.checked_at:
            raise ValidationError("A completed release check requires a check timestamp")


class ServiceObjective(TenantOwnedModel):
    class IndicatorType(models.TextChoices):
        AVAILABILITY = "availability", "Availability"
        LATENCY = "latency", "Latency"
        ERROR_RATE = "error_rate", "Error rate"
        QUEUE_AGE = "queue_age", "Queue age"

    code = models.CharField(max_length=100)
    name = models.CharField(max_length=180)
    service_code = models.CharField(max_length=100)
    indicator_type = models.CharField(max_length=20, choices=IndicatorType.choices)
    target_value = models.DecimalField(max_digits=12, decimal_places=4)
    warning_threshold = models.DecimalField(max_digits=12, decimal_places=4)
    critical_threshold = models.DecimalField(max_digits=12, decimal_places=4)
    window_days = models.PositiveSmallIntegerField(default=30)
    unit_code = models.CharField(max_length=40, default="percent")
    is_active = models.BooleanField(default=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "adminops_service_objective"
        ordering = ["service_code", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="adm_slo_code_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "service_code", "is_active"],
                name="adm_slo_service_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if not 1 <= self.window_days <= 365:
            raise ValidationError("The SLO window must be between 1 and 365 days")
        if self.target_value < 0 or self.warning_threshold < 0 or self.critical_threshold < 0:
            raise ValidationError("SLO values cannot be negative")


class HealthSnapshot(TenantOwnedModel):
    class Status(models.TextChoices):
        HEALTHY = "healthy", "Healthy"
        DEGRADED = "degraded", "Degraded"
        UNAVAILABLE = "unavailable", "Unavailable"
        UNKNOWN = "unknown", "Unknown"

    environment = models.ForeignKey(
        RuntimeEnvironment,
        on_delete=models.PROTECT,
        related_name="health_snapshots",
    )
    service_code = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=Status.choices)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    observed_value = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    source = models.CharField(max_length=120, default="manual")
    details = models.JSONField(default=dict)
    checked_at = models.DateTimeField()

    class Meta:
        db_table = "adminops_health_snapshot"
        ordering = ["-checked_at"]
        indexes = [
            models.Index(
                fields=["company", "environment", "service_code", "checked_at"],
                name="adm_health_lookup_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.environment_id and self.environment.company_id != self.company_id:
            raise ValidationError("A health snapshot cannot cross companies")


class Incident(TenantOwnedModel):
    class Severity(models.TextChoices):
        SEV1 = "sev1", "Critical"
        SEV2 = "sev2", "High"
        SEV3 = "sev3", "Medium"
        SEV4 = "sev4", "Low"

    class Status(models.TextChoices):
        IDENTIFIED = "identified", "Identified"
        INVESTIGATING = "investigating", "Investigating"
        MITIGATED = "mitigated", "Mitigated"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"

    environment = models.ForeignKey(
        RuntimeEnvironment,
        on_delete=models.PROTECT,
        related_name="incidents",
    )
    number = models.CharField(max_length=60)
    severity = models.CharField(max_length=10, choices=Severity.choices)
    title = models.CharField(max_length=220)
    summary = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IDENTIFIED)
    owner_membership_public_id = models.UUIDField(null=True, blank=True)
    detected_at = models.DateTimeField()
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    mitigated_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    customer_impact = models.TextField(blank=True)
    root_cause = models.TextField(blank=True)
    corrective_actions = models.JSONField(default=list)
    postmortem_required = models.BooleanField(default=False)
    postmortem_reference = models.CharField(max_length=240, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "adminops_incident"
        ordering = ["-detected_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "number"],
                name="adm_incident_number_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "status", "severity", "detected_at"],
                name="adm_incident_status_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.environment_id and self.environment.company_id != self.company_id:
            raise ValidationError("An incident cannot cross companies")
        missing_postmortem = (
            self.status == self.Status.CLOSED
            and self.postmortem_required
            and not self.postmortem_reference
        )
        if missing_postmortem:
            raise ValidationError("A required postmortem must be recorded before closure")


class Runbook(TenantOwnedModel):
    code = models.CharField(max_length=100)
    title = models.CharField(max_length=220)
    category = models.CharField(max_length=100)
    purpose = models.TextField(blank=True)
    steps = models.JSONField(default=list)
    owner_membership_public_id = models.UUIDField(null=True, blank=True)
    review_due_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "adminops_runbook"
        ordering = ["category", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="adm_runbook_code_uq",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if not isinstance(self.steps, list) or not self.steps:
            raise ValidationError("A runbook requires at least one ordered step")


class FeatureFlag(TenantOwnedModel):
    code = models.CharField(max_length=100)
    name = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    is_enabled = models.BooleanField(default=False)
    rollout_percent = models.PositiveSmallIntegerField(default=0)
    scope = models.JSONField(default=dict)
    requires_approval = models.BooleanField(default=True)
    requested_by_public_id = models.UUIDField(null=True, blank=True)
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "adminops_feature_flag"
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="adm_flag_code_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "is_enabled"],
                name="adm_flag_enabled_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.rollout_percent > 100:
            raise ValidationError("Feature rollout cannot exceed 100 percent")
        if self.is_enabled and self.rollout_percent == 0:
            raise ValidationError("An enabled feature requires a rollout above zero")
        if self.requires_approval and self.is_enabled and not self.approved_by_public_id:
            raise ValidationError(
                "An approval-controlled feature requires approval before enablement"
            )


class MaintenanceWindow(TenantOwnedModel):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        APPROVED = "approved", "Approved"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    environment = models.ForeignKey(
        RuntimeEnvironment,
        on_delete=models.PROTECT,
        related_name="maintenance_windows",
    )
    reference = models.CharField(max_length=80)
    title = models.CharField(max_length=220)
    reason = models.TextField(blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNED)
    affected_services = models.JSONField(default=list)
    requested_by_public_id = models.UUIDField()
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "adminops_maintenance_window"
        ordering = ["-starts_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "reference"],
                name="adm_maint_ref_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "environment", "status", "starts_at"],
                name="adm_maint_status_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.environment_id and self.environment.company_id != self.company_id:
            raise ValidationError("A maintenance window cannot cross companies")
        if self.ends_at <= self.starts_at:
            raise ValidationError("Maintenance end time must be after start time")
        if self.status == self.Status.APPROVED and not self.approved_by_public_id:
            raise ValidationError("An approved maintenance window requires an approver")
