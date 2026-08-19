from __future__ import annotations

import uuid
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.apps import apps
from django.core import checks
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.migrations.recorder import MigrationRecorder
from django.urls import resolve
from django.utils import timezone

from modules.identity.models import Permission
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
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

DEFAULT_ENDPOINTS = [
    ("HEALTH_LIVE", "Backend live health", "/api/v1/health/live", 250, True),
    ("HEALTH_READY", "Backend readiness health", "/api/v1/health/ready", 500, True),
    ("TENANT_CONTEXT", "Current company context", "/api/v1/companies/current", 500, True),
    ("RELEASE_READINESS", "Release readiness overview", "/api/v1/release-readiness/overview", 750, True),
    ("PROJECT_WORK", "Project and work overview", "/api/v1/project-work/overview", 750, True),
    ("MY_WORK", "Employee My Work overview", "/api/v1/my-work/overview", 750, True),
]

DEFAULT_GATES = [
    ("NO_CRITICAL_ERRORS", "No unresolved critical errors", "RELIABILITY"),
    ("PERFORMANCE_BUDGET", "Core routes remain inside performance budgets", "PERFORMANCE"),
    ("SECURITY_REGRESSION", "No open security regression", "SECURITY"),
    ("TENANT_ISOLATION", "Tenant isolation regression suite passed", "SECURITY"),
    ("MIGRATION_CLEAN", "Migration state is clean", "DATABASE"),
    ("BACKUP_RESTORE", "Backup restore drill is current", "RECOVERY"),
    ("UAT_NO_BLOCKERS", "No blocking UAT defect remains", "QUALITY"),
    ("OBSERVABILITY", "Request timing and production telemetry are active", "OBSERVABILITY"),
    ("INCIDENT_RESPONSE", "Incident response ownership and SLAs are ready", "OPERATIONS"),
    ("PRODUCTION_SIGNOFF", "Production stabilization sign-off completed", "GOVERNANCE"),
]


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
    policy, policy_created = StabilityPolicyVersion.objects.get_or_create(
        company=company,
        version=1,
        defaults={
            "status_code": "DRAFT",
            "configuration": {"phase": 34, "release": "v1-stabilization"},
        },
    )
    endpoint_count = 0
    for code, name, route, target, critical in DEFAULT_ENDPOINTS:
        _, created = ServiceEndpoint.objects.get_or_create(
            company=company,
            code=code,
            defaults={
                "name": name,
                "route_pattern": route,
                "method_code": "GET",
                "service_code": "BACKEND",
                "critical": critical,
                "target_p95_ms": target,
                "active": True,
            },
        )
        endpoint_count += int(created)
    gate_count = 0
    for code, name, category in DEFAULT_GATES:
        _, created = StabilizationGate.objects.get_or_create(
            company=company,
            code=code,
            defaults={
                "name": name,
                "category_code": category,
                "description": "Required Build360 v1 stabilization control.",
                "is_required": True,
            },
        )
        gate_count += int(created)
    return {"policy": int(policy_created), "endpoints": endpoint_count, "gates": gate_count, "policy_version": policy.version}


@transaction.atomic
def create_endpoint(
    *,
    company: Company,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    **data: Any,
) -> ServiceEndpoint:
    endpoint = ServiceEndpoint(company=company, **data)
    endpoint.full_clean()
    endpoint.save()
    _record(
        company=company,
        action="CREATE",
        event_type="stability.endpoint.created",
        entity_type="ServiceEndpoint",
        entity_public_id=endpoint.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=endpoint.version,
        after={"code": endpoint.code, "route": endpoint.route_pattern, "critical": endpoint.critical},
    )
    return endpoint


@transaction.atomic
def record_performance_sample(
    *,
    company: Company,
    endpoint: ServiceEndpoint | None,
    **data: Any,
) -> PerformanceSample:
    if endpoint and endpoint.company_id != company.id:
        raise ValidationError("Performance endpoint cannot cross companies")
    duration = int(data.get("duration_ms", 0))
    if duration < 0 or duration > 86_400_000:
        raise ValidationError({"duration_ms": "Duration must be between 0 and 86400000 milliseconds."})
    sample = PerformanceSample(company=company, endpoint=endpoint, **data)
    sample.full_clean()
    sample.save()
    return sample


