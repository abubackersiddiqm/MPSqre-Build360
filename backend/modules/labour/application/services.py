from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from modules.fieldops.application.stages import assert_transition, initial_stage, resolve_stage
from modules.fieldops.models import FieldStage
from modules.labour.models import AttendanceRecord, WorkerProfile, WorkforceAllocation
from modules.platform.actors import RequestActor
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.projects.models import Project
from modules.tenant.models import Company


def _record(
    actor: RequestActor, company: Company, action: str, entity: Any, payload: dict[str, Any]
) -> None:
    append_audit(
        AuditRecord(
            action=action,
            entity_type=entity._meta.model_name,
            entity_public_id=entity.public_id,
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
            aggregate_type=entity._meta.model_name,
            aggregate_public_id=entity.public_id,
            aggregate_version=getattr(entity, "version", 1),
            company_public_id=company.public_id,
            correlation_id=actor.request_id,
            payload=payload,
        )
    )


@transaction.atomic
def create_worker(
    *,
    company: Company,
    actor: RequestActor,
    code: str,
    display_name: str,
    worker_type: str,
    trade_code: str,
    joined_on: date,
    currency: str,
    daily_rate: Decimal = Decimal("0"),
    skill_codes: list[str] | None = None,
    employee_public_id: uuid.UUID | None = None,
    vendor_public_id: uuid.UUID | None = None,
) -> WorkerProfile:
    worker = WorkerProfile(
        company=company,
        code=code.strip().upper(),
        display_name=display_name.strip(),
        worker_type=worker_type,
        trade_code=trade_code.strip().lower(),
        skill_codes=skill_codes or [],
        daily_rate=daily_rate,
        currency=currency.upper(),
        joined_on=joined_on,
        employee_public_id=employee_public_id,
        vendor_public_id=vendor_public_id,
    )
    worker.full_clean()
    worker.save()
    _record(
        actor,
        company,
        "labour.worker_created",
        worker,
        {"code": worker.code, "trade_code": worker.trade_code},
    )
    return worker


@transaction.atomic
def allocate_worker(
    *,
    company: Company,
    actor: RequestActor,
    worker_public_id: uuid.UUID,
    project_public_id: uuid.UUID,
    allocated_from: date,
    planned_hours: Decimal = Decimal("8"),
    allocated_to: date | None = None,
    supervisor_membership_public_id: uuid.UUID | None = None,
    notes: str = "",
) -> WorkforceAllocation:
    worker = WorkerProfile.objects.filter(
        company=company, public_id=worker_public_id, is_active=True
    ).first()
    project = Project.objects.filter(
        company=company, public_id=project_public_id, archived_at__isnull=True
    ).first()
    if worker is None or project is None:
        raise ValidationError("Worker or project was not found")
    allocation = WorkforceAllocation(
        company=company,
        worker=worker,
        project=project,
        stage=initial_stage(company, FieldStage.EntityType.LABOUR_ALLOCATION),
        allocated_from=allocated_from,
        allocated_to=allocated_to,
        planned_hours=planned_hours,
        supervisor_membership_public_id=supervisor_membership_public_id,
        notes=notes.strip(),
    )
    allocation.full_clean()
    allocation.save()
    _record(
        actor,
        company,
        "labour.worker_allocated",
        allocation,
        {"worker": worker.code, "project": project.code, "stage": allocation.stage.code},
    )
    return allocation


@transaction.atomic
def record_attendance(
    *,
    company: Company,
    actor: RequestActor,
    worker_public_id: uuid.UUID,
    project_public_id: uuid.UUID,
    work_date: date,
    regular_hours: Decimal,
    overtime_hours: Decimal = Decimal("0"),
    source: str = AttendanceRecord.EntrySource.WEB,
    operation_id: uuid.UUID | None = None,
) -> AttendanceRecord:
    if operation_id:
        existing = AttendanceRecord.objects.filter(
            company=company, operation_id=operation_id
        ).first()
        if existing:
            return existing
    worker = WorkerProfile.objects.filter(
        company=company, public_id=worker_public_id, is_active=True
    ).first()
    project = Project.objects.filter(
        company=company, public_id=project_public_id, archived_at__isnull=True
    ).first()
    if worker is None or project is None:
        raise ValidationError("Worker or project was not found")
    record = AttendanceRecord(
        company=company,
        worker=worker,
        project=project,
        stage=initial_stage(company, FieldStage.EntityType.ATTENDANCE),
        work_date=work_date,
        regular_hours=regular_hours,
        overtime_hours=overtime_hours,
        source=source,
        operation_id=operation_id,
    )
    record.full_clean()
    record.save()
    _record(
        actor,
        company,
        "labour.attendance_recorded",
        record,
        {
            "worker": worker.code,
            "project": project.code,
            "work_date": str(work_date),
            "hours": str(regular_hours + overtime_hours),
        },
    )
    return record


@transaction.atomic
def transition_attendance(
    *,
    company: Company,
    actor: RequestActor,
    attendance_public_id: uuid.UUID,
    target_stage_code: str,
    expected_version: int,
) -> AttendanceRecord:
    record = (
        AttendanceRecord.objects.select_for_update()
        .select_related("stage")
        .filter(company=company, public_id=attendance_public_id)
        .first()
    )
    if record is None:
        raise ValidationError("Attendance record was not found")
    if record.version != expected_version:
        raise ValidationError("Attendance record changed; refresh and retry")
    target = resolve_stage(company, FieldStage.EntityType.ATTENDANCE, target_stage_code)
    assert_transition(record.stage, target)
    record.stage = target
    record.version += 1
    if target.code == "approved":
        record.approved_by_public_id = actor.user_public_id
        record.approved_at = timezone.now()
    record.full_clean()
    record.save()
    _record(
        actor,
        company,
        "labour.attendance_transitioned",
        record,
        {"stage": target.code, "version": record.version},
    )
    return record
