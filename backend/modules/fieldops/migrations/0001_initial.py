import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [("tenant", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="FieldStage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("entity_type", models.CharField(choices=[("labour_allocation", "Labour allocation"), ("attendance", "Attendance"), ("equipment", "Equipment"), ("equipment_allocation", "Equipment allocation"), ("maintenance", "Maintenance"), ("inspection", "Inspection"), ("ncr", "Non-conformance"), ("incident", "Safety incident"), ("offline_operation", "Offline operation")], max_length=40)),
                ("code", models.CharField(max_length=80)),
                ("name", models.CharField(max_length=160)),
                ("outcome", models.CharField(choices=[("open", "Open"), ("review", "Under review"), ("approved", "Approved"), ("rejected", "Rejected"), ("active", "Active"), ("complete", "Complete"), ("cancelled", "Cancelled"), ("blocked", "Blocked")], default="open", max_length=30)),
                ("sort_order", models.PositiveIntegerField(default=100)),
                ("allowed_next_codes", models.JSONField(default=list)),
                ("is_initial", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("effective_from", models.DateTimeField()),
                ("effective_to", models.DateTimeField(blank=True, null=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="tenant.company")),
            ],
            options={
                "db_table": "fieldops_stage",
                "ordering": ["entity_type", "sort_order", "name"],
                "constraints": [models.UniqueConstraint(fields=("company", "entity_type", "code"), name="fld_stage_company_code_uq"), models.CheckConstraint(condition=models.Q(("effective_to__isnull", True), ("effective_to__gt", models.F("effective_from")), _connector="OR"), name="fld_stage_range_valid")],
                "indexes": [models.Index(fields=["company", "entity_type", "is_active", "sort_order"], name="fld_stage_active_idx")],
            },
        ),
        migrations.CreateModel(
            name="OfflineOperation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("operation_id", models.UUIDField()),
                ("device_id", models.UUIDField()),
                ("actor_membership_public_id", models.UUIDField()),
                ("operation_type", models.CharField(max_length=100)),
                ("aggregate_type", models.CharField(max_length=80)),
                ("aggregate_public_id", models.UUIDField(blank=True, null=True)),
                ("expected_version", models.PositiveBigIntegerField(blank=True, null=True)),
                ("payload", models.JSONField(default=dict)),
                ("status", models.CharField(choices=[("received", "Received"), ("applied", "Applied"), ("conflict", "Conflict"), ("rejected", "Rejected")], default="received", max_length=20)),
                ("result", models.JSONField(default=dict)),
                ("rejection_code", models.CharField(blank=True, max_length=100)),
                ("received_at", models.DateTimeField()),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="tenant.company")),
            ],
            options={
                "db_table": "fieldops_offline_operation",
                "constraints": [models.UniqueConstraint(fields=("company", "operation_id"), name="fld_offline_operation_uq")],
                "indexes": [models.Index(fields=["company", "device_id", "received_at"], name="fld_offline_device_idx"), models.Index(fields=["company", "status", "received_at"], name="fld_offline_status_idx")],
            },
        ),
        migrations.CreateModel(
            name="SyncCheckpoint",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("device_id", models.UUIDField()),
                ("actor_membership_public_id", models.UUIDField()),
                ("last_operation_received_at", models.DateTimeField(blank=True, null=True)),
                ("last_server_sequence", models.PositiveBigIntegerField(default=0)),
                ("last_successful_sync_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="tenant.company")),
            ],
            options={
                "db_table": "fieldops_sync_checkpoint",
                "constraints": [models.UniqueConstraint(fields=("company", "device_id", "actor_membership_public_id"), name="fld_checkpoint_device_uq")],
                "indexes": [models.Index(fields=["company", "actor_membership_public_id", "revoked_at"], name="fld_checkpoint_actor_idx")],
            },
        ),
        migrations.CreateModel(
            name="SyncConflict",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("conflict_code", models.CharField(max_length=100)),
                ("server_version", models.PositiveBigIntegerField(blank=True, null=True)),
                ("client_version", models.PositiveBigIntegerField(blank=True, null=True)),
                ("server_snapshot", models.JSONField(default=dict)),
                ("resolution", models.JSONField(default=dict)),
                ("resolved_by_public_id", models.UUIDField(blank=True, null=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="tenant.company")),
                ("operation", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="conflict", to="fieldops.offlineoperation")),
            ],
            options={"db_table": "fieldops_sync_conflict", "indexes": [models.Index(fields=["company", "resolved_at", "created_at"], name="fld_conflict_open_idx")]},
        ),
    ]
