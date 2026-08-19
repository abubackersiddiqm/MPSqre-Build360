from django.db import migrations

PERMISSIONS = [
    ("compliance.dashboard.read", "Read security and compliance dashboard", "restricted"),
    ("compliance.framework.read", "Read compliance frameworks", "restricted"),
    ("compliance.framework.manage", "Manage compliance frameworks", "restricted"),
    ("compliance.framework.publish", "Publish compliance frameworks", "restricted"),
    ("compliance.control.read", "Read compliance controls", "restricted"),
    ("compliance.control.manage", "Manage compliance controls", "restricted"),
    ("compliance.assessment.read", "Read compliance assessments", "restricted"),
    ("compliance.assessment.create", "Create compliance assessments", "restricted"),
    ("compliance.assessment.evaluate", "Evaluate compliance controls", "restricted"),
    ("compliance.assessment.submit", "Submit compliance assessments", "restricted"),
    ("compliance.assessment.approve", "Approve compliance assessments", "restricted"),
    ("compliance.risk.read", "Read security and compliance risks", "restricted"),
    ("compliance.risk.manage", "Manage security and compliance risks", "restricted"),
    ("compliance.risk.accept", "Accept security and compliance risks", "restricted"),
    ("compliance.exception.read", "Read security exceptions", "restricted"),
    ("compliance.exception.request", "Request security exceptions", "restricted"),
    ("compliance.exception.approve", "Approve security exceptions", "restricted"),
    ("compliance.access_review.read", "Read access-review campaigns", "restricted"),
    ("compliance.access_review.manage", "Manage access-review campaigns", "restricted"),
    ("compliance.access_review.decide", "Decide access-review items", "restricted"),
    ("compliance.access_review.approve", "Approve access-review campaigns", "restricted"),
    ("compliance.audit.read", "Read compliance audit evidence", "restricted"),
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
    dependencies = [("identity", "0015_phase16_pilotops_permissions")]
    operations = [migrations.RunPython(create_permissions, delete_permissions)]
