from django.db import migrations

PERMISSIONS = [
    ("adminops.dashboard.read", "Read enterprise administration dashboard", "adminops"),
    ("adminops.environment.read", "Read runtime environments", "adminops"),
    ("adminops.environment.manage", "Manage runtime environments", "adminops"),
    ("adminops.release.read", "Read governed releases", "adminops"),
    ("adminops.release.create", "Create governed releases", "adminops"),
    ("adminops.release.validate", "Validate governed releases", "adminops"),
    ("adminops.release.approve", "Approve governed releases", "adminops"),
    ("adminops.release.deploy", "Record governed deployments", "adminops"),
    ("adminops.release.rollback", "Record governed release rollbacks", "adminops"),
    ("adminops.check.read", "Read release-readiness checks", "adminops"),
    ("adminops.check.manage", "Manage release-readiness checks", "adminops"),
    ("adminops.check.waive", "Waive release-readiness checks", "restricted"),
    ("adminops.slo.read", "Read service objectives", "adminops"),
    ("adminops.slo.manage", "Manage service objectives", "adminops"),
    ("adminops.health.read", "Read service health evidence", "adminops"),
    ("adminops.health.record", "Record service health evidence", "adminops"),
    ("adminops.incident.read", "Read operational incidents", "adminops"),
    ("adminops.incident.create", "Create operational incidents", "adminops"),
    ("adminops.incident.manage", "Manage operational incidents", "adminops"),
    ("adminops.incident.close", "Close operational incidents", "restricted"),
    ("adminops.runbook.read", "Read operational runbooks", "adminops"),
    ("adminops.runbook.manage", "Manage operational runbooks", "adminops"),
    ("adminops.feature_flag.read", "Read feature flags", "adminops"),
    ("adminops.feature_flag.manage", "Manage feature flags", "adminops"),
    ("adminops.feature_flag.approve", "Approve feature-flag enablement", "restricted"),
    ("adminops.maintenance.read", "Read maintenance windows", "adminops"),
    ("adminops.maintenance.manage", "Manage maintenance windows", "adminops"),
    ("adminops.maintenance.approve", "Approve maintenance windows", "restricted"),
    ("adminops.security.read", "Read production security posture", "restricted"),
    ("adminops.audit.export", "Export operational audit evidence", "restricted"),
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
    dependencies = [("identity", "0011_phase11_ai_permissions")]
    operations = [migrations.RunPython(create_permissions, delete_permissions)]
