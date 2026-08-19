from django.db import migrations
from django.db.models import Q

PERMISSIONS = [
    ("lease.view", "View property, lease, occupancy and tenant experience operations"),
    ("lease.manage", "Manage property and lease governance policy"),
    ("lease.property", "Register and govern managed properties"),
    ("lease.unit", "Manage leaseable units and availability"),
    ("lease.tenant", "Manage tenant and occupant accounts"),
    ("lease.agreement", "Create and manage lease agreements"),
    ("lease.billing", "Manage recurring charges, invoices and receivables"),
    ("lease.occupancy", "Manage move-in, move-out and occupancy evidence"),
    ("lease.experience", "Manage tenant service, complaints and feedback"),
    ("lease.approve", "Approve leases, invoices and occupancy evidence"),
    ("lease.export", "Export property, lease and occupancy evidence"),
]


def seed_permissions(apps, schema_editor):
    Permission = apps.get_model("identity", "Permission")
    Role = apps.get_model("identity", "Role")
    RolePermission = apps.get_model("identity", "RolePermission")
    permissions = []
    for code, description in PERMISSIONS:
        permission, _ = Permission.objects.update_or_create(
            code=code,
            defaults={"description": description, "data_class": "PROPERTY_LEASE_OCCUPANCY"},
        )
        permissions.append(permission)
    roles = Role.objects.filter(retired_at__isnull=True).filter(
        Q(code__icontains="ADMIN")
        | Q(code__icontains="OPERATOR")
        | Q(code__icontains="DIRECTOR")
        | Q(code__icontains="PROPERTY")
        | Q(code__icontains="LEASE")
        | Q(code__icontains="FACILITY")
        | Q(code__icontains="FINANCE")
        | Q(code__icontains="COMMERCIAL")
        | Q(name__icontains="ADMINISTRATOR")
        | Q(name__icontains="PROPERTY")
        | Q(name__icontains="LEASE")
        | Q(name__icontains="FACILITY")
        | Q(name__icontains="FINANCE")
        | Q(name__icontains="COMMERCIAL")
    )
    for role in roles:
        for permission in permissions:
            RolePermission.objects.get_or_create(role=role, permission=permission)


def reverse_permissions(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [
        ("leaseops", "0001_initial"),
        ("identity", "0002_remove_user_is_staff_remove_user_is_superuser"),
    ]
    operations = [migrations.RunPython(seed_permissions, reverse_permissions)]
