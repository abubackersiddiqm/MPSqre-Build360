from django.db import migrations


PERMISSIONS = (
    ("access.view", "View company people, roles and onboarding state"),
    ("access.manage", "Manage company access-control configuration"),
    ("access.invite", "Create and revoke company invitations"),
    ("access.role.manage", "Create versioned company roles and grants"),
    ("access.membership.manage", "Assign roles and control membership status"),
    ("platform.company.manage", "Create, suspend and activate tenant companies"),
    ("platform.operator.manage", "Manage platform control-plane operators"),
)


def seed_permissions(apps, schema_editor):
    Permission = apps.get_model("identity", "Permission")
    for code, description in PERMISSIONS:
        Permission.objects.update_or_create(
            code=code,
            defaults={"description": description, "data_class": "ACCESS_CONTROL"},
        )




class Migration(migrations.Migration):
    dependencies = [
        ("accessops", "0001_initial"),
        ("identity", "0002_remove_user_is_staff_remove_user_is_superuser"),
    ]

    operations = [migrations.RunPython(seed_permissions, migrations.RunPython.noop)]
