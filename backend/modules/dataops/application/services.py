
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from modules.dataops.models import (
    ImportJob,
    ImportRowError,
    ImportStagingRow,
    ImportTemplate,
    PrivacyRequest,
    RecoveryVerification,
    RetentionPolicy,
)
from modules.platform.actors import RequestActor
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.projects.application.services import create_project
from modules.tenant.models import Company
from modules.vendor.application.services import create_vendor


def _record(
    *,
    company: Company,
    actor: RequestActor,
    action: str,
    entity_type: str,
    entity_public_id: uuid.UUID,
    version: int,
    payload: dict[str, Any],
) -> None:
    append_audit(
        AuditRecord(
            action=action,
            entity_type=entity_type,
            entity_public_id=entity_public_id,
            actor_public_id=actor.user_public_id,
            company_public_id=company.public_id,
            request_id=actor.request_id,
            correlation_id=actor.request_id,
            ip_address=actor.ip_address,
            user_agent=actor.user_agent,
            after=payload,
        )
    )
    append_event(
        EventRecord(
            event_type=action,
            aggregate_type=entity_type,
            aggregate_public_id=entity_public_id,
            aggregate_version=version,
            company_public_id=company.public_id,
            correlation_id=actor.request_id,
            payload=payload,
        )
    )


def dataops_summary(company: Company) -> dict[str, int]:
    now = timezone.now()
    return {
        "active_templates": ImportTemplate.objects.filter(company=company, is_active=True).count(),
        "pending_imports": ImportJob.objects.filter(
            company=company,
            status__in=[ImportJob.Status.UPLOADED, ImportJob.Status.VALIDATED, ImportJob.Status.COMMITTING],
        ).count(),
        "open_privacy_requests": PrivacyRequest.objects.filter(
            company=company,
            status__in=[
                PrivacyRequest.Status.RECEIVED,
                PrivacyRequest.Status.VERIFYING,
                PrivacyRequest.Status.IN_PROGRESS,
            ],
        ).count(),
        "overdue_privacy_requests": PrivacyRequest.objects.filter(
            company=company,
            due_at__lt=now,
            status__in=[
                PrivacyRequest.Status.RECEIVED,
                PrivacyRequest.Status.VERIFYING,
                PrivacyRequest.Status.IN_PROGRESS,
            ],
        ).count(),
        "active_retention_policies": RetentionPolicy.objects.filter(
            company=company,
            is_active=True,
        ).count(),
        "recovery_checks_passed": RecoveryVerification.objects.filter(
            company=company,
            status=RecoveryVerification.Status.PASSED,
        ).count(),
    }


def _mask(value: object) -> str:
    text = str(value)
    if len(text) <= 4:
        return "*" * len(text)
    return text[:2] + "*" * min(len(text) - 4, 20) + text[-2:]


def _normalize_field(value: object, field_type: str) -> object:
    if field_type == "string":
        return str(value).strip()
    if field_type == "upper_string":
        return str(value).strip().upper()
    if field_type == "decimal":
        try:
            return str(Decimal(str(value)))
        except (InvalidOperation, ValueError) as exc:
            raise ValidationError("Value must be a decimal number") from exc
    if field_type == "list":
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [item.strip() for item in str(value).split(",") if item.strip()]
    raise ValidationError(f"Unsupported field type: {field_type}")