@transaction.atomic
def create_incident(
    *,
    company: Company,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    **data: Any,
) -> ProductionIncident:
    incident = ProductionIncident(company=company, created_by_public_id=actor_public_id, **data)
    incident.full_clean()
    incident.save()
    _record(
        company=company,
        action="CREATE",
        event_type="stability.incident.created",
        entity_type="ProductionIncident",
        entity_public_id=incident.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=incident.version,
        after={"code": incident.code, "severity": incident.severity_code, "status": incident.status_code},
    )
    return incident


@transaction.atomic
def transition_incident(
    *,
    incident: ProductionIncident,
    status_code: str,
    expected_version: int,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    owner_public_id: uuid.UUID | None = None,
    root_cause: str = "",
    resolution_summary: str = "",
) -> ProductionIncident:
    incident = ProductionIncident.objects.select_for_update().get(pk=incident.pk)
    if incident.version != expected_version:
        raise ValidationError("Incident changed. Refresh and retry.")
    allowed = {
        "OPEN": {"ACKNOWLEDGED", "MITIGATING", "RESOLVED"},
        "ACKNOWLEDGED": {"MITIGATING", "RESOLVED"},
        "MITIGATING": {"RESOLVED", "OPEN"},
        "RESOLVED": {"CLOSED", "OPEN"},
        "CLOSED": {"OPEN"},
    }
    if status_code not in allowed.get(incident.status_code, set()):
        raise ValidationError(f"Invalid incident transition from {incident.status_code} to {status_code}.")
    before = {"status": incident.status_code, "version": incident.version}
    incident.status_code = status_code
    if owner_public_id is not None:
        incident.owner_public_id = owner_public_id
    if root_cause:
        incident.root_cause = root_cause
    if resolution_summary:
        incident.resolution_summary = resolution_summary
    now = timezone.now()
    if status_code in {"ACKNOWLEDGED", "MITIGATING"} and incident.acknowledged_at is None:
        incident.acknowledged_at = now
    if status_code in {"RESOLVED", "CLOSED"}:
        incident.resolved_at = now
    if status_code == "OPEN":
        incident.resolved_at = None
    incident.version += 1
    incident.full_clean()
    incident.save()
    _record(
        company=incident.company,
        action="TRANSITION",
        event_type="stability.incident.transitioned",
        entity_type="ProductionIncident",
        entity_public_id=incident.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=incident.version,
        before=before,
        after={"status": incident.status_code, "code": incident.code},
    )
    return incident


@transaction.atomic
def create_regression(
    *,
    company: Company,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    incident: ProductionIncident | None = None,
    **data: Any,
) -> RegressionRecord:
    if incident and incident.company_id != company.id:
        raise ValidationError("Regression incident cannot cross companies")
    regression = RegressionRecord(
        company=company,
        incident=incident,
        created_by_public_id=actor_public_id,
        **data,
    )
    regression.full_clean()
    regression.save()
    _record(
        company=company,
        action="CREATE",
        event_type="stability.regression.created",
        entity_type="RegressionRecord",
        entity_public_id=regression.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=regression.version,
        after={"code": regression.code, "severity": regression.severity_code, "status": regression.status_code},
    )
    return regression


