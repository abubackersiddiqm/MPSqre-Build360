from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from modules.facilityops.models import (
    AssetLifecycleEvent,
    ConditionInspection,
    Facility,
    FacilityPolicyVersion,
    FacilitySpace,
    FacilityWorkOrder,
    MaintenancePlan,
    OperationalAsset,
    ServiceRequest,
    WarrantyClaim,
)
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.tenant.models import Company


def _record(
    *,
    company: Company,
    action: str,
    event_type: str,
    entity_type: str,
    entity_public_id: uuid.UUID,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    version: int,
    after: dict[str, Any],
    before: dict[str, Any] | None = None,
) -> None:
    append_audit(
        AuditRecord(
            action=action,
            entity_type=entity_type,
            entity_public_id=entity_public_id,
            actor_public_id=actor_public_id,
            company_public_id=company.public_id,
            request_id=correlation_id,
            correlation_id=correlation_id,
            before=before or {},
            after=after,
        )
    )
    append_event(
        EventRecord(
            event_type=event_type,
            aggregate_type=entity_type,
            aggregate_public_id=entity_public_id,
            aggregate_version=version,
            company_public_id=company.public_id,
            correlation_id=correlation_id,
            payload=after,
        )
    )


def seed_defaults(company: Company) -> dict[str, int]:
    _, created = FacilityPolicyVersion.objects.get_or_create(
        company=company,
        version=1,
        defaults={
            "status_code": "DRAFT",
            "preventive_horizon_days": 90,
            "warranty_alert_days": 60,
            "service_response_minutes": 240,
            "service_resolution_minutes": 1440,
            "configuration": {
                "phase": 40,
                "release": "facilities-asset-lifecycle-warranty",
                "maintenance_provider": "PROVIDER_NEUTRAL",
                "work_order_numbering": "TENANT_CONFIGURABLE",
                "handover_source": "REFERENCE_ONLY",
            },
        },
    )
    return {"policy": int(created)}


def _identity(item: Any) -> str:
    for field in (
        "code",
        "asset_tag",
        "request_number",
        "work_order_number",
        "claim_number",
        "inspection_number",
        "event_type_code",
    ):
        value = getattr(item, field, None)
        if value:
            return str(value)
    return str(item.public_id)


def _create(model, *, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, event: str, **data: Any):
    item = model(company=company, **data)
    item.full_clean()
    item.save()
    _record(
        company=company,
        action="CREATE",
        event_type=event,
        entity_type=model.__name__,
        entity_public_id=item.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=getattr(item, "version", 1),
        after={
            "code": _identity(item),
            "status": getattr(item, "status_code", getattr(item, "operation_status_code", "RECORDED")),
        },
    )
    return item


