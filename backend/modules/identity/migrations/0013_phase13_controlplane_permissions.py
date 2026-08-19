from django.db import migrations

PERMISSIONS = [
    ("controlplane.dashboard.read", "Read SaaS control-plane dashboard", "controlplane"),
    ("controlplane.tenant.read", "Read tenant lifecycle records", "controlplane"),
    ("controlplane.tenant.manage", "Manage tenant lifecycle records", "restricted"),
    ("controlplane.plan.read", "Read subscription plan versions", "controlplane"),
    ("controlplane.plan.manage", "Manage draft subscription plan versions", "restricted"),
    ("controlplane.plan.publish", "Publish subscription plan versions", "restricted"),
    ("controlplane.subscription.read", "Read tenant subscriptions", "controlplane"),
    ("controlplane.subscription.manage", "Assign tenant subscriptions", "restricted"),
    ("controlplane.usage.read", "Read tenant usage and quota evidence", "controlplane"),
    ("controlplane.usage.collect", "Collect tenant usage snapshots", "controlplane"),
    ("controlplane.support.read", "Read governed support access requests", "restricted"),
    ("controlplane.support.request", "Request governed tenant support access", "restricted"),
    ("controlplane.support.approve", "Approve tenant support access requests", "restricted"),
    ("controlplane.operator.read", "Read platform operator assignments", "restricted"),
    ("controlplane.operator.manage", "Manage platform operator assignments", "restricted"),
    ("controlplane.audit.read", "Read cross-tenant control-plane audit evidence", "restricted"),
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
    dependencies = [("identity", "0012_phase12_adminops_permissions")]
    operations = [migrations.RunPython(create_permissions, delete_permissions)]
