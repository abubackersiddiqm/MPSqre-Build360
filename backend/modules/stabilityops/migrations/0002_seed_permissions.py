from django.db import migrations
from django.db.models import Q

PERMISSIONS = [
    ("stability.view", "View production stability, performance and incident evidence"),
    ("stability.manage", "Manage production stability operations"),
    ("stability.scan", "Execute stabilization and production readiness scans"),
    ("stability.telemetry", "Record governed performance telemetry"),
    ("stability.incident", "Create and manage production incidents"),
    ("stability.regression", "Create and manage stabilization regressions"),
    ("stability.gate", "Decide stabilization gates"),
    ("stability.configure", "Configure stability policies and monitored endpoints"),
    ("stability.export", "Export stabilization evidence"),
]


def seed_permissions(apps, schema_editor):
    Permission = apps.get_model("identity", "Permission")
    Role = apps.get_model("identity", "Role")
    RolePermission = apps.get_model("identity", "RolePermission")
    permissions = []
    for code, description in PERMISSIONS:
        permission, _ = Permission.objects.update_or_create(
            code=code,
            defaults={"description": description, "data_class": "PRODUCTION_STABILITY"},
        )
        permissions.append(permission)

    admin_roles = Role.objects.filter(retired_at__isnull=True).filter(
        Q(code__icontains="ADMIN")
        | Q(code__icontains="OPERATOR")
        | Q(name__icontains="ADMINISTRATOR")
        | Q(name__icontains="RELEASE")
    )
    for role in admin_roles:
        for permission in permissions:
            RolePermission.objects.get_or_create(role=role, permission=permission)


def reverse_permissions(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [
        ("stabilityops", "0001_initial"),
        ("identity", "0002_remove_user_is_staff_remove_user_is_superuser"),
    ]
    operations = [migrations.RunPython(seed_permissions, reverse_permissions)]
