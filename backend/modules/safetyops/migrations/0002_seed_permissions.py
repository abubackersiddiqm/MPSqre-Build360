from django.db import migrations


PERMISSIONS = (
    ("safety.view", "View tenant HSE, incident, permit, inspection and action summaries"),
    ("safety.manage", "Manage observations, inspections, toolbox talks, actions and risks"),
    ("safety.incident", "Report and govern safety incidents and investigations"),
    ("safety.permit", "Create and control permits to work"),
    ("safety.approve", "Decide safety approvals and controlled HSE transitions"),
    ("safety.configure", "Create versioned tenant HSE and safety policies"),
    ("safety.export", "Generate governed safety and compliance exports"),
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
                "data_class": "safety_restricted",
            },
        )
        permissions.append(permission)

    for role in Role.objects.filter(code="company_administrator").iterator():
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
        ("safetyops", "0001_initial"),
    ]

    operations = [migrations.RunPython(seed_permissions, remove_permissions)]
