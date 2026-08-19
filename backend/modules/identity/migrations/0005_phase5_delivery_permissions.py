from django.db import migrations


PERMISSIONS = [
    ("project.dashboard.read", "Read project delivery dashboard"),
    ("project.stage.read", "Read configurable delivery stages"),
    ("project.stage.manage", "Manage configurable delivery stages"),
    ("project.project.read", "Read projects"),
    ("project.project.manage", "Create and update projects"),
    ("project.project.transition", "Transition projects"),
    ("project.project.baseline", "Create immutable project baselines"),
    ("project.wbs.read", "Read project work breakdown structures"),
    ("project.wbs.manage", "Manage project work breakdown structures"),
    ("project.task.read", "Read project tasks"),
    ("project.task.manage", "Create and update project tasks"),
    ("project.task.transition", "Transition project tasks"),
    ("design.dashboard.read", "Read design control dashboard"),
    ("design.document.read", "Read design documents"),
    ("design.document.manage", "Create and update design documents"),
    ("design.version.read", "Read design document versions"),
    ("design.version.manage", "Create design document versions"),
    ("design.version.transition", "Transition design document versions"),
    ("design.review.read", "Read design reviews"),
    ("design.review.manage", "Request design reviews"),
    ("design.review.decide", "Decide design reviews"),
    ("design.issue.read", "Read design issues"),
    ("design.issue.manage", "Create and close design issues"),
    ("design.transmittal.read", "Read design transmittals"),
    ("design.transmittal.manage", "Issue design transmittals"),
    ("estimation.dashboard.read", "Read estimation dashboard"),
    ("estimation.estimate.read", "Read estimates"),
    ("estimation.estimate.manage", "Create and update estimates"),
    ("estimation.version.read", "Read estimate versions"),
    ("estimation.version.manage", "Create estimate versions"),
    ("estimation.version.transition", "Transition estimate versions"),
    ("estimation.version.baseline", "Create immutable estimate baselines"),
    ("estimation.boq.read", "Read bills of quantities"),
    ("estimation.boq.manage", "Manage bill-of-quantities sections and items"),
]


def create_permissions(apps, schema_editor):
    permission = apps.get_model("identity", "Permission")
    for code, description in PERMISSIONS:
        permission.objects.get_or_create(
            code=code,
            defaults={"description": description, "data_class": "delivery"},
        )


def delete_permissions(apps, schema_editor):
    permission = apps.get_model("identity", "Permission")
    permission.objects.filter(code__in=[code for code, _ in PERMISSIONS]).delete()


class Migration(migrations.Migration):
    dependencies = [("identity", "0004_crm_permissions")]
    operations = [migrations.RunPython(create_permissions, delete_permissions)]
