from django.db import migrations


PERMISSIONS = (
    ("equipment.view", "View tenant equipment, deployment, maintenance and compliance summaries"),
    ("equipment.manage", "Register equipment, deployments and governed meter readings"),
    ("equipment.maintain", "Manage maintenance, inspections, risks and approval requests"),
    ("equipment.approve", "Decide equipment approvals and controlled maintenance transitions"),
    ("equipment.configure", "Create versioned equipment and fleet operating policies"),
    ("equipment.export", "Generate governed equipment, maintenance and compliance exports"),
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
                "data_class": "equipment_restricted",
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
        ("equipmentops", "0001_initial"),
    ]

    operations = [migrations.RunPython(seed_permissions, remove_permissions)]
