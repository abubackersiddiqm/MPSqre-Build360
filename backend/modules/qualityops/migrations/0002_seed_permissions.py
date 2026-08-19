from django.db import migrations


PERMISSIONS = (
    ("quality.view", "View tenant quality, ITP, inspection, test and NCR summaries"),
    ("quality.manage", "Manage quality plans, corrective actions, approvals and risks"),
    ("quality.inspect", "Create inspection requests, inspections and laboratory test results"),
    ("quality.ncr", "Raise and govern nonconformance reports and dispositions"),
    ("quality.approve", "Decide quality approvals and controlled QA/QC transitions"),
    ("quality.configure", "Create versioned tenant quality and QA/QC policies"),
    ("quality.export", "Generate governed quality dossiers and compliance exports"),
)


def seed_permissions(apps, schema_editor):
    Permission = apps.get_model("identity", "Permission")
    Role = apps.get_model("identity", "Role")
    RolePermission = apps.get_model("identity", "RolePermission")

    permissions = []
    for code, description in PERMISSIONS:
        permission, _ = Permission.objects.get_or_create(
            code=code,
            defaults={"description": description, "data_class": "quality_restricted"},
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
        ("qualityops", "0001_initial"),
    ]

    operations = [migrations.RunPython(seed_permissions, remove_permissions)]
