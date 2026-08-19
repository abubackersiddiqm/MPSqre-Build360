from django.db import migrations


PERMISSIONS = [
    ("crm.dashboard.read", "Read CRM dashboard metrics"),
    ("crm.stage.read", "Read CRM pipeline stages"),
    ("crm.stage.manage", "Manage CRM pipeline stages"),
    ("crm.customer.read", "Read CRM customers"),
    ("crm.customer.manage", "Create and update CRM customers"),
    ("crm.contact.read", "Read masked CRM contacts"),
    ("crm.contact.manage", "Create and update CRM contacts"),
    ("crm.contact.reveal", "Reveal protected CRM contact endpoints"),
    ("crm.lead.read", "Read CRM leads"),
    ("crm.lead.manage", "Create and update CRM leads"),
    ("crm.lead.assign", "Assign CRM leads to active memberships"),
    ("crm.lead.transition", "Transition CRM leads"),
    ("crm.lead.convert", "Convert qualified CRM leads"),
    ("crm.opportunity.read", "Read CRM opportunities"),
    ("crm.opportunity.manage", "Create and update CRM opportunities"),
    ("crm.opportunity.assign", "Assign CRM opportunities to active memberships"),
    ("crm.opportunity.transition", "Transition CRM opportunities"),
    ("crm.activity.read", "Read CRM activities"),
    ("crm.activity.manage", "Create and update CRM activities"),
]


def create_permissions(apps, schema_editor):
    permission = apps.get_model("identity", "Permission")
    for code, description in PERMISSIONS:
        permission.objects.get_or_create(
            code=code,
            defaults={"description": description, "data_class": "crm"},
        )


def delete_permissions(apps, schema_editor):
    permission = apps.get_model("identity", "Permission")
    permission.objects.filter(code__in=[code for code, _ in PERMISSIONS]).delete()


class Migration(migrations.Migration):
    dependencies = [("identity", "0003_phase3_permissions")]
    operations = [migrations.RunPython(create_permissions, delete_permissions)]
