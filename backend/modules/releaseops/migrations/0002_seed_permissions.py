from django.db import migrations
from django.db.models import Q

PERMISSIONS = [
    ("release.view", "View release readiness and UAT evidence"),
    ("release.manage", "Create and maintain release candidates"),
    ("release.target", "Manage deployment targets"),
    ("release.gate", "Decide release readiness gates"),
    ("release.uat", "Execute end-to-end UAT scenarios"),
    ("release.backup", "Register backup and restore evidence"),
    ("release.approve", "Approve governed release candidates"),
    ("release.publish", "Publish approved releases"),
    ("release.export", "Export release evidence"),
]


def seed_permissions(apps, schema_editor):
    Permission = apps.get_model("identity", "Permission")
    Role = apps.get_model("identity", "Role")
    RolePermission = apps.get_model("identity", "RolePermission")
    permission_rows = []
    for code, description in PERMISSIONS:
        permission, _ = Permission.objects.update_or_create(
            code=code,
            defaults={"description": description, "data_class": "RELEASE_GOVERNANCE"},
        )
        permission_rows.append(permission)

    admin_roles = Role.objects.filter(retired_at__isnull=True).filter(
        Q(code__icontains="ADMIN") | Q(code__icontains="OPERATOR") | Q(name__icontains="ADMINISTRATOR")
    )
    for role in admin_roles:
        for permission in permission_rows:
            RolePermission.objects.get_or_create(role=role, permission=permission)


def reverse_permissions(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [
        ("releaseops", "0001_initial"),
        ("identity", "0002_remove_user_is_staff_remove_user_is_superuser"),
    ]
    operations = [migrations.RunPython(seed_permissions, reverse_permissions)]
