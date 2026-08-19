from django.db import migrations
from django.db.models import Q

PERMISSIONS = [
    ("integration.meta_leads.read", "Read Meta Lead Ads connector and ingestion evidence", "integration"),
    ("integration.meta_leads.manage", "Configure and activate Meta Lead Ads ingestion", "restricted"),
    ("integration.meta_leads.retry", "Retry failed Meta Lead Ads receipts", "restricted"),
]


def seed_permissions(apps, schema_editor):
    Permission = apps.get_model("identity", "Permission")
    Role = apps.get_model("identity", "Role")
    RolePermission = apps.get_model("identity", "RolePermission")

    created = []
    for code, description, data_class in PERMISSIONS:
        item, _ = Permission.objects.get_or_create(
            code=code,
            defaults={"description": description, "data_class": data_class},
        )
        created.append(item)

    admin_roles = Role.objects.filter(retired_at__isnull=True).filter(
        Q(code__icontains="ADMIN") | Q(name__icontains="ADMINISTRATOR")
    )
    for role in admin_roles.iterator():
        for permission in created:
            RolePermission.objects.get_or_create(role=role, permission=permission)


def remove_permissions(apps, schema_editor):
    Permission = apps.get_model("identity", "Permission")
    RolePermission = apps.get_model("identity", "RolePermission")
    permissions = Permission.objects.filter(code__in=[code for code, _, _ in PERMISSIONS])
    RolePermission.objects.filter(permission__in=permissions).delete()
    permissions.delete()


class Migration(migrations.Migration):
    dependencies = [("identity", "0019_phase20_peopleops_permissions")]
    operations = [migrations.RunPython(seed_permissions, remove_permissions)]
