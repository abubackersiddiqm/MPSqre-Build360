from django.db import migrations

PERMISSIONS = [
    ("field.dashboard.read", "Read field operations dashboard", "field"),
    ("field.stage.read", "Read configurable field stages", "field"),
    ("field.stage.manage", "Manage configurable field stages", "field"),
    ("field.offline.read", "Read offline operation status", "field"),
    ("field.offline.submit", "Submit approved offline operations", "field"),
    ("field.offline.resolve", "Resolve offline synchronization conflicts", "field"),
    ("labour.dashboard.read", "Read labour dashboard", "labour"),
    ("labour.worker.read", "Read worker profiles", "labour"),
    ("labour.worker.manage", "Manage worker profiles", "labour"),
    ("labour.allocation.read", "Read workforce allocations", "labour"),
    ("labour.allocation.manage", "Manage workforce allocations", "labour"),
    ("labour.attendance.read", "Read attendance records", "labour"),
    ("labour.attendance.manage", "Capture and correct attendance", "labour"),
    ("labour.attendance.approve", "Approve attendance records", "labour"),
    ("equipment.dashboard.read", "Read equipment dashboard", "equipment"),
    ("equipment.asset.read", "Read equipment assets", "equipment"),
    ("equipment.asset.manage", "Manage equipment assets", "equipment"),
    ("equipment.allocation.read", "Read equipment allocations", "equipment"),
    ("equipment.allocation.manage", "Manage equipment allocations", "equipment"),
    ("equipment.meter.read", "Read equipment meter history", "equipment"),
    ("equipment.meter.manage", "Capture equipment meter readings", "equipment"),
    ("equipment.maintenance.read", "Read maintenance work orders", "equipment"),
    ("equipment.maintenance.manage", "Manage maintenance work orders", "equipment"),
    ("quality.dashboard.read", "Read quality dashboard", "quality"),
    ("quality.template.read", "Read inspection templates", "quality"),
    ("quality.template.manage", "Manage inspection templates", "quality"),
    ("quality.inspection.read", "Read inspections", "quality"),
    ("quality.inspection.manage", "Schedule and manage inspections", "quality"),
    ("quality.inspection.submit", "Submit inspection evidence and results", "quality"),
    ("quality.inspection.approve", "Approve inspection results", "quality"),
    ("quality.ncr.read", "Read non-conformance reports", "quality"),
    ("quality.ncr.manage", "Manage non-conformance reports", "quality"),
    ("quality.ncr.close", "Verify and close non-conformance reports", "quality"),
    ("safety.dashboard.read", "Read safety dashboard", "safety"),
    ("safety.incident.read", "Read safety incidents", "safety"),
    ("safety.incident.report", "Report safety incidents", "safety"),
    ("safety.incident.investigate", "Investigate safety incidents", "safety"),
    ("safety.incident.close", "Close safety incidents", "safety"),
    ("safety.observation.read", "Read safety observations", "safety"),
    ("safety.observation.manage", "Manage safety observations", "safety"),
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
    dependencies = [("identity", "0006_phase6_supply_permissions")]
    operations = [migrations.RunPython(create_permissions, delete_permissions)]
