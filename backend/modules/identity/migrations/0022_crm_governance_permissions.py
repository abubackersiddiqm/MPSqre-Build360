from django.db import migrations


PERMISSIONS = (
    (
        "crm.configuration.read",
        "Read CRM configuration, industry packs, custom fields, sources and pipeline setup",
        "crm",
    ),
    (
        "crm.configuration.manage",
        "Manage CRM configuration, industry packs, custom fields, sources and pipeline setup",
        "crm",
    ),
    (
        "crm.automation.read",
        "Read CRM automation rules and execution evidence",
        "crm",
    ),
    (
        "crm.automation.manage",
        "Create, update, activate and pause CRM automation rules",
        "crm",
    ),
    (
        "crm.contact_center.use",
        "Use the CRM Contact Center and contact interaction timeline",
        "restricted",
    ),
)

LEGACY_GRANT_MAP = {
    "crm.configuration.read": ("crm.stage.read",),
    "crm.configuration.manage": ("crm.stage.manage",),
    "crm.automation.read": ("crm.stage.read",),
    "crm.automation.manage": ("crm.stage.manage",),
    "crm.contact_center.use": ("crm.contact.read", "crm.activity.read"),
}


def seed_permissions(apps, schema_editor):
    Permission = apps.get_model("identity", "Permission")
    RolePermission = apps.get_model("identity", "RolePermission")

    created = {}
    for code, description, data_class in PERMISSIONS:
        permission, _ = Permission.objects.update_or_create(
            code=code,
            defaults={"description": description, "data_class": data_class},
        )
        created[code] = permission

    # Preserve the effective access of roles that already had the pre-v20n CRM
    # permissions. This migration does not broaden a role beyond its old
    # capabilities; it only translates those capabilities to the new explicit
    # permission boundary.
    for new_code, legacy_codes in LEGACY_GRANT_MAP.items():
        legacy_permissions = list(Permission.objects.filter(code__in=legacy_codes))
        if len(legacy_permissions) != len(legacy_codes):
            continue
        role_sets = [
            set(
                RolePermission.objects.filter(permission=permission).values_list(
                    "role_id", flat=True
                )
            )
            for permission in legacy_permissions
        ]
        role_ids = set.intersection(*role_sets) if role_sets else set()
        RolePermission.objects.bulk_create(
            [
                RolePermission(role_id=role_id, permission_id=created[new_code].id)
                for role_id in role_ids
            ],
            ignore_conflicts=True,
        )


def remove_permissions(apps, schema_editor):
    Permission = apps.get_model("identity", "Permission")
    RolePermission = apps.get_model("identity", "RolePermission")
    permissions = Permission.objects.filter(code__in=[row[0] for row in PERMISSIONS])
    RolePermission.objects.filter(permission__in=permissions).delete()
    permissions.delete()


class Migration(migrations.Migration):
    dependencies = [("identity", "0021_crm_ai_lead_permissions")]

    operations = [migrations.RunPython(seed_permissions, remove_permissions)]
