from django.db import migrations


def seed_defaults(apps, schema_editor):
    Company = apps.get_model("tenant", "Company")
    Policy = apps.get_model("leaseops", "PropertyPolicyVersion")
    for company in Company.objects.all().iterator():
        Policy.objects.get_or_create(
            company=company,
            version=1,
            defaults={
                "status_code": "DRAFT",
                "lease_expiry_alert_days": 90,
                "invoice_grace_days": 5,
                "case_response_minutes": 240,
                "case_resolution_minutes": 2880,
                "configuration": {
                    "phase": 41,
                    "release": "property-lease-occupancy-tenant-experience",
                    "finance_integration": "REFERENCE_ONLY",
                    "payment_provider": "PROVIDER_NEUTRAL",
                    "lease_numbering": "TENANT_CONFIGURABLE",
                    "tax_rules": "TENANT_CONFIGURABLE",
                },
            },
        )


def reverse_defaults(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [("leaseops", "0002_seed_permissions")]
    operations = [migrations.RunPython(seed_defaults, reverse_defaults)]