@transaction.atomic
def create_facility(*, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> Facility:
    data.setdefault("owner_public_id", actor_public_id)
    if not data.get("timezone"):
        data["timezone"] = company.timezone
    return _create(
        Facility,
        company=company,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        event="facility.facility.created",
        **data,
    )


@transaction.atomic
def create_space(
    *, company: Company, facility: Facility, parent: FacilitySpace | None, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any
) -> FacilitySpace:
    return _create(
        FacilitySpace,
        company=company,
        facility=facility,
        parent=parent,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        event="facility.space.created",
        **data,
    )


@transaction.atomic
def create_asset(
    *, company: Company, facility: Facility, space: FacilitySpace | None, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any
) -> OperationalAsset:
    data.setdefault("captured_by_public_id", actor_public_id)
    return _create(
        OperationalAsset,
        company=company,
        facility=facility,
        space=space,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        event="facility.asset.created",
        **data,
    )


def _lifecycle_event(
    *, asset: OperationalAsset, event_type_code: str, actor_public_id: uuid.UUID, correlation_id: uuid.UUID,
    summary: str, from_status_code: str = "", to_status_code: str = "", reference: str = "", metadata: dict | None = None,
) -> AssetLifecycleEvent:
    item = AssetLifecycleEvent(
        company=asset.company,
        asset=asset,
        event_type_code=event_type_code,
        occurred_at=timezone.now(),
        from_status_code=from_status_code,
        to_status_code=to_status_code,
        summary=summary,
        reference=reference,
        event_metadata=metadata or {},
        recorded_by_public_id=actor_public_id,
    )
    item.full_clean()
    item.save()
    _record(
        company=asset.company,
        action="CREATE",
        event_type="facility.asset.lifecycle.recorded",
        entity_type="AssetLifecycleEvent",
        entity_public_id=item.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=1,
        after={"asset_tag": asset.asset_tag, "event_type": event_type_code, "summary": summary},
    )
    return item


@transaction.atomic
def transition_asset(
    *, asset: OperationalAsset, status_code: str, expected_version: int, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, note: str = ""
) -> OperationalAsset:
    asset = OperationalAsset.objects.select_for_update().get(pk=asset.pk)
    status_code = status_code.strip().upper()
    if asset.version != expected_version:
        raise ValidationError("Operational asset changed. Refresh and retry.")
    allowed = {
        "DRAFT": {"VERIFIED", "CANCELLED"},
        "VERIFIED": {"IN_SERVICE", "OUT_OF_SERVICE"},
        "IN_SERVICE": {"OUT_OF_SERVICE", "DECOMMISSIONED"},
        "OUT_OF_SERVICE": {"IN_SERVICE", "DECOMMISSIONED"},
        "DECOMMISSIONED": {"RETIRED"},
        "RETIRED": set(),
        "CANCELLED": set(),
    }
    if status_code not in allowed.get(asset.operation_status_code, set()):
        raise ValidationError(f"Invalid asset transition from {asset.operation_status_code} to {status_code}.")
    if status_code == "VERIFIED" and asset.captured_by_public_id == actor_public_id:
        raise ValidationError("The asset recorder cannot verify the same asset.")
    before_status = asset.operation_status_code
    before = {"status": before_status, "version": asset.version}
    asset.operation_status_code = status_code
    if status_code == "VERIFIED":
        asset.verified_by_public_id = actor_public_id
    if status_code == "RETIRED":
        asset.maintainable = False
    asset.version += 1
    asset.full_clean()
    asset.save()
    _lifecycle_event(
        asset=asset,
        event_type_code="STATUS_TRANSITION",
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        summary=note or f"Asset moved from {before_status} to {status_code}.",
        from_status_code=before_status,
        to_status_code=status_code,
    )
    _record(
        company=asset.company,
        action="TRANSITION",
        event_type="facility.asset.transitioned",
        entity_type="OperationalAsset",
        entity_public_id=asset.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=asset.version,
        before=before,
        after={"asset_tag": asset.asset_tag, "status": status_code, "condition": asset.condition_code},
    )
    return asset


@transaction.atomic
def create_plan(
    *, company: Company, asset: OperationalAsset, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any
) -> MaintenancePlan:
    data.setdefault("owner_public_id", actor_public_id)
    return _create(
        MaintenancePlan,
        company=company,
        asset=asset,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        event="facility.maintenance.plan.created",
        **data,
    )


@transaction.atomic
def create_service_request(
    *, company: Company, facility: Facility, space: FacilitySpace | None, asset: OperationalAsset | None,
    actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any
) -> ServiceRequest:
    policy = FacilityPolicyVersion.objects.filter(company=company).order_by("-version").first()
    now = timezone.now()
    data.setdefault("requester_public_id", actor_public_id)
    data.setdefault("response_due_at", now + timedelta(minutes=policy.service_response_minutes if policy else 240))
    data.setdefault("resolution_due_at", now + timedelta(minutes=policy.service_resolution_minutes if policy else 1440))
    return _create(
        ServiceRequest,
        company=company,
        facility=facility,
        space=space,
        asset=asset,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        event="facility.service.request.created",
        **data,
    )


@transaction.atomic
def transition_service_request(
    *, request_item: ServiceRequest, status_code: str, expected_version: int, actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID, note: str = ""
) -> ServiceRequest:
    request_item = ServiceRequest.objects.select_for_update().get(pk=request_item.pk)
    status_code = status_code.strip().upper()
    if request_item.version != expected_version:
        raise ValidationError("Service request changed. Refresh and retry.")
    allowed = {
        "NEW": {"ACKNOWLEDGED", "ASSIGNED", "CANCELLED"},
        "ACKNOWLEDGED": {"ASSIGNED", "IN_PROGRESS", "CANCELLED"},
        "ASSIGNED": {"IN_PROGRESS", "RESOLVED", "CANCELLED"},
        "IN_PROGRESS": {"RESOLVED", "ON_HOLD", "CANCELLED"},
        "ON_HOLD": {"IN_PROGRESS", "CANCELLED"},
        "RESOLVED": {"CLOSED", "REOPENED"},
        "REOPENED": {"ASSIGNED", "IN_PROGRESS"},
        "CLOSED": set(),
        "CANCELLED": set(),
    }
    if status_code not in allowed.get(request_item.status_code, set()):
        raise ValidationError(f"Invalid service request transition from {request_item.status_code} to {status_code}.")
    before = {"status": request_item.status_code, "version": request_item.version}
    request_item.status_code = status_code
    if status_code in {"ACKNOWLEDGED", "ASSIGNED", "IN_PROGRESS"} and request_item.responded_at is None:
        request_item.responded_at = timezone.now()
    if status_code in {"RESOLVED", "CLOSED"}:
        request_item.resolved_at = request_item.resolved_at or timezone.now()
    elif status_code == "REOPENED":
        request_item.resolved_at = None
    if note:
        request_item.closure_note = note
    request_item.version += 1
    request_item.full_clean()
    request_item.save()
    _record(
        company=request_item.company,
        action="TRANSITION",
        event_type="facility.service.request.transitioned",
        entity_type="ServiceRequest",
        entity_public_id=request_item.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=request_item.version,
        before=before,
        after={"request_number": request_item.request_number, "status": status_code, "priority": request_item.priority_code},
    )
    return request_item


@transaction.atomic
def create_work_order(
    *, company: Company, asset: OperationalAsset, plan: MaintenancePlan | None, service_request: ServiceRequest | None,
    actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any
) -> FacilityWorkOrder:
    data.setdefault("created_by_public_id", actor_public_id)
    data.setdefault("currency_code", company.currency)
    return _create(
        FacilityWorkOrder,
        company=company,
        asset=asset,
        plan=plan,
        service_request=service_request,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        event="facility.work_order.created",
        **data,
    )


@transaction.atomic
def transition_work_order(
    *, work_order: FacilityWorkOrder, status_code: str, expected_version: int, actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID, note: str = "", completion_evidence: dict | None = None
) -> FacilityWorkOrder:
    work_order = FacilityWorkOrder.objects.select_for_update(of=("self",)).select_related("asset", "plan").get(pk=work_order.pk)
    status_code = status_code.strip().upper()
    if work_order.version != expected_version:
        raise ValidationError("Facility work order changed. Refresh and retry.")
    allowed = {
        "DRAFT": {"SUBMITTED", "CANCELLED"},
        "SUBMITTED": {"APPROVED", "REJECTED"},
        "REJECTED": {"DRAFT", "CANCELLED"},
        "APPROVED": {"SCHEDULED", "IN_PROGRESS", "CANCELLED"},
        "SCHEDULED": {"IN_PROGRESS", "CANCELLED"},
        "IN_PROGRESS": {"COMPLETED", "ON_HOLD"},
        "ON_HOLD": {"IN_PROGRESS", "CANCELLED"},
        "COMPLETED": {"VERIFIED", "IN_PROGRESS"},
        "VERIFIED": {"CLOSED", "IN_PROGRESS"},
        "CLOSED": set(),
        "CANCELLED": set(),
    }
    if status_code not in allowed.get(work_order.status_code, set()):
        raise ValidationError(f"Invalid work-order transition from {work_order.status_code} to {status_code}.")
    if status_code == "APPROVED" and work_order.created_by_public_id == actor_public_id:
        raise ValidationError("The work-order creator cannot approve the same work order.")
    if status_code == "VERIFIED" and work_order.assigned_to_public_id == actor_public_id:
        raise ValidationError("The assigned technician cannot verify the same work order.")
    before = {"status": work_order.status_code, "version": work_order.version}
    work_order.status_code = status_code
    if status_code == "APPROVED":
        work_order.approved_by_public_id = actor_public_id
    if status_code == "IN_PROGRESS" and work_order.started_at is None:
        work_order.started_at = timezone.now()
    if status_code == "COMPLETED":
        work_order.completed_at = timezone.now()
    if status_code == "VERIFIED":
        work_order.verified_by_public_id = actor_public_id
    if completion_evidence:
        work_order.completion_evidence = completion_evidence
    if note:
        evidence = dict(work_order.completion_evidence or {})
        evidence["note"] = note
        work_order.completion_evidence = evidence
    work_order.version += 1
    work_order.full_clean()
    work_order.save()

    if status_code == "CLOSED":
        asset = OperationalAsset.objects.select_for_update().get(pk=work_order.asset_id)
        service_date = (work_order.completed_at or timezone.now()).date()
        asset.last_service_on = service_date
        interval = None
        if work_order.plan_id:
            plan = MaintenancePlan.objects.select_for_update().get(pk=work_order.plan_id)
            interval = plan.frequency_days
            plan.next_due_date = service_date + timedelta(days=plan.frequency_days)
            plan.version += 1
            plan.save(update_fields=["next_due_date", "version", "updated_at"])
        elif asset.service_interval_days:
            interval = asset.service_interval_days
        if interval:
            asset.next_service_on = service_date + timedelta(days=interval)
        asset.version += 1
        asset.save(update_fields=["last_service_on", "next_service_on", "version", "updated_at"])
        _lifecycle_event(
            asset=asset,
            event_type_code="MAINTENANCE_COMPLETED",
            actor_public_id=actor_public_id,
            correlation_id=correlation_id,
            summary=f"Work order {work_order.work_order_number} closed.",
            reference=work_order.work_order_number,
            metadata={"work_type": work_order.work_type_code, "actual_cost": str(work_order.actual_cost or "")},
        )

    _record(
        company=work_order.company,
        action="TRANSITION",
        event_type="facility.work_order.transitioned",
        entity_type="FacilityWorkOrder",
        entity_public_id=work_order.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=work_order.version,
        before=before,
        after={"work_order": work_order.work_order_number, "status": status_code, "asset_tag": work_order.asset.asset_tag},
    )
    return work_order


@transaction.atomic
def create_warranty_claim(
    *, company: Company, asset: OperationalAsset, work_order: FacilityWorkOrder | None,
    actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any
) -> WarrantyClaim:
    data.setdefault("owner_public_id", actor_public_id)
    data.setdefault("currency_code", company.currency)
    return _create(
        WarrantyClaim,
        company=company,
        asset=asset,
        work_order=work_order,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        event="facility.warranty.claim.created",
        **data,
    )


@transaction.atomic
def transition_warranty_claim(
    *, claim: WarrantyClaim, status_code: str, expected_version: int, actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID, note: str = "", approved_amount: Any = None
) -> WarrantyClaim:
    claim = WarrantyClaim.objects.select_for_update().select_related("asset").get(pk=claim.pk)
    status_code = status_code.strip().upper()
    if claim.version != expected_version:
        raise ValidationError("Warranty claim changed. Refresh and retry.")
    allowed = {
        "DRAFT": {"FILED", "CANCELLED"},
        "FILED": {"UNDER_REVIEW", "WITHDRAWN"},
        "UNDER_REVIEW": {"APPROVED", "REJECTED", "INFO_REQUIRED"},
        "INFO_REQUIRED": {"UNDER_REVIEW", "WITHDRAWN"},
        "APPROVED": {"SETTLED", "CLOSED"},
        "REJECTED": {"CLOSED"},
        "SETTLED": {"CLOSED"},
        "CLOSED": set(),
        "WITHDRAWN": set(),
        "CANCELLED": set(),
    }
    if status_code not in allowed.get(claim.status_code, set()):
        raise ValidationError(f"Invalid warranty transition from {claim.status_code} to {status_code}.")
    if status_code in {"APPROVED", "REJECTED"} and claim.owner_public_id == actor_public_id:
        raise ValidationError("The claim owner cannot decide the same warranty claim.")
    before = {"status": claim.status_code, "version": claim.version}
    claim.status_code = status_code
    if status_code == "FILED":
        claim.filed_at = timezone.now()
    if status_code in {"APPROVED", "REJECTED"}:
        claim.approved_by_public_id = actor_public_id
        claim.decision_at = timezone.now()
    if status_code == "SETTLED":
        claim.settled_at = timezone.now()
    if approved_amount is not None:
        claim.approved_amount = approved_amount
    if note:
        claim.resolution_note = note
    claim.version += 1
    claim.full_clean()
    claim.save()
    _record(
        company=claim.company,
        action="TRANSITION",
        event_type="facility.warranty.claim.transitioned",
        entity_type="WarrantyClaim",
        entity_public_id=claim.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=claim.version,
        before=before,
        after={"claim_number": claim.claim_number, "status": status_code, "asset_tag": claim.asset.asset_tag},
    )
    return claim


@transaction.atomic
def create_inspection(
    *, company: Company, facility: Facility, space: FacilitySpace | None, asset: OperationalAsset | None,
    actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any
) -> ConditionInspection:
    data.setdefault("inspector_public_id", actor_public_id)
    return _create(
        ConditionInspection,
        company=company,
        facility=facility,
        space=space,
        asset=asset,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        event="facility.inspection.created",
        **data,
    )


@transaction.atomic
def transition_inspection(
    *, inspection: ConditionInspection, status_code: str, expected_version: int, actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID, note: str = ""
) -> ConditionInspection:
    inspection = ConditionInspection.objects.select_for_update().get(pk=inspection.pk)
    status_code = status_code.strip().upper()
    if inspection.version != expected_version:
        raise ValidationError("Condition inspection changed. Refresh and retry.")
    allowed = {
        "DRAFT": {"SUBMITTED", "CANCELLED"},
        "SUBMITTED": {"VERIFIED", "REJECTED"},
        "REJECTED": {"DRAFT", "CANCELLED"},
        "VERIFIED": {"CLOSED"},
        "CLOSED": set(),
        "CANCELLED": set(),
    }
    if status_code not in allowed.get(inspection.status_code, set()):
        raise ValidationError(f"Invalid inspection transition from {inspection.status_code} to {status_code}.")
    if status_code == "VERIFIED" and inspection.inspector_public_id == actor_public_id:
        raise ValidationError("The inspector cannot verify the same inspection.")
    before = {"status": inspection.status_code, "version": inspection.version}
    inspection.status_code = status_code
    if status_code == "VERIFIED":
        inspection.verified_by_public_id = actor_public_id
    if note:
        inspection.actions_required = note
    inspection.version += 1
    inspection.full_clean()
    inspection.save()
    if status_code == "VERIFIED" and inspection.asset_id:
        asset = OperationalAsset.objects.select_for_update().get(pk=inspection.asset_id)
        asset.condition_code = inspection.condition_code
        asset.version += 1
        asset.save(update_fields=["condition_code", "version", "updated_at"])
    _record(
        company=inspection.company,
        action="TRANSITION",
        event_type="facility.inspection.transitioned",
        entity_type="ConditionInspection",
        entity_public_id=inspection.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=inspection.version,
        before=before,
        after={"inspection_number": inspection.inspection_number, "status": status_code, "condition": inspection.condition_code},
    )
    return inspection


@transaction.atomic
def record_lifecycle_event(
    *, company: Company, asset: OperationalAsset, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any
) -> AssetLifecycleEvent:
    return _lifecycle_event(
        asset=asset,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        event_type_code=data["event_type_code"],
        summary=data["summary"],
        from_status_code=data.get("from_status_code", ""),
        to_status_code=data.get("to_status_code", ""),
        reference=data.get("reference", ""),
        metadata=data.get("event_metadata", {}),
    )
