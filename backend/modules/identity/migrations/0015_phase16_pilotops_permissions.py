from django.db import migrations

PERMISSIONS = [
    ("pilot.dashboard.read", "Read pilot operations dashboard", "operations"),
    ("pilot.program.read", "Read pilot program", "operations"),
    ("pilot.program.manage", "Manage pilot program", "restricted"),
    ("pilot.checklist.read", "Read pilot checklist", "operations"),
    ("pilot.checklist.manage", "Manage pilot checklist", "restricted"),
    ("pilot.checklist.complete", "Complete pilot checklist items", "operations"),
    ("pilot.checklist.waive", "Waive pilot checklist items", "restricted"),
    ("pilot.master_data.read", "Read master-data readiness", "operations"),
    ("pilot.master_data.validate", "Validate pilot master data", "restricted"),
    ("pilot.training.read", "Read training readiness", "operations"),
    ("pilot.training.manage", "Manage pilot training", "restricted"),
    ("pilot.training.complete", "Complete assigned pilot training", "operations"),
    ("pilot.readiness.read", "Read pilot readiness assessments", "operations"),
    ("pilot.readiness.assess", "Generate pilot readiness assessments", "restricted"),
    ("pilot.golive.read", "Read go-live plans and sign-offs", "operations"),
    ("pilot.golive.manage", "Manage go-live plans", "restricted"),
    ("pilot.golive.signoff", "Approve or reject go-live sign-offs", "restricted"),
    ("pilot.golive.waive", "Waive go-live sign-offs", "restricted"),
    ("pilot.golive.approve", "Approve pilot go-live", "restricted"),
    ("pilot.golive.execute", "Execute pilot cutover", "restricted"),
    ("pilot.golive.rollback", "Execute governed pilot rollback", "restricted"),
    ("pilot.adoption.read", "Read pilot adoption evidence", "operations"),
    ("pilot.adoption.collect", "Collect pilot adoption evidence", "restricted"),
    ("pilot.audit.read", "Read pilot audit evidence", "restricted"),
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
    dependencies = [("identity", "0014_phase14_integration_permissions")]
    operations = [migrations.RunPython(create_permissions, delete_permissions)]
