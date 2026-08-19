
from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from modules.platform.models import TenantOwnedModel


class DataClassification(models.TextChoices):
    INTERNAL = "internal", "Internal"
    CONFIDENTIAL = "confidential", "Confidential"
    RESTRICTED = "restricted", "Restricted"


class MetricDefinition(TenantOwnedModel):
    code = models.CharField(max_length=100)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    domain_code = models.CharField(max_length=80)
    calculation_code = models.CharField(max_length=120)
    unit_code = models.CharField(max_length=40, default="count")
    data_classification = models.CharField(
        max_length=20,
        choices=DataClassification.choices,
        default=DataClassification.INTERNAL,
    )
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "reporting_metric_definition"
        ordering = ["domain_code", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code", "version"],
                name="rpt_metric_version_uq",
            ),
            models.UniqueConstraint(
                fields=["company", "code"],
                condition=Q(is_active=True),
                name="rpt_metric_active_uq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "domain_code", "is_active"],
                name="rpt_metric_domain_idx",
            )
        ]


class SavedReport(TenantOwnedModel):
    class Visibility(models.TextChoices):
        PRIVATE = "private", "Private"
        COMPANY = "company", "Company"
        ROLE = "role", "Role"

    class ExportFormat(models.TextChoices):
        CSV = "csv", "CSV"
        XLSX = "xlsx", "Excel"
        PDF = "pdf", "PDF"

    code = models.CharField(max_length=100)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    report_type = models.CharField(max_length=80)
    metric_codes = models.JSONField(default=list)
    filters = models.JSONField(default=dict)
    columns = models.JSONField(default=list)
    visibility = models.CharField(
        max_length=20,
        choices=Visibility.choices,
        default=Visibility.PRIVATE,
    )
    role_public_ids = models.JSONField(default=list)
    owner_user_public_id = models.UUIDField()
    default_export_format = models.CharField(
        max_length=10,
        choices=ExportFormat.choices,
        default=ExportFormat.CSV,
    )
    schedule_expression = models.CharField(max_length=120, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "reporting_saved_report"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="rpt_saved_code_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "is_active", "next_run_at"],
                name="rpt_saved_schedule_idx",
            ),
            models.Index(
                fields=["company", "owner_user_public_id", "visibility"],
                name="rpt_saved_owner_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if not isinstance(self.metric_codes, list) or len(self.metric_codes) > 50:
            raise ValidationError("A saved report supports at most 50 metrics")
        if self.visibility != self.Visibility.ROLE and self.role_public_ids:
            raise ValidationError("Role visibility is required when role IDs are provided")


class ReportRun(TenantOwnedModel):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    saved_report = models.ForeignKey(
        SavedReport,
        on_delete=models.PROTECT,
        related_name="runs",
        null=True,
        blank=True,
    )
    report_code = models.CharField(max_length=100)
    requested_by_public_id = models.UUIDField()
    idempotency_key = models.CharField(max_length=120)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.QUEUED,
    )
    export_format = models.CharField(
        max_length=10,
        choices=SavedReport.ExportFormat.choices,
        default=SavedReport.ExportFormat.CSV,
    )
    parameters = models.JSONField(default=dict, blank=True)
    metric_snapshot = models.JSONField(default=dict)
    row_count = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    error_message = models.CharField(max_length=1000, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "reporting_report_run"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "idempotency_key"],
                name="rpt_run_idempotency_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "status", "created_at"],
                name="rpt_run_status_idx",
            ),
            models.Index(
                fields=["company", "requested_by_public_id", "created_at"],
                name="rpt_run_requester_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.saved_report_id and self.saved_report.company_id != self.company_id:
            raise ValidationError("A report run cannot cross companies")


class ExportArtifact(TenantOwnedModel):
    run = models.OneToOneField(
        ReportRun,
        on_delete=models.PROTECT,
        related_name="artifact",
    )
    file_name = models.CharField(max_length=240)
    content_type = models.CharField(max_length=120)
    sha256 = models.CharField(max_length=64)
    byte_size = models.PositiveBigIntegerField()
    data_classification = models.CharField(
        max_length=20,
        choices=DataClassification.choices,
        default=DataClassification.INTERNAL,
    )
    created_by_public_id = models.UUIDField()
    expires_at = models.DateTimeField()
    download_count = models.PositiveIntegerField(default=0)
    last_downloaded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "reporting_export_artifact"
        indexes = [
            models.Index(
                fields=["company", "expires_at"],
                name="rpt_artifact_expiry_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.run_id and self.run.company_id != self.company_id:
            raise ValidationError("An export artifact cannot cross companies")
