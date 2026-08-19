from django.db import migrations
from django.db.models import Q


PEOPLE_CODES = (
    "peopleorg.view",
    "peopleorg.manage",
    "peopleorg.structure.manage",
    "peopleorg.assignment.manage",
    "peopleorg.leave.manage",
    "peopleorg.attendance.manage",
    "peopleorg.import",
    "peopleorg.export",
)


def bootstrap_existing_people(apps, schema_editor):
    Employee = apps.get_model("employee", "Employee")
    EmployeeOrganizationProfile = apps.get_model("orgops", "EmployeeOrganizationProfile")
    Permission = apps.get_model("identity", "Permission")
    Role = apps.get_model("identity", "Role")
    RolePermission = apps.get_model("identity", "RolePermission")

    for employee in Employee.objects.all().iterator():
        EmployeeOrganizationProfile.objects.get_or_create(
            company_id=employee.company_id,
            employee_id=employee.id,
            defaults={
                "employment_type_code": "FULL_TIME",
                "status_code": "ACTIVE",
            },
        )

    permissions = list(Permission.objects.filter(code__in=PEOPLE_CODES))
    admin_roles = Role.objects.filter(retired_at__isnull=True).filter(
        Q(code__icontains="ADMIN") | Q(name__icontains="ADMINISTRATOR")
    )
    for role in admin_roles.iterator():
        for permission in permissions:
            RolePermission.objects.get_or_create(role_id=role.id, permission_id=permission.id)


class Migration(migrations.Migration):
    dependencies = [
        ("orgops", "0002_seed_permissions"),
        ("accessops", "0003_bootstrap_existing_companies"),
    ]

    operations = [
        migrations.RunPython(bootstrap_existing_people, migrations.RunPython.noop),
    ]
