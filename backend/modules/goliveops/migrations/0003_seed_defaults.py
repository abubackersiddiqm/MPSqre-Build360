from decimal import Decimal

from django.db import migrations

GATES = [
    ("MASTER_DATA_VALIDATED", "Master data migration validated", "DATA"),
    ("USER_ACCESS_READY", "User identities, roles and access are ready", "ACCESS"),
    ("TRAINING_COMPLETE", "Required user training is complete", "ENABLEMENT"),
    ("CUTOVER_PLAN_APPROVED", "Cutover plan and rollback path are approved", "CUTOVER"),
    ("BACKUP_RESTORE_READY", "Backup and restore evidence is current", "RECOVERY"),
    ("SUPPORT_ROSTER_READY", "Hypercare support roster is staffed", "SUPPORT"),
    ("COMMUNICATIONS_READY", "Stakeholder communications are ready", "COMMUNICATIONS"),
    ("SECURITY_SIGNOFF", "Security and tenant isolation sign-off is complete", "SECURITY"),
    ("PERFORMANCE_SIGNOFF", "Performance and stability sign-off is complete", "PERFORMANCE"),
    ("GO_LIVE_APPROVAL", "Independent go-live approval is recorded", "GOVERNANCE"),
]


def seed_defaults(apps, schema_editor):
    Company = apps.get_model("tenant", "Company")
    Policy = apps.get_model("goliveops", "GoLivePolicyVersion")
    Gate = apps.get_model("goliveops", "GoLiveGate")
    for company in Company.objects.all().iterator():
        Policy.objects.get_or_create(
            company=company,
            version=1,
            defaults={
                "status_code": "DRAFT",
                "migration_error_tolerance_percent": Decimal("0.00"),
                "minimum_training_completion_percent": Decimal("100.00"),
                "cutover_freeze_hours": 24,
                "hypercare_days": 14,
                "configuration": {"phase": 35, "release": "v1-go-live-enablement"},
            },
        )
        for code, name, category in GATES:
            Gate.objects.get_or_create(
                company=company,
                code=code,
                defaults={
                    "name": name,
                    "category_code": category,
                    "description": "Required Build360 production go-live control.",
                    "is_required": True,
                },
            )


def reverse_defaults(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [("goliveops", "0002_seed_permissions")]
    operations = [migrations.RunPython(seed_defaults, reverse_defaults)]
