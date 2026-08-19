from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from modules.equipment.models import (
    EquipmentAllocation,
    EquipmentAsset,
    MaintenanceWorkOrder,
    MeterReading,
)
from modules.fieldops.application.stages import initial_stage
from modules.fieldops.models import FieldStage
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
def create_equipment(
    *,
    company: Company,
    actor: RequestActor,
    code: str,
    name: str,
    category_code: str,
    currency: str,
    ownership_type: str = "owned",
    hourly_cost: Decimal = Decimal("0"),
    meter_unit: str = "hours",
    serial_number: str = "",
    registration_number: str = "",
) -> EquipmentAsset:
    asset = EquipmentAsset(
        company=company,
        code=code.strip().upper(),
        name=name.strip(),
        category_code=category_code.strip().lower(),
        ownership_type=ownership_type.strip().lower(),
        serial_number=serial_number.strip(),
        registration_number=registration_number.strip(),
        stage=initial_stage(company, FieldStage.EntityType.EQUIPMENT),
        hourly_cost=hourly_cost,
        currency=currency.upper(),
        meter_unit=meter_unit.strip().lower(),
    )
    asset.full_clean()
    asset.save()
    _record(
        actor,
        company,
        "equipment.asset_created",
        asset,
        {"code": asset.code, "stage": asset.stage.code},
    )
    return asset


@transaction.atomic
def allocate_equipment(
    *,
    company: Company,
    actor: RequestActor,
    equipment_public_id: uuid.UUID,
    project_public_id: uuid.UUID,
    allocated_from: datetime,
    allocated_to: datetime | None = None,
    planned_meter_usage: Decimal = Decimal("0"),
    notes: str = "",
) -> EquipmentAllocation:
    asset = EquipmentAsset.objects.filter(
        company=company, public_id=equipment_public_id, retired_at__isnull=True
    ).first()
    project = Project.objects.filter(
        company=company, public_id=project_public_id, archived_at__isnull=True
    ).first()
    if asset is None or project is None:
        raise ValidationError("Equipment or project was not found")
    allocation = EquipmentAllocation(
        company=company,
        equipment=asset,
        project=project,
        stage=initial_stage(company, FieldStage.EntityType.EQUIPMENT_ALLOCATION),
        allocated_from=allocated_from,
        allocated_to=allocated_to,
        planned_meter_usage=planned_meter_usage,
        notes=notes.strip(),
    )
    allocation.full_clean()
    allocation.save()
    _record(
        actor,
        company,
        "equipment.asset_allocated",
        allocation,
        {"equipment": asset.code, "project": project.code},
    )
    return allocation


@transaction.atomic
def record_meter(
    *,
    company: Company,
    actor: RequestActor,
    equipment_public_id: uuid.UUID,
    reading: Decimal,
    reading_at: datetime,
    source: str = "web",
    operation_id: uuid.UUID | None = None,
) -> MeterReading:
    if operation_id:
        existing = MeterReading.objects.filter(company=company, operation_id=operation_id).first()
        if existing:
            return existing
    asset = (
        EquipmentAsset.objects.select_for_update()
        .filter(company=company, public_id=equipment_public_id, retired_at__isnull=True)
        .first()
    )
    if asset is None:
        raise ValidationError("Equipment was not found")
    if reading < asset.current_meter:
        raise ValidationError("Meter reading cannot move backwards")
    meter = MeterReading(
        company=company,
        equipment=asset,
        reading=reading,
        reading_at=reading_at,
        source=source,
        operation_id=operation_id,
        recorded_by_public_id=actor.user_public_id,
    )
    meter.full_clean()
    meter.save()
    asset.current_meter = reading
    asset.version += 1
    asset.full_clean()
    asset.save(update_fields=["current_meter", "version", "updated_at"])
    _record(
        actor,
        company,
        "equipment.meter_recorded",
        meter,
        {"equipment": asset.code, "reading": str(reading)},
    )
    return meter


@transaction.atomic
def create_maintenance(
    *,
    company: Company,
    actor: RequestActor,
    equipment_public_id: uuid.UUID,
    work_order_number: str,
    maintenance_type: str,
    summary: str,
    currency: str,
    due_date: Any = None,
    description: str = "",
) -> MaintenanceWorkOrder:
    asset = EquipmentAsset.objects.filter(
        company=company, public_id=equipment_public_id, retired_at__isnull=True
    ).first()
    if asset is None:
        raise ValidationError("Equipment was not found")
    order = MaintenanceWorkOrder(
        company=company,
        equipment=asset,
        stage=initial_stage(company, FieldStage.EntityType.MAINTENANCE),
        work_order_number=work_order_number.strip().upper(),
        maintenance_type=maintenance_type.strip().lower(),
        summary=summary.strip(),
        description=description.strip(),
        due_date=due_date,
        opened_at=timezone.now(),
        meter_at_open=asset.current_meter,
        currency=currency.upper(),
    )
    order.full_clean()
    order.save()
    _record(
        actor,
        company,
        "equipment.maintenance_opened",
        order,
        {"equipment": asset.code, "work_order": order.work_order_number},
    )
    return order
