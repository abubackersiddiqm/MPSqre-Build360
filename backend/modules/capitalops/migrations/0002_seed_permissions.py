from django.db import migrations
from django.db.models import Q

PERMISSIONS = [
    ("capital.view", "View capital planning, funding and investor operations"),
    ("capital.manage", "Manage capital governance policy and evidence"),
    ("capital.program", "Manage funding programs and capital plans"),
    ("capital.investor", "Manage investor profiles and KYC evidence"),
    ("capital.jv", "Manage joint-venture arrangements and governance"),
    ("capital.commitment", "Manage investor and partner capital commitments"),
    ("capital.facility", "Manage debt facilities and lender terms"),
    ("capital.drawdown", "Manage equity calls and debt drawdowns"),
    ("capital.covenant", "Manage covenant testing and compliance evidence"),
    ("capital.distribution", "Manage investor distributions and returns"),
    ("capital.approve", "Approve capital programs, commitments, facilities, drawdowns and distributions"),
    ("capital.export", "Export capital, investor and funding evidence"),
]


def seed_permissions(apps, schema_editor):
    Permission = apps.get_model("identity", "Permission")
    Role = apps.get_model("identity", "Role")
    RolePermission = apps.get_model("identity", "RolePermission")
    permissions = []
    for code, description in PERMISSIONS:
        permission, _ = Permission.objects.update_or_create(
            code=code,
            defaults={"description": description, "data_class": "CAPITAL_JV_FUNDING_INVESTOR"},
        )
        permissions.append(permission)
    roles = Role.objects.filter(retired_at__isnull=True).filter(
        Q(code__icontains="ADMIN")
        | Q(code__icontains="OPERATOR")
        | Q(code__icontains="DIRECTOR")
        | Q(code__icontains="FINANCE")
        | Q(code__icontains="TREASURY")
        | Q(code__icontains="INVEST")
        | Q(code__icontains="CAPITAL")
        | Q(code__icontains="CFO")
        | Q(code__icontains="COMMERCIAL")
        | Q(name__icontains="ADMINISTRATOR")
        | Q(name__icontains="FINANCE")
        | Q(name__icontains="TREASURY")
        | Q(name__icontains="INVEST")
        | Q(name__icontains="CAPITAL")
    )
    for role in roles:
        for permission in permissions:
            RolePermission.objects.get_or_create(role=role, permission=permission)


def reverse_permissions(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [
        ("capitalops", "0001_initial"),
        ("identity", "0002_remove_user_is_staff_remove_user_is_superuser"),
    ]
    operations = [migrations.RunPython(seed_permissions, reverse_permissions)]
