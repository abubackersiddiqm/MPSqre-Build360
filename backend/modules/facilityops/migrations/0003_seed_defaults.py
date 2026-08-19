from django.db import migrations


def seed_defaults(apps, schema_editor):
    Company = apps.get_model("tenant", "Company")
    Policy = apps.get_model("facilityops", "FacilityPolicyVersion")
    for company in Company.objects.all().iterator():
        Policy.objects.get_or_create(
            company=company,
            version=1,
            defaults={
                "status_code": "DRAFT",
                "preventive_horizon_days": 90,
                "warranty_alert_days": 60,
                "service_response_minutes": 240,
                "service_resolution_minutes": 1440,
                "configuration": {
                    "phase": 40,
                    "release": "facilities-asset-lifecycle-warranty",
                    "maintenance_provider": "PROVIDER_NEUTRAL",
                    "work_order_numbering": "TENANT_CONFIGURABLE",
                    "handover_source": "REFERENCE_ONLY",
                },
            },
        )


def reverse_defaults(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [("facilityops", "0002_seed_permissions")]
    operations = [migrations.RunPython(seed_defaults, reverse_defaults)]
