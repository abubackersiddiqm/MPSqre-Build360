from django.db import migrations
from django.utils import timezone


def seed_plan(apps, schema_editor):
    plan = apps.get_model("subscription", "PlanVersion")
    plan.objects.get_or_create(
        code="FOUNDATION",
        version=1,
        defaults={
            "name": "Build360 Foundation",
            "status": "PUBLISHED",
            "entitlements": {
                "configuration": True,
                "workflow": True,
                "governed_files": True,
                "audit_search": True,
            },
            "limits": {"file_upload_max_bytes": 26214400},
            "effective_from": timezone.now(),
            "published_at": timezone.now(),
        },
    )


def remove_plan(apps, schema_editor):
    plan = apps.get_model("subscription", "PlanVersion")
    plan.objects.filter(code="FOUNDATION", version=1).delete()


class Migration(migrations.Migration):
    dependencies = [("subscription", "0001_initial")]
    operations = [migrations.RunPython(seed_plan, remove_plan)]
