from __future__ import annotations

from decimal import Decimal

from django.db.models import Avg, Sum
from django.utils import timezone

from modules.insightops.models import (
    BenefitMeasurement,
    BenefitPlan,
    BoardReport,
    ExecutiveAction,
    InsightPolicyVersion,
    KPIDefinition,
    KPIObservation,
    PortfolioSnapshot,
    StrategicObjective,
)
from modules.tenant.models import Company


def _company_payload(company: Company) -> dict[str, str]:
    return {
        "name": getattr(company, "display_name", "") or getattr(company, "legal_name", ""),
        "code": company.code,
        "timezone": company.timezone,
        "currency": company.currency,
    }


def _kpi_status(kpi: KPIDefinition, actual: Decimal | None) -> str:
    if actual is None:
        return "NO_DATA"
    if kpi.direction_code == "TARGET_RANGE":
        if kpi.target_low is None or kpi.target_high is None:
            return "NO_TARGET"
        return "ON_TARGET" if kpi.target_low <= actual <= kpi.target_high else "OFF_TARGET"
    if kpi.target_value is None:
        return "NO_TARGET"
    if kpi.direction_code == "LOWER_BETTER":
        if actual <= kpi.target_value:
            return "ON_TARGET"
        if kpi.warning_value is not None and actual <= kpi.warning_value:
            return "WARNING"
        return "CRITICAL"
    if actual >= kpi.target_value:
        return "ON_TARGET"
    if kpi.warning_value is not None and actual >= kpi.warning_value:
        return "WARNING"
    return "CRITICAL"


