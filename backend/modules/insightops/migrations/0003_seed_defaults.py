from decimal import Decimal

from django.db import migrations

KPIS = [
    ("ON_TIME_MILESTONES", "On-time milestones", "PERCENT", "HIGHER_BETTER", Decimal("90.0000"), Decimal("80.0000")),
    ("COST_VARIANCE", "Cost variance", "PERCENT", "LOWER_BETTER", Decimal("5.0000"), Decimal("10.0000")),
    ("SAFETY_INCIDENT_RATE", "Safety incident rate", "RATE", "LOWER_BETTER", Decimal("0.0000"), Decimal("1.0000")),
    ("QUALITY_FIRST_PASS", "Quality first-pass acceptance", "PERCENT", "HIGHER_BETTER", Decimal("95.0000"), Decimal("85.0000")),
    ("CUSTOMER_SATISFACTION", "Customer satisfaction", "SCORE", "HIGHER_BETTER", Decimal("4.5000"), Decimal("4.0000")),
]


def seed_defaults(apps, schema_editor):
    Company = apps.get_model("tenant", "Company")
    Policy = apps.get_model("insightops", "InsightPolicyVersion")
    KPI = apps.get_model("insightops", "KPIDefinition")
    for company in Company.objects.all().iterator():
        Policy.objects.get_or_create(
            company=company, version=1,
            defaults={"status_code": "DRAFT", "configuration": {"phase": 37, "release": "executive-portfolio-intelligence"}},
        )
        for code, name, unit, direction, target, warning in KPIS:
            KPI.objects.get_or_create(
                company=company, code=code,
                defaults={"name": name, "unit_code": unit, "direction_code": direction, "target_value": target, "warning_value": warning, "frequency_code": "MONTHLY", "aggregation_code": "LATEST", "active": True},
            )


def reverse_defaults(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [("insightops", "0002_seed_permissions")]
    operations = [migrations.RunPython(seed_defaults, reverse_defaults)]
