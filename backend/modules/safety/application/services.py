from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from modules.fieldops.application.stages import initial_stage
from modules.fieldops.models import FieldStage
from modules.platform.actors import RequestActor
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.projects.models import Project
from modules.safety.models import SafetyIncident, SafetyObservation
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
def report_incident(
    *,
    company: Company,
    actor: RequestActor,
    project_public_id: uuid.UUID,
    incident_number: str,
    title: str,
    description: str,
    severity: str,
    occurred_at: datetime,
    reported_by_membership_public_id: uuid.UUID,
    location: dict[str, Any] | None = None,
    immediate_actions: str = "",
    operation_id: uuid.UUID | None = None,
) -> SafetyIncident:
    if operation_id:
        existing = SafetyIncident.objects.filter(company=company, operation_id=operation_id).first()
        if existing:
            return existing
    project = Project.objects.filter(
        company=company, public_id=project_public_id, archived_at__isnull=True
    ).first()
    if project is None:
        raise ValidationError("Project was not found")
    item = SafetyIncident(
        company=company,
        project=project,
        stage=initial_stage(company, FieldStage.EntityType.INCIDENT),
        incident_number=incident_number.strip().upper(),
        title=title.strip(),
        description=description.strip(),
        severity=severity,
        occurred_at=occurred_at,
        reported_at=timezone.now(),
        reported_by_membership_public_id=reported_by_membership_public_id,
        location=location or {},
        immediate_actions=immediate_actions.strip(),
        operation_id=operation_id,
    )
    item.full_clean()
    item.save()
    _record(
        actor,
        company,
        "safety.incident_reported",
        item,
        {"number": item.incident_number, "severity": item.severity, "project": project.code},
    )
    return item


@transaction.atomic
def create_observation(
    *,
    company: Company,
    actor: RequestActor,
    project_public_id: uuid.UUID,
    observation_number: str,
    observation_type: str,
    description: str,
    observed_at: datetime,
    observed_by_membership_public_id: uuid.UUID,
    is_positive: bool = False,
    action_required: bool = False,
) -> SafetyObservation:
    project = Project.objects.filter(
        company=company, public_id=project_public_id, archived_at__isnull=True
    ).first()
    if project is None:
        raise ValidationError("Project was not found")
    item = SafetyObservation(
        company=company,
        project=project,
        observation_number=observation_number.strip().upper(),
        observation_type=observation_type.strip().lower(),
        description=description.strip(),
        observed_at=observed_at,
        observed_by_membership_public_id=observed_by_membership_public_id,
        is_positive=is_positive,
        action_required=action_required,
    )
    item.full_clean()
    item.save()
    _record(
        actor,
        company,
        "safety.observation_created",
        item,
        {"number": item.observation_number, "positive": item.is_positive},
    )
    return item
