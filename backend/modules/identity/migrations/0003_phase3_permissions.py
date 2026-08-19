from django.db import migrations


PERMISSIONS = [
    ("configuration.read", "Read active tenant configuration"),
    ("configuration.manage", "Create tenant configuration drafts"),
    ("configuration.publish", "Publish tenant configuration versions"),
    ("configuration.secret.read", "Read secret-class configuration payloads"),
    ("workflow.manage", "Create workflow definitions and draft versions"),
    ("workflow.publish", "Publish workflow versions"),
    ("workflow.execute", "Start and transition workflow instances"),
    ("workflow.approve", "Approve or reject workflow approval tasks"),
    ("subscription.read", "Read effective plan entitlements"),
    ("subscription.manage", "Create effective-dated entitlement overrides"),
    ("files.upload", "Initiate and finalize governed file uploads"),
    ("files.read", "Read governed file metadata"),
    ("files.download", "Request governed file download grants"),
    ("audit.read", "Read tenant audit evidence"),
]


def create_permissions(apps, schema_editor):
    permission = apps.get_model("identity", "Permission")
    for code, description in PERMISSIONS:
        permission.objects.get_or_create(code=code, defaults={"description": description})


def delete_permissions(apps, schema_editor):
    permission = apps.get_model("identity", "Permission")
    permission.objects.filter(code__in=[code for code, _ in PERMISSIONS]).delete()


class Migration(migrations.Migration):
    dependencies = [("identity", "0002_remove_user_is_staff_remove_user_is_superuser")]
    operations = [migrations.RunPython(create_permissions, delete_permissions)]
