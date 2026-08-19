from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from modules.files.application.storage import (
    create_download_url,
    create_upload_url,
    head_object,
)
from modules.files.models import FileObject, FileVersion
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.tenant.models import Company


@dataclass(frozen=True, slots=True)
class UploadGrant:
    file_object: FileObject
    file_version: FileVersion
    upload_url: str
    expires_in_seconds: int


_ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
    "text/csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain",
    "audio/mpeg",
    "audio/mp4",
    "audio/wav",
    "audio/x-wav",
    "audio/webm",
    "audio/ogg",
    "video/mp4",
    "video/quicktime",
    "video/webm",
}


def _safe_name(name: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", name.strip()).strip(".-")
    return (normalized or "file")[:120]


@transaction.atomic
def initiate_upload(
    *,
    company: Company,
    purpose_code: str,
    data_class: str,
    original_name: str,
    content_type: str,
    size_bytes: int,
    sha256: str,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> UploadGrant:
    if content_type not in _ALLOWED_CONTENT_TYPES:
        raise ValidationError("This file type is not allowed")
    if size_bytes < 1 or size_bytes > settings.FILE_UPLOAD_MAX_BYTES:
        raise ValidationError("File size is outside the allowed range")
    sha256 = sha256.strip().lower()
    if len(sha256) != 64 or any(ch not in "0123456789abcdef" for ch in sha256):
        raise ValidationError("A valid SHA-256 checksum is required")
    file_object = FileObject.objects.create(
        company=company,
        purpose_code=purpose_code,
        data_class=data_class,
        created_by_public_id=actor_public_id,
    )
    object_key = (
        f"companies/{company.public_id}/{purpose_code}/{file_object.public_id}/"
        f"v1/{uuid.uuid4()}-{_safe_name(original_name)}"
    )
    file_version = FileVersion(
        file_object=file_object,
        version=1,
        object_key=object_key,
        original_name=original_name[:255],
        content_type=content_type,
        expected_size_bytes=size_bytes,
        expected_sha256=sha256,
        created_by_public_id=actor_public_id,
    )
    file_version.full_clean()
    file_version.save()
    append_audit(
        AuditRecord(
            action="files.upload.initiated",
            entity_type="file_version",
            entity_public_id=file_version.public_id,
            actor_public_id=actor_public_id,
            company_public_id=company.public_id,
            request_id=correlation_id,
            correlation_id=correlation_id,
            after={
                "file_object_public_id": str(file_object.public_id),
                "purpose_code": purpose_code,
                "content_type": content_type,
                "expected_size_bytes": size_bytes,
            },
        )
    )
    expires = settings.FILE_UPLOAD_URL_TTL_SECONDS
    return UploadGrant(
        file_object=file_object,
        file_version=file_version,
        upload_url=create_upload_url(
            object_key=object_key,
            content_type=content_type,
            sha256=sha256,
            expires_seconds=expires,
        ),
        expires_in_seconds=expires,
    )


def finalize_upload(
    *,
    version_public_id: uuid.UUID,
    company: Company,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> FileVersion:
    rejection_message: str | None = None
    with transaction.atomic():
        version = (
            FileVersion.objects.select_for_update()
            .select_related("file_object")
            .filter(public_id=version_public_id, file_object__company=company)
            .first()
        )
        if not version:
            raise ValidationError("File version was not found")
        if version.upload_status != FileVersion.UploadStatus.INITIATED:
            raise ValidationError("The upload is not awaiting finalization")
        metadata = head_object(object_key=version.object_key)
        if metadata.size_bytes != version.expected_size_bytes:
            version.upload_status = FileVersion.UploadStatus.REJECTED
            version.rejection_reason = "size_mismatch"
            version.actual_size_bytes = metadata.size_bytes
            version.save(
                update_fields=[
                    "upload_status",
                    "rejection_reason",
                    "actual_size_bytes",
                    "updated_at",
                ]
            )
            rejection_message = "Uploaded file size does not match the declared size"
        elif metadata.sha256 != version.expected_sha256:
            version.upload_status = FileVersion.UploadStatus.REJECTED
            version.rejection_reason = "checksum_mismatch"
            version.actual_size_bytes = metadata.size_bytes
            version.actual_sha256 = metadata.sha256
            version.save(
                update_fields=[
                    "upload_status",
                    "rejection_reason",
                    "actual_size_bytes",
                    "actual_sha256",
                    "updated_at",
                ]
            )
            rejection_message = "Uploaded file checksum does not match"
        elif metadata.content_type != version.content_type:
            version.upload_status = FileVersion.UploadStatus.REJECTED
            version.rejection_reason = "content_type_mismatch"
            version.actual_size_bytes = metadata.size_bytes
            version.actual_sha256 = metadata.sha256
            version.save(
                update_fields=[
                    "upload_status",
                    "rejection_reason",
                    "actual_size_bytes",
                    "actual_sha256",
                    "updated_at",
                ]
            )
            rejection_message = "Uploaded file content type does not match"
        else:
            version.upload_status = FileVersion.UploadStatus.FINALIZED
            version.actual_size_bytes = metadata.size_bytes
            version.actual_sha256 = metadata.sha256
            version.finalized_at = timezone.now()
            version.save(
                update_fields=[
                    "upload_status",
                    "actual_size_bytes",
                    "actual_sha256",
                    "finalized_at",
                    "updated_at",
                ]
            )
        action = (
            "files.upload.rejected"
            if rejection_message
            else "files.upload.finalized"
        )
        append_audit(
            AuditRecord(
                action=action,
                entity_type="file_version",
                entity_public_id=version.public_id,
                actor_public_id=actor_public_id,
                company_public_id=company.public_id,
                request_id=correlation_id,
                correlation_id=correlation_id,
                after={
                    "upload_status": version.upload_status,
                    "scan_status": version.scan_status,
                    "rejection_reason": version.rejection_reason,
                },
            )
        )
        if not rejection_message:
            append_event(
                EventRecord(
                    event_type="files.upload_finalized",
                    aggregate_type="file_object",
                    aggregate_public_id=version.file_object.public_id,
                    aggregate_version=version.version,
                    company_public_id=company.public_id,
                    correlation_id=correlation_id,
                    payload={"file_version_public_id": str(version.public_id)},
                )
            )
    if rejection_message:
        raise ValidationError(rejection_message)
    return version


@transaction.atomic
def record_scan_result(
    *,
    version_public_id: uuid.UUID,
    clean: bool,
    scanner_reference: str,
    correlation_id: uuid.UUID,
) -> FileVersion:
    version = (
        FileVersion.objects.select_for_update()
        .select_related("file_object", "file_object__company")
        .filter(public_id=version_public_id, upload_status=FileVersion.UploadStatus.FINALIZED)
        .first()
    )
    if not version:
        raise ValidationError("Finalized file version was not found")
    if version.scan_status != FileVersion.ScanStatus.PENDING:
        raise ValidationError("The file scan has already been completed")
    version.scan_status = FileVersion.ScanStatus.CLEAN if clean else FileVersion.ScanStatus.INFECTED
    version.scan_completed_at = timezone.now()
    version.save(update_fields=["scan_status", "scan_completed_at", "updated_at"])
    if not clean:
        version.file_object.status = FileObject.Status.QUARANTINED
        version.file_object.save(update_fields=["status", "updated_at"])
    append_audit(
        AuditRecord(
            action="files.scan.completed",
            entity_type="file_version",
            entity_public_id=version.public_id,
            actor_type="service",
            company_public_id=version.file_object.company.public_id,
            request_id=correlation_id,
            correlation_id=correlation_id,
            after={
                "scan_status": version.scan_status,
                "scanner_reference": scanner_reference[:100],
            },
        )
    )
    append_event(
        EventRecord(
            event_type="files.scan_completed",
            aggregate_type="file_object",
            aggregate_public_id=version.file_object.public_id,
            aggregate_version=version.version + 1,
            company_public_id=version.file_object.company.public_id,
            correlation_id=correlation_id,
            payload={"scan_status": version.scan_status},
        )
    )
    return version


def governed_download_url(*, file_object: FileObject) -> tuple[FileVersion, str]:
    version = file_object.versions.filter(
        upload_status=FileVersion.UploadStatus.FINALIZED,
        scan_status=FileVersion.ScanStatus.CLEAN,
    ).order_by("-version").first()
    if not version or file_object.status != FileObject.Status.ACTIVE:
        raise ValidationError("File is not available for download")
    return version, create_download_url(
        object_key=version.object_key,
        expires_seconds=settings.FILE_DOWNLOAD_URL_TTL_SECONDS,
    )
