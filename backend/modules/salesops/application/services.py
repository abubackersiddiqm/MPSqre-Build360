from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.salesops.models import (
    BookingAgreement,
    BrokerCommission,
    BuyerAccount,
    CollectionReceipt,
    CustomerHandover,
    DevelopmentInventory,
    PaymentMilestone,
    SaleableUnit,
    SalesPolicyVersion,
    UnitReservation,
)
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
    _, created = SalesPolicyVersion.objects.get_or_create(
        company=company,
        version=1,
        defaults={
            "status_code": "DRAFT",
            "reservation_expiry_hours": 72,
            "collection_grace_days": 7,
            "handover_alert_days": 30,
            "configuration": {
                "phase": 42,
                "release": "development-sales-booking-collections-handover",
                "crm_integration": "REFERENCE_ONLY",
                "finance_integration": "REFERENCE_ONLY",
                "payment_provider": "PROVIDER_NEUTRAL",
                "tax_rules": "TENANT_CONFIGURABLE",
                "booking_numbering": "TENANT_CONFIGURABLE",
            },
        },
    )
    return {"policy": int(created)}


def _identity(item: Any) -> str:
    for field in (
        "code",
        "account_code",
        "reservation_number",
        "booking_number",
        "milestone_code",
        "receipt_number",
        "broker_reference",
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
        after={"code": _identity(item), "status": getattr(item, "status_code", "RECORDED")},
    )
    return item


