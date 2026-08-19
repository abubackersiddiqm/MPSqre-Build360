from django.db import migrations


def seed_defaults(apps, schema_editor):
    Company = apps.get_model("tenant", "Company")
    Policy = apps.get_model("salesops", "SalesPolicyVersion")
    for company in Company.objects.all().iterator():
        Policy.objects.get_or_create(
            company=company,
            version=1,
            defaults={
                "status_code": "DRAFT",
                "reservation_expiry_hours": 72,
                "collection_grace_days": 7,
                "handover_alert_days": 30,
                "configuration": {
                    "phase": 42,
                    "release": "development-sales-booking-collections-handover",
                    "crm_integration": "REFERENCE_ONLY",
                    "finance_integration": "REFERENCE_ONLY",
                    "payment_provider": "PROVIDER_NEUTRAL",
                    "tax_rules": "TENANT_CONFIGURABLE",
                    "booking_numbering": "TENANT_CONFIGURABLE",
                },
            },
        )


def reverse_defaults(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [("salesops", "0002_seed_permissions")]
    operations = [migrations.RunPython(seed_defaults, reverse_defaults)]
