from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from modules.leaseops.models import (
    LeaseableUnit,
    LeaseAgreement,
    LeaseCharge,
    LeaseLifecycleEvent,
    ManagedProperty,
    OccupancyRecord,
    PropertyPolicyVersion,
    RentInvoice,
    TenantAccount,
    TenantExperienceCase,
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
    _, created = PropertyPolicyVersion.objects.get_or_create(
        company=company,
        version=1,
        defaults={
            "status_code": "DRAFT",
            "lease_expiry_alert_days": 90,
            "invoice_grace_days": 5,
            "case_response_minutes": 240,
            "case_resolution_minutes": 2880,
            "configuration": {
                "phase": 41,
                "release": "property-lease-occupancy-tenant-experience",
                "finance_integration": "REFERENCE_ONLY",
                "payment_provider": "PROVIDER_NEUTRAL",
                "lease_numbering": "TENANT_CONFIGURABLE",
                "tax_rules": "TENANT_CONFIGURABLE",
            },
        },
    )
    return {"policy": int(created)}


def _identity(item: Any) -> str:
    for field in ("code", "account_code", "lease_number", "charge_code", "invoice_number", "case_number", "event_type_code"):
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
        after={"code": _identity(item), "status": getattr(item, "status_code", "RECORDED")},
    )
    return item


