from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from modules.platform.models import TenantOwnedModel

_SHA256_CHARS = frozenset("0123456789abcdef")


def _validate_sha256(value: str, field_name: str) -> None:
    normalized = value.lower()
    if len(normalized) != 64 or any(char not in _SHA256_CHARS for char in normalized):
        raise ValidationError({field_name: "A SHA-256 digest is required"})


class CloudTarget(TenantOwnedModel):
    class Provider(models.TextChoices):
        GENERIC = "generic", "Provider neutral"
        AWS = "aws", "Amazon Web Services"
        AZURE = "azure", "Microsoft Azure"
        GCP = "gcp", "Google Cloud"
        RENDER = "render", "Render"
        VERCEL = "vercel", "Vercel"
        CLOUDFLARE = "cloudflare", "Cloudflare"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        READY = "ready", "Ready"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        RETIRED = "retired", "Retired"

    environment = models.ForeignKey(
        "adminops.RuntimeEnvironment",
        on_delete=models.PROTECT,
        related_name="cloud_targets",
    )
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=180)
    provider = models.CharField(max_length=24, choices=Provider.choices)
    region = models.CharField(max_length=100)
    data_residency = models.CharField(max_length=100)
    backend_service = models.CharField(max_length=160, blank=True)
    frontend_service = models.CharField(max_length=160, blank=True)
    database_service = models.CharField(max_length=160, blank=True)
    cache_service = models.CharField(max_length=160, blank=True)
    object_storage_service = models.CharField(max_length=160, blank=True)
    worker_service = models.CharField(max_length=160, blank=True)
    secret_manager_service = models.CharField(max_length=160, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    production_approved = models.BooleanField(default=False)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "cloudops_target"
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="cld_target_code_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "status", "provider"],
                name="cld_target_status_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.environment_id and self.environment.company_id != self.company_id:
            raise ValidationError("A cloud target cannot use another company's environment")
        if self.status == self.Status.ACTIVE and not self.backend_service:
            raise ValidationError("An active cloud target requires a backend service")
        is_production = (
            self.environment_id
            and self.environment.environment_type == "production"
        )
        if is_production and self.status == self.Status.ACTIVE and not self.production_approved:
            raise ValidationError("An active production target requires explicit approval")


class DeploymentPipeline(TenantOwnedModel):
    class TriggerMode(models.TextChoices):
        MANUAL = "manual", "Manual"
        PUSH = "push", "Source push"
        TAG = "tag", "Release tag"

    target = models.ForeignKey(
        CloudTarget,
        on_delete=models.PROTECT,
        related_name="pipelines",
    )
    code = models.CharField(max_length=100)
    name = models.CharField(max_length=180)
    source_branch = models.CharField(max_length=160, default="main")
    trigger_mode = models.CharField(
        max_length=20,
        choices=TriggerMode.choices,
        default=TriggerMode.MANUAL,
    )
    quality_gates = models.JSONField(default=list)
    requires_approval = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "cloudops_pipeline"
        ordering = ["target__code", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["target", "code"],
                name="cld_pipeline_code_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "is_active", "trigger_mode"],
                name="cld_pipeline_active_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.target_id and self.target.company_id != self.company_id:
            raise ValidationError("A deployment pipeline cannot cross companies")
        if not isinstance(self.quality_gates, list):
            raise ValidationError({"quality_gates": "Quality gates must be a list"})
        invalid = [item for item in self.quality_gates if not isinstance(item, str)]
        if invalid:
            raise ValidationError({"quality_gates": "Every quality gate must be a string"})


class DeploymentExecution(TenantOwnedModel):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        VALIDATED = "validated", "Validated"
        APPROVED = "approved", "Approved"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        ROLLED_BACK = "rolled_back", "Rolled back"

    pipeline = models.ForeignKey(
        DeploymentPipeline,
        on_delete=models.PROTECT,
        related_name="executions",
    )
    release = models.ForeignKey(
        "adminops.ReleaseRecord",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cloud_deployments",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.REQUESTED,
    )
    source_revision = models.CharField(max_length=160)
    artifact_sha256 = models.CharField(max_length=64)
    migration_plan_sha256 = models.CharField(max_length=64, blank=True)
    deployment_url = models.URLField(blank=True)
    requested_by_public_id = models.UUIDField()
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    executed_by_public_id = models.UUIDField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    logs_sha256 = models.CharField(max_length=64, blank=True)
    error_summary = models.CharField(max_length=1000, blank=True)
    rollback_reference = models.CharField(max_length=500, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "cloudops_deployment"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["company", "status", "created_at"],
                name="cld_deploy_status_idx",
            ),
            models.Index(
                fields=["pipeline", "created_at"],
                name="cld_deploy_pipe_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.pipeline_id and self.pipeline.company_id != self.company_id:
            raise ValidationError("A deployment execution cannot cross companies")
        if self.release_id and self.release.company_id != self.company_id:
            raise ValidationError("A deployment cannot reference another company's release")
        _validate_sha256(self.artifact_sha256, "artifact_sha256")
        if self.migration_plan_sha256:
            _validate_sha256(self.migration_plan_sha256, "migration_plan_sha256")
        if self.logs_sha256:
            _validate_sha256(self.logs_sha256, "logs_sha256")
        if self.status == self.Status.SUCCEEDED and not self.deployment_url:
            raise ValidationError("A successful deployment requires a deployment URL")
        if self.status == self.Status.FAILED and not self.error_summary:
            raise ValidationError("A failed deployment requires an error summary")
        if self.status == self.Status.ROLLED_BACK and not self.rollback_reference:
            raise ValidationError("A rolled-back deployment requires rollback evidence")


class BackupPolicy(TenantOwnedModel):
    class ResourceType(models.TextChoices):
        DATABASE = "database", "PostgreSQL database"
        OBJECT_STORAGE = "object_storage", "Object storage"
        CONFIGURATION = "configuration", "Configuration and secrets inventory"
        FULL = "full", "Full platform backup"

    target = models.ForeignKey(
        CloudTarget,
        on_delete=models.PROTECT,
        related_name="backup_policies",
    )
    code = models.CharField(max_length=100)
    name = models.CharField(max_length=180)
    resource_type = models.CharField(max_length=24, choices=ResourceType.choices)
    schedule_cron = models.CharField(max_length=100)
    retention_days = models.PositiveIntegerField(default=30)
    encryption_required = models.BooleanField(default=True)
    point_in_time_recovery = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "cloudops_backup_policy"
        ordering = ["target__code", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["target", "code"],
                name="cld_backup_policy_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "is_active", "resource_type"],
                name="cld_backup_active_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.target_id and self.target.company_id != self.company_id:
            raise ValidationError("A backup policy cannot cross companies")
        if not 1 <= self.retention_days <= 3650:
            raise ValidationError("Backup retention must be between 1 and 3650 days")
        if len(self.schedule_cron.split()) not in {5, 6}:
            raise ValidationError("A five-part or six-part cron expression is required")


class BackupExecution(TenantOwnedModel):
    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        VERIFIED = "verified", "Verified"

    policy = models.ForeignKey(
        BackupPolicy,
        on_delete=models.PROTECT,
        related_name="executions",
    )
    status = models.CharField(max_length=20, choices=Status.choices)
    backup_reference = models.CharField(max_length=500, blank=True)
    backup_sha256 = models.CharField(max_length=64, blank=True)
    size_bytes = models.PositiveBigIntegerField(default=0)
    recovery_point_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)
    evidence_sha256 = models.CharField(max_length=64, blank=True)
    error_summary = models.CharField(max_length=1000, blank=True)

    class Meta:
        db_table = "cloudops_backup_execution"
        ordering = ["-started_at"]
        indexes = [
            models.Index(
                fields=["company", "status", "started_at"],
                name="cld_backup_run_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.policy_id and self.policy.company_id != self.company_id:
            raise ValidationError("A backup execution cannot cross companies")
        if self.backup_sha256:
            _validate_sha256(self.backup_sha256, "backup_sha256")
        if self.evidence_sha256:
            _validate_sha256(self.evidence_sha256, "evidence_sha256")
        if self.status in {self.Status.SUCCEEDED, self.Status.VERIFIED}:
            if not self.backup_reference or not self.backup_sha256:
                raise ValidationError("A successful backup requires reference and digest")
            if self.finished_at is None:
                raise ValidationError("A completed backup requires a finish timestamp")
        if self.status == self.Status.FAILED and not self.error_summary:
            raise ValidationError("A failed backup requires an error summary")


class RestoreExercise(TenantOwnedModel):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        RUNNING = "running", "Running"
        PASSED = "passed", "Passed"
        FAILED = "failed", "Failed"
        APPROVED = "approved", "Approved"

    target = models.ForeignKey(
        CloudTarget,
        on_delete=models.PROTECT,
        related_name="restore_exercises",
    )
    backup_execution = models.ForeignKey(
        BackupExecution,
        on_delete=models.PROTECT,
        related_name="restore_exercises",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PLANNED,
    )
    requested_by_public_id = models.UUIDField()
    reviewed_by_public_id = models.UUIDField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    measured_rpo_minutes = models.PositiveIntegerField(null=True, blank=True)
    measured_rto_minutes = models.PositiveIntegerField(null=True, blank=True)
    evidence_sha256 = models.CharField(max_length=64, blank=True)
    notes = models.CharField(max_length=1000, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "cloudops_restore_exercise"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["company", "status", "created_at"],
                name="cld_restore_status_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.target_id and self.target.company_id != self.company_id:
            raise ValidationError("A restore exercise cannot cross companies")
        if (
            self.backup_execution_id
            and self.backup_execution.company_id != self.company_id
        ):
            raise ValidationError("A restore exercise cannot use another company's backup")
        if self.evidence_sha256:
            _validate_sha256(self.evidence_sha256, "evidence_sha256")
        if self.status in {self.Status.PASSED, self.Status.APPROVED}:
            if self.measured_rpo_minutes is None or self.measured_rto_minutes is None:
                raise ValidationError("A passed restore exercise requires measured RPO and RTO")
            if not self.evidence_sha256:
                raise ValidationError("A passed restore exercise requires evidence")
        if self.status == self.Status.APPROVED and not self.reviewed_by_public_id:
            raise ValidationError("An approved restore exercise requires an independent reviewer")


class SecretRotationPolicy(TenantOwnedModel):
    class Status(models.TextChoices):
        CURRENT = "current", "Current"
        DUE = "due", "Due"
        OVERDUE = "overdue", "Overdue"
        SUSPENDED = "suspended", "Suspended"

    target = models.ForeignKey(
        CloudTarget,
        on_delete=models.PROTECT,
        related_name="secret_policies",
    )
    code = models.CharField(max_length=100)
    name = models.CharField(max_length=180)
    secret_provider = models.CharField(max_length=100)
    secret_reference = models.CharField(max_length=500)
    rotation_interval_days = models.PositiveIntegerField(default=90)
    last_rotated_at = models.DateTimeField(null=True, blank=True)
    next_rotation_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DUE,
    )
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "cloudops_secret_policy"
        ordering = ["target__code", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["target", "code"],
                name="cld_secret_policy_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "status", "next_rotation_at"],
                name="cld_secret_due_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.target_id and self.target.company_id != self.company_id:
            raise ValidationError("A secret policy cannot cross companies")
        if not 1 <= self.rotation_interval_days <= 730:
            raise ValidationError("Secret rotation must be between 1 and 730 days")
        normalized_reference = self.secret_reference.strip()
        allowed_prefixes = ("env://", "vault://", "secret://", "arn:", "projects/")
        if (
            not normalized_reference.startswith(allowed_prefixes)
            or "=" in normalized_reference
            or "\n" in normalized_reference
            or "begin private key" in normalized_reference.lower()
        ):
            raise ValidationError(
                "Store only a secret-manager reference, never a raw secret value"
            )