@transaction.atomic
def transition_regression(
    *,
    regression: RegressionRecord,
    status_code: str,
    notes: str,
    expected_version: int,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> RegressionRecord:
    regression = RegressionRecord.objects.select_for_update().get(pk=regression.pk)
    if regression.version != expected_version:
        raise ValidationError("Regression changed. Refresh and retry.")
    if status_code not in {"OPEN", "ACCEPTED", "FIXED", "WONT_FIX"}:
        raise ValidationError("Unsupported regression status")
    before = {"status": regression.status_code, "version": regression.version}
    regression.status_code = status_code
    regression.notes = notes
    regression.fixed_at = timezone.now() if status_code == "FIXED" else None
    regression.version += 1
    regression.full_clean()
    regression.save()
    _record(
        company=regression.company,
        action="TRANSITION",
        event_type="stability.regression.transitioned",
        entity_type="RegressionRecord",
        entity_public_id=regression.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=regression.version,
        before=before,
        after={"status": regression.status_code, "code": regression.code},
    )
    return regression


@transaction.atomic
def decide_gate(
    *,
    gate: StabilizationGate,
    status_code: str,
    notes: str,
    evidence: dict[str, Any],
    expected_version: int,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> StabilizationGate:
    gate = StabilizationGate.objects.select_for_update().get(pk=gate.pk)
    if gate.version != expected_version:
        raise ValidationError("Stabilization gate changed. Refresh and retry.")
    if status_code not in {"PENDING", "PASSED", "FAILED", "WAIVED"}:
        raise ValidationError("Unsupported gate status")
    if status_code == "WAIVED" and not notes.strip():
        raise ValidationError("Waived controls require a decision note")
    before = {"status": gate.status_code, "version": gate.version}
    gate.status_code = status_code
    gate.notes = notes
    gate.evidence = evidence
    gate.decided_at = timezone.now()
    gate.decided_by_public_id = actor_public_id
    gate.version += 1
    gate.full_clean()
    gate.save()
    _record(
        company=gate.company,
        action="DECIDE",
        event_type="stability.gate.decided",
        entity_type="StabilizationGate",
        entity_public_id=gate.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=gate.version,
        before=before,
        after={"status": gate.status_code, "code": gate.code},
    )
    return gate


def _percentile(values: list[int], percentile: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * percentile))))
    return int(ordered[index])


def _check(code: str, passed: bool, detail: str, *, critical: bool = True) -> dict[str, object]:
    return {"code": code, "passed": bool(passed), "critical": critical, "detail": detail}