@transaction.atomic
def create_inventory(*, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> DevelopmentInventory:
    data.setdefault("manager_public_id", actor_public_id)
    data.setdefault("currency_code", company.currency)
    return _create(DevelopmentInventory, company=company, actor_public_id=actor_public_id, correlation_id=correlation_id, event="development.inventory.created", **data)


@transaction.atomic
def create_unit(*, company: Company, inventory: DevelopmentInventory, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> SaleableUnit:
    if inventory.company_id != company.id:
        raise ValidationError("Development inventory cannot cross companies.")
    data.setdefault("currency_code", inventory.currency_code or company.currency)
    return _create(SaleableUnit, company=company, inventory=inventory, actor_public_id=actor_public_id, correlation_id=correlation_id, event="development.unit.created", **data)


@transaction.atomic
def create_buyer(*, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> BuyerAccount:
    data.setdefault("owner_public_id", actor_public_id)
    return _create(BuyerAccount, company=company, actor_public_id=actor_public_id, correlation_id=correlation_id, event="development.buyer.created", **data)


@transaction.atomic
def create_reservation(*, company: Company, unit: SaleableUnit, buyer: BuyerAccount, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> UnitReservation:
    if unit.company_id != company.id or buyer.company_id != company.id:
        raise ValidationError("Reservation cannot cross companies.")
    if unit.status_code not in {"RELEASED", "AVAILABLE"}:
        raise ValidationError("Only released or available units may be reserved.")
    now = timezone.now()
    reserved_at = data.get("reserved_at") or now
    policy = SalesPolicyVersion.objects.filter(company=company).order_by("-version").first()
    expires_at = data.get("expires_at") or reserved_at + timedelta(hours=policy.reservation_expiry_hours if policy else 72)
    conflict = UnitReservation.objects.select_for_update().filter(
        company=company,
        unit=unit,
        status_code="ACTIVE",
        expires_at__gt=now,
    ).exists()
    if conflict:
        raise ValidationError("The unit already has an active reservation.")
    data["reserved_at"] = reserved_at
    data["expires_at"] = expires_at
    data.setdefault("currency_code", unit.currency_code)
    data.setdefault("created_by_public_id", actor_public_id)
    item = _create(UnitReservation, company=company, unit=unit, buyer=buyer, actor_public_id=actor_public_id, correlation_id=correlation_id, event="development.reservation.created", **data)
    unit.status_code = "RESERVED"
    unit.version += 1
    unit.save(update_fields=["status_code", "version", "updated_at"])
    return item


@transaction.atomic
def transition_reservation(*, reservation: UnitReservation, status_code: str, expected_version: int, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, note: str = "") -> UnitReservation:
    reservation = UnitReservation.objects.select_for_update().select_related("unit").get(pk=reservation.pk)
    status_code = status_code.strip().upper()
    if reservation.version != expected_version:
        raise ValidationError("Reservation changed. Refresh and retry.")
    allowed = {
        "ACTIVE": {"CONVERTED", "EXPIRED", "CANCELLED"},
        "CONVERTED": set(),
        "EXPIRED": set(),
        "CANCELLED": set(),
    }
    if status_code not in allowed.get(reservation.status_code, set()):
        raise ValidationError(f"Invalid reservation transition from {reservation.status_code} to {status_code}.")
    if status_code == "CONVERTED" and not reservation.converted_booking_public_id:
        raise ValidationError("Reservation conversion requires a linked booking.")
    before = {"status": reservation.status_code, "version": reservation.version}
    reservation.status_code = status_code
    if status_code in {"EXPIRED", "CANCELLED"}:
        reservation.cancellation_reason = note
        if reservation.unit.status_code == "RESERVED":
            reservation.unit.status_code = "AVAILABLE"
            reservation.unit.version += 1
            reservation.unit.save(update_fields=["status_code", "version", "updated_at"])
    reservation.version += 1
    reservation.full_clean()
    reservation.save()
    _record(company=reservation.company, action="TRANSITION", event_type="development.reservation.transitioned", entity_type="UnitReservation", entity_public_id=reservation.public_id, actor_public_id=actor_public_id, correlation_id=correlation_id, version=reservation.version, before=before, after={"status": reservation.status_code, "note": note})
    return reservation


@transaction.atomic
def create_booking(*, company: Company, unit: SaleableUnit, buyer: BuyerAccount, reservation: UnitReservation | None, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> BookingAgreement:
    if unit.company_id != company.id or buyer.company_id != company.id:
        raise ValidationError("Booking cannot cross companies.")
    if reservation:
        if reservation.company_id != company.id or reservation.unit_id != unit.id or reservation.buyer_id != buyer.id:
            raise ValidationError("Booking reservation must match the buyer and unit.")
        if reservation.status_code != "ACTIVE":
            raise ValidationError("Only an active reservation may be converted into a booking.")
        if reservation.expires_at <= timezone.now():
            raise ValidationError("The reservation has expired.")
    elif unit.status_code not in {"RELEASED", "AVAILABLE"}:
        raise ValidationError("The unit is not available for booking.")
    active_booking = BookingAgreement.objects.select_for_update().filter(company=company, unit=unit).exclude(status_code__in=["CANCELLED", "REJECTED"]).exists()
    if active_booking:
        raise ValidationError("The unit already has an active booking.")
    data.setdefault("created_by_public_id", actor_public_id)
    data.setdefault("currency_code", unit.currency_code)
    data.setdefault("total_consideration", data["base_price"] - data.get("discount_amount", Decimal("0")) + data.get("tax_amount", Decimal("0")) + data.get("other_charges", Decimal("0")))
    return _create(BookingAgreement, company=company, unit=unit, buyer=buyer, reservation=reservation, actor_public_id=actor_public_id, correlation_id=correlation_id, event="development.booking.created", **data)


@transaction.atomic
def transition_booking(*, booking: BookingAgreement, status_code: str, expected_version: int, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, note: str = "") -> BookingAgreement:
    booking = BookingAgreement.objects.select_for_update(of=("self",)).select_related("unit", "reservation").get(pk=booking.pk)
    status_code = status_code.strip().upper()
    if booking.version != expected_version:
        raise ValidationError("Booking changed. Refresh and retry.")
    allowed = {
        "DRAFT": {"SUBMITTED", "CANCELLED"},
        "SUBMITTED": {"APPROVED", "REJECTED"},
        "REJECTED": {"DRAFT", "CANCELLED"},
        "APPROVED": {"ACTIVE", "CANCELLED"},
        "ACTIVE": {"CANCELLED"},
        "HANDED_OVER": {"CLOSED"},
        "CLOSED": set(),
        "CANCELLED": set(),
    }
    if status_code not in allowed.get(booking.status_code, set()):
        raise ValidationError(f"Invalid booking transition from {booking.status_code} to {status_code}.")
    if status_code == "APPROVED" and booking.created_by_public_id == actor_public_id:
        raise ValidationError("The booking creator cannot approve the same booking.")
    before = {"status": booking.status_code, "version": booking.version}
    booking.status_code = status_code
    if status_code == "APPROVED":
        booking.approved_by_public_id = actor_public_id
        booking.approved_at = timezone.now()
        booking.unit.status_code = "BOOKED"
        if booking.reservation:
            booking.reservation.converted_booking_public_id = booking.public_id
            booking.reservation.status_code = "CONVERTED"
            booking.reservation.version += 1
            booking.reservation.save(update_fields=["converted_booking_public_id", "status_code", "version", "updated_at"])
    elif status_code == "ACTIVE":
        booking.unit.status_code = "SOLD"
    elif status_code == "HANDED_OVER":
        booking.unit.status_code = "HANDED_OVER"
    elif status_code == "CANCELLED":
        booking.cancelled_at = timezone.now()
        booking.cancellation_reason = note
        booking.unit.status_code = "AVAILABLE"
    booking.unit.version += 1
    booking.unit.save(update_fields=["status_code", "version", "updated_at"])
    booking.version += 1
    booking.full_clean()
    booking.save()
    _record(company=booking.company, action="TRANSITION", event_type="development.booking.transitioned", entity_type="BookingAgreement", entity_public_id=booking.public_id, actor_public_id=actor_public_id, correlation_id=correlation_id, version=booking.version, before=before, after={"status": booking.status_code, "note": note})
    return booking


@transaction.atomic
def create_milestone(*, company: Company, booking: BookingAgreement, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> PaymentMilestone:
    if booking.company_id != company.id:
        raise ValidationError("Payment milestone cannot cross companies.")
    total = data["amount"] + data.get("tax_amount", Decimal("0"))
    scheduled = PaymentMilestone.objects.filter(company=company, booking=booking).aggregate(
        amount=Sum("amount"), tax=Sum("tax_amount")
    )
    scheduled_total = (scheduled["amount"] or Decimal("0")) + (scheduled["tax"] or Decimal("0"))
    if scheduled_total + total > booking.total_consideration:
        raise ValidationError("Payment milestones cannot exceed the booking consideration.")
    return _create(PaymentMilestone, company=company, booking=booking, actor_public_id=actor_public_id, correlation_id=correlation_id, event="development.milestone.created", **data)


@transaction.atomic
def create_receipt(*, company: Company, booking: BookingAgreement, milestone: PaymentMilestone | None, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> CollectionReceipt:
    if booking.company_id != company.id:
        raise ValidationError("Collection receipt cannot cross companies.")
    if booking.status_code not in {"APPROVED", "ACTIVE", "HANDED_OVER", "CLOSED"}:
        raise ValidationError("Receipts may only be recorded for approved or active bookings.")
    if milestone and (milestone.company_id != company.id or milestone.booking_id != booking.id):
        raise ValidationError("Receipt milestone must belong to the booking.")
    data.setdefault("created_by_public_id", actor_public_id)
    data.setdefault("currency_code", booking.currency_code)
    return _create(CollectionReceipt, company=company, booking=booking, milestone=milestone, actor_public_id=actor_public_id, correlation_id=correlation_id, event="development.receipt.created", **data)


@transaction.atomic
def transition_receipt(*, receipt: CollectionReceipt, status_code: str, expected_version: int, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, note: str = "") -> CollectionReceipt:
    receipt = CollectionReceipt.objects.select_for_update(of=("self",)).select_related("milestone", "booking").get(pk=receipt.pk)
    status_code = status_code.strip().upper()
    if receipt.version != expected_version:
        raise ValidationError("Receipt changed. Refresh and retry.")
    allowed = {
        "DRAFT": {"SUBMITTED", "CANCELLED"},
        "SUBMITTED": {"CONFIRMED", "REJECTED"},
        "REJECTED": {"DRAFT", "CANCELLED"},
        "CONFIRMED": {"REVERSED"},
        "REVERSED": set(),
        "CANCELLED": set(),
    }
    if status_code not in allowed.get(receipt.status_code, set()):
        raise ValidationError(f"Invalid receipt transition from {receipt.status_code} to {status_code}.")
    if status_code == "CONFIRMED" and receipt.created_by_public_id == actor_public_id:
        raise ValidationError("The receipt creator cannot confirm the same receipt.")
    before = {"status": receipt.status_code, "version": receipt.version}
    if receipt.milestone and status_code == "CONFIRMED":
        total_due = receipt.milestone.amount + receipt.milestone.tax_amount
        if receipt.milestone.paid_amount + receipt.amount > total_due:
            raise ValidationError("Confirmed receipt would overpay the payment milestone.")
        receipt.milestone.paid_amount += receipt.amount
        receipt.milestone.status_code = "PAID" if receipt.milestone.paid_amount == total_due else "PARTIALLY_PAID"
        receipt.milestone.version += 1
        receipt.milestone.full_clean()
        receipt.milestone.save()
        receipt.confirmed_by_public_id = actor_public_id
        receipt.confirmed_at = timezone.now()
    elif receipt.milestone and status_code == "REVERSED" and receipt.status_code == "CONFIRMED":
        receipt.milestone.paid_amount = max(Decimal("0"), receipt.milestone.paid_amount - receipt.amount)
        receipt.milestone.status_code = "SCHEDULED" if receipt.milestone.paid_amount == 0 else "PARTIALLY_PAID"
        receipt.milestone.version += 1
        receipt.milestone.save()
    receipt.status_code = status_code
    receipt.version += 1
    receipt.full_clean()
    receipt.save()
    _record(company=receipt.company, action="TRANSITION", event_type="development.receipt.transitioned", entity_type="CollectionReceipt", entity_public_id=receipt.public_id, actor_public_id=actor_public_id, correlation_id=correlation_id, version=receipt.version, before=before, after={"status": receipt.status_code, "note": note})
    return receipt


@transaction.atomic
def create_commission(*, company: Company, booking: BookingAgreement, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> BrokerCommission:
    if booking.company_id != company.id:
        raise ValidationError("Broker commission cannot cross companies.")
    data.setdefault("created_by_public_id", actor_public_id)
    data.setdefault("currency_code", booking.currency_code)
    return _create(BrokerCommission, company=company, booking=booking, actor_public_id=actor_public_id, correlation_id=correlation_id, event="development.commission.created", **data)


@transaction.atomic
def transition_commission(*, commission: BrokerCommission, status_code: str, expected_version: int, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, note: str = "") -> BrokerCommission:
    commission = BrokerCommission.objects.select_for_update().get(pk=commission.pk)
    status_code = status_code.strip().upper()
    if commission.version != expected_version:
        raise ValidationError("Broker commission changed. Refresh and retry.")
    allowed = {
        "DRAFT": {"SUBMITTED", "CANCELLED"},
        "SUBMITTED": {"APPROVED", "REJECTED"},
        "REJECTED": {"DRAFT", "CANCELLED"},
        "APPROVED": {"PAYABLE", "CANCELLED"},
        "PAYABLE": {"PAID"},
        "PAID": set(),
        "CANCELLED": set(),
    }
    if status_code not in allowed.get(commission.status_code, set()):
        raise ValidationError(f"Invalid commission transition from {commission.status_code} to {status_code}.")
    if status_code == "APPROVED" and commission.created_by_public_id == actor_public_id:
        raise ValidationError("The commission creator cannot approve the same commission.")
    before = {"status": commission.status_code, "version": commission.version}
    commission.status_code = status_code
    if status_code == "APPROVED":
        commission.approved_by_public_id = actor_public_id
        commission.approved_at = timezone.now()
    if status_code == "PAID":
        commission.paid_at = timezone.now()
    commission.version += 1
    commission.full_clean()
    commission.save()
    _record(company=commission.company, action="TRANSITION", event_type="development.commission.transitioned", entity_type="BrokerCommission", entity_public_id=commission.public_id, actor_public_id=actor_public_id, correlation_id=correlation_id, version=commission.version, before=before, after={"status": commission.status_code, "note": note})
    return commission


@transaction.atomic
def create_handover(*, company: Company, booking: BookingAgreement, unit: SaleableUnit, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> CustomerHandover:
    if booking.company_id != company.id or unit.company_id != company.id or booking.unit_id != unit.id:
        raise ValidationError("Customer handover must use the booked unit in the same company.")
    if booking.status_code not in {"ACTIVE", "HANDED_OVER", "CLOSED"}:
        raise ValidationError("Customer handover requires an active booking.")
    data.setdefault("created_by_public_id", actor_public_id)
    return _create(CustomerHandover, company=company, booking=booking, unit=unit, actor_public_id=actor_public_id, correlation_id=correlation_id, event="development.handover.created", **data)


@transaction.atomic
def transition_handover(*, handover: CustomerHandover, status_code: str, expected_version: int, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, note: str = "") -> CustomerHandover:
    handover = CustomerHandover.objects.select_for_update().select_related("booking", "unit").get(pk=handover.pk)
    status_code = status_code.strip().upper()
    if handover.version != expected_version:
        raise ValidationError("Customer handover changed. Refresh and retry.")
    allowed = {
        "DRAFT": {"READINESS_REVIEW", "CANCELLED"},
        "READINESS_REVIEW": {"READY", "REJECTED"},
        "REJECTED": {"DRAFT", "CANCELLED"},
        "READY": {"OFFERED"},
        "OFFERED": {"POSSESSED"},
        "POSSESSED": {"CLOSED"},
        "CLOSED": set(),
        "CANCELLED": set(),
    }
    if status_code not in allowed.get(handover.status_code, set()):
        raise ValidationError(f"Invalid handover transition from {handover.status_code} to {status_code}.")
    if status_code == "READY" and handover.created_by_public_id == actor_public_id:
        raise ValidationError("The handover creator cannot verify the same handover.")
    if status_code in {"READY", "OFFERED", "POSSESSED"} and handover.open_defect_count > 0:
        raise ValidationError("Open defects must be resolved before progressing the customer handover.")
    before = {"status": handover.status_code, "version": handover.version}
    handover.status_code = status_code
    if status_code == "READY":
        handover.verified_by_public_id = actor_public_id
    elif status_code == "OFFERED":
        handover.offered_on = handover.offered_on or timezone.localdate()
    elif status_code == "POSSESSED":
        handover.possession_on = handover.possession_on or timezone.localdate()
        handover.booking.status_code = "HANDED_OVER"
        handover.booking.version += 1
        handover.booking.save(update_fields=["status_code", "version", "updated_at"])
        handover.unit.status_code = "HANDED_OVER"
        handover.unit.version += 1
        handover.unit.save(update_fields=["status_code", "version", "updated_at"])
    elif status_code == "CLOSED":
        handover.booking.status_code = "CLOSED"
        handover.booking.version += 1
        handover.booking.save(update_fields=["status_code", "version", "updated_at"])
    handover.version += 1
    handover.full_clean()
    handover.save()
    _record(company=handover.company, action="TRANSITION", event_type="development.handover.transitioned", entity_type="CustomerHandover", entity_public_id=handover.public_id, actor_public_id=actor_public_id, correlation_id=correlation_id, version=handover.version, before=before, after={"status": handover.status_code, "note": note})
    return handover
