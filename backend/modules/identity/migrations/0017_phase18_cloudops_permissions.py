from django.db import migrations


PERMISSIONS = [
    ("cloudops.dashboard.read", "Read cloud launch dashboard", "restricted"),
    ("cloudops.target.read", "Read cloud deployment targets", "restricted"),
    ("cloudops.target.manage", "Manage cloud deployment targets", "restricted"),
    ("cloudops.target.activate", "Activate cloud deployment targets", "restricted"),
    ("cloudops.pipeline.read", "Read deployment pipelines", "restricted"),
    ("cloudops.pipeline.manage", "Manage deployment pipelines", "restricted"),
    ("cloudops.deployment.read", "Read deployment executions", "restricted"),
    ("cloudops.deployment.create", "Request deployments", "restricted"),
    ("cloudops.deployment.validate", "Validate deployments", "restricted"),
    ("cloudops.deployment.approve", "Approve deployments", "restricted"),
    ("cloudops.deployment.execute", "Execute deployments", "restricted"),
    ("cloudops.deployment.rollback", "Rollback deployments", "restricted"),
    ("cloudops.backup.read", "Read backup policies and runs", "restricted"),
    ("cloudops.backup.manage", "Manage backup policies", "restricted"),
    ("cloudops.backup.execute", "Execute backup policies", "restricted"),
    ("cloudops.backup.verify", "Verify backup evidence", "restricted"),
    ("cloudops.restore.read", "Read restore exercises", "restricted"),
    ("cloudops.restore.create", "Create restore exercises", "restricted"),
    ("cloudops.restore.execute", "Execute restore exercises", "restricted"),
    ("cloudops.restore.approve", "Approve restore exercises", "restricted"),
    ("cloudops.secret.read", "Read secret rotation inventory", "restricted"),
    ("cloudops.secret.manage", "Manage secret rotation policies", "restricted"),
    ("cloudops.secret.rotate", "Record secret rotation evidence", "restricted"),
    ("cloudops.audit.read", "Read cloud launch audit evidence", "restricted"),
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
    dependencies = [("identity", "0016_phase17_compliance_permissions")]
    operations = [migrations.RunPython(create_permissions, delete_permissions)]