@transaction.atomic
def run_stability_scan(
    *,
    company: Company,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> StabilityScan:
    seed_defaults(company)
    started = timezone.now()
    scan = StabilityScan.objects.create(
        company=company,
        started_at=started,
        executed_by_public_id=actor_public_id,
    )
    results: list[dict[str, object]] = []

    try:
        connection.ensure_connection()
        results.append(_check("DATABASE", True, "Database connection is available."))
    except Exception as exc:  # pragma: no cover - environment dependent
        results.append(_check("DATABASE", False, f"Database connection failed: {exc}"))

    system_errors = [message for message in checks.run_checks() if message.level >= checks.ERROR]
    results.append(
        _check(
            "DJANGO_CHECKS",
            not system_errors,
            "Django system checks passed." if not system_errors else f"Django reported {len(system_errors)} error-level checks.",
        )
    )

    required_apps = [
        "accessops",
        "orgops",
        "workops",
        "myworkops",
        "collabops",
        "releaseops",
        "stabilityops",
    ]
    missing_apps = [label for label in required_apps if not apps.is_installed(f"modules.{label}")]
    results.append(
        _check(
            "APPLICATIONS",
            not missing_apps,
            "Required v1 applications are installed." if not missing_apps else f"Missing apps: {', '.join(missing_apps)}",
        )
    )

    unresolved: list[str] = []
    endpoints = ServiceEndpoint.objects.filter(company=company, active=True, critical=True)
    for endpoint in endpoints:
        try:
            resolve(endpoint.route_pattern)
        except Exception:
            unresolved.append(endpoint.route_pattern)
    results.append(
        _check(
            "CRITICAL_ROUTES",
            not unresolved,
            "All critical monitored routes resolve." if not unresolved else f"Unresolved routes: {', '.join(unresolved)}",
        )
    )

    applied = set(MigrationRecorder(connection).applied_migrations())
    required_migrations = {
        ("stabilityops", "0001_initial"),
        ("stabilityops", "0002_seed_permissions"),
        ("stabilityops", "0003_seed_defaults"),
    }
    missing_migrations = sorted(required_migrations - applied)
    results.append(
        _check(
            "MIGRATIONS",
            not missing_migrations,
            "Phase 34 migrations are applied." if not missing_migrations else f"Missing migrations: {missing_migrations}",
        )
    )

    permission_count = Permission.objects.filter(code__startswith="stability.").count()
    results.append(_check("PERMISSIONS", permission_count == 9, f"Stability permission inventory: {permission_count}/9."))

    policy = (
        StabilityPolicyVersion.objects.filter(company=company, status_code="PUBLISHED").order_by("-version").first()
        or StabilityPolicyVersion.objects.filter(company=company).order_by("-version").first()
    )
    if policy is None:
        policy = StabilityPolicyVersion.objects.create(company=company, version=1)

    since = timezone.now() - timezone.timedelta(hours=24)
    telemetry_qs = PerformanceSample.objects.filter(company=company, observed_at__gte=since)
    telemetry_rows = list(
        telemetry_qs.order_by("-observed_at").values_list("duration_ms", "http_status")[:5000]
    )
    durations = [row[0] for row in telemetry_rows]
    failures = sum(1 for _, status in telemetry_rows if status is not None and status >= 500)
    error_rate = Decimal("0.000")
    if telemetry_rows:
        error_rate = (Decimal(failures) * Decimal(100) / Decimal(len(telemetry_rows))).quantize(
            Decimal("0.001"), rounding=ROUND_HALF_UP
        )
    p50 = _percentile(durations, 0.50)
    p95 = _percentile(durations, 0.95)
    p99 = _percentile(durations, 0.99)

    telemetry_available = bool(telemetry_rows)
    results.append(
        _check(
            "TELEMETRY",
            telemetry_available,
            f"{len(telemetry_rows)} performance samples observed in 24 hours."
            if telemetry_available
            else "No performance samples observed in the last 24 hours. Run the browser benchmark.",
            critical=False,
        )
    )
    performance_ok = p95 is not None and p95 <= policy.api_p95_budget_ms
    results.append(
        _check(
            "API_P95_BUDGET",
            performance_ok,
            f"Observed API p95 is {p95} ms against {policy.api_p95_budget_ms} ms budget."
            if p95 is not None
            else "API p95 cannot be calculated without telemetry.",
            critical=False,
        )
    )
    error_budget_ok = telemetry_available and error_rate <= policy.error_budget_percent
    results.append(
        _check(
            "ERROR_BUDGET",
            error_budget_ok,
            f"Observed 5xx rate is {error_rate}% against {policy.error_budget_percent}% budget."
            if telemetry_available
            else "Error budget cannot be evaluated without telemetry.",
            critical=False,
        )
    )

    critical_incidents = ProductionIncident.objects.filter(
        company=company,
        severity_code__in=["P0", "P1"],
    ).exclude(status_code__in=["RESOLVED", "CLOSED"])
    results.append(
        _check(
            "CRITICAL_INCIDENTS",
            not critical_incidents.exists(),
            "No unresolved P0/P1 production incident."
            if not critical_incidents.exists()
            else f"{critical_incidents.count()} unresolved P0/P1 incidents require action.",
        )
    )

    blocking_regressions = RegressionRecord.objects.filter(
        company=company,
        severity_code__in=["CRITICAL", "HIGH"],
        status_code="OPEN",
    )
    results.append(
        _check(
            "BLOCKING_REGRESSIONS",
            not blocking_regressions.exists(),
            "No open critical/high regression."
            if not blocking_regressions.exists()
            else f"{blocking_regressions.count()} critical/high regressions remain open.",
        )
    )

    passed = sum(1 for item in results if item["passed"])
    failed = len(results) - passed
    critical_failed = any(not item["passed"] and item["critical"] for item in results)
    scan.status_code = "FAILED" if critical_failed else ("WARNING" if failed else "PASSED")
    scan.checks_total = len(results)
    scan.checks_passed = passed
    scan.checks_failed = failed
    scan.api_p50_ms = p50
    scan.api_p95_ms = p95
    scan.api_p99_ms = p99
    scan.error_rate_percent = error_rate
    scan.results = results
    scan.completed_at = timezone.now()
    scan.version += 1
    scan.save()
    _record(
        company=company,
        action="EXECUTE",
        event_type="stability.scan.completed",
        entity_type="StabilityScan",
        entity_public_id=scan.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=scan.version,
        after={"status": scan.status_code, "passed": passed, "failed": failed, "p95_ms": p95},
    )
    return scan
