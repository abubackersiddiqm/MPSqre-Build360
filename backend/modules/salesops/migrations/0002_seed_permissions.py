from django.db import migrations
from django.db.models import Q

PERMISSIONS = [
    ("sales.view", "View development sales, booking, collections and handover operations"),
    ("sales.manage", "Manage development sales governance policy"),
    ("sales.inventory", "Manage development inventory, pricing and unit release"),
    ("sales.customer", "Manage buyer and customer accounts"),
    ("sales.reservation", "Manage unit reservations and expiry controls"),
    ("sales.booking", "Create and manage booking agreements"),
    ("sales.collection", "Manage payment schedules, receipts and collections"),
    ("sales.commission", "Manage broker and channel commissions"),
    ("sales.handover", "Manage customer readiness, possession and handover evidence"),
    ("sales.approve", "Approve bookings, receipts, commissions and handovers"),
    ("sales.export", "Export development sales and collection evidence"),
]


def seed_permissions(apps, schema_editor):
    Permission = apps.get_model("identity", "Permission")
    Role = apps.get_model("identity", "Role")
    RolePermission = apps.get_model("identity", "RolePermission")
    permissions = []
    for code, description in PERMISSIONS:
        permission, _ = Permission.objects.update_or_create(
            code=code,
            defaults={"description": description, "data_class": "DEVELOPMENT_SALES_BOOKING_COLLECTIONS"},
        )
        permissions.append(permission)
    roles = Role.objects.filter(retired_at__isnull=True).filter(
        Q(code__icontains="ADMIN")
        | Q(code__icontains="OPERATOR")
        | Q(code__icontains="DIRECTOR")
        | Q(code__icontains="SALES")
        | Q(code__icontains="CRM")
        | Q(code__icontains="COMMERCIAL")
        | Q(code__icontains="FINANCE")
        | Q(code__icontains="PROPERTY")
        | Q(name__icontains="ADMINISTRATOR")
        | Q(name__icontains="SALES")
        | Q(name__icontains="CRM")
        | Q(name__icontains="COMMERCIAL")
        | Q(name__icontains="FINANCE")
        | Q(name__icontains="PROPERTY")
    )
    for role in roles:
        for permission in permissions:
            RolePermission.objects.get_or_create(role=role, permission=permission)


def reverse_permissions(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [
        ("salesops", "0001_initial"),
        ("identity", "0002_remove_user_is_staff_remove_user_is_superuser"),
    ]
    operations = [migrations.RunPython(seed_permissions, reverse_permissions)]
