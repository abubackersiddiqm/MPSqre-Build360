from django.db import migrations
from django.db.models import Q

PERMISSIONS = [
    ("support.view", "View service desk, SLA and continuous improvement operations"),
    ("support.manage", "Manage service desk policy and governed support operations"),
    ("support.ticket", "Create support tickets and customer interactions"),
    ("support.resolve", "Triage, assign, resolve and close support tickets"),
    ("support.sla", "Refresh, monitor and govern service-level controls"),
    ("support.problem", "Manage problem records, root cause and known errors"),
    ("support.change", "Manage governed service change requests"),
    ("support.knowledge", "Author, review and publish knowledge articles"),
    ("support.improve", "Manage customer feedback and continuous improvement backlog"),
    ("support.export", "Export support, SLA and improvement evidence"),
]


def seed_permissions(apps, schema_editor):
    Permission = apps.get_model("identity", "Permission")
    Role = apps.get_model("identity", "Role")
    RolePermission = apps.get_model("identity", "RolePermission")
    permissions = []
    for code, description in PERMISSIONS:
        permission, _ = Permission.objects.update_or_create(
            code=code,
            defaults={"description": description, "data_class": "SUPPORT_OPERATIONS"},
        )
        permissions.append(permission)

    admin_roles = Role.objects.filter(retired_at__isnull=True).filter(
        Q(code__icontains="ADMIN")
        | Q(code__icontains="OPERATOR")
        | Q(name__icontains="ADMINISTRATOR")
        | Q(name__icontains="SUPPORT")
        | Q(name__icontains="CUSTOMER SUCCESS")
        | Q(name__icontains="PROJECT DIRECTOR")
    )
    for role in admin_roles:
        for permission in permissions:
            RolePermission.objects.get_or_create(role=role, permission=permission)


def reverse_permissions(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [
        ("supportops", "0001_initial"),
        ("identity", "0002_remove_user_is_staff_remove_user_is_superuser"),
    ]
    operations = [migrations.RunPython(seed_permissions, reverse_permissions)]
