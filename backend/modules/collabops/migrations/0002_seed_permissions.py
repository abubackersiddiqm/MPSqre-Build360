from django.db import migrations
from django.db.models import Q
from django.utils import timezone


PERMISSIONS = (
    ("collaboration.view", "View partner organizations, contacts, grants and collaboration activity"),
    ("collaboration.manage", "Manage external partner organization records"),
    ("collaboration.invite", "Invite and govern external partner contacts"),
    ("collaboration.grant", "Grant external contacts project and site access"),
    ("collaboration.request", "Create governed external collaboration requests"),
    ("collaboration.submit", "Submit external responses and evidence"),
    ("collaboration.approve", "Approve or reject external collaboration submissions"),
    ("collaboration.message", "Exchange governed collaboration messages"),
    ("collaboration.configure", "Configure external collaboration policies"),
    ("collaboration.export", "Export external collaboration records"),
    ("collaboration.portal", "Access the external partner portal"),
)

EXTERNAL_ROLES = {
    "EXTERNAL_COLLABORATOR": ("External Collaborator", ["collaboration.portal", "collaboration.submit", "collaboration.message"]),
    "EXTERNAL_APPROVER": ("External Approver", ["collaboration.portal", "collaboration.submit", "collaboration.message", "collaboration.approve"]),
}


def seed_and_grant_permissions(apps, schema_editor):
    Permission = apps.get_model("identity", "Permission")
    Role = apps.get_model("identity", "Role")
    RolePermission = apps.get_model("identity", "RolePermission")
    Company = apps.get_model("tenant", "Company")

    targets = {}
    for code, description in PERMISSIONS:
        permission, _ = Permission.objects.update_or_create(
            code=code,
            defaults={"description": description, "data_class": "EXTERNAL_COLLABORATION"},
        )
        targets[code] = permission

    admin_roles = Role.objects.filter(retired_at__isnull=True).filter(
        Q(code__icontains="ADMIN") | Q(name__icontains="ADMINISTRATOR")
    )
    for role in admin_roles.iterator():
        for permission in targets.values():
            RolePermission.objects.get_or_create(role_id=role.id, permission_id=permission.id)

    now = timezone.now()
    for company in Company.objects.all().iterator():
        for code, (name, permission_codes) in EXTERNAL_ROLES.items():
            role = Role.objects.filter(
                company_public_id=company.public_id,
                code=code,
                retired_at__isnull=True,
            ).order_by("-version").first()
            if role is None:
                role = Role.objects.create(
                    company_public_id=company.public_id,
                    code=code,
                    name=name,
                    version=1,
                    effective_from=now,
                )
            for permission_code in permission_codes:
                RolePermission.objects.get_or_create(role_id=role.id, permission_id=targets[permission_code].id)


class Migration(migrations.Migration):
    dependencies = [
        ("collabops", "0001_initial"),
        ("identity", "0002_remove_user_is_staff_remove_user_is_superuser"),
    ]

    operations = [migrations.RunPython(seed_and_grant_permissions, migrations.RunPython.noop)]
