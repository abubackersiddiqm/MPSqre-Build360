from django.core.exceptions import ValidationError
from django.db import models

from modules.platform.models import PublicIdModel, TimestampedModel
from modules.tenant.models import Company


class FileObject(PublicIdModel, TimestampedModel):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        DELETED = "DELETED", "Deleted"
        QUARANTINED = "QUARANTINED", "Quarantined"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="file_objects",
    )
    purpose_code = models.CharField(max_length=100)
    data_class = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    created_by_public_id = models.UUIDField()

    class Meta:
        db_table = "files_file_object"
        indexes = [
            models.Index(
                fields=["company", "purpose_code", "status"],
                name="files_company_purpose_idx",
            )
        ]


class FileVersion(PublicIdModel, TimestampedModel):
    class UploadStatus(models.TextChoices):
        INITIATED = "INITIATED", "Initiated"
        UPLOADED = "UPLOADED", "Uploaded"
        FINALIZED = "FINALIZED", "Finalized"
        REJECTED = "REJECTED", "Rejected"

    class ScanStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CLEAN = "CLEAN", "Clean"
        INFECTED = "INFECTED", "Infected"
        FAILED = "FAILED", "Failed"

    file_object = models.ForeignKey(
        FileObject,
        on_delete=models.PROTECT,
        related_name="versions",
    )
    version = models.PositiveIntegerField()
    object_key = models.CharField(max_length=700, unique=True)
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=150)
    expected_size_bytes = models.PositiveBigIntegerField()
    actual_size_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    expected_sha256 = models.CharField(max_length=64)
    actual_sha256 = models.CharField(max_length=64, blank=True)
    upload_status = models.CharField(
        max_length=20,
        choices=UploadStatus.choices,
        default=UploadStatus.INITIATED,
    )
    scan_status = models.CharField(
        max_length=20,
        choices=ScanStatus.choices,
        default=ScanStatus.PENDING,
    )
    created_by_public_id = models.UUIDField()
    finalized_at = models.DateTimeField(null=True, blank=True)
    scan_completed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = "files_file_version"
        constraints = [
            models.UniqueConstraint(
                fields=["file_object", "version"],
                name="files_object_version_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(actual_size_bytes__isnull=True)
                | models.Q(actual_size_bytes__gte=0),
                name="files_actual_size_nonnegative",
            ),
        ]
        indexes = [
            models.Index(
                fields=["file_object", "upload_status", "scan_status"],
                name="files_version_state_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        for field_name in ["expected_sha256", "actual_sha256"]:
            value = getattr(self, field_name)
            if value and (len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value)):
                raise ValidationError({field_name: "SHA-256 must be lowercase hexadecimal"})