@transaction.atomic
def create_property(*, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> ManagedProperty:
    data.setdefault("manager_public_id", actor_public_id)
    if not data.get("timezone"):
        data["timezone"] = company.timezone
    return _create(ManagedProperty, company=company, actor_public_id=actor_public_id, correlation_id=correlation_id, event="lease.property.created", **data)


@transaction.atomic
def create_unit(*, company: Company, property: ManagedProperty, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> LeaseableUnit:
    data.setdefault("currency_code", company.currency)
    return _create(LeaseableUnit, company=company, property=property, actor_public_id=actor_public_id, correlation_id=correlation_id, event="lease.unit.created", **data)


@transaction.atomic
def create_tenant(*, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> TenantAccount:
    data.setdefault("owner_public_id", actor_public_id)
    return _create(TenantAccount, company=company, actor_public_id=actor_public_id, correlation_id=correlation_id, event="lease.tenant.created", **data)


def _ensure_unit_available(*, company: Company, unit: LeaseableUnit, start_on, end_on, exclude_pk: int | None = None) -> None:
    conflicts = LeaseAgreement.objects.filter(
        company=company,
        unit=unit,
        status_code__in=["SUBMITTED", "APPROVED", "ACTIVE"],
        start_on__lte=end_on,
        end_on__gte=start_on,
    )
    if exclude_pk:
        conflicts = conflicts.exclude(pk=exclude_pk)
    if conflicts.exists():
        raise ValidationError("The lease period overlaps another submitted, approved or active lease for this unit.")


@transaction.atomic
def create_lease(
    *, company: Company, property: ManagedProperty, unit: LeaseableUnit, tenant: TenantAccount,
    actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any
) -> LeaseAgreement:
    data.setdefault("created_by_public_id", actor_public_id)
    data.setdefault("currency_code", company.currency)
    _ensure_unit_available(company=company, unit=unit, start_on=data["start_on"], end_on=data["end_on"])
    return _create(
        LeaseAgreement,
        company=company,
        property=property,
        unit=unit,
        tenant=tenant,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        event="lease.agreement.created",
        **data,
    )


def _lease_event(
    *, lease: LeaseAgreement, event_type_code: str, actor_public_id: uuid.UUID, correlation_id: uuid.UUID,
    summary: str, from_status_code: str = "", to_status_code: str = "", amount: Decimal | None = None,
    metadata: dict | None = None,
) -> LeaseLifecycleEvent:
    item = LeaseLifecycleEvent(
        company=lease.company,
        lease=lease,
        event_type_code=event_type_code,
        occurred_at=timezone.now(),
        from_status_code=from_status_code,
        to_status_code=to_status_code,
        summary=summary,
        amount=amount,
        currency_code=lease.currency_code if amount is not None else "",
        event_metadata=metadata or {},
        recorded_by_public_id=actor_public_id,
    )
    item.full_clean()
    item.save()
    _record(
        company=lease.company,
        action="CREATE",
        event_type="lease.lifecycle.recorded",
        entity_type="LeaseLifecycleEvent",
        entity_public_id=item.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=1,
        after={"lease_number": lease.lease_number, "event_type": item.event_type_code, "summary": summary},
    )
    return item


@transaction.atomic
def transition_lease(
    *, lease: LeaseAgreement, status_code: str, expected_version: int, actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID, note: str = ""
) -> LeaseAgreement:
    lease = LeaseAgreement.objects.select_for_update().select_related("unit").get(pk=lease.pk)
    status_code = status_code.strip().upper()
    if lease.version != expected_version:
        raise ValidationError("Lease agreement changed. Refresh and retry.")
    allowed = {
        "DRAFT": {"SUBMITTED", "CANCELLED"},
        "SUBMITTED": {"APPROVED", "REJECTED"},
        "REJECTED": {"DRAFT", "CANCELLED"},
        "APPROVED": {"ACTIVE", "CANCELLED"},
        "ACTIVE": {"EXPIRED", "TERMINATED"},
        "EXPIRED": {"CLOSED"},
        "TERMINATED": {"CLOSED"},
        "CLOSED": set(),
        "CANCELLED": set(),
    }
    if status_code not in allowed.get(lease.status_code, set()):
        raise ValidationError(f"Invalid lease transition from {lease.status_code} to {status_code}.")
    if status_code == "APPROVED" and lease.created_by_public_id == actor_public_id:
        raise ValidationError("The lease creator cannot approve the same lease.")
    if status_code in {"SUBMITTED", "APPROVED", "ACTIVE"}:
        _ensure_unit_available(company=lease.company, unit=lease.unit, start_on=lease.start_on, end_on=lease.end_on, exclude_pk=lease.pk)
    before_status = lease.status_code
    before = {"status": before_status, "version": lease.version}
    lease.status_code = status_code
    if status_code == "APPROVED":
        lease.approved_by_public_id = actor_public_id
        lease.unit.status_code = "RESERVED"
        lease.unit.version += 1
        lease.unit.save(update_fields=["status_code", "version", "updated_at"])
    if status_code == "ACTIVE":
        lease.activated_at = timezone.now()
        lease.unit.status_code = "LEASED"
        lease.unit.version += 1
        lease.unit.save(update_fields=["status_code", "version", "updated_at"])
    if status_code == "TERMINATED":
        lease.terminated_at = timezone.now()
    if status_code in {"CLOSED", "CANCELLED"}:
        lease.unit.status_code = "AVAILABLE"
        lease.unit.version += 1
        lease.unit.save(update_fields=["status_code", "version", "updated_at"])
    lease.version += 1
    lease.full_clean()
    lease.save()
    _lease_event(
        lease=lease,
        event_type_code="STATUS_TRANSITION",
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        summary=note or f"Lease moved from {before_status} to {status_code}.",
        from_status_code=before_status,
        to_status_code=status_code,
    )
    _record(
        company=lease.company,
        action="TRANSITION",
        event_type="lease.agreement.transitioned",
        entity_type="LeaseAgreement",
        entity_public_id=lease.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=lease.version,
        before=before,
        after={"lease_number": lease.lease_number, "status": status_code, "unit": lease.unit.code},
    )
    return lease


@transaction.atomic
def create_charge(*, company: Company, lease: LeaseAgreement, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> LeaseCharge:
    data.setdefault("currency_code", lease.currency_code)
    return _create(LeaseCharge, company=company, lease=lease, actor_public_id=actor_public_id, correlation_id=correlation_id, event="lease.charge.created", **data)


@transaction.atomic
def create_occupancy(*, company: Company, lease: LeaseAgreement, unit: LeaseableUnit, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> OccupancyRecord:
    data.setdefault("captured_by_public_id", actor_public_id)
    return _create(OccupancyRecord, company=company, lease=lease, unit=unit, actor_public_id=actor_public_id, correlation_id=correlation_id, event="lease.occupancy.created", **data)


@transaction.atomic
def transition_occupancy(
    *, occupancy: OccupancyRecord, status_code: str, expected_version: int, actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID, note: str = ""
) -> OccupancyRecord:
    occupancy = OccupancyRecord.objects.select_for_update().select_related("lease", "unit").get(pk=occupancy.pk)
    status_code = status_code.strip().upper()
    if occupancy.version != expected_version:
        raise ValidationError("Occupancy record changed. Refresh and retry.")
    allowed = {
        "DRAFT": {"SUBMITTED", "CANCELLED"},
        "SUBMITTED": {"VERIFIED", "REJECTED"},
        "REJECTED": {"DRAFT", "CANCELLED"},
        "VERIFIED": {"OCCUPIED"},
        "OCCUPIED": {"MOVED_OUT"},
        "MOVED_OUT": {"CLOSED"},
        "CLOSED": set(),
        "CANCELLED": set(),
    }
    if status_code not in allowed.get(occupancy.status_code, set()):
        raise ValidationError(f"Invalid occupancy transition from {occupancy.status_code} to {status_code}.")
    if status_code == "VERIFIED" and occupancy.captured_by_public_id == actor_public_id:
        raise ValidationError("The occupancy recorder cannot verify the same record.")
    before = {"status": occupancy.status_code, "version": occupancy.version}
    occupancy.status_code = status_code
    if status_code == "VERIFIED":
        occupancy.verified_by_public_id = actor_public_id
    if status_code == "OCCUPIED":
        occupancy.move_in_on = occupancy.move_in_on or timezone.localdate()
        occupancy.unit.status_code = "OCCUPIED"
        occupancy.unit.version += 1
        occupancy.unit.save(update_fields=["status_code", "version", "updated_at"])
    if status_code == "MOVED_OUT":
        occupancy.move_out_on = occupancy.move_out_on or timezone.localdate()
    if status_code == "CLOSED":
        occupancy.unit.status_code = "LEASED" if occupancy.lease.status_code == "ACTIVE" else "AVAILABLE"
        occupancy.unit.version += 1
        occupancy.unit.save(update_fields=["status_code", "version", "updated_at"])
    occupancy.version += 1
    occupancy.full_clean()
    occupancy.save()
    _record(
        company=occupancy.company,
        action="TRANSITION",
        event_type="lease.occupancy.transitioned",
        entity_type="OccupancyRecord",
        entity_public_id=occupancy.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=occupancy.version,
        before=before,
        after={"lease_number": occupancy.lease.lease_number, "status": status_code, "note": note},
    )
    return occupancy


@transaction.atomic
def create_invoice(*, company: Company, lease: LeaseAgreement, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> RentInvoice:
    data.setdefault("created_by_public_id", actor_public_id)
    data.setdefault("currency_code", lease.currency_code)
    return _create(RentInvoice, company=company, lease=lease, actor_public_id=actor_public_id, correlation_id=correlation_id, event="lease.invoice.created", **data)


@transaction.atomic
def transition_invoice(
    *, invoice: RentInvoice, status_code: str, expected_version: int, actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID, paid_amount: Decimal | None = None, note: str = ""
) -> RentInvoice:
    invoice = RentInvoice.objects.select_for_update().select_related("lease").get(pk=invoice.pk)
    status_code = status_code.strip().upper()
    if invoice.version != expected_version:
        raise ValidationError("Rent invoice changed. Refresh and retry.")
    allowed = {
        "DRAFT": {"SUBMITTED", "VOID"},
        "SUBMITTED": {"ISSUED", "REJECTED"},
        "REJECTED": {"DRAFT", "VOID"},
        "ISSUED": {"PARTIALLY_PAID", "PAID", "VOID"},
        "PARTIALLY_PAID": {"PAID", "VOID"},
        "PAID": set(),
        "VOID": set(),
    }
    if status_code not in allowed.get(invoice.status_code, set()):
        raise ValidationError(f"Invalid invoice transition from {invoice.status_code} to {status_code}.")
    if status_code == "ISSUED" and invoice.created_by_public_id == actor_public_id:
        raise ValidationError("The invoice creator cannot issue the same invoice.")
    total = invoice.gross_amount + invoice.tax_amount
    before = {"status": invoice.status_code, "version": invoice.version, "paid_amount": str(invoice.paid_amount)}
    if paid_amount is not None:
        if paid_amount < invoice.paid_amount or paid_amount > total:
            raise ValidationError("Paid amount must be between the current paid amount and the invoice total.")
        invoice.paid_amount = paid_amount
    if status_code == "PAID":
        invoice.paid_amount = total
    if status_code == "PARTIALLY_PAID" and not (Decimal("0") < invoice.paid_amount < total):
        raise ValidationError("Partially paid invoices require a paid amount below the invoice total.")
    invoice.status_code = status_code
    if status_code == "ISSUED":
        invoice.issued_by_public_id = actor_public_id
    invoice.version += 1
    invoice.full_clean()
    invoice.save()
    _lease_event(
        lease=invoice.lease,
        event_type_code="INVOICE_TRANSITION",
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        summary=note or f"Invoice {invoice.invoice_number} moved to {status_code}.",
        amount=invoice.paid_amount if status_code in {"PARTIALLY_PAID", "PAID"} else total,
        metadata={"invoice_number": invoice.invoice_number, "status": status_code},
    )
    _record(
        company=invoice.company,
        action="TRANSITION",
        event_type="lease.invoice.transitioned",
        entity_type="RentInvoice",
        entity_public_id=invoice.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=invoice.version,
        before=before,
        after={"invoice_number": invoice.invoice_number, "status": status_code, "paid_amount": str(invoice.paid_amount)},
    )
    return invoice


@transaction.atomic
def create_case(
    *, company: Company, tenant: TenantAccount, property: ManagedProperty, unit: LeaseableUnit | None,
    actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any
) -> TenantExperienceCase:
    policy = PropertyPolicyVersion.objects.filter(company=company).order_by("-version").first()
    now = timezone.now()
    data.setdefault("response_due_at", now + timedelta(minutes=policy.case_response_minutes if policy else 240))
    data.setdefault("resolution_due_at", now + timedelta(minutes=policy.case_resolution_minutes if policy else 2880))
    return _create(
        TenantExperienceCase,
        company=company,
        tenant=tenant,
        property=property,
        unit=unit,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        event="lease.tenant_case.created",
        **data,
    )


@transaction.atomic
def transition_case(
    *, case: TenantExperienceCase, status_code: str, expected_version: int, actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID, note: str = "", satisfaction_score: int | None = None
) -> TenantExperienceCase:
    case = TenantExperienceCase.objects.select_for_update().get(pk=case.pk)
    status_code = status_code.strip().upper()
    if case.version != expected_version:
        raise ValidationError("Tenant experience case changed. Refresh and retry.")
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
    if status_code not in allowed.get(case.status_code, set()):
        raise ValidationError(f"Invalid tenant case transition from {case.status_code} to {status_code}.")
    before = {"status": case.status_code, "version": case.version}
    case.status_code = status_code
    if status_code in {"ACKNOWLEDGED", "ASSIGNED", "IN_PROGRESS"} and case.responded_at is None:
        case.responded_at = timezone.now()
    if status_code in {"RESOLVED", "CLOSED"}:
        case.resolved_at = case.resolved_at or timezone.now()
    elif status_code == "REOPENED":
        case.resolved_at = None
    if satisfaction_score is not None:
        case.satisfaction_score = satisfaction_score
    if note:
        case.resolution_note = note
    case.version += 1
    case.full_clean()
    case.save()
    _record(
        company=case.company,
        action="TRANSITION",
        event_type="lease.tenant_case.transitioned",
        entity_type="TenantExperienceCase",
        entity_public_id=case.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=case.version,
        before=before,
        after={"case_number": case.case_number, "status": status_code, "priority": case.priority_code},
    )
    return case
