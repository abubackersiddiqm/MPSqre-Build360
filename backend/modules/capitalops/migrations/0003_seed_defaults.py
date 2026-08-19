from decimal import Decimal

from django.db import migrations


def seed_defaults(apps, schema_editor):
    Company = apps.get_model("tenant", "Company")
    Policy = apps.get_model("capitalops", "CapitalPolicyVersion")
    for company in Company.objects.all().iterator():
        Policy.objects.get_or_create(
            company=company,
            version=1,
            defaults={
                "status_code": "DRAFT",
                "covenant_alert_days": 30,
                "commitment_expiry_alert_days": 45,
                "maximum_leverage_percent": Decimal("70.0000"),
                "configuration": {
                    "phase": 44,
                    "release": "capital-joint-venture-funding-investor-operations",
                    "banking_provider": "PROVIDER_NEUTRAL",
                    "payment_rail": "PROVIDER_NEUTRAL",
                    "investor_registry": "TENANT_CONFIGURABLE",
                    "funding_workflow": "TENANT_CONFIGURABLE",
                    "regional_securities_rules": "TENANT_CONFIGURABLE",
                },
            },
        )


def reverse_defaults(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [("capitalops", "0002_seed_permissions")]
    operations = [migrations.RunPython(seed_defaults, reverse_defaults)]
