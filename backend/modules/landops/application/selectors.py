from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from modules.landops.models import (
    AcquisitionEvent,
    AcquisitionOpportunity,
    CommercialOffer,
    DueDiligenceCase,
    FeasibilityScenario,
    LandParcel,
    LandPolicyVersion,
    LandRisk,
    OwnershipInterest,
    StatutoryApproval,
)
from modules.tenant.models import Company


def _decimal(value) -> str:
    return str(value if value is not None else Decimal("0"))


def land_acquisition_overview(company: Company) -> dict:
    today = timezone.localdate()
    policy = LandPolicyVersion.objects.filter(company=company).order_by("-version").first()
    due_days = policy.due_diligence_target_days if policy else 45
    approval_days = policy.approval_alert_days if policy else 60
    margin_threshold = policy.minimum_margin_percent if policy else Decimal("15.0000")

    parcel_qs = LandParcel.objects.filter(company=company)
    owner_qs = OwnershipInterest.objects.filter(company=company)
    diligence_qs = DueDiligenceCase.objects.filter(company=company)
    feasibility_qs = FeasibilityScenario.objects.filter(company=company)
    opportunity_qs = AcquisitionOpportunity.objects.filter(company=company)
    offer_qs = CommercialOffer.objects.filter(company=company)
    approval_qs = StatutoryApproval.objects.filter(company=company)
    risk_qs = LandRisk.objects.filter(company=company)
    event_qs = AcquisitionEvent.objects.filter(company=company)

    active_parcels = parcel_qs.exclude(status_code__in=["REJECTED", "ARCHIVED", "DISPOSED"]).count()
    open_diligence = diligence_qs.exclude(status_code__in=["CLEARED", "REJECTED", "CANCELLED"]).count()
    diligence_blockers = sum(len(item or []) for item in diligence_qs.exclude(status_code__in=["CLEARED", "CANCELLED"]).values_list("blockers", flat=True))
    approved_scenarios = feasibility_qs.filter(status_code="APPROVED").count()
    margin_exceptions = feasibility_qs.filter(status_code="APPROVED", projected_margin_percent__lt=margin_threshold).count()
    pipeline = opportunity_qs.exclude(stage_code__in=["ACQUIRED", "CLOSED", "DROPPED"])
    expiring_approvals = approval_qs.filter(status_code="APPROVED", expiry_on__range=(today, today + timedelta(days=approval_days))).count()
    open_high_risks = risk_qs.filter(severity_code__in=["HIGH", "CRITICAL"]).exclude(status_code__in=["ACCEPTED", "CLOSED"]).count()

    pipeline_value = list(
        pipeline.values("currency_code").annotate(
            amount=Coalesce(Sum("target_price"), Decimal("0"), output_field=DecimalField(max_digits=24, decimal_places=2)),
            count=Count("id"),
        ).order_by("currency_code")
    )
    accepted_offer_value = list(
        offer_qs.filter(status_code="ACCEPTED").values("currency_code").annotate(
            amount=Coalesce(Sum("amount"), Decimal("0"), output_field=DecimalField(max_digits=24, decimal_places=2)),
            count=Count("id"),
        ).order_by("currency_code")
    )
    area_by_unit = list(
        parcel_qs.values("area_unit_code").annotate(
            gross_area=Coalesce(Sum("gross_area"), Decimal("0"), output_field=DecimalField(max_digits=24, decimal_places=3)),
            usable_area=Coalesce(Sum("usable_area"), Decimal("0"), output_field=DecimalField(max_digits=24, decimal_places=3)),
            count=Count("id"),
        ).order_by("area_unit_code")
    )

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
            "due_diligence_target_days": due_days,
            "approval_alert_days": approval_days,
            "minimum_margin_percent": _decimal(margin_threshold),
        },
        "metrics": {
            "active_parcels": active_parcels,
            "verified_owners": owner_qs.filter(verification_status_code="VERIFIED").count(),
            "open_diligence": open_diligence,
            "diligence_blockers": diligence_blockers,
            "approved_scenarios": approved_scenarios,
            "margin_exceptions": margin_exceptions,
            "pipeline_opportunities": pipeline.count(),
            "accepted_offers": offer_qs.filter(status_code="ACCEPTED").count(),
            "expiring_approvals": expiring_approvals,
            "open_high_risks": open_high_risks,
        },
        "parcels": list(
            parcel_qs.order_by("parcel_code").values(
                "public_id", "parcel_code", "name", "parcel_type_code", "jurisdiction_code", "survey_reference",
                "title_reference", "gross_area", "usable_area", "area_unit_code", "zoning_code", "current_use_code",
                "status_code", "version",
            )[:200]
        ),
        "ownerships": list(
            owner_qs.select_related("parcel").order_by("parcel__parcel_code", "owner_name").values(
                "public_id", "parcel__public_id", "parcel__parcel_code", "owner_name", "owner_type_code", "share_percent",
                "ownership_document_reference", "encumbrance_flag", "encumbrance_summary", "verification_status_code",
                "verified_at", "version",
            )[:300]
        ),
        "diligence": list(
            diligence_qs.select_related("parcel").order_by("target_on", "case_number").values(
                "public_id", "case_number", "parcel__public_id", "parcel__parcel_code", "parcel__name", "category_code",
                "opened_on", "target_on", "status_code", "risk_rating_code", "findings", "blockers", "decision_note", "version",
            )[:300]
        ),
        "feasibilities": list(
            feasibility_qs.select_related("parcel").order_by("parcel__parcel_code", "scenario_code").values(
                "public_id", "scenario_code", "name", "parcel__public_id", "parcel__parcel_code", "scenario_type_code",
                "gross_development_area", "saleable_area", "area_unit_code", "planned_units", "estimated_revenue", "land_cost",
                "construction_cost", "soft_cost", "finance_cost", "contingency_cost", "projected_margin_percent", "irr_percent",
                "currency_code", "status_code", "decision_note", "version",
            )[:250]
        ),
        "opportunities": list(
            opportunity_qs.select_related("parcel", "feasibility").order_by("expected_close_on", "opportunity_code").values(
                "public_id", "opportunity_code", "parcel__public_id", "parcel__parcel_code", "parcel__name",
                "feasibility__public_id", "feasibility__scenario_code", "seller_name", "acquisition_method_code", "stage_code",
                "asking_price", "target_price", "approved_budget", "currency_code", "probability_percent", "expected_close_on", "version",
            )[:250]
        ),
        "offers": list(
            offer_qs.select_related("opportunity", "opportunity__parcel").order_by("-offer_date", "offer_number").values(
                "public_id", "offer_number", "opportunity__public_id", "opportunity__opportunity_code",
                "opportunity__parcel__parcel_code", "offer_date", "amount", "currency_code", "validity_until",
                "status_code", "conditions", "decision_note", "version",
            )[:250]
        ),
        "approvals": list(
            approval_qs.select_related("parcel", "opportunity").order_by("expiry_on", "approval_code").values(
                "public_id", "approval_code", "parcel__public_id", "parcel__parcel_code", "opportunity__public_id",
                "opportunity__opportunity_code", "approval_type_code", "authority_name", "application_reference",
                "submitted_on", "expected_on", "approved_on", "expiry_on", "status_code", "mandatory_for_acquisition",
                "evidence_reference", "version",
            )[:300]
        ),
        "risks": list(
            risk_qs.select_related("parcel", "opportunity").order_by("due_on", "risk_number").values(
                "public_id", "risk_number", "parcel__public_id", "parcel__parcel_code", "opportunity__public_id",
                "opportunity__opportunity_code", "category_code", "severity_code", "probability_code", "title",
                "description", "mitigation_plan", "due_on", "status_code", "version",
            )[:300]
        ),
        "events": list(
            event_qs.select_related("opportunity", "opportunity__parcel").order_by("-event_on").values(
                "public_id", "opportunity__public_id", "opportunity__opportunity_code", "opportunity__parcel__parcel_code",
                "event_type_code", "event_on", "summary", "evidence",
            )[:200]
        ),
        "portfolio": {
            "parcel_status": list(parcel_qs.values("status_code").annotate(count=Count("id")).order_by("status_code")),
            "opportunity_stage": list(opportunity_qs.values("stage_code").annotate(count=Count("id")).order_by("stage_code")),
            "risk_status": list(risk_qs.values("status_code", "severity_code").annotate(count=Count("id")).order_by("severity_code", "status_code")),
            "pipeline_value": pipeline_value,
            "accepted_offer_value": accepted_offer_value,
            "area_by_unit": area_by_unit,
        },
    }
