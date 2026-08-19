from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from modules.fieldops.application.stages import assert_transition, initial_stage, resolve_stage
from modules.fieldops.models import FieldStage
from modules.platform.actors import RequestActor
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.projects.models import Project
from modules.quality.models import Inspection, InspectionTemplate, NonConformanceReport
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
def create_template(
    *,
    company: Company,
    actor: RequestActor,
    code: str,
    name: str,
    discipline_code: str,
    checklist: list[dict[str, Any]],
) -> InspectionTemplate:
    item = InspectionTemplate(
        company=company,
        code=code.strip().upper(),
        name=name.strip(),
        discipline_code=discipline_code.strip().lower(),
        checklist=checklist,
    )
    item.full_clean()
    item.save()
    _record(
        actor,
        company,
        "quality.template_created",
        item,
        {"code": item.code, "version": item.version_number},
    )
    return item


@transaction.atomic
def create_inspection(
    *,
    company: Company,
    actor: RequestActor,
    project_public_id: uuid.UUID,
    template_public_id: uuid.UUID,
    inspection_number: str,
    title: str,
    inspector_membership_public_id: uuid.UUID,
    scheduled_at: datetime | None = None,
    location: dict[str, Any] | None = None,
    operation_id: uuid.UUID | None = None,
) -> Inspection:
    if operation_id:
        existing = Inspection.objects.filter(company=company, operation_id=operation_id).first()
        if existing:
            return existing
    project = Project.objects.filter(
        company=company, public_id=project_public_id, archived_at__isnull=True
    ).first()
    template = InspectionTemplate.objects.filter(
        company=company, public_id=template_public_id, retired_at__isnull=True
    ).first()
    if project is None or template is None:
        raise ValidationError("Project or inspection template was not found")
    item = Inspection(
        company=company,
        project=project,
        template=template,
        stage=initial_stage(company, FieldStage.EntityType.INSPECTION),
        inspection_number=inspection_number.strip().upper(),
        title=title.strip(),
        inspector_membership_public_id=inspector_membership_public_id,
        scheduled_at=scheduled_at,
        location=location or {},
        operation_id=operation_id,
    )
    item.full_clean()
    item.save()
    _record(
        actor,
        company,
        "quality.inspection_created",
        item,
        {"number": item.inspection_number, "project": project.code},
    )
    return item


@transaction.atomic
def submit_inspection(
    *,
    company: Company,
    actor: RequestActor,
    inspection_public_id: uuid.UUID,
    checklist_result: list[dict[str, Any]],
    overall_result: str,
    expected_version: int,
) -> Inspection:
    item = (
        Inspection.objects.select_for_update()
        .select_related("stage")
        .filter(company=company, public_id=inspection_public_id)
        .first()
    )
    if item is None:
        raise ValidationError("Inspection was not found")
    if item.version != expected_version:
        raise ValidationError("Inspection changed; refresh and retry")
    target = resolve_stage(company, FieldStage.EntityType.INSPECTION, "submitted")
    assert_transition(item.stage, target)
    item.checklist_result = checklist_result
    item.overall_result = overall_result.strip().lower()
    item.inspected_at = timezone.now()
    item.stage = target
    item.version += 1
    item.full_clean()
    item.save()
    _record(
        actor,
        company,
        "quality.inspection_submitted",
        item,
        {"result": item.overall_result, "version": item.version},
    )
    return item


@transaction.atomic
def create_ncr(
    *,
    company: Company,
    actor: RequestActor,
    project_public_id: uuid.UUID,
    ncr_number: str,
    title: str,
    description: str,
    severity: str,
    inspection_public_id: uuid.UUID | None = None,
    due_date: date | None = None,
    responsible_membership_public_id: uuid.UUID | None = None,
) -> NonConformanceReport:
    project = Project.objects.filter(
        company=company, public_id=project_public_id, archived_at__isnull=True
    ).first()
    if project is None:
        raise ValidationError("Project was not found")
    inspection = None
    if inspection_public_id:
        inspection = Inspection.objects.filter(
            company=company, project=project, public_id=inspection_public_id
        ).first()
        if inspection is None:
            raise ValidationError("Inspection was not found")
    item = NonConformanceReport(
        company=company,
        project=project,
        inspection=inspection,
        stage=initial_stage(company, FieldStage.EntityType.NCR),
        ncr_number=ncr_number.strip().upper(),
        title=title.strip(),
        description=description.strip(),
        severity=severity.strip().lower(),
        due_date=due_date,
        responsible_membership_public_id=responsible_membership_public_id,
    )
    item.full_clean()
    item.save()
    _record(
        actor,
        company,
        "quality.ncr_created",
        item,
        {"number": item.ncr_number, "severity": item.severity},
    )
    return item
