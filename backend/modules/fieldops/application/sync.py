from __future__ import annotations

import uuid
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from modules.fieldops.models import OfflineOperation, SyncCheckpoint, SyncConflict
from modules.platform.actors import RequestActor
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.tenant.models import Company

APPROVED_OPERATION_TYPES = {
    "labour.attendance.create",
    "equipment.meter_reading.create",
    "quality.inspection.submit",
    "safety.incident.report",
}


def _record(actor: RequestActor, company: Company, operation: OfflineOperation) -> None:
    payload = {
        "operation_id": str(operation.operation_id),
        "operation_type": operation.operation_type,
        "status": operation.status,
    }
    append_audit(
        AuditRecord(
            action="fieldops.offline_operation_received",
            entity_type="offline_operation",
            entity_public_id=operation.public_id,
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
            event_type="fieldops.offline_operation_received",
            aggregate_type="offline_operation",
            aggregate_public_id=operation.public_id,
            aggregate_version=1,
            company_public_id=company.public_id,
            correlation_id=actor.request_id,
            payload=payload,
        )
    )


def _serializer_errors(serializer: Any) -> ValidationError:
    return ValidationError(serializer.errors)


def _apply_operation(
    *,
    company: Company,
    actor: RequestActor,
    membership_public_id: uuid.UUID,
    operation: OfflineOperation,
) -> dict[str, Any]:
    payload = operation.payload
    if operation.operation_type == "labour.attendance.create":
        from modules.labour.api.serializers import AttendanceCreateSerializer
        from modules.labour.application.services import record_attendance

        serializer = AttendanceCreateSerializer(data=payload)
        if not serializer.is_valid():
            raise _serializer_errors(serializer)
        values = dict(serializer.validated_data)
        values["source"] = "offline"
        values["operation_id"] = operation.operation_id
        record = record_attendance(company=company, actor=actor, **values)
        return {"aggregate_public_id": str(record.public_id), "version": record.version}

    if operation.operation_type == "equipment.meter_reading.create":
        from modules.equipment.api.serializers import MeterReadingSerializer
        from modules.equipment.application.services import record_meter

        serializer = MeterReadingSerializer(data=payload)
        if not serializer.is_valid():
            raise _serializer_errors(serializer)
        values = dict(serializer.validated_data)
        values["source"] = "offline"
        values["operation_id"] = operation.operation_id
        reading = record_meter(company=company, actor=actor, **values)
        return {"aggregate_public_id": str(reading.public_id)}

    if operation.operation_type == "quality.inspection.submit":
        from modules.quality.api.serializers import InspectionSubmitSerializer
        from modules.quality.application.services import submit_inspection

        if operation.aggregate_public_id is None:
            raise ValidationError("Inspection public ID is required")
        serializer = InspectionSubmitSerializer(data=payload)
        if not serializer.is_valid():
            raise _serializer_errors(serializer)
        values = dict(serializer.validated_data)
        if operation.expected_version is not None:
            values["expected_version"] = operation.expected_version
        inspection = submit_inspection(
            company=company,
            actor=actor,
            inspection_public_id=operation.aggregate_public_id,
            **values,
        )
        return {
            "aggregate_public_id": str(inspection.public_id),
            "version": inspection.version,
        }

    if operation.operation_type == "safety.incident.report":
        from modules.safety.api.serializers import IncidentCreateSerializer
        from modules.safety.application.services import report_incident

        serializer = IncidentCreateSerializer(data=payload)
        if not serializer.is_valid():
            raise _serializer_errors(serializer)
        values = dict(serializer.validated_data)
        values["reported_by_membership_public_id"] = membership_public_id
        values["operation_id"] = operation.operation_id
        incident = report_incident(company=company, actor=actor, **values)
        return {"aggregate_public_id": str(incident.public_id), "version": incident.version}

    raise ValidationError("This operation is not approved for offline capture")


@transaction.atomic
def receive_operation(
    *,
    company: Company,
    actor: RequestActor,
    membership_public_id: uuid.UUID,
    operation_id: uuid.UUID,
    device_id: uuid.UUID,
    operation_type: str,
    aggregate_type: str,
    payload: dict[str, Any],
    aggregate_public_id: uuid.UUID | None = None,
    expected_version: int | None = None,
) -> tuple[OfflineOperation, bool]:
    existing = OfflineOperation.objects.filter(
        company=company,
        operation_id=operation_id,
    ).first()
    if existing is not None:
        return existing, False
    normalized = operation_type.strip().lower()
    if normalized not in APPROVED_OPERATION_TYPES:
        raise ValidationError("This operation is not approved for offline capture")
    operation = OfflineOperation(
        company=company,
        operation_id=operation_id,
        device_id=device_id,
        actor_membership_public_id=membership_public_id,
        operation_type=normalized,
        aggregate_type=aggregate_type.strip().lower(),
        aggregate_public_id=aggregate_public_id,
        expected_version=expected_version,
        payload=payload,
        status=OfflineOperation.Status.RECEIVED,
        received_at=timezone.now(),
    )
    operation.full_clean()
    operation.save()
    _record(actor, company, operation)

    try:
        result = _apply_operation(
            company=company,
            actor=actor,
            membership_public_id=membership_public_id,
            operation=operation,
        )
    except ValidationError as exc:
        messages = getattr(exc, "messages", [str(exc)])
        text = " ".join(str(item) for item in messages).lower()
        if "changed" in text or "version" in text or "conflict" in text:
            operation.status = OfflineOperation.Status.CONFLICT
            operation.rejection_code = "VERSION_CONFLICT"
            SyncConflict.objects.create(
                company=company,
                operation=operation,
                conflict_code="VERSION_CONFLICT",
                client_version=operation.expected_version,
                server_snapshot={},
            )
        else:
            operation.status = OfflineOperation.Status.REJECTED
            operation.rejection_code = "VALIDATION_FAILED"
        operation.result = {"errors": messages}
    else:
        operation.status = OfflineOperation.Status.APPLIED
        operation.result = result
    operation.processed_at = timezone.now()
    operation.save(
        update_fields=[
            "status",
            "result",
            "rejection_code",
            "processed_at",
            "updated_at",
        ]
    )

    SyncCheckpoint.objects.update_or_create(
        company=company,
        device_id=device_id,
        actor_membership_public_id=membership_public_id,
        defaults={
            "last_operation_received_at": operation.received_at,
            "last_server_sequence": operation.id,
            "last_successful_sync_at": timezone.now(),
            "revoked_at": None,
        },
    )
    return operation, True


@transaction.atomic
def mark_conflict(
    *,
    company: Company,
    operation: OfflineOperation,
    code: str,
    server_version: int | None,
    server_snapshot: dict[str, Any],
) -> SyncConflict:
    if operation.company_id != company.id:
        raise ValidationError("Offline operation was not found")
    operation.status = OfflineOperation.Status.CONFLICT
    operation.processed_at = timezone.now()
    operation.save(update_fields=["status", "processed_at", "updated_at"])
    conflict, _ = SyncConflict.objects.update_or_create(
        company=company,
        operation=operation,
        defaults={
            "conflict_code": code.strip(),
            "server_version": server_version,
            "client_version": operation.expected_version,
            "server_snapshot": server_snapshot,
        },
    )
    return conflict
