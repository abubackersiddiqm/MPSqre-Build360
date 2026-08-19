from django.db import migrations

PERMISSIONS = [
    ("integration.dashboard.read", "Read globalization and integration dashboard", "integration"),
    ("integration.localization.read", "Read localization packs", "integration"),
    ("integration.localization.manage", "Manage draft localization packs", "restricted"),
    ("integration.localization.publish", "Publish localization packs", "restricted"),
    ("integration.currency.read", "Read exchange-rate evidence", "finance"),
    ("integration.currency.manage", "Record exchange-rate evidence", "restricted"),
    ("integration.connector.read", "Read connector profiles", "integration"),
    ("integration.connector.manage", "Manage connector profiles", "restricted"),
    ("integration.connector.health", "Evaluate connector configuration health", "integration"),
    ("integration.api_client.read", "Read API client metadata", "restricted"),
    ("integration.api_client.manage", "Issue API client credentials", "restricted"),
    ("integration.api_client.rotate", "Rotate API client credentials", "restricted"),
    ("integration.api_client.revoke", "Revoke API client credentials", "restricted"),
    ("integration.webhook.read", "Read webhook subscriptions and delivery evidence", "integration"),
    ("integration.webhook.manage", "Manage webhook subscriptions", "restricted"),
    ("integration.webhook.test", "Run governed webhook delivery simulations", "restricted"),
    ("integration.mapping.read", "Read integration mapping profiles", "integration"),
    ("integration.mapping.manage", "Manage draft integration mappings", "restricted"),
    ("integration.mapping.publish", "Publish integration mapping profiles", "restricted"),
    ("integration.sync.read", "Read synchronization run evidence", "integration"),
    ("integration.sync.run", "Start and complete synchronization runs", "restricted"),
    ("integration.audit.read", "Read integration audit evidence", "restricted"),
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
    dependencies = [("identity", "0013_phase13_controlplane_permissions")]
    operations = [migrations.RunPython(create_permissions, delete_permissions)]
