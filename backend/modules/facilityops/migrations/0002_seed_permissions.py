from django.db import migrations
from django.db.models import Q

PERMISSIONS = [
    ("facility.view", "View facilities, asset lifecycle and warranty operations"),
    ("facility.manage", "Manage facilities policy and configuration"),
    ("facility.facility", "Register and govern facilities"),
    ("facility.space", "Manage facility spaces and location hierarchy"),
    ("facility.asset", "Manage operational and maintainable assets"),
    ("facility.maintenance", "Manage maintenance plans and work orders"),
    ("facility.service", "Manage facility service requests and SLA execution"),
    ("facility.warranty", "Manage warranty claims and supplier recovery"),
    ("facility.inspect", "Perform facility and asset condition inspections"),
    ("facility.approve", "Approve work orders, assets, warranties and inspections"),
    ("facility.export", "Export facilities, maintenance and warranty evidence"),
]


def seed_permissions(apps, schema_editor):
    Permission = apps.get_model("identity", "Permission")
    Role = apps.get_model("identity", "Role")
    RolePermission = apps.get_model("identity", "RolePermission")
    permissions = []
    for code, description in PERMISSIONS:
        permission, _ = Permission.objects.update_or_create(
            code=code,
            defaults={"description": description, "data_class": "FACILITIES_ASSET_LIFECYCLE"},
        )
        permissions.append(permission)
    roles = Role.objects.filter(retired_at__isnull=True).filter(
        Q(code__icontains="ADMIN")
        | Q(code__icontains="OPERATOR")
        | Q(code__icontains="DIRECTOR")
        | Q(code__icontains="PROJECT")
        | Q(code__icontains="FACILITY")
        | Q(code__icontains="ASSET")
        | Q(code__icontains="MAINTENANCE")
        | Q(code__icontains="ENGINEER")
        | Q(name__icontains="ADMINISTRATOR")
        | Q(name__icontains="FACILITY")
        | Q(name__icontains="ASSET")
        | Q(name__icontains="MAINTENANCE")
        | Q(name__icontains="ENGINEER")
    )
    for role in roles:
        for permission in permissions:
            RolePermission.objects.get_or_create(role=role, permission=permission)


def reverse_permissions(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [
        ("facilityops", "0001_initial"),
        ("identity", "0002_remove_user_is_staff_remove_user_is_superuser"),
    ]
    operations = [migrations.RunPython(seed_permissions, reverse_permissions)]
