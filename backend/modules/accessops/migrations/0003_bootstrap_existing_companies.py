from django.db import migrations
from django.db.models import Q


COMPANY_ACCESS_CODES = (
    "access.view",
    "access.manage",
    "access.invite",
    "access.role.manage",
    "access.membership.manage",
)


def bootstrap_existing_companies(apps, schema_editor):
    Company = apps.get_model("tenant", "Company")
    CompanyAccessProfile = apps.get_model("accessops", "CompanyAccessProfile")
    Permission = apps.get_model("identity", "Permission")
    Role = apps.get_model("identity", "Role")
    RolePermission = apps.get_model("identity", "RolePermission")

    permissions = list(Permission.objects.filter(code__in=COMPANY_ACCESS_CODES))
    for company in Company.objects.all():
        CompanyAccessProfile.objects.get_or_create(
            company=company,
            defaults={
                "onboarding_status_code": "EXISTING_TENANT",
                "primary_admin_email": "",
            },
        )
        admin_roles = Role.objects.filter(
            company_public_id=company.public_id,
            retired_at__isnull=True,
        ).filter(
            Q(code__icontains="ADMIN") | Q(name__icontains="ADMINISTRATOR")
        )
        for role in admin_roles:
            for permission in permissions:
                RolePermission.objects.get_or_create(role=role, permission=permission)


class Migration(migrations.Migration):
    dependencies = [("accessops", "0002_seed_permissions")]
    operations = [migrations.RunPython(bootstrap_existing_companies, migrations.RunPython.noop)]
