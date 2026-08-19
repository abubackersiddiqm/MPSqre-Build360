from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Count
from django.utils import timezone

from modules.stabilityops.models import (
    PerformanceSample,
    ProductionIncident,
    RegressionRecord,
    ServiceEndpoint,
    StabilityPolicyVersion,
    StabilityScan,
    StabilizationGate,
)
from modules.tenant.models import Company


def _percentile(values: list[int], percentile: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * percentile))))
    return int(ordered[index])


def _iso(value):
    return value.isoformat() if value else None


def stability_overview(company: Company) -> dict[str, object]:
    policy = (
        StabilityPolicyVersion.objects.filter(company=company, status_code="PUBLISHED").order_by("-version").first()
        or StabilityPolicyVersion.objects.filter(company=company).order_by("-version").first()
    )
    since = timezone.now() - timezone.timedelta(hours=24)
    sample_base = PerformanceSample.objects.filter(company=company, observed_at__gte=since)
    sample_rows = list(sample_base.order_by("-observed_at").values_list("duration_ms", "http_status")[:5000])
    durations = [duration for duration, _ in sample_rows]
    failures = sum(1 for _, status in sample_rows if status is not None and status >= 500)
    successful = sum(1 for _, status in sample_rows if status is not None and status < 500)
    error_rate = Decimal("0.000")
    availability = Decimal("0.000")
    if sample_rows:
        error_rate = (Decimal(failures) * Decimal(100) / Decimal(len(sample_rows))).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        availability = (Decimal(successful) * Decimal(100) / Decimal(len(sample_rows))).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)

    incident_base = ProductionIncident.objects.filter(company=company)
    regression_base = RegressionRecord.objects.filter(company=company)
    gate_base = StabilizationGate.objects.filter(company=company)
    required_gates = gate_base.filter(is_required=True)
    latest_scan = StabilityScan.objects.filter(company=company).order_by("-started_at").first()

    endpoints = list(
        ServiceEndpoint.objects.filter(company=company).order_by("code").values(
            "public_id",
            "code",
            "name",
            "route_pattern",
            "method_code",
            "service_code",
            "critical",
            "target_p95_ms",
            "target_availability_percent",
            "active",
            "version",
        )
    )
    incidents = [
        {
            "public_id": str(item.public_id),
            "code": item.code,
            "title": item.title,
            "severity": item.severity_code,
            "status": item.status_code,
            "source": item.source_code,
            "service": item.affected_service_code,
            "impact": item.impact_summary,
            "root_cause": item.root_cause,
            "resolution": item.resolution_summary,
            "detected_at": _iso(item.detected_at),
            "acknowledged_at": _iso(item.acknowledged_at),
            "resolved_at": _iso(item.resolved_at),
            "version": item.version,
        }
        for item in incident_base.order_by("-detected_at")[:30]
    ]
    regressions = [
        {
            "public_id": str(item.public_id),
            "code": item.code,
            "title": item.title,
            "area": item.area_code,
            "severity": item.severity_code,
            "status": item.status_code,
            "baseline": str(item.baseline_value) if item.baseline_value is not None else None,
            "current": str(item.current_value) if item.current_value is not None else None,
            "threshold": str(item.threshold_value) if item.threshold_value is not None else None,
            "unit": item.unit_code,
            "detected_at": _iso(item.detected_at),
            "fixed_at": _iso(item.fixed_at),
            "notes": item.notes,
            "version": item.version,
        }
        for item in regression_base.order_by("-detected_at")[:30]
    ]
    gates = [
        {
            "public_id": str(item.public_id),
            "code": item.code,
            "name": item.name,
            "category": item.category_code,
            "description": item.description,
            "required": item.is_required,
            "status": item.status_code,
            "notes": item.notes,
            "evidence": item.evidence,
            "decided_at": _iso(item.decided_at),
            "version": item.version,
        }
        for item in gate_base.order_by("category_code", "code")
    ]
    recent_samples = [
        {
            "public_id": str(item.public_id),
            "endpoint_code": item.endpoint.code if item.endpoint else None,
            "source": item.source_code,
            "route": item.route_label,
            "method": item.method_code,
            "http_status": item.http_status,
            "duration_ms": item.duration_ms,
            "observed_at": _iso(item.observed_at),
        }
        for item in PerformanceSample.objects.filter(company=company).select_related("endpoint").order_by("-observed_at")[:50]
    ]
    latest_scan_payload = None
    if latest_scan:
        latest_scan_payload = {
            "public_id": str(latest_scan.public_id),
            "status": latest_scan.status_code,
            "checks_total": latest_scan.checks_total,
            "checks_passed": latest_scan.checks_passed,
            "checks_failed": latest_scan.checks_failed,
            "api_p50_ms": latest_scan.api_p50_ms,
            "api_p95_ms": latest_scan.api_p95_ms,
            "api_p99_ms": latest_scan.api_p99_ms,
            "error_rate_percent": str(latest_scan.error_rate_percent),
            "results": latest_scan.results,
            "started_at": _iso(latest_scan.started_at),
            "completed_at": _iso(latest_scan.completed_at),
        }

    policy_payload = {
        "status": policy.status_code if policy else "NOT_CONFIGURED",
        "version": policy.version if policy else 0,
        "availability_target_percent": str(policy.availability_target_percent) if policy else "99.90",
        "api_p95_budget_ms": policy.api_p95_budget_ms if policy else 750,
        "page_load_budget_ms": policy.page_load_budget_ms if policy else 2500,
        "slow_request_threshold_ms": policy.slow_request_threshold_ms if policy else 1000,
        "error_budget_percent": str(policy.error_budget_percent) if policy else "0.10",
        "incident_ack_sla_minutes": policy.incident_ack_sla_minutes if policy else 15,
        "critical_resolution_sla_minutes": policy.critical_resolution_sla_minutes if policy else 240,
        "telemetry_retention_days": policy.telemetry_retention_days if policy else 30,
    }

    return {
        "company": {
            "name": company.display_name,
            "code": company.code,
            "timezone": company.timezone,
            "currency": company.currency,
        },
        "policy": policy_payload,
        "metrics": {
            "availability_24h": float(availability),
            "error_rate_24h": float(error_rate),
            "api_p50_ms": _percentile(durations, 0.50) or 0,
            "api_p95_ms": _percentile(durations, 0.95) or 0,
            "api_p99_ms": _percentile(durations, 0.99) or 0,
            "samples_24h": len(sample_rows),
            "open_incidents": incident_base.exclude(status_code__in=["RESOLVED", "CLOSED"]).count(),
            "critical_incidents": incident_base.filter(severity_code__in=["P0", "P1"]).exclude(status_code__in=["RESOLVED", "CLOSED"]).count(),
            "open_regressions": regression_base.filter(status_code="OPEN").count(),
            "required_gates_total": required_gates.count(),
            "required_gates_passed": required_gates.filter(status_code="PASSED").count(),
            "endpoint_count": len(endpoints),
            "endpoint_samples": sample_base.values("endpoint_id").annotate(total=Count("id")).count(),
        },
        "endpoints": endpoints,
        "incidents": incidents,
        "regressions": regressions,
        "gates": gates,
        "recent_samples": recent_samples,
        "latest_scan": latest_scan_payload,
    }
