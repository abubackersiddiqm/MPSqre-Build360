from django.db import migrations
from django.db.models import Q

PERMISSIONS = [
    ("digitaltwin.view", "View BIM, digital twin and smart-site operations"),
    ("digitaltwin.manage", "Manage digital twin policy and configuration"),
    ("digitaltwin.model", "Register BIM models and revisions"),
    ("digitaltwin.coordinate", "Manage model federations and clash coordination"),
    ("digitaltwin.issue", "Manage BIM and coordination issues"),
    ("digitaltwin.device", "Register smart-site and IoT devices"),
    ("digitaltwin.telemetry", "Record provider-neutral telemetry"),
    ("digitaltwin.alert", "Acknowledge and resolve smart-site alerts"),
    ("digitaltwin.handover", "Manage digital handover asset information"),
    ("digitaltwin.approve", "Approve model revisions and handover evidence"),
    ("digitaltwin.export", "Export BIM, twin, telemetry and handover evidence"),
]


def seed_permissions(apps, schema_editor):
    Permission = apps.get_model("identity", "Permission")
    Role = apps.get_model("identity", "Role")
    RolePermission = apps.get_model("identity", "RolePermission")
    permissions = []
    for code, description in PERMISSIONS:
        permission, _ = Permission.objects.update_or_create(
            code=code,
            defaults={"description": description, "data_class": "BIM_DIGITAL_TWIN"},
        )
        permissions.append(permission)
    roles = Role.objects.filter(retired_at__isnull=True).filter(
        Q(code__icontains="ADMIN")
        | Q(code__icontains="OPERATOR")
        | Q(code__icontains="DIRECTOR")
        | Q(code__icontains="PROJECT")
        | Q(code__icontains="BIM")
        | Q(code__icontains="ENGINEER")
        | Q(code__icontains="DIGITAL")
        | Q(name__icontains="ADMINISTRATOR")
        | Q(name__icontains="PROJECT MANAGER")
        | Q(name__icontains="BIM")
        | Q(name__icontains="ENGINEER")
    )
    for role in roles:
        for permission in permissions:
            RolePermission.objects.get_or_create(role=role, permission=permission)


def reverse_permissions(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [
        ("digitaltwinops", "0001_initial"),
        ("identity", "0002_remove_user_is_staff_remove_user_is_superuser"),
    ]
    operations = [migrations.RunPython(seed_permissions, reverse_permissions)]