def insight_overview(company: Company) -> dict[str, object]:
    policy = InsightPolicyVersion.objects.filter(company=company).order_by("-version").first()
    objectives = StrategicObjective.objects.filter(company=company)
    kpis = KPIDefinition.objects.filter(company=company)
    observations = KPIObservation.objects.filter(company=company)
    snapshots = PortfolioSnapshot.objects.filter(company=company)
    benefits = BenefitPlan.objects.filter(company=company)
    measurements = BenefitMeasurement.objects.filter(company=company)
    actions = ExecutiveAction.objects.filter(company=company)
    reports = BoardReport.objects.filter(company=company)
    now = timezone.now()

    latest_observations = {}
    for item in observations.order_by("kpi_id", "-period_end", "-captured_at"):
        latest_observations.setdefault(item.kpi_id, item)

    kpi_rows: list[dict[str, object]] = []
    status_counts = {"ON_TARGET": 0, "WARNING": 0, "CRITICAL": 0, "NO_DATA": 0, "NO_TARGET": 0, "OFF_TARGET": 0}
    for kpi in kpis.select_related("objective").order_by("code"):
        observation = latest_observations.get(kpi.id)
        actual = observation.actual_value if observation else None
        status = _kpi_status(kpi, actual)
        if kpi.active:
            status_counts[status] = status_counts.get(status, 0) + 1
        kpi_rows.append(
            {
                "public_id": kpi.public_id,
                "objective__code": kpi.objective.code if kpi.objective else None,
                "code": kpi.code,
                "name": kpi.name,
                "unit_code": kpi.unit_code,
                "direction_code": kpi.direction_code,
                "frequency_code": kpi.frequency_code,
                "target_value": kpi.target_value,
                "warning_value": kpi.warning_value,
                "critical_value": kpi.critical_value,
                "target_low": kpi.target_low,
                "target_high": kpi.target_high,
                "active": kpi.active,
                "version": kpi.version,
                "latest_actual": actual,
                "latest_period_end": observation.period_end if observation else None,
                "status": status,
            }
        )

    active_kpis = max(sum(1 for row in kpi_rows if row["active"]), 1)
    on_target = status_counts.get("ON_TARGET", 0)
    kpi_health_percent = round(on_target * 100 / active_kpis, 2)
    latest_snapshot = snapshots.order_by("-as_of_date", "-created_at").first()
    expected_by_currency = {
        row["currency"]: row["value"] or Decimal("0.00")
        for row in benefits.values("currency").annotate(value=Sum("expected_financial_value"))
    }
    realized_by_currency = {
        row["currency"]: row["value"] or Decimal("0.00")
        for row in measurements.values("currency").annotate(value=Sum("realized_financial_value"))
    }
    expected = expected_by_currency.get(company.currency, Decimal("0.00"))
    realized = realized_by_currency.get(company.currency, Decimal("0.00"))
    average_confidence = measurements.aggregate(value=Avg("confidence_percent"))["value"] or Decimal("0.00")

    return {
        "company": _company_payload(company),
        "policy": {
            "status": policy.status_code if policy else "MISSING",
            "version": policy.version if policy else 0,
            "review_frequency_code": policy.review_frequency_code if policy else "MONTHLY",
            "on_target_threshold": str(policy.on_target_threshold if policy else Decimal("90.00")),
            "warning_threshold": str(policy.warning_threshold if policy else Decimal("75.00")),
        },
        "metrics": {
            "active_objectives": objectives.filter(status_code__in=["ACTIVE", "ON_TRACK", "AT_RISK"]).count(),
            "active_kpis": kpis.filter(active=True).count(),
            "kpi_health_percent": kpi_health_percent,
            "kpis_on_target": on_target,
            "kpis_warning": status_counts.get("WARNING", 0),
            "kpis_critical": status_counts.get("CRITICAL", 0) + status_counts.get("OFF_TARGET", 0),
            "portfolio_projects": latest_snapshot.projects_total if latest_snapshot else 0,
            "portfolio_at_risk": (latest_snapshot.projects_at_risk + latest_snapshot.projects_critical) if latest_snapshot else 0,
            "expected_benefit": str(expected),
            "realized_benefit": str(realized),
            "benefit_confidence_percent": str(round(average_confidence, 2)),
            "open_actions": actions.exclude(status_code__in=["COMPLETED", "CANCELLED"]).count(),
            "overdue_actions": actions.exclude(status_code__in=["COMPLETED", "CANCELLED"]).filter(due_at__lt=now).count(),
            "pending_board_reports": reports.filter(status_code__in=["DRAFT", "IN_REVIEW", "APPROVED"]).count(),
        },
        "benefit_currency_breakdown": {
            code: {"expected": str(expected_by_currency.get(code, Decimal("0.00"))), "realized": str(realized_by_currency.get(code, Decimal("0.00")))}
            for code in sorted(set(expected_by_currency) | set(realized_by_currency))
        },
        "objectives": list(
            objectives.order_by("status_code", "target_date", "code").values(
                "public_id", "code", "name", "description", "perspective_code", "status_code",
                "owner_public_id", "weight_percent", "start_date", "target_date", "target_outcome", "version",
            )[:50]
        ),
        "kpis": kpi_rows[:80],
        "observations": list(
            observations.select_related("kpi").order_by("-period_end", "kpi__code").values(
                "public_id", "kpi__code", "period_start", "period_end", "actual_value", "source_code",
                "source_reference", "data_quality_code", "captured_by_public_id", "captured_at",
            )[:80]
        ),
        "portfolio_snapshots": list(
            snapshots.order_by("-as_of_date", "-created_at").values(
                "public_id", "code", "as_of_date", "status_code", "projects_total", "projects_healthy",
                "projects_at_risk", "projects_critical", "schedule_performance_percent",
                "cost_performance_percent", "portfolio_value", "currency", "narrative", "version",
            )[:30]
        ),
        "benefits": list(
            benefits.select_related("objective").order_by("status_code", "target_date", "code").values(
                "public_id", "objective__code", "code", "name", "category_code", "status_code", "unit_code",
                "baseline_value", "target_value", "expected_financial_value", "currency", "owner_public_id",
                "target_date", "version",
            )[:50]
        ),
        "benefit_measurements": list(
            measurements.select_related("benefit").order_by("-measured_at").values(
                "public_id", "benefit__code", "measured_at", "actual_value", "realized_financial_value",
                "currency", "confidence_percent", "captured_by_public_id",
            )[:60]
        ),
        "actions": list(
            actions.order_by("status_code", "priority_code", "due_at").values(
                "public_id", "code", "title", "description", "priority_code", "status_code",
                "source_type_code", "source_public_id", "owner_public_id", "due_at", "completed_at",
                "resolution_summary", "version",
            )[:60]
        ),
        "board_reports": list(
            reports.order_by("status_code", "-period_end").values(
                "public_id", "code", "title", "period_start", "period_end", "status_code",
                "executive_summary", "scorecard", "decisions", "prepared_by_public_id",
                "approved_by_public_id", "published_at", "version",
            )[:40]
        ),
    }
