from django.db import migrations
from django.db.models import Q

PERMISSIONS = [
    ("risktransfer.view", "View insurance, bonds, guarantees and risk-transfer operations"),
    ("risktransfer.manage", "Manage risk-transfer governance policy and evidence"),
    ("risktransfer.counterparty", "Manage insurers, banks, sureties and brokers"),
    ("risktransfer.program", "Manage insurance and risk-transfer programs"),
    ("risktransfer.coverage", "Manage insurance coverage and policy records"),
    ("risktransfer.premium", "Manage premium schedules and payment evidence"),
    ("risktransfer.loss", "Manage loss events and incident evidence"),
    ("risktransfer.claim", "Manage insurance claims, reserves and recoveries"),
    ("risktransfer.instrument", "Manage bonds, guarantees and surety instruments"),
    ("risktransfer.call", "Manage guarantee calls, disputes and settlements"),
    ("risktransfer.approve", "Approve risk counterparties, coverage, claims and instruments"),
    ("risktransfer.export", "Export insurance, claims, guarantees and risk-transfer evidence"),
]


def seed_permissions(apps, schema_editor):
    Permission = apps.get_model("identity", "Permission")
    Role = apps.get_model("identity", "Role")
    RolePermission = apps.get_model("identity", "RolePermission")
    permissions = []
    for code, description in PERMISSIONS:
        permission, _ = Permission.objects.update_or_create(
            code=code,
            defaults={"description": description, "data_class": "INSURANCE_BONDS_GUARANTEES_RISK_TRANSFER"},
        )
        permissions.append(permission)
    roles = Role.objects.filter(retired_at__isnull=True).filter(
        Q(code__icontains="ADMIN")
        | Q(code__icontains="OPERATOR")
        | Q(code__icontains="DIRECTOR")
        | Q(code__icontains="RISK")
        | Q(code__icontains="INSURANCE")
        | Q(code__icontains="COMMERCIAL")
        | Q(code__icontains="FINANCE")
        | Q(code__icontains="LEGAL")
        | Q(code__icontains="TREASURY")
        | Q(code__icontains="CFO")
        | Q(name__icontains="ADMINISTRATOR")
        | Q(name__icontains="RISK")
        | Q(name__icontains="INSURANCE")
        | Q(name__icontains="COMMERCIAL")
        | Q(name__icontains="FINANCE")
        | Q(name__icontains="LEGAL")
    )
    for role in roles:
        for permission in permissions:
            RolePermission.objects.get_or_create(role=role, permission=permission)


def reverse_permissions(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [
        ("risktransferops", "0001_initial"),
        ("identity", "0002_remove_user_is_staff_remove_user_is_superuser"),
    ]
    operations = [migrations.RunPython(seed_permissions, reverse_permissions)]
