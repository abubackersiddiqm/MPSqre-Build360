from django.db import migrations
from django.db.models import Q

PERMISSIONS = [
    ("ai.crm_lead.read", "Read governed CRM lead AI intelligence", "ai"),
    ("ai.crm_lead.generate", "Generate or refresh governed CRM lead AI intelligence", "ai"),
    ("ai.crm_lead.override", "Override governed CRM lead AI summary and recommended next action", "restricted"),
]


def seed_permissions(apps, schema_editor):
    Permission = apps.get_model("identity", "Permission")
    Role = apps.get_model("identity", "Role")
    RolePermission = apps.get_model("identity", "RolePermission")

    created = []
    for code, description, data_class in PERMISSIONS:
        permission, _ = Permission.objects.get_or_create(
            code=code,
            defaults={"description": description, "data_class": data_class},
        )
        created.append(permission)

    admin_roles = Role.objects.filter(retired_at__isnull=True).filter(
        Q(code__icontains="ADMIN") | Q(name__icontains="ADMINISTRATOR")
    )
    for role in admin_roles.iterator():
        for permission in created:
            RolePermission.objects.get_or_create(role=role, permission=permission)


def remove_permissions(apps, schema_editor):
    Permission = apps.get_model("identity", "Permission")
    RolePermission = apps.get_model("identity", "RolePermission")
    permissions = Permission.objects.filter(code__in=[row[0] for row in PERMISSIONS])
    RolePermission.objects.filter(permission__in=permissions).delete()
    permissions.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("identity", "0020_meta_lead_ads_permissions"),
    ]

    operations = [
        migrations.RunPython(seed_permissions, remove_permissions),
    ]
