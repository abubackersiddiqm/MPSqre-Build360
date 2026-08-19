from django.db import migrations

PERMISSIONS = [
    ("reporting.dashboard.read", "Read reporting and operations dashboard", "reporting"),
    ("reporting.metric.read", "Read metric catalogue", "reporting"),
    ("reporting.metric.manage", "Manage metric catalogue", "reporting"),
    ("reporting.report.read", "Read saved reports", "reporting"),
    ("reporting.report.manage", "Manage saved reports", "reporting"),
    ("reporting.run.read", "Read report execution history", "reporting"),
    ("reporting.run.execute", "Execute governed reports", "reporting"),
    ("reporting.export.download", "Download governed report exports", "reporting"),
    ("reporting.schedule.manage", "Manage report schedules", "reporting"),
    ("portal.dashboard.read", "Read portal administration dashboard", "portal"),
    ("portal.invitation.read", "Read portal invitations", "portal"),
    ("portal.invitation.manage", "Create and manage portal invitations", "portal"),
    ("portal.grant.read", "Read portal access grants", "portal"),
    ("portal.grant.manage", "Create portal access grants", "portal"),
    ("portal.grant.revoke", "Revoke portal access grants", "portal"),
    ("portal.share.read", "Read portal shares", "portal"),
    ("portal.share.manage", "Manage portal shares", "portal"),
    ("dataops.dashboard.read", "Read data operations dashboard", "dataops"),
    ("dataops.template.read", "Read import templates", "dataops"),
    ("dataops.template.manage", "Manage import templates", "dataops"),
    ("dataops.import.read", "Read import jobs and validation errors", "dataops"),
    ("dataops.import.create", "Create governed import previews", "dataops"),
    ("dataops.import.commit", "Commit validated import jobs", "dataops"),
    ("dataops.privacy.read", "Read privacy request register", "privacy"),
    ("dataops.privacy.manage", "Create and manage privacy requests", "privacy"),
    ("dataops.privacy.resolve", "Resolve privacy requests", "privacy"),
    ("dataops.retention.read", "Read retention policies", "privacy"),
    ("dataops.retention.manage", "Publish retention policies", "privacy"),
    ("dataops.recovery.read", "Read recovery verification evidence", "operations"),
    ("dataops.recovery.manage", "Manage backup and recovery verification", "operations"),
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
    dependencies = [("identity", "0009_phase9_communication_permissions")]
    operations = [migrations.RunPython(create_permissions, delete_permissions)]
