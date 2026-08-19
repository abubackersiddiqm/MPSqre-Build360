from django.db import migrations


def seed_defaults(apps, schema_editor):
    Company = apps.get_model("tenant", "Company")
    Policy = apps.get_model("sustainabilityops", "SustainabilityPolicyVersion")
    for company in Company.objects.all().iterator():
        Policy.objects.get_or_create(
            company=company,
            version=1,
            defaults={
                "status_code": "DRAFT",
                "organizational_boundary_code": "OPERATIONAL_CONTROL",
                "reporting_frequency_code": "MONTHLY",
                "configuration": {
                    "phase": 38,
                    "release": "sustainability-esg-carbon-operations",
                    "factor_governance": "TENANT_CONFIGURED",
                    "do_not_mix_units": True,
                },
            },
        )


def reverse_defaults(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [("sustainabilityops", "0002_seed_permissions")]
    operations = [migrations.RunPython(seed_defaults, reverse_defaults)]
