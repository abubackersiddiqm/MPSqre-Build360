from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

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


def _decimal(value) -> str:
    return str(value if value is not None else Decimal("0"))


def development_sales_overview(company: Company) -> dict:
    today = timezone.localdate()
    now = timezone.now()
    policy = SalesPolicyVersion.objects.filter(company=company).order_by("-version").first()
    reservation_hours = policy.reservation_expiry_hours if policy else 72
    collection_grace_days = policy.collection_grace_days if policy else 7
    handover_alert_days = policy.handover_alert_days if policy else 30

    inventory_qs = DevelopmentInventory.objects.filter(company=company)
    unit_qs = SaleableUnit.objects.filter(company=company)
    buyer_qs = BuyerAccount.objects.filter(company=company)
    reservation_qs = UnitReservation.objects.filter(company=company)
    booking_qs = BookingAgreement.objects.filter(company=company)
    milestone_qs = PaymentMilestone.objects.filter(company=company)
    receipt_qs = CollectionReceipt.objects.filter(company=company)
    commission_qs = BrokerCommission.objects.filter(company=company)
    handover_qs = CustomerHandover.objects.filter(company=company)

    confirmed_receipts = receipt_qs.filter(status_code="CONFIRMED")
    booking_value = booking_qs.filter(status_code__in=["APPROVED", "ACTIVE", "HANDED_OVER", "CLOSED"]).aggregate(
        total=Coalesce(Sum("total_consideration"), Decimal("0"), output_field=DecimalField(max_digits=22, decimal_places=2))
    )["total"]
    collected = confirmed_receipts.aggregate(
        total=Coalesce(Sum("amount"), Decimal("0"), output_field=DecimalField(max_digits=22, decimal_places=2))
    )["total"]
    outstanding = max(Decimal("0"), booking_value - collected)
    milestone_total = ExpressionWrapper(F("amount") + F("tax_amount"), output_field=DecimalField(max_digits=20, decimal_places=2))
    overdue_milestones = milestone_qs.annotate(total_due=milestone_total).filter(
        due_on__lt=today,
        paid_amount__lt=F("total_due"),
    ).exclude(status_code__in=["CANCELLED", "WAIVED"]).count()
    expiry_horizon = now + timedelta(hours=reservation_hours)
    expiring_reservations = reservation_qs.filter(status_code="ACTIVE", expires_at__range=(now, expiry_horizon)).count()
    handover_horizon = today + timedelta(days=handover_alert_days)
    pending_handovers = handover_qs.exclude(status_code__in=["POSSESSED", "CLOSED", "CANCELLED"]).count()
    handovers_due = handover_qs.exclude(status_code__in=["POSSESSED", "CLOSED", "CANCELLED"]).filter(planned_on__lte=handover_horizon).count()

    return {
        "company": {
            "name": company.display_name,
            "code": company.code,
            "timezone": company.timezone,
            "currency": company.currency,
        },
        "policy": {
            "status": policy.status_code if policy else "NOT_CONFIGURED",
            "version": policy.version if policy else 0,
            "reservation_expiry_hours": reservation_hours,
            "collection_grace_days": collection_grace_days,
            "handover_alert_days": handover_alert_days,
        },
        "metrics": {
            "active_developments": inventory_qs.exclude(status_code__in=["CLOSED", "CANCELLED"]).count(),
            "released_units": unit_qs.exclude(status_code__in=["DRAFT", "WITHDRAWN", "CANCELLED"]).count(),
            "available_units": unit_qs.filter(status_code__in=["RELEASED", "AVAILABLE"]).count(),
            "reserved_units": unit_qs.filter(status_code="RESERVED").count(),
            "booked_units": unit_qs.filter(status_code__in=["BOOKED", "SOLD"]).count(),
            "handed_over_units": unit_qs.filter(status_code="HANDED_OVER").count(),
            "booking_value": _decimal(booking_value),
            "collected_amount": _decimal(collected),
            "outstanding_amount": _decimal(outstanding),
            "overdue_milestones": overdue_milestones,
            "expiring_reservations": expiring_reservations,
            "pending_handovers": pending_handovers,
            "handovers_due": handovers_due,
        },
        "inventories": list(
            inventory_qs.order_by("code").values(
                "public_id", "code", "name", "project_public_id", "property_public_id", "development_type_code",
                "launch_on", "currency_code", "status_code", "version",
            )[:100]
        ),
        "units": list(
            unit_qs.select_related("inventory").order_by("inventory__code", "code").values(
                "public_id", "inventory__public_id", "inventory__code", "code", "name", "unit_type_code",
                "tower_reference", "floor_reference", "carpet_area", "saleable_area", "area_unit_code",
                "list_price", "currency_code", "tax_code", "status_code", "version",
            )[:300]
        ),
        "buyers": list(
            buyer_qs.order_by("display_name").values(
                "public_id", "account_code", "legal_name", "display_name", "buyer_type_code", "contact_name",
                "contact_email", "contact_phone", "crm_party_public_id", "status_code", "version",
            )[:250]
        ),
        "reservations": list(
            reservation_qs.select_related("unit", "unit__inventory", "buyer").order_by("-reserved_at").values(
                "public_id", "reservation_number", "unit__public_id", "unit__code", "unit__inventory__code",
                "buyer__public_id", "buyer__display_name", "reserved_at", "expires_at", "token_amount",
                "currency_code", "source_code", "status_code", "converted_booking_public_id", "version",
            )[:200]
        ),
        "bookings": list(
            booking_qs.select_related("unit", "unit__inventory", "buyer", "reservation").order_by("-booking_date", "-created_at").values(
                "public_id", "booking_number", "booking_date", "agreement_date", "unit__public_id", "unit__code",
                "unit__inventory__code", "buyer__public_id", "buyer__display_name", "reservation__public_id",
                "base_price", "discount_amount", "tax_amount", "other_charges", "total_consideration",
                "currency_code", "status_code", "version",
            )[:250]
        ),
        "milestones": list(
            milestone_qs.select_related("booking", "booking__buyer", "booking__unit").order_by("due_on", "sequence").annotate(
                total_due=milestone_total,
                outstanding=ExpressionWrapper(milestone_total - F("paid_amount"), output_field=DecimalField(max_digits=20, decimal_places=2)),
            ).values(
                "public_id", "booking__public_id", "booking__booking_number", "booking__buyer__display_name",
                "booking__unit__code", "sequence", "milestone_code", "description", "due_on", "percentage",
                "amount", "tax_amount", "paid_amount", "total_due", "outstanding", "status_code", "version",
            )[:350]
        ),
        "receipts": list(
            receipt_qs.select_related("booking", "booking__buyer", "milestone").order_by("-receipt_date", "-created_at").values(
                "public_id", "receipt_number", "booking__public_id", "booking__booking_number", "booking__buyer__display_name",
                "milestone__public_id", "milestone__milestone_code", "receipt_date", "amount", "currency_code",
                "payment_method_code", "payment_reference", "finance_reference", "status_code", "version",
            )[:300]
        ),
        "commissions": list(
            commission_qs.select_related("booking", "booking__buyer", "booking__unit").order_by("-created_at").values(
                "public_id", "booking__public_id", "booking__booking_number", "booking__buyer__display_name",
                "booking__unit__code", "broker_reference", "broker_name", "commission_percent", "commission_amount",
                "currency_code", "status_code", "approved_at", "paid_at", "version",
            )[:200]
        ),
        "handovers": list(
            handover_qs.select_related("booking", "booking__buyer", "unit", "unit__inventory").order_by("planned_on", "created_at").values(
                "public_id", "booking__public_id", "booking__booking_number", "booking__buyer__display_name",
                "unit__public_id", "unit__code", "unit__inventory__code", "planned_on", "offered_on", "possession_on",
                "open_defect_count", "status_code", "version",
            )[:200]
        ),
        "portfolio": {
            "unit_status": list(unit_qs.values("status_code").annotate(count=Count("id")).order_by("status_code")),
            "booking_status": list(booking_qs.values("status_code").annotate(count=Count("id")).order_by("status_code")),
            "collection_status": list(receipt_qs.values("status_code").annotate(count=Count("id")).order_by("status_code")),
        },
    }