def validate_import_row(template: ImportTemplate, payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    fields = template.schema.get("fields", []) if isinstance(template.schema, dict) else []
    normalized: dict[str, Any] = {}
    errors: list[dict[str, str]] = []
    allowed_names = {str(field.get("name")) for field in fields if isinstance(field, dict)}
    unknown = sorted(set(payload) - allowed_names)
    for name in unknown:
        errors.append({
            "field_name": name,
            "error_code": "unknown_field",
            "message": "Field is not allowed by the import template",
            "masked_value": _mask(payload.get(name, "")),
        })
    for field in fields:
        if not isinstance(field, dict):
            continue
        name = str(field.get("name", ""))
        required = bool(field.get("required", False))
        field_type = str(field.get("type", "string"))
        value = payload.get(name)
        if value in (None, ""):
            if required:
                errors.append({
                    "field_name": name,
                    "error_code": "required",
                    "message": "Required value is missing",
                    "masked_value": "",
                })
            continue
        try:
            normalized[name] = _normalize_field(value, field_type)
        except ValidationError as exc:
            errors.append({
                "field_name": name,
                "error_code": "invalid_type",
                "message": "; ".join(exc.messages),
                "masked_value": _mask(value),
            })
    return normalized, errors


@transaction.atomic
def create_import_job(
    *,
    company: Company,
    actor: RequestActor,
    template_public_id: uuid.UUID,
    source_name: str,
    idempotency_key: str,
    rows: list[dict[str, Any]],
) -> ImportJob:
    existing = ImportJob.objects.filter(company=company, idempotency_key=idempotency_key).first()
    if existing is not None:
        return existing
    template = ImportTemplate.objects.filter(
        company=company,
        public_id=template_public_id,
        is_active=True,
    ).first()
    if template is None:
        raise ValidationError("Import template was not found")
    max_rows = int(template.schema.get("max_rows", 500))
    if not rows or len(rows) > min(max_rows, 500):
        raise ValidationError(f"Import requires 1 to {min(max_rows, 500)} rows")
    canonical = json.dumps(rows, sort_keys=True, separators=(",", ":"), default=str).encode()
    job = ImportJob.objects.create(
        company=company,
        template=template,
        source_name=source_name.strip(),
        source_sha256=hashlib.sha256(canonical).hexdigest(),
        idempotency_key=idempotency_key.strip(),
        requested_by_public_id=actor.user_public_id,
        total_rows=len(rows),
        started_at=timezone.now(),
    )
    valid_rows = 0
    error_rows = 0
    for row_number, payload in enumerate(rows, start=1):
        if not isinstance(payload, dict):
            payload = {"value": payload}
        normalized, errors = validate_import_row(template, payload)
        row_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
        ).hexdigest()
        staging = ImportStagingRow.objects.create(
            company=company,
            job=job,
            row_number=row_number,
            payload=payload,
            normalized_payload=normalized,
            row_sha256=row_hash,
            status=ImportStagingRow.Status.ERROR if errors else ImportStagingRow.Status.VALID,
        )
        if errors:
            error_rows += 1
            for error in errors:
                ImportRowError.objects.create(company=company, row=staging, **error)
        else:
            valid_rows += 1
    job.valid_rows = valid_rows
    job.error_rows = error_rows
    job.status = ImportJob.Status.VALIDATED if not error_rows else ImportJob.Status.INVALID
    job.completed_at = timezone.now()
    job.result_summary = {"preview_complete": True, "valid_rows": valid_rows, "error_rows": error_rows}
    job.version += 1
    job.save()
    _record(
        company=company,
        actor=actor,
        action="dataops.import.validated",
        entity_type="import_job",
        entity_public_id=job.public_id,
        version=job.version,
        payload={"total_rows": job.total_rows, "valid_rows": valid_rows, "error_rows": error_rows},
    )
    return job


def _commit_row(*, company: Company, actor: RequestActor, template: ImportTemplate, payload: dict[str, Any]) -> uuid.UUID:
    if template.destination_code == "projects.project":
        item = create_project(
            company=company,
            actor=actor,
            code=str(payload["code"]),
            name=str(payload["name"]),
            description=str(payload.get("description", "")),
            currency=str(payload.get("currency", company.currency)),
            approved_budget=Decimal(str(payload.get("approved_budget", "0"))),
        )
        return item.public_id
    if template.destination_code == "vendor.vendor":
        item = create_vendor(
            company=company,
            actor=actor,
            code=str(payload["code"]),
            legal_name=str(payload["legal_name"]),
            display_name=str(payload.get("display_name", payload["legal_name"])),
            categories=list(payload.get("categories", [])),
            service_regions=list(payload.get("service_regions", [])),
        )
        return item.public_id
    raise ValidationError("Import destination is not supported")


