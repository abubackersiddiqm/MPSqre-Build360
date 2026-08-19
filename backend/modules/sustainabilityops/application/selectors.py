from __future__ import annotations

from decimal import Decimal

from django.db.models import DecimalField, ExpressionWrapper, F, Sum, Value
from django.utils import timezone

from modules.sustainabilityops.models import (
    AssuranceAssessment,
    CarbonActivity,
    CarbonInventory,
    DisclosureReport,
    EmissionFactor,
    ESGInitiative,
    ResourceConsumption,
    SustainabilityPolicyVersion,
    SustainabilityTarget,
    WasteMovement,
)
from modules.tenant.models import Company


def _decimal(value: Decimal | None, places: str = "0.00") -> str:
    return str((value or Decimal("0")).quantize(Decimal(places)))


def sustainability_overview(company: Company) -> dict:
    policy = SustainabilityPolicyVersion.objects.filter(company=company).order_by("-version").first()

    verified_activities = CarbonActivity.objects.filter(company=company, status_code="VERIFIED")
    total_emissions = verified_activities.aggregate(total=Sum("calculated_kg_co2e"))["total"] or Decimal("0")
    scope_totals = {"SCOPE_1": Decimal("0"), "SCOPE_2": Decimal("0"), "SCOPE_3": Decimal("0")}
    for row in verified_activities.values("factor__scope_code").annotate(total=Sum("calculated_kg_co2e")):
        scope = row["factor__scope_code"]
        if scope in scope_totals:
            scope_totals[scope] = row["total"] or Decimal("0")

    energy_kwh = (
        ResourceConsumption.objects.filter(company=company, resource_type_code="ENERGY", unit_code="KWH")
        .aggregate(total=Sum("quantity"))["total"]
        or Decimal("0")
    )
    renewable_quantity = ExpressionWrapper(
        F("quantity") * F("renewable_percent") / Value(Decimal("100")),
        output_field=DecimalField(max_digits=24, decimal_places=8),
    )
    renewable_energy_kwh = (
        ResourceConsumption.objects.filter(
            company=company, resource_type_code="ENERGY", unit_code="KWH", renewable_percent__gt=0
        ).aggregate(total=Sum(renewable_quantity))["total"]
        or Decimal("0")
    )
    water_m3 = (
        ResourceConsumption.objects.filter(company=company, resource_type_code="WATER", unit_code="M3")
        .aggregate(total=Sum("quantity"))["total"]
        or Decimal("0")
    )
    waste_kg = (
        WasteMovement.objects.filter(company=company, unit_code="KG").aggregate(total=Sum("quantity"))["total"]
        or Decimal("0")
    )
    diverted_kg = (
        WasteMovement.objects.filter(
            company=company,
            unit_code="KG",
            treatment_code__in=["RECYCLED", "REUSED", "RECOVERY", "COMPOSTED"],
        ).aggregate(total=Sum("quantity"))["total"]
        or Decimal("0")
    )
    diversion_percent = (diverted_kg / waste_kg * Decimal("100")) if waste_kg else Decimal("0")
    renewable_percent = (renewable_energy_kwh / energy_kwh * Decimal("100")) if energy_kwh else Decimal("0")

    targets_qs = SustainabilityTarget.objects.filter(company=company)
    initiatives_qs = ESGInitiative.objects.filter(company=company)
    assessments_qs = AssuranceAssessment.objects.filter(company=company)
    disclosures_qs = DisclosureReport.objects.filter(company=company)
    inventories_qs = CarbonInventory.objects.filter(company=company)

    factors = list(
        EmissionFactor.objects.filter(company=company)
        .order_by("-active", "category_code", "code")
        .values(
            "public_id", "code", "name", "category_code", "scope_code", "activity_unit_code",
            "factor_kg_co2e_per_unit", "region_code", "source_name", "valid_from", "valid_to", "active", "version",
        )[:30]
    )
    activities = list(
        CarbonActivity.objects.filter(company=company)
        .order_by("-activity_date", "-created_at")
        .values(
            "public_id", "factor__code", "factor__name", "factor__scope_code", "project_public_id",
            "site_reference", "activity_date", "quantity", "activity_unit_code", "calculated_kg_co2e",
            "status_code", "version", "source_reference",
        )[:30]
    )
    inventories = list(
        inventories_qs.order_by("-period_end", "-created_at").values(
            "public_id", "code", "period_start", "period_end", "status_code", "scope1_kg_co2e",
            "scope2_kg_co2e", "scope3_kg_co2e", "offsets_kg_co2e", "net_kg_co2e", "activity_count",
            "methodology_code", "version", "published_at",
        )[:20]
    )
    resources = list(
        ResourceConsumption.objects.filter(company=company)
        .order_by("-period_end", "-created_at")
        .values(
            "public_id", "resource_type_code", "resource_subtype_code", "project_public_id", "site_reference",
            "period_start", "period_end", "quantity", "unit_code", "renewable_percent", "cost_amount", "currency",
            "source_reference", "version",
        )[:30]
    )
    waste = list(
        WasteMovement.objects.filter(company=company)
        .order_by("-movement_date", "-created_at")
        .values(
            "public_id", "movement_date", "waste_type_code", "classification_code", "quantity", "unit_code",
            "treatment_code", "site_reference", "manifest_reference", "destination", "status_code", "version",
        )[:30]
    )
    targets = list(
        targets_qs.order_by("target_date", "code").values(
            "public_id", "code", "name", "category_code", "metric_unit_code", "direction_code", "baseline_value",
            "target_value", "latest_value", "progress_percent", "start_date", "target_date", "status_code", "version",
        )[:30]
    )
    initiatives = list(
        initiatives_qs.order_by("due_date", "code").values(
            "public_id", "target__code", "code", "name", "pillar_code", "status_code", "project_public_id",
            "budget_amount", "realized_value", "currency", "due_date", "completed_at", "version",
        )[:30]
    )
    assessments = list(
        assessments_qs.order_by("-period_end", "-created_at").values(
            "public_id", "code", "assessment_type_code", "framework_code", "period_start", "period_end",
            "status_code", "findings_total", "major_findings", "minor_findings", "opinion_code", "assessor_name",
            "version", "published_at",
        )[:30]
    )
    disclosures = list(
        disclosures_qs.order_by("-period_end", "-created_at").values(
            "public_id", "code", "title", "framework_code", "period_start", "period_end", "status_code",
            "version", "published_at",
        )[:30]
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
            "base_year": policy.base_year if policy else None,
            "boundary": policy.organizational_boundary_code if policy else "NOT_CONFIGURED",
        },
        "metrics": {
            "verified_emissions_tco2e": _decimal(total_emissions / Decimal("1000")),
            "scope1_tco2e": _decimal(scope_totals["SCOPE_1"] / Decimal("1000")),
            "scope2_tco2e": _decimal(scope_totals["SCOPE_2"] / Decimal("1000")),
            "scope3_tco2e": _decimal(scope_totals["SCOPE_3"] / Decimal("1000")),
            "verified_activities": verified_activities.count(),
            "active_factors": EmissionFactor.objects.filter(company=company, active=True).count(),
            "energy_kwh": _decimal(energy_kwh),
            "renewable_energy_percent": _decimal(renewable_percent),
            "water_m3": _decimal(water_m3),
            "waste_kg": _decimal(waste_kg),
            "waste_diversion_percent": _decimal(diversion_percent),
            "active_targets": targets_qs.filter(status_code__in=["ACTIVE", "AT_RISK"]).count(),
            "targets_at_risk": targets_qs.filter(status_code="AT_RISK").count(),
            "open_initiatives": initiatives_qs.exclude(status_code__in=["COMPLETED", "CANCELLED"]).count(),
            "open_assessments": assessments_qs.exclude(status_code__in=["CLOSED", "CANCELLED"]).count(),
            "major_findings": assessments_qs.exclude(status_code__in=["CLOSED", "CANCELLED"]).aggregate(total=Sum("major_findings"))["total"] or 0,
            "pending_disclosures": disclosures_qs.exclude(status_code__in=["PUBLISHED", "ARCHIVED", "CANCELLED"]).count(),
            "published_inventories": inventories_qs.filter(status_code="PUBLISHED").count(),
            "generated_at": timezone.now().isoformat(),
        },
        "factors": factors,
        "activities": activities,
        "inventories": inventories,
        "resources": resources,
        "waste": waste,
        "targets": targets,
        "initiatives": initiatives,
        "assessments": assessments,
        "disclosures": disclosures,
    }
