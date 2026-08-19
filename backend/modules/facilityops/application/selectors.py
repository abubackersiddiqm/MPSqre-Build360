from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

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
from modules.tenant.models import Company


def _company_payload(company: Company) -> dict[str, str]:
    return {
        "name": company.display_name,
        "code": company.code,
        "timezone": company.timezone,
        "currency": company.currency,
    }


def _rows(queryset, *fields: str, limit: int = 50) -> list[dict]:
    return list(queryset.values(*fields)[:limit])


def facility_overview(company: Company) -> dict:
    now = timezone.now()
    today = timezone.localdate()
    policy = FacilityPolicyVersion.objects.filter(company=company).order_by("-version").first()
    service_horizon = policy.preventive_horizon_days if policy else 90
    warranty_horizon = policy.warranty_alert_days if policy else 60

    facility_qs = Facility.objects.filter(company=company)
    space_qs = FacilitySpace.objects.filter(company=company)
    asset_qs = OperationalAsset.objects.filter(company=company)
    plan_qs = MaintenancePlan.objects.filter(company=company)
    request_qs = ServiceRequest.objects.filter(company=company)
    work_order_qs = FacilityWorkOrder.objects.filter(company=company)
    claim_qs = WarrantyClaim.objects.filter(company=company)
    inspection_qs = ConditionInspection.objects.filter(company=company)
    event_qs = AssetLifecycleEvent.objects.filter(company=company)

    active_assets = asset_qs.exclude(operation_status_code__in=["RETIRED", "CANCELLED"]).count()
    in_service = asset_qs.filter(operation_status_code="IN_SERVICE").count()
    availability = Decimal("0.00") if active_assets == 0 else (Decimal(in_service) * Decimal("100") / Decimal(active_assets)).quantize(Decimal("0.01"))

    metrics = {
        "active_facilities": facility_qs.filter(status_code="ACTIVE").count(),
        "managed_spaces": space_qs.exclude(status_code="RETIRED").count(),
        "operational_assets": active_assets,
        "asset_availability": str(availability),
        "service_due": asset_qs.filter(next_service_on__isnull=False, next_service_on__lte=today + timedelta(days=service_horizon)).exclude(operation_status_code__in=["RETIRED", "CANCELLED"]).count(),
        "overdue_work_orders": work_order_qs.filter(due_date__lt=today).exclude(status_code__in=["CLOSED", "CANCELLED"]).count(),
        "open_service_requests": request_qs.exclude(status_code__in=["CLOSED", "CANCELLED"]).count(),
        "sla_breaches": request_qs.filter(resolution_due_at__lt=now).exclude(status_code__in=["RESOLVED", "CLOSED", "CANCELLED"]).count(),
        "active_warranty_claims": claim_qs.exclude(status_code__in=["CLOSED", "WITHDRAWN", "CANCELLED"]).count(),
        "warranties_expiring": asset_qs.filter(warranty_end_on__gte=today, warranty_end_on__lte=today + timedelta(days=warranty_horizon)).count(),
        "critical_condition": asset_qs.filter(condition_code__in=["POOR", "CRITICAL"]).exclude(operation_status_code__in=["RETIRED", "CANCELLED"]).count(),
        "pending_inspections": inspection_qs.filter(status_code__in=["DRAFT", "SUBMITTED"]).count(),
    }

    policy_payload = {
        "status": policy.status_code if policy else "MISSING",
        "version": policy.version if policy else 0,
        "preventive_horizon_days": policy.preventive_horizon_days if policy else 0,
        "warranty_alert_days": policy.warranty_alert_days if policy else 0,
    }

    return {
        "company": _company_payload(company),
        "policy": policy_payload,
        "metrics": metrics,
        "facilities": _rows(
            facility_qs.order_by("status_code", "code"),
            "public_id", "code", "name", "facility_type_code", "site_reference", "timezone", "gross_area",
            "area_unit_code", "occupancy_capacity", "status_code", "operational_from", "version",
        ),
        "spaces": _rows(
            space_qs.select_related("facility", "parent").order_by("facility__code", "floor_reference", "code"),
            "public_id", "facility__public_id", "facility__code", "parent__public_id", "parent__code", "code", "name",
            "space_type_code", "floor_reference", "area", "area_unit_code", "criticality_code", "status_code", "version",
        ),
        "assets": _rows(
            asset_qs.select_related("facility", "space").order_by("operation_status_code", "asset_tag"),
            "public_id", "facility__public_id", "facility__code", "space__public_id", "space__code", "asset_tag", "asset_name",
            "classification_code", "manufacturer", "model_number", "serial_number", "warranty_end_on", "criticality_code",
            "condition_code", "operation_status_code", "last_service_on", "next_service_on", "maintainable", "version",
        ),
        "maintenance_plans": _rows(
            plan_qs.select_related("asset").order_by("status_code", "next_due_date"),
            "public_id", "asset__public_id", "asset__asset_tag", "code", "name", "plan_type_code", "frequency_days",
            "lead_time_days", "next_due_date", "status_code", "version",
        ),
        "work_orders": _rows(
            work_order_qs.select_related("asset", "plan", "service_request").order_by("status_code", "due_date"),
            "public_id", "asset__public_id", "asset__asset_tag", "plan__public_id", "plan__code", "service_request__request_number",
            "work_order_number", "work_type_code", "priority_code", "title", "status_code", "due_date", "scheduled_start_at",
            "completed_at", "estimated_cost", "actual_cost", "currency_code", "version",
        ),
        "service_requests": _rows(
            request_qs.select_related("facility", "space", "asset").order_by("status_code", "resolution_due_at"),
            "public_id", "facility__public_id", "facility__code", "space__code", "asset__asset_tag", "request_number",
            "category_code", "priority_code", "channel_code", "title", "status_code", "response_due_at", "resolution_due_at",
            "responded_at", "resolved_at", "version",
        ),
        "warranty_claims": _rows(
            claim_qs.select_related("asset", "work_order").order_by("status_code", "reported_on"),
            "public_id", "asset__public_id", "asset__asset_tag", "work_order__work_order_number", "claim_number",
            "supplier_reference", "warranty_reference", "reported_on", "failure_date", "claimed_amount", "approved_amount",
            "currency_code", "status_code", "resolution_note", "version",
        ),
        "inspections": _rows(
            inspection_qs.select_related("facility", "space", "asset").order_by("status_code", "scheduled_on"),
            "public_id", "facility__public_id", "facility__code", "space__code", "asset__asset_tag", "inspection_number",
            "inspection_type_code", "scheduled_on", "inspected_on", "condition_code", "score", "findings", "actions_required",
            "status_code", "version",
        ),
        "lifecycle_events": _rows(
            event_qs.select_related("asset").order_by("-occurred_at"),
            "public_id", "asset__public_id", "asset__asset_tag", "event_type_code", "occurred_at", "from_status_code",
            "to_status_code", "summary", "reference", limit=100,
        ),
    }