@transaction.atomic
def commit_import_job(
    *,
    company: Company,
    actor: RequestActor,
    job_public_id: uuid.UUID,
    expected_version: int,
    allow_partial: bool = False,
) -> ImportJob:
    job = (
        ImportJob.objects.select_for_update()
        .select_related("template")
        .filter(company=company, public_id=job_public_id)
        .first()
    )
    if job is None:
        raise ValidationError("Import job was not found")
    if job.version != expected_version:
        raise ValidationError("Import job changed; refresh before retrying")
    if job.status in {ImportJob.Status.COMMITTED, ImportJob.Status.PARTIAL}:
        return job
    if job.error_rows and not allow_partial:
        raise ValidationError("Import preview contains errors; enable partial commit or correct the rows")
    job.status = ImportJob.Status.COMMITTING
    job.started_at = timezone.now()
    job.version += 1
    job.save()
    committed = 0
    failed = 0
    for row in job.rows.select_for_update().filter(status=ImportStagingRow.Status.VALID).order_by("row_number"):
        try:
            with transaction.atomic():
                target_id = _commit_row(
                    company=company,
                    actor=actor,
                    template=job.template,
                    payload=row.normalized_payload,
                )
            row.target_public_id = target_id
            row.status = ImportStagingRow.Status.COMMITTED
            row.save(update_fields=["target_public_id", "status", "updated_at"])
            committed += 1
        except (ValidationError, IntegrityError) as exc:
            row.status = ImportStagingRow.Status.ERROR
            row.save(update_fields=["status", "updated_at"])
            ImportRowError.objects.create(
                company=company,
                row=row,
                error_code="commit_failed",
                message=str(exc)[:500],
            )
            failed += 1
    job.committed_rows += committed
    job.error_rows += failed
    job.status = ImportJob.Status.COMMITTED if not job.error_rows else ImportJob.Status.PARTIAL
    job.completed_at = timezone.now()
    job.result_summary = {
        "preview_complete": True,
        "committed_rows": job.committed_rows,
        "error_rows": job.error_rows,
    }
    job.version += 1
    job.save()
    _record(
        company=company,
        actor=actor,
        action="dataops.import.committed",
        entity_type="import_job",
        entity_public_id=job.public_id,
        version=job.version,
        payload={"committed_rows": committed, "failed_rows": failed, "status": job.status},
    )
    return job


@transaction.atomic
def create_privacy_request(
    *,
    company: Company,
    actor: RequestActor,
    request_number: str,
    request_type: str,
    subject_type: str,
    subject_public_id: uuid.UUID,
    due_in_days: int = 30,
) -> PrivacyRequest:
    if due_in_days < 1 or due_in_days > 90:
        raise ValidationError("Privacy request due date must be within 1 to 90 days")
    item = PrivacyRequest(
        company=company,
        request_number=request_number.strip().upper(),
        request_type=request_type,
        subject_type=subject_type.strip().lower(),
        subject_public_id=subject_public_id,
        requested_by_public_id=actor.user_public_id,
        due_at=timezone.now() + timedelta(days=due_in_days),
    )
    item.full_clean()
    item.save()
    _record(
        company=company,
        actor=actor,
        action="dataops.privacy.received",
        entity_type="privacy_request",
        entity_public_id=item.public_id,
        version=item.version,
        payload={"request_number": item.request_number, "request_type": item.request_type},
    )
    return item


