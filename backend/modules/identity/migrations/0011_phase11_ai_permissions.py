from django.db import migrations

PERMISSIONS = [
    ("ai.dashboard.read", "Read AI governance dashboard", "ai"),
    ("ai.provider.read", "Read AI provider profiles", "ai"),
    ("ai.provider.manage", "Manage AI provider profiles", "ai"),
    ("ai.policy.read", "Read AI model policies", "ai"),
    ("ai.policy.manage", "Create and version AI model policies", "ai"),
    ("ai.policy.activate", "Activate or retire AI model policies", "ai"),
    ("ai.interaction.read", "Read AI interaction history", "ai"),
    ("ai.interaction.create", "Create grounded AI interactions", "ai"),
    ("ai.interaction.review", "Review AI responses", "ai"),
    ("ai.citation.read", "Read AI citations", "ai"),
    ("ai.extraction.read", "Read AI extraction jobs", "ai"),
    ("ai.extraction.create", "Create AI extraction jobs", "ai"),
    ("ai.extraction.review", "Review AI extraction results", "ai"),
    ("ai.risk.read", "Read AI risk signals", "ai"),
    ("ai.risk.scan", "Run governed AI risk scans", "ai"),
    ("ai.risk.manage", "Acknowledge and resolve AI risk signals", "ai"),
    ("ai.action.read", "Read AI tool proposals", "ai"),
    ("ai.action.propose", "Create AI tool proposals", "ai"),
    ("ai.action.confirm", "Confirm or reject AI tool proposals", "ai"),
    ("ai.evaluation.read", "Read AI evaluation evidence", "ai"),
    ("ai.evaluation.run", "Run AI governance evaluations", "ai"),
    ("ai.source.restricted", "Use restricted records in governed AI retrieval", "restricted"),
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
    dependencies = [("identity", "0010_phase10_operations_permissions")]
    operations = [migrations.RunPython(create_permissions, delete_permissions)]
