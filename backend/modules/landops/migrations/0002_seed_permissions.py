from django.db import migrations
from django.db.models import Q

PERMISSIONS = [
    ("land.view", "View land acquisition, feasibility and statutory approval operations"),
    ("land.manage", "Manage land acquisition governance policy"),
    ("land.parcel", "Manage land parcels, location and zoning records"),
    ("land.title", "Manage ownership, title and encumbrance evidence"),
    ("land.diligence", "Manage legal, title, technical and environmental due diligence"),
    ("land.feasibility", "Create and manage development feasibility scenarios"),
    ("land.acquisition", "Manage acquisition opportunities, offers and negotiation evidence"),
    ("land.approval", "Manage statutory and development approval registers"),
    ("land.risk", "Manage land acquisition risks and mitigations"),
    ("land.approve", "Approve ownership evidence, feasibility, offers and acquisition controls"),
    ("land.export", "Export land acquisition, due-diligence and approval evidence"),
]


def seed_permissions(apps, schema_editor):
    Permission = apps.get_model("identity", "Permission")
    Role = apps.get_model("identity", "Role")
    RolePermission = apps.get_model("identity", "RolePermission")
    permissions = []
    for code, description in PERMISSIONS:
        permission, _ = Permission.objects.update_or_create(
            code=code,
            defaults={"description": description, "data_class": "LAND_ACQUISITION_FEASIBILITY_APPROVALS"},
        )
        permissions.append(permission)
    roles = Role.objects.filter(retired_at__isnull=True).filter(
        Q(code__icontains="ADMIN")
        | Q(code__icontains="OPERATOR")
        | Q(code__icontains="DIRECTOR")
        | Q(code__icontains="LAND")
        | Q(code__icontains="LEGAL")
        | Q(code__icontains="DEVELOPMENT")
        | Q(code__icontains="COMMERCIAL")
        | Q(code__icontains="FINANCE")
        | Q(code__icontains="PROJECT")
        | Q(name__icontains="ADMINISTRATOR")
        | Q(name__icontains="LAND")
        | Q(name__icontains="LEGAL")
        | Q(name__icontains="DEVELOPMENT")
        | Q(name__icontains="COMMERCIAL")
        | Q(name__icontains="FINANCE")
    )
    for role in roles:
        for permission in permissions:
            RolePermission.objects.get_or_create(role=role, permission=permission)


def reverse_permissions(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [
        ("landops", "0001_initial"),
        ("identity", "0002_remove_user_is_staff_remove_user_is_superuser"),
    ]
    operations = [migrations.RunPython(seed_permissions, reverse_permissions)]
