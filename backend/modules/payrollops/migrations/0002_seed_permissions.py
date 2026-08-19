from django.db import migrations


PERMISSIONS = (
    ("payroll.view", "View tenant payroll operations and governed payroll summaries"),
    ("payroll.manage", "Create payroll periods, runs, lines, exceptions and approval requests"),
    ("payroll.approve", "Decide payroll approvals and configured approval transitions"),
    ("payroll.configure", "Create and publish versioned payroll control policies"),
    ("payroll.export", "Generate or release governed payroll export batches"),
)


def seed_permissions(apps, schema_editor):
    Permission = apps.get_model("identity", "Permission")
    Role = apps.get_model("identity", "Role")
    RolePermission = apps.get_model("identity", "RolePermission")

    permissions = []
    for code, description in PERMISSIONS:
        permission, _ = Permission.objects.get_or_create(
            code=code,
            defaults={"description": description, "data_class": "payroll_restricted"},
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
        ("payrollops", "0001_initial"),
    ]

    operations = [migrations.RunPython(seed_permissions, remove_permissions)]
