from django.db import migrations
from django.db.models import Q


WORK_PERMISSION_CODES = (
    "work.view",
    "work.project.manage",
    "work.plan.manage",
    "work.assign",
    "work.progress",
    "work.time.manage",
    "work.approve",
    "work.configure",
    "work.export",
)


def grant_existing_admin_roles(apps, schema_editor):
    Permission = apps.get_model("identity", "Permission")
    Role = apps.get_model("identity", "Role")
    RolePermission = apps.get_model("identity", "RolePermission")

    permissions = list(Permission.objects.filter(code__in=WORK_PERMISSION_CODES))
    admin_roles = Role.objects.filter(retired_at__isnull=True).filter(
        Q(code__icontains="ADMIN") | Q(name__icontains="ADMINISTRATOR")
    )

    for role in admin_roles.iterator():
        for permission in permissions:
            RolePermission.objects.get_or_create(
                role_id=role.id,
                permission_id=permission.id,
            )


class Migration(migrations.Migration):
    dependencies = [
        ("workops", "0002_seed_permissions"),
    ]

    operations = [
        migrations.RunPython(
            grant_existing_admin_roles,
            migrations.RunPython.noop,
        ),
    ]
