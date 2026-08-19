from django.db import migrations
from django.db.models import Q


PERMISSIONS = (
    ("mywork.view", "View the signed-in employee's personal work, time, approvals and activity"),
    ("mywork.execute", "Update assigned work, checklists and personal progress"),
    ("mywork.time", "Create and submit the signed-in employee's timesheets"),
    ("mywork.approve", "Decide assigned work approvals and direct-report timesheets"),
    ("mywork.offline", "Create, synchronize and discard governed offline drafts"),
    ("mywork.configure", "Configure personal-work controls and policies"),
    ("mywork.export", "Export governed personal-work records"),
)

SOURCE_GRANTS = {
    "mywork.view": ("work.view",),
    "mywork.execute": ("work.progress", "work.assign"),
    "mywork.time": ("work.view", "work.time.manage"),
    "mywork.approve": ("work.approve",),
    "mywork.offline": ("work.view",),
    "mywork.configure": ("work.configure",),
    "mywork.export": ("work.export",),
}


def seed_and_grant_permissions(apps, schema_editor):
    Permission = apps.get_model("identity", "Permission")
    Role = apps.get_model("identity", "Role")
    RolePermission = apps.get_model("identity", "RolePermission")

    targets = {}
    for code, description in PERMISSIONS:
        permission, _ = Permission.objects.update_or_create(
            code=code,
            defaults={"description": description, "data_class": "PERSONAL_WORK_OPERATIONS"},
        )
        targets[code] = permission

    for target_code, source_codes in SOURCE_GRANTS.items():
        source_ids = list(Permission.objects.filter(code__in=source_codes).values_list("id", flat=True))
        if not source_ids:
            continue
        role_ids = RolePermission.objects.filter(permission_id__in=source_ids).values_list("role_id", flat=True)
        for role_id in set(role_ids):
            RolePermission.objects.get_or_create(role_id=role_id, permission_id=targets[target_code].id)

    admin_roles = Role.objects.filter(retired_at__isnull=True).filter(
        Q(code__icontains="ADMIN") | Q(name__icontains="ADMINISTRATOR")
    )
    for role in admin_roles.iterator():
        for permission in targets.values():
            RolePermission.objects.get_or_create(role_id=role.id, permission_id=permission.id)


class Migration(migrations.Migration):
    dependencies = [
        ("myworkops", "0001_initial"),
        ("identity", "0002_remove_user_is_staff_remove_user_is_superuser"),
    ]

    operations = [migrations.RunPython(seed_and_grant_permissions, migrations.RunPython.noop)]
