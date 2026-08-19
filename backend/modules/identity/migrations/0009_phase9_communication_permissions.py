from django.db import migrations

PERMISSIONS = [
    ("communication.dashboard.read", "Read communication and notification dashboard", "communication"),
    ("communication.policy.read", "Read channel policies", "communication"),
    ("communication.policy.manage", "Manage channel policies", "communication"),
    ("communication.provider.read", "Read provider configurations", "communication"),
    ("communication.provider.manage", "Manage provider configurations", "communication"),
    ("communication.template.read", "Read communication templates", "communication"),
    ("communication.template.manage", "Manage communication templates", "communication"),
    ("communication.template.publish", "Publish communication templates", "communication"),
    ("communication.consent.read", "Read communication consent evidence", "communication"),
    ("communication.consent.manage", "Record communication consent changes", "communication"),
    ("communication.request.read", "Read communication requests", "communication"),
    ("communication.request.create", "Create communication requests", "communication"),
    ("communication.request.dispatch", "Dispatch communication requests", "communication"),
    ("communication.request.cancel", "Cancel communication requests", "communication"),
    ("communication.callback.read", "Read provider callback receipts", "communication"),
    ("communication.inbound.read", "Read inbound communications", "communication"),
    ("notification.dashboard.read", "Read notification dashboard", "notification"),
    ("notification.read", "Read own notifications", "notification"),
    ("notification.create", "Create governed notifications", "notification"),
    ("notification.mark_read", "Mark own notifications as read", "notification"),
    ("notification.preference.read", "Read own notification preferences", "notification"),
    ("notification.preference.manage", "Manage own notification preferences", "notification"),
    ("notification.rule.read", "Read notification routing rules", "notification"),
    ("notification.rule.manage", "Manage notification routing rules", "notification"),
    ("notification.delivery.read", "Read notification delivery evidence", "notification"),
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
    dependencies = [("identity", "0008_phase8_finance_permissions")]
    operations = [migrations.RunPython(create_permissions, delete_permissions)]
