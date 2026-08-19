from django.db import migrations


PERMISSIONS = (
    ("work.view", "View projects, plans, work assignments, progress and approvals"),
    ("work.project.manage", "Create and govern projects, sites and milestones"),
    ("work.plan.manage", "Manage WBS nodes, work packages, dependencies and checklists"),
    ("work.assign", "Create work items and assign employees"),
    ("work.progress", "Update work status, record daily progress and request work approvals"),
    ("work.time.manage", "Create and submit governed timesheets"),
    ("work.approve", "Decide work approvals and review submitted timesheets"),
    ("work.configure", "Configure project and work management controls"),
    ("work.export", "Export governed project and work records"),
)


def seed_permissions(apps, schema_editor):
    Permission = apps.get_model("identity", "Permission")
    for code, description in PERMISSIONS:
        Permission.objects.update_or_create(
            code=code,
            defaults={"description": description, "data_class": "PROJECT_WORK_MANAGEMENT"},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("workops", "0001_initial"),
        ("identity", "0002_remove_user_is_staff_remove_user_is_superuser"),
    ]

    operations = [migrations.RunPython(seed_permissions, migrations.RunPython.noop)]
