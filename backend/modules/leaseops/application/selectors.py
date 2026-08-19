from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import Coalesce
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
from modules.tenant.models import Company


def _decimal(value) -> str:
    return str(value if value is not None else Decimal("0"))


def property_lease_overview(company: Company) -> dict:
    today = timezone.localdate()
    now = timezone.now()
    policy = PropertyPolicyVersion.objects.filter(company=company).order_by("-version").first()
    expiry_days = policy.lease_expiry_alert_days if policy else 90
    expiry_horizon = today + timedelta(days=expiry_days)

    property_qs = ManagedProperty.objects.filter(company=company)
    unit_qs = LeaseableUnit.objects.filter(company=company)
    tenant_qs = TenantAccount.objects.filter(company=company)
    lease_qs = LeaseAgreement.objects.filter(company=company)
    charge_qs = LeaseCharge.objects.filter(company=company)
    occupancy_qs = OccupancyRecord.objects.filter(company=company)
    invoice_qs = RentInvoice.objects.filter(company=company)
    case_qs = TenantExperienceCase.objects.filter(company=company)
    event_qs = LeaseLifecycleEvent.objects.filter(company=company)

    open_invoice_statuses = ["ISSUED", "PARTIALLY_PAID"]
    invoice_total = ExpressionWrapper(F("gross_amount") + F("tax_amount"), output_field=DecimalField(max_digits=20, decimal_places=2))
    invoice_due = ExpressionWrapper(invoice_total - F("paid_amount"), output_field=DecimalField(max_digits=20, decimal_places=2))
    receivable = invoice_qs.filter(status_code__in=open_invoice_statuses).aggregate(
        total=Coalesce(Sum(invoice_due), Decimal("0"), output_field=DecimalField(max_digits=20, decimal_places=2))
    )["total"]
    overdue_receivable = invoice_qs.filter(status_code__in=open_invoice_statuses, due_date__lt=today).aggregate(
        total=Coalesce(Sum(invoice_due), Decimal("0"), output_field=DecimalField(max_digits=20, decimal_places=2))
    )["total"]
    units_total = unit_qs.exclude(status_code__in=["RETIRED", "INACTIVE"]).count()
    occupied_units = unit_qs.filter(status_code__in=["LEASED", "OCCUPIED"]).count()
    occupancy_rate = round((occupied_units / units_total * 100), 2) if units_total else 0
    active_cases = case_qs.exclude(status_code__in=["CLOSED", "CANCELLED"]).count()
    case_breaches = case_qs.exclude(status_code__in=["RESOLVED", "CLOSED", "CANCELLED"]).filter(resolution_due_at__lt=now).count()
    expiring_leases = lease_qs.filter(status_code="ACTIVE", end_on__range=(today, expiry_horizon)).count()
    deposits = lease_qs.filter(status_code__in=["APPROVED", "ACTIVE"]).aggregate(
        total=Coalesce(Sum("security_deposit"), Decimal("0"), output_field=DecimalField(max_digits=20, decimal_places=2))
    )["total"]

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
            "lease_expiry_alert_days": expiry_days,
            "invoice_grace_days": policy.invoice_grace_days if policy else 5,
        },
        "metrics": {
            "active_properties": property_qs.filter(status_code="ACTIVE").count(),
            "occupancy_rate": occupancy_rate,
            "available_units": unit_qs.filter(status_code="AVAILABLE").count(),
            "active_leases": lease_qs.filter(status_code="ACTIVE").count(),
            "expiring_leases": expiring_leases,
            "open_receivable": _decimal(receivable),
            "overdue_receivable": _decimal(overdue_receivable),
            "open_cases": active_cases,
            "case_sla_breaches": case_breaches,
            "security_deposits": _decimal(deposits),
        },
        "properties": list(
            property_qs.order_by("code").values(
                "public_id", "code", "name", "property_type_code", "facility_public_id", "external_reference",
                "timezone", "gross_area", "area_unit_code", "ownership_code", "status_code", "version",
            )[:100]
        ),
        "units": list(
            unit_qs.select_related("property").order_by("property__code", "code").values(
                "public_id", "property__public_id", "property__code", "code", "name", "unit_type_code",
                "floor_reference", "area", "area_unit_code", "bedroom_count", "parking_count", "market_rent",
                "currency_code", "status_code", "version",
            )[:250]
        ),
        "tenants": list(
            tenant_qs.order_by("display_name").values(
                "public_id", "account_code", "legal_name", "display_name", "tenant_type_code", "contact_name",
                "status_code", "version",
            )[:200]
        ),
        "leases": list(
            lease_qs.select_related("property", "unit", "tenant").order_by("-created_at").values(
                "public_id", "lease_number", "lease_type_code", "property__public_id", "property__code",
                "unit__public_id", "unit__code", "tenant__public_id", "tenant__display_name", "start_on", "end_on",
                "billing_cycle_code", "base_rent", "currency_code", "security_deposit", "escalation_percent",
                "notice_days", "status_code", "version",
            )[:150]
        ),
        "charges": list(
            charge_qs.select_related("lease").order_by("lease__lease_number", "charge_code").values(
                "public_id", "lease__public_id", "lease__lease_number", "charge_code", "charge_type_code",
                "description", "amount", "currency_code", "frequency_code", "effective_from", "effective_to",
                "tax_code", "recoverable", "status_code", "version",
            )[:250]
        ),
        "occupancies": list(
            occupancy_qs.select_related("lease", "unit").order_by("-created_at").values(
                "public_id", "lease__public_id", "lease__lease_number", "unit__public_id", "unit__code",
                "occupant_reference", "move_in_on", "move_out_on", "occupant_count", "status_code", "version",
            )[:150]
        ),
        "invoices": list(
            invoice_qs.select_related("lease", "lease__tenant", "lease__unit").order_by("-issue_date", "-created_at").annotate(
                invoice_total=invoice_total, outstanding=invoice_due
            ).values(
                "public_id", "invoice_number", "lease__public_id", "lease__lease_number", "lease__tenant__display_name",
                "lease__unit__code", "period_start", "period_end", "issue_date", "due_date", "gross_amount",
                "tax_amount", "paid_amount", "invoice_total", "outstanding", "currency_code", "status_code",
                "external_finance_reference", "version",
            )[:250]
        ),
        "tenant_cases": list(
            case_qs.select_related("tenant", "property", "unit").order_by("-created_at").values(
                "public_id", "case_number", "tenant__public_id", "tenant__display_name", "property__public_id",
                "property__code", "unit__public_id", "unit__code", "category_code", "priority_code", "channel_code",
                "title", "status_code", "response_due_at", "resolution_due_at", "responded_at", "resolved_at",
                "satisfaction_score", "version",
            )[:200]
        ),
        "lifecycle_events": list(
            event_qs.select_related("lease").order_by("-occurred_at").values(
                "public_id", "lease__lease_number", "event_type_code", "occurred_at", "from_status_code",
                "to_status_code", "summary", "amount", "currency_code",
            )[:100]
        ),
        "portfolio": {
            "unit_status": list(unit_qs.values("status_code").annotate(count=Count("id")).order_by("status_code")),
            "lease_status": list(lease_qs.values("status_code").annotate(count=Count("id")).order_by("status_code")),
            "case_priority": list(case_qs.exclude(status_code__in=["CLOSED", "CANCELLED"]).values("priority_code").annotate(count=Count("id")).order_by("priority_code")),
        },
    }
