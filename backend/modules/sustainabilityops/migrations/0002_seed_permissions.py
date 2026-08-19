from django.db import migrations
from django.db.models import Q

PERMISSIONS = [
    ("sustainability.view", "View sustainability, ESG, carbon and resource operations"),
    ("sustainability.manage", "Manage sustainability policy and configuration"),
    ("sustainability.factor", "Manage governed emission factors"),
    ("sustainability.activity", "Record carbon activities and evidence"),
    ("sustainability.inventory", "Prepare carbon inventories"),
    ("sustainability.resource", "Record energy, water, fuel and material consumption"),
    ("sustainability.waste", "Record waste movement and treatment evidence"),
    ("sustainability.target", "Manage sustainability targets and ESG initiatives"),
    ("sustainability.assure", "Verify activities and approve assurance evidence"),
    ("sustainability.report", "Prepare sustainability and ESG disclosures"),
    ("sustainability.export", "Export sustainability, carbon and ESG evidence"),
]


def seed_permissions(apps, schema_editor):
    Permission = apps.get_model("identity", "Permission")
    Role = apps.get_model("identity", "Role")
    RolePermission = apps.get_model("identity", "RolePermission")
    permissions = []
    for code, description in PERMISSIONS:
        permission, _ = Permission.objects.update_or_create(
            code=code,
            defaults={"description": description, "data_class": "SUSTAINABILITY_ESG"},
        )
        permissions.append(permission)
    roles = Role.objects.filter(retired_at__isnull=True).filter(
        Q(code__icontains="ADMIN")
        | Q(code__icontains="OPERATOR")
        | Q(code__icontains="DIRECTOR")
        | Q(code__icontains="EXECUTIVE")
        | Q(code__icontains="ESG")
        | Q(code__icontains="SUSTAIN")
        | Q(code__icontains="HSE")
        | Q(name__icontains="ADMINISTRATOR")
        | Q(name__icontains="DIRECTOR")
        | Q(name__icontains="SUSTAINABILITY")
        | Q(name__icontains="ENVIRONMENT")
    )
    for role in roles:
        for permission in permissions:
            RolePermission.objects.get_or_create(role=role, permission=permission)


def reverse_permissions(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [
        ("sustainabilityops", "0001_initial"),
        ("identity", "0002_remove_user_is_staff_remove_user_is_superuser"),
    ]
    operations = [migrations.RunPython(seed_permissions, reverse_permissions)]
