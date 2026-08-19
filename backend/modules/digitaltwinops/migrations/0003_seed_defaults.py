from django.db import migrations


def seed_defaults(apps, schema_editor):
    Company = apps.get_model("tenant", "Company")
    Policy = apps.get_model("digitaltwinops", "DigitalTwinPolicyVersion")
    for company in Company.objects.all().iterator():
        Policy.objects.get_or_create(
            company=company,
            version=1,
            defaults={
                "status_code": "DRAFT",
                "coordinate_system_code": "PROJECT_LOCAL",
                "model_review_frequency_code": "WEEKLY",
                "telemetry_retention_days": 365,
                "alert_acknowledgement_minutes": 30,
                "configuration": {
                    "phase": 39,
                    "release": "bim-digital-twin-smart-site",
                    "model_storage": "REFERENCE_ONLY",
                    "iot_provider": "PROVIDER_NEUTRAL",
                    "ifc_processing": "EXTERNAL_CONNECTOR",
                },
            },
        )


def reverse_defaults(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [("digitaltwinops", "0002_seed_permissions")]
    operations = [migrations.RunPython(seed_defaults, reverse_defaults)]
