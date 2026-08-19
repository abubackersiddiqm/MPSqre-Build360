from django.db import migrations


PERMISSIONS = (
    ("document.view", "View tenant document, revision, RFI, transmittal and submittal summaries"),
    ("document.manage", "Manage controlled documents, workflows, approvals and engineering risks"),
    ("document.issue", "Issue revisions, transmittals and governed document distributions"),
    ("document.rfi", "Raise, assign, respond to and close requests for information"),
    ("document.submittal", "Create, review and govern technical submittals"),
    ("document.approve", "Decide document-control and engineering approvals"),
    ("document.configure", "Create versioned tenant document-control policies"),
    ("document.export", "Generate governed document registers, dossiers and audit exports"),
)


def seed_permissions(apps, schema_editor):
    Permission = apps.get_model("identity", "Permission")
    Role = apps.get_model("identity", "Role")
    RolePermission = apps.get_model("identity", "RolePermission")

    permissions = []
    for code, description in PERMISSIONS:
        permission, _ = Permission.objects.get_or_create(
            code=code,
            defaults={
                "description": description,
                "data_class": "document_restricted",
            },
        )
        permissions.append(permission)

    for role in Role.objects.filter(code="company_administrator").iterator():
        for permission in permissions:
            RolePermission.objects.get_or_create(role=role, permission=permission)


def remove_permissions(apps, schema_editor):
    Permission = apps.get_model("identity", "Permission")
    RolePermission = apps.get_model("identity", "RolePermission")
    permission_ids = Permission.objects.filter(
        code__in=[code for code, _ in PERMISSIONS]
    ).values_list("id", flat=True)
    RolePermission.objects.filter(permission_id__in=permission_ids).delete()
    Permission.objects.filter(id__in=permission_ids).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("identity", "0002_remove_user_is_staff_remove_user_is_superuser"),
        ("documentops", "0001_initial"),
    ]

    operations = [migrations.RunPython(seed_permissions, remove_permissions)]
