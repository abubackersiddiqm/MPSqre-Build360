from django.db import migrations
from django.db.models import Q

PERMISSIONS = [
    ("insights.view", "View executive portfolio intelligence and benefits realization"),
    ("insights.manage", "Manage executive intelligence policy and configuration"),
    ("insights.objective", "Manage strategic objectives and accountability"),
    ("insights.kpi", "Define KPIs and record governed observations"),
    ("insights.portfolio", "Create and govern portfolio snapshots"),
    ("insights.benefit", "Manage benefits plans and realization measurements"),
    ("insights.action", "Manage executive actions and follow-up"),
    ("insights.board", "Prepare board and executive reporting packs"),
    ("insights.approve", "Approve and publish portfolio and board evidence"),
    ("insights.export", "Export executive scorecard and portfolio evidence"),
]


def seed_permissions(apps, schema_editor):
    Permission = apps.get_model("identity", "Permission")
    Role = apps.get_model("identity", "Role")
    RolePermission = apps.get_model("identity", "RolePermission")
    permissions = []
    for code, description in PERMISSIONS:
        permission, _ = Permission.objects.update_or_create(
            code=code, defaults={"description": description, "data_class": "EXECUTIVE_INTELLIGENCE"}
        )
        permissions.append(permission)
    roles = Role.objects.filter(retired_at__isnull=True).filter(
        Q(code__icontains="ADMIN") | Q(code__icontains="OPERATOR") | Q(code__icontains="DIRECTOR")
        | Q(code__icontains="EXECUTIVE") | Q(code__icontains="PMO") | Q(name__icontains="ADMINISTRATOR")
        | Q(name__icontains="DIRECTOR") | Q(name__icontains="EXECUTIVE") | Q(name__icontains="PORTFOLIO")
    )
    for role in roles:
        for permission in permissions:
            RolePermission.objects.get_or_create(role=role, permission=permission)


def reverse_permissions(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [("insightops", "0001_initial"), ("identity", "0002_remove_user_is_staff_remove_user_is_superuser")]
    operations = [migrations.RunPython(seed_permissions, reverse_permissions)]
