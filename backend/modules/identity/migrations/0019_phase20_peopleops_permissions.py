from django.db import migrations


PERMISSIONS = [
    ("people.dashboard.read", "Read people operations dashboard", "restricted"),
    ("people.employee.read", "Read employee records", "restricted"),
    ("people.employee.manage", "Manage employee records", "restricted"),
    ("people.department.read", "Read departments", "restricted"),
    ("people.department.manage", "Manage departments", "restricted"),
    ("people.contract.read", "Read employment contracts", "confidential"),
    ("people.contract.manage", "Manage employment contracts", "confidential"),
    ("people.contract.approve", "Approve employment contracts", "confidential"),
    ("people.leave.policy.read", "Read leave policies", "restricted"),
    ("people.leave.policy.manage", "Manage leave policies", "restricted"),
    ("people.leave.balance.read", "Read leave balances", "confidential"),
    ("people.leave.balance.manage", "Manage leave balances", "confidential"),
    ("people.leave.read", "Read leave requests", "confidential"),
    ("people.leave.request", "Create own leave requests", "confidential"),
    ("people.leave.approve", "Approve leave requests", "confidential"),
    ("people.timesheet.read", "Read timesheets", "restricted"),
    ("people.timesheet.create", "Create own timesheets", "restricted"),
    ("people.timesheet.approve", "Approve timesheets", "restricted"),
    ("people.payroll.read", "Read payroll evidence", "highly_restricted"),
    ("people.payroll.manage", "Manage payroll runs", "highly_restricted"),
    ("people.payroll.approve", "Approve payroll runs", "highly_restricted"),
    ("people.payroll.post", "Post payroll runs", "highly_restricted"),
    ("people.audit.read", "Read people operations audit evidence", "restricted"),
    ("people.export", "Export governed people records", "highly_restricted"),
]


def create_permissions(apps, schema_editor):
    permission = apps.get_model("identity", "Permission")
    for code, description, data_class in PERMISSIONS:
        permission.objects.get_or_create(
            code=code,
            defaults={"description": description, "data_class": data_class},
        )


def delete_permissions(apps, schema_editor):
    apps.get_model("identity", "Permission").objects.filter(
        code__in=[code for code, _, _ in PERMISSIONS]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("identity", "0018_phase19_successops_permissions")]
    operations = [migrations.RunPython(create_permissions, delete_permissions)]
