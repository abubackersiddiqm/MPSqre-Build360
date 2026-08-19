from decimal import Decimal

from django.db import migrations


def seed_defaults(apps, schema_editor):
    Company = apps.get_model("tenant", "Company")
    Policy = apps.get_model("landops", "LandPolicyVersion")
    for company in Company.objects.all().iterator():
        Policy.objects.get_or_create(
            company=company,
            version=1,
            defaults={
                "status_code": "DRAFT",
                "due_diligence_target_days": 45,
                "approval_alert_days": 60,
                "minimum_margin_percent": Decimal("15.0000"),
                "configuration": {
                    "phase": 43,
                    "release": "land-acquisition-feasibility-statutory-approvals",
                    "title_registry": "PROVIDER_NEUTRAL",
                    "gis_provider": "PROVIDER_NEUTRAL",
                    "valuation_methodology": "TENANT_CONFIGURABLE",
                    "approval_catalogue": "TENANT_CONFIGURABLE",
                    "regional_land_law": "TENANT_CONFIGURABLE",
                },
            },
        )


def reverse_defaults(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [("landops", "0002_seed_permissions")]
    operations = [migrations.RunPython(seed_defaults, reverse_defaults)]
