from decimal import Decimal

from django.db import migrations

CATALOG = [
    ("ACCESS_SUPPORT", "Access and authentication support", "ACCESS", 60, 480),
    ("APPLICATION_SUPPORT", "Application functionality support", "APPLICATION", 240, 2880),
    ("DATA_SUPPORT", "Data correction and migration support", "DATA", 480, 4320),
    ("INTEGRATION_SUPPORT", "Integration and connector support", "INTEGRATION", 240, 2880),
    ("PRODUCTION_INCIDENT", "Production service incident", "INCIDENT", 30, 240),
]


def seed_defaults(apps, schema_editor):
    Company = apps.get_model("tenant", "Company")
    Policy = apps.get_model("supportops", "SupportPolicyVersion")
    Catalog = apps.get_model("supportops", "ServiceCatalogItem")
    for company in Company.objects.all().iterator():
        Policy.objects.get_or_create(
            company=company,
            version=1,
            defaults={
                "status_code": "DRAFT",
                "default_response_minutes": 240,
                "default_resolution_minutes": 2880,
                "escalation_warning_percent": Decimal("80.00"),
                "customer_feedback_required": True,
                "configuration": {"phase": 36, "release": "v1-service-desk-continuous-improvement"},
            },
        )
        for code, name, category, response, resolution in CATALOG:
            Catalog.objects.get_or_create(
                company=company,
                code=code,
                defaults={
                    "name": name,
                    "category_code": category,
                    "response_minutes": response,
                    "resolution_minutes": resolution,
                    "business_hours_only": True,
                    "active": True,
                },
            )


def reverse_defaults(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [("supportops", "0002_seed_permissions")]
    operations = [migrations.RunPython(seed_defaults, reverse_defaults)]
