from django.db import migrations
from django.db.models import Q

PERMISSIONS = [
    ("golive.view", "View data migration, training, cutover and hypercare evidence"),
    ("golive.manage", "Manage go-live and user enablement operations"),
    ("golive.migration", "Manage data migration batches and data-quality issues"),
    ("golive.training", "Manage training cohorts and completion evidence"),
    ("golive.cutover", "Manage cutover plans, tasks and go-live waves"),
    ("golive.approve", "Approve cutover, migration and go-live controls"),
    ("golive.hypercare", "Manage post-go-live hypercare issues"),
    ("golive.configure", "Configure go-live policies and readiness gates"),
    ("golive.export", "Export go-live, migration and training evidence"),
]


def seed_permissions(apps, schema_editor):
    Permission = apps.get_model("identity", "Permission")
    Role = apps.get_model("identity", "Role")
    RolePermission = apps.get_model("identity", "RolePermission")
    permissions = []
    for code, description in PERMISSIONS:
        permission, _ = Permission.objects.update_or_create(
            code=code,
            defaults={"description": description, "data_class": "GO_LIVE_OPERATIONS"},
        )
        permissions.append(permission)

    admin_roles = Role.objects.filter(retired_at__isnull=True).filter(
        Q(code__icontains="ADMIN")
        | Q(code__icontains="OPERATOR")
        | Q(name__icontains="ADMINISTRATOR")
        | Q(name__icontains="RELEASE")
        | Q(name__icontains="PROJECT DIRECTOR")
    )
    for role in admin_roles:
        for permission in permissions:
            RolePermission.objects.get_or_create(role=role, permission=permission)


def reverse_permissions(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [
        ("goliveops", "0001_initial"),
        ("identity", "0002_remove_user_is_staff_remove_user_is_superuser"),
    ]
    operations = [migrations.RunPython(seed_permissions, reverse_permissions)]
