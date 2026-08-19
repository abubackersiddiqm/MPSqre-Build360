from django.db import migrations


PERMISSIONS = (
    ("workforce.view", "View tenant workforce plans, skills, gaps and compliance summaries"),
    ("workforce.manage", "Create plans, demands, assignments, credentials, risks and approvals"),
    ("workforce.approve", "Decide workforce approvals and configured plan transitions"),
    ("workforce.configure", "Create versioned workforce policies and skill definitions"),
    ("workforce.export", "Generate governed workforce planning and credential exports"),
)


def seed_permissions(apps, schema_editor):
    Permission = apps.get_model("identity", "Permission")
    Role = apps.get_model("identity", "Role")
    RolePermission = apps.get_model("identity", "RolePermission")

    permissions = []
    for code, description in PERMISSIONS:
        permission, _ = Permission.objects.get_or_create(
            code=code,
            defaults={
                "description": description,
                "data_class": "workforce_restricted",
            },
        )
        permissions.append(permission)

    administrator_roles = Role.objects.filter(code="company_administrator")
    for role in administrator_roles.iterator():
        for permission in permissions:
            RolePermission.objects.get_or_create(role=role, permission=permission)


def remove_permissions(apps, schema_editor):
    Permission = apps.get_model("identity", "Permission")
    RolePermission = apps.get_model("identity", "RolePermission")
    permission_ids = Permission.objects.filter(
        code__in=[code for code, _ in PERMISSIONS]
    ).values_list("id", flat=True)
    RolePermission.objects.filter(permission_id__in=permission_ids).delete()
    Permission.objects.filter(id__in=permission_ids).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("identity", "0002_remove_user_is_staff_remove_user_is_superuser"),
        ("workforceops", "0001_initial"),
    ]

    operations = [migrations.RunPython(seed_permissions, remove_permissions)]
