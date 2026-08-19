from decimal import Decimal

from django.db import migrations


def seed_defaults(apps, schema_editor):
    Company = apps.get_model("tenant", "Company")
    Policy = apps.get_model("risktransferops", "RiskTransferPolicyVersion")
    for company in Company.objects.all().iterator():
        Policy.objects.get_or_create(
            company=company,
            version=1,
            defaults={
                "status_code": "DRAFT",
                "expiry_alert_days": 45,
                "claim_notification_sla_days": 7,
                "minimum_coverage_percent": Decimal("100.0000"),
                "configuration": {
                    "phase": 45,
                    "release": "insurance-bonds-guarantees-risk-transfer-operations",
                    "insurance_provider": "PROVIDER_NEUTRAL",
                    "surety_provider": "PROVIDER_NEUTRAL",
                    "bank_guarantee_provider": "PROVIDER_NEUTRAL",
                    "coverage_catalogue": "TENANT_CONFIGURABLE",
                    "claim_workflow": "TENANT_CONFIGURABLE",
                    "regional_insurance_rules": "TENANT_CONFIGURABLE",
                },
            },
        )


def reverse_defaults(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [("risktransferops", "0002_seed_permissions")]
    operations = [migrations.RunPython(seed_defaults, reverse_defaults)]
