
from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from modules.platform.models import TenantOwnedModel


class ImportTemplate(TenantOwnedModel):
    code = models.CharField(max_length=100)
    name = models.CharField(max_length=200)
    destination_code = models.CharField(max_length=100)
    version = models.PositiveIntegerField(default=1)
    schema = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "dataops_import_template"
        ordering = ["name", "-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code", "version"],
                name="dop_template_version_uq",
            ),
            models.UniqueConstraint(
                fields=["company", "code"],
                condition=Q(is_active=True),
                name="dop_template_active_uq",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.destination_code not in {"projects.project", "vendor.vendor"}:
            raise ValidationError("Unsupported import destination")
        if not isinstance(self.schema, dict):
            raise ValidationError("Import template schema must be an object")


class ImportJob(TenantOwnedModel):
    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        VALIDATED = "validated", "Validated"
        INVALID = "invalid", "Invalid"
        COMMITTING = "committing", "Committing"
        COMMITTED = "committed", "Committed"
        PARTIAL = "partial", "Partially committed"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    template = models.ForeignKey(
        ImportTemplate,
        on_delete=models.PROTECT,
        related_name="jobs",
    )
    source_name = models.CharField(max_length=240)
    source_sha256 = models.CharField(max_length=64)
    idempotency_key = models.CharField(max_length=120)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.UPLOADED,
    )
    requested_by_public_id = models.UUIDField()
    total_rows = models.PositiveIntegerField(default=0)
    valid_rows = models.PositiveIntegerField(default=0)
    error_rows = models.PositiveIntegerField(default=0)
    committed_rows = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    result_summary = models.JSONField(default=dict)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "dataops_import_job"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "idempotency_key"],
                name="dop_job_idempotency_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "status", "created_at"],
                name="dop_job_status_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.template_id and self.template.company_id != self.company_id:
            raise ValidationError("An import job cannot cross companies")


class ImportStagingRow(TenantOwnedModel):
    class Status(models.TextChoices):
        VALID = "valid", "Valid"
        ERROR = "error", "Error"
        COMMITTED = "committed", "Committed"
        SKIPPED = "skipped", "Skipped"

    job = models.ForeignKey(
        ImportJob,
        on_delete=models.PROTECT,
        related_name="rows",
    )
    row_number = models.PositiveIntegerField()
    payload = models.JSONField(default=dict)
    normalized_payload = models.JSONField(default=dict)
    row_sha256 = models.CharField(max_length=64)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.VALID,
    )
    target_public_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "dataops_import_row"
        ordering = ["row_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "job", "row_number"],
                name="dop_row_number_uq",
            ),
            models.UniqueConstraint(
                fields=["company", "job", "row_sha256"],
                name="dop_row_hash_uq",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.job_id and self.job.company_id != self.company_id:
            raise ValidationError("An import row cannot cross companies")


class ImportRowError(TenantOwnedModel):
    row = models.ForeignKey(
        ImportStagingRow,
        on_delete=models.PROTECT,
        related_name="errors",
    )
    field_name = models.CharField(max_length=120, blank=True)
    error_code = models.CharField(max_length=100)
    message = models.CharField(max_length=500)
    masked_value = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = "dataops_import_row_error"
        indexes = [
            models.Index(
                fields=["company", "row", "error_code"],
                name="dop_row_error_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.row_id and self.row.company_id != self.company_id:
            raise ValidationError("An import error cannot cross companies")


class PrivacyRequest(TenantOwnedModel):
    class RequestType(models.TextChoices):
        ACCESS = "access", "Access"
        RECTIFICATION = "rectification", "Rectification"
        DELETION = "deletion", "Deletion"
        RESTRICTION = "restriction", "Restriction"

    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        VERIFYING = "verifying", "Verifying identity"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    request_number = models.CharField(max_length=80)
    request_type = models.CharField(max_length=30, choices=RequestType.choices)
    subject_type = models.CharField(max_length=80)
    subject_public_id = models.UUIDField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RECEIVED,
    )
    requested_by_public_id = models.UUIDField()
    assigned_to_public_id = models.UUIDField(null=True, blank=True)
    due_at = models.DateTimeField()
    verified_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    resolution_summary = models.TextField(blank=True)
    reason_code = models.CharField(max_length=100, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "dataops_privacy_request"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "request_number"],
                name="dop_privacy_number_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "status", "due_at"],
                name="dop_privacy_due_idx",
            ),
            models.Index(
                fields=["company", "subject_type", "subject_public_id"],
                name="dop_privacy_subject_idx",
            ),
        ]


class RetentionPolicy(TenantOwnedModel):
    record_type = models.CharField(max_length=120)
    retention_days = models.PositiveIntegerField()
    legal_hold_default = models.BooleanField(default=False)
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "dataops_retention_policy"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "record_type", "version"],
                name="dop_retention_version_uq",
            ),
            models.UniqueConstraint(
                fields=["company", "record_type"],
                condition=Q(is_active=True),
                name="dop_retention_active_uq",
            ),
            models.CheckConstraint(
                condition=Q(retention_days__gte=1),
                name="dop_retention_days_ok",
            ),
            models.CheckConstraint(
                condition=Q(effective_to__isnull=True) | Q(effective_to__gt=models.F("effective_from")),
                name="dop_retention_range_ok",
            ),
        ]


class RecoveryVerification(TenantOwnedModel):
    class Scope(models.TextChoices):
        BACKUP = "backup", "Backup"
        RESTORE = "restore", "Restore"
        ROLLBACK = "rollback", "Rollback"

    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        RUNNING = "running", "Running"
        PASSED = "passed", "Passed"
        FAILED = "failed", "Failed"

    reference = models.CharField(max_length=120)
    scope = models.CharField(max_length=20, choices=Scope.choices)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PLANNED,
    )
    target_rpo_minutes = models.PositiveIntegerField()
    measured_rpo_minutes = models.PositiveIntegerField(null=True, blank=True)
    target_rto_minutes = models.PositiveIntegerField()
    measured_rto_minutes = models.PositiveIntegerField(null=True, blank=True)
    evidence_summary = models.TextField(blank=True)
    performed_by_public_id = models.UUIDField()
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "dataops_recovery_verification"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "reference"],
                name="dop_recovery_reference_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "status", "created_at"],
                name="dop_recovery_status_idx",
            )
        ]
