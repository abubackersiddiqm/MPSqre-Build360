from django.db import migrations


def seed_definitions(apps, schema_editor):
    definition = apps.get_model("configuration", "ConfigurationDefinition")
    rows = [
        {
            "code": "platform.localization",
            "name": "Localization defaults",
            "description": "Tenant terminology, formats, and localization defaults.",
            "schema": {
                "type": "object",
                "required": ["locale", "timezone", "currency", "unit_system_code"],
                "properties": {
                    "locale": {"type": "string"},
                    "timezone": {"type": "string"},
                    "currency": {"type": "string"},
                    "unit_system_code": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
        {
            "code": "workflow.approval_defaults",
            "name": "Approval defaults",
            "description": "Default approval SLA and escalation behavior.",
            "schema": {
                "type": "object",
                "required": ["default_due_hours", "escalation_enabled"],
                "properties": {
                    "default_due_hours": {"type": "integer"},
                    "escalation_enabled": {"type": "boolean"},
                },
                "additionalProperties": False,
            },
        },
        {
            "code": "files.retention",
            "name": "File retention policy",
            "description": "Default retention and deletion review settings.",
            "schema": {
                "type": "object",
                "required": ["default_retention_days"],
                "properties": {
                    "default_retention_days": {"type": "integer"},
                    "legal_hold_enabled": {"type": "boolean"},
                },
                "additionalProperties": False,
            },
        },
    ]
    for row in rows:
        definition.objects.get_or_create(code=row["code"], defaults=row)


def unseed_definitions(apps, schema_editor):
    definition = apps.get_model("configuration", "ConfigurationDefinition")
    definition.objects.filter(
        code__in=[
            "platform.localization",
            "workflow.approval_defaults",
            "files.retention",
        ]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("configuration", "0001_initial")]
    operations = [migrations.RunPython(seed_definitions, unseed_definitions)]
