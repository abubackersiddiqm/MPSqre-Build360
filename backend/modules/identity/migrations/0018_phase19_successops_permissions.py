from django.db import migrations


PERMISSIONS = [
    ("success.dashboard.read", "Read customer success dashboard", "restricted"),
    ("success.account.read", "Read customer success accounts", "restricted"),
    ("success.account.manage", "Manage customer success accounts", "restricted"),
    ("success.account.health", "Manage customer health evidence", "restricted"),
    ("success.billing.read", "Read subscription billing records", "restricted"),
    ("success.billing.manage", "Manage subscription billing records", "restricted"),
    ("success.billing.issue", "Issue subscription invoices", "restricted"),
    ("success.billing.payment", "Record subscription payments", "restricted"),
    ("success.billing.void", "Void subscription invoices", "restricted"),
    ("success.support.read", "Read support tickets and SLAs", "restricted"),
    ("success.support.create", "Create support tickets", "restricted"),
    ("success.support.manage", "Manage support ticket lifecycle", "restricted"),
    ("success.support.escalate", "Escalate support tickets", "restricted"),
    ("success.support.resolve", "Resolve support tickets", "restricted"),
    ("success.plan.read", "Read customer success plans", "restricted"),
    ("success.plan.manage", "Manage customer success plans", "restricted"),
    ("success.plan.review", "Review customer success plans", "restricted"),
    ("success.adoption.read", "Read adoption evidence", "restricted"),
    ("success.adoption.collect", "Collect adoption evidence", "restricted"),
    ("success.service_review.read", "Read service reviews", "restricted"),
    ("success.service_review.manage", "Manage service reviews", "restricted"),
    ("success.audit.read", "Read customer success audit evidence", "restricted"),
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
    dependencies = [("identity", "0017_phase18_cloudops_permissions")]
    operations = [migrations.RunPython(create_permissions, delete_permissions)]