@transaction.atomic
def resolve_privacy_request(
    *,
    company: Company,
    actor: RequestActor,
    request_public_id: uuid.UUID,
    expected_version: int,
    status: str,
    resolution_summary: str,
    reason_code: str = "",
) -> PrivacyRequest:
    item = PrivacyRequest.objects.select_for_update().filter(
        company=company,
        public_id=request_public_id,
    ).first()
    if item is None:
        raise ValidationError("Privacy request was not found")
    if item.version != expected_version:
        raise ValidationError("Privacy request changed; refresh before retrying")
    if status not in {PrivacyRequest.Status.COMPLETED, PrivacyRequest.Status.REJECTED, PrivacyRequest.Status.CANCELLED}:
        raise ValidationError("Privacy resolution status is invalid")
    item.status = status
    item.resolution_summary = resolution_summary.strip()
    item.reason_code = reason_code.strip()
    item.completed_at = timezone.now()
    item.version += 1
    item.full_clean()
    item.save()
    _record(
        company=company,
        actor=actor,
        action="dataops.privacy.resolved",
        entity_type="privacy_request",
        entity_public_id=item.public_id,
        version=item.version,
        payload={"status": item.status, "reason_code": item.reason_code},
    )
    return item


@transaction.atomic
def create_retention_policy(
    *,
    company: Company,
    actor: RequestActor,
    record_type: str,
    retention_days: int,
    legal_hold_default: bool = False,
) -> RetentionPolicy:
    RetentionPolicy.objects.filter(
        company=company,
        record_type=record_type.strip().lower(),
        is_active=True,
    ).update(is_active=False, effective_to=timezone.now())
    latest = RetentionPolicy.objects.filter(
        company=company,
        record_type=record_type.strip().lower(),
    ).order_by("-version").first()
    item = RetentionPolicy(
        company=company,
        record_type=record_type.strip().lower(),
        retention_days=retention_days,
        legal_hold_default=legal_hold_default,
        effective_from=timezone.now(),
        version=(latest.version + 1) if latest else 1,
    )
    item.full_clean()
    item.save()
    _record(
        company=company,
        actor=actor,
        action="dataops.retention.published",
        entity_type="retention_policy",
        entity_public_id=item.public_id,
        version=item.version,
        payload={"record_type": item.record_type, "retention_days": item.retention_days},
    )
    return item


@transaction.atomic
def create_recovery_verification(
    *,
    company: Company,
    actor: RequestActor,
    reference: str,
    scope: str,
    target_rpo_minutes: int,
    target_rto_minutes: int,
) -> RecoveryVerification:
    item = RecoveryVerification(
        company=company,
        reference=reference.strip().upper(),
        scope=scope,
        target_rpo_minutes=target_rpo_minutes,
        target_rto_minutes=target_rto_minutes,
        performed_by_public_id=actor.user_public_id,
    )
    item.full_clean()
    item.save()
    _record(
        company=company,
        actor=actor,
        action="dataops.recovery.planned",
        entity_type="recovery_verification",
        entity_public_id=item.public_id,
        version=item.version,
        payload={"reference": item.reference, "scope": item.scope},
    )
    return item


@transaction.atomic
def complete_recovery_verification(
    *,
    company: Company,
    actor: RequestActor,
    verification_public_id: uuid.UUID,
    expected_version: int,
    measured_rpo_minutes: int,
    measured_rto_minutes: int,
    evidence_summary: str,
) -> RecoveryVerification:
    item = RecoveryVerification.objects.select_for_update().filter(
        company=company,
        public_id=verification_public_id,
    ).first()
    if item is None:
        raise ValidationError("Recovery verification was not found")
    if item.version != expected_version:
        raise ValidationError("Recovery verification changed; refresh before retrying")
    item.measured_rpo_minutes = measured_rpo_minutes
    item.measured_rto_minutes = measured_rto_minutes
    item.evidence_summary = evidence_summary.strip()
    item.started_at = item.started_at or timezone.now()
    item.completed_at = timezone.now()
    item.status = (
        RecoveryVerification.Status.PASSED
        if measured_rpo_minutes <= item.target_rpo_minutes
        and measured_rto_minutes <= item.target_rto_minutes
        else RecoveryVerification.Status.FAILED
    )
    item.version += 1
    item.full_clean()
    item.save()
    _record(
        company=company,
        actor=actor,
        action="dataops.recovery.completed",
        entity_type="recovery_verification",
        entity_public_id=item.public_id,
        version=item.version,
        payload={"status": item.status, "rpo": measured_rpo_minutes, "rto": measured_rto_minutes},
    )
    return item
