from django.db import migrations


PERMISSIONS = (
    ("peopleorg.view", "View organization structure, people and operating records"),
    ("peopleorg.manage", "Manage employee organization profiles and reporting lines"),
    ("peopleorg.structure.manage", "Manage departments, designations and work calendars"),
    ("peopleorg.assignment.manage", "Manage employee project, site and location allocations"),
    ("peopleorg.leave.manage", "Configure leave types and govern leave requests"),
    ("peopleorg.attendance.manage", "Record and correct employee attendance"),
    ("peopleorg.import", "Bulk import people and onboarding records"),
    ("peopleorg.export", "Export governed people and organization records"),
)


def seed_permissions(apps, schema_editor):
    Permission = apps.get_model("identity", "Permission")
    for code, description in PERMISSIONS:
        Permission.objects.update_or_create(
            code=code,
            defaults={"description": description, "data_class": "PEOPLE_ORGANIZATION"},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("orgops", "0001_initial"),
        ("identity", "0002_remove_user_is_staff_remove_user_is_superuser"),
    ]

    operations = [migrations.RunPython(seed_permissions, migrations.RunPython.noop)]
