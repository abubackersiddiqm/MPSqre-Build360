from decimal import Decimal

from django.db import migrations

ENDPOINTS = [
    ("HEALTH_LIVE", "Backend live health", "/api/v1/health/live", 250, True),
    ("HEALTH_READY", "Backend readiness health", "/api/v1/health/ready", 500, True),
    ("TENANT_CONTEXT", "Current company context", "/api/v1/companies/current", 500, True),
    ("RELEASE_READINESS", "Release readiness overview", "/api/v1/release-readiness/overview", 750, True),
    ("PROJECT_WORK", "Project and work overview", "/api/v1/project-work/overview", 750, True),
    ("MY_WORK", "Employee My Work overview", "/api/v1/my-work/overview", 750, True),
]

GATES = [
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


def seed_defaults(apps, schema_editor):
    Company = apps.get_model("tenant", "Company")
    Policy = apps.get_model("stabilityops", "StabilityPolicyVersion")
    Endpoint = apps.get_model("stabilityops", "ServiceEndpoint")
    Gate = apps.get_model("stabilityops", "StabilizationGate")

    for company in Company.objects.all().iterator():
        Policy.objects.get_or_create(
            company=company,
            version=1,
            defaults={
                "status_code": "DRAFT",
                "availability_target_percent": Decimal("99.90"),
                "api_p95_budget_ms": 750,
                "page_load_budget_ms": 2500,
                "slow_request_threshold_ms": 1000,
                "error_budget_percent": Decimal("0.10"),
                "incident_ack_sla_minutes": 15,
                "critical_resolution_sla_minutes": 240,
                "telemetry_retention_days": 30,
                "configuration": {"phase": 34, "release": "v1-stabilization"},
            },
        )
        for code, name, route, target, critical in ENDPOINTS:
            Endpoint.objects.get_or_create(
                company=company,
                code=code,
                defaults={
                    "name": name,
                    "route_pattern": route,
                    "method_code": "GET",
                    "service_code": "BACKEND",
                    "critical": critical,
                    "target_p95_ms": target,
                    "target_availability_percent": Decimal("99.90"),
                    "active": True,
                },
            )
        for code, name, category in GATES:
            Gate.objects.get_or_create(
                company=company,
                code=code,
                defaults={
                    "name": name,
                    "category_code": category,
                    "description": "Required Build360 v1 stabilization control.",
                    "is_required": True,
                },
            )


def reverse_defaults(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [("stabilityops", "0002_seed_permissions")]
    operations = [migrations.RunPython(seed_defaults, reverse_defaults)]
