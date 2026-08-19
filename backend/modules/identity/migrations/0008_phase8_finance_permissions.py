from django.db import migrations

PERMISSIONS = [
    ("finance.dashboard.read", "Read finance and commercial dashboard", "finance"),
    ("finance.stage.read", "Read commercial stages", "finance"),
    ("finance.stage.manage", "Manage commercial stages", "finance"),
    ("finance.policy.read", "Read finance policy", "finance"),
    ("finance.policy.manage", "Manage finance policy", "finance"),
    ("finance.period.read", "Read financial periods", "finance"),
    ("finance.period.manage", "Manage financial periods", "finance"),
    ("finance.period.lock", "Lock financial periods", "finance"),
    ("finance.budget.read", "Read project budgets", "finance"),
    ("finance.budget.manage", "Manage project budgets", "finance"),
    ("finance.budget.approve", "Approve project budgets", "finance"),
    ("finance.variation.read", "Read variations", "finance"),
    ("finance.variation.manage", "Manage variations", "finance"),
    ("finance.variation.approve", "Approve variations", "finance"),
    ("finance.invoice.read", "Read invoices", "finance"),
    ("finance.invoice.manage", "Manage invoices", "finance"),
    ("finance.invoice.approve", "Approve and post invoices", "finance"),
    ("finance.payment.read", "Read payments", "finance"),
    ("finance.payment.manage", "Manage payments", "finance"),
    ("finance.payment.post", "Post payments", "finance"),
    ("finance.retention.read", "Read retention balances", "finance"),
    ("finance.retention.release", "Release retention", "finance"),
    ("finance.ledger.read", "Read commercial ledger", "finance"),
    ("finance.ledger.export", "Export commercial ledger", "finance"),
    ("finance.forecast.read", "Read project forecasts", "finance"),
    ("finance.forecast.manage", "Manage project forecasts", "finance"),
    ("finance.accrual.read", "Read accruals", "finance"),
    ("finance.accrual.manage", "Manage accruals", "finance"),
    ("finance.adjustment.read", "Read commercial adjustments", "finance"),
    ("finance.adjustment.post", "Post commercial adjustments", "finance"),
    ("finance.report.read", "Read finance reports", "finance"),
]


def create_permissions(apps, schema_editor):
    permission = apps.get_model("identity", "Permission")
    for code, description, data_class in PERMISSIONS:
        permission.objects.get_or_create(code=code, defaults={"description": description, "data_class": data_class})


def delete_permissions(apps, schema_editor):
    apps.get_model("identity", "Permission").objects.filter(code__in=[code for code, _, _ in PERMISSIONS]).delete()


class Migration(migrations.Migration):
    dependencies = [("identity", "0007_phase7_field_permissions")]
    operations = [migrations.RunPython(create_permissions, delete_permissions)]
