# Generated for MPSqre Build360 Phase 10.
import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [("tenant", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="MetricDefinition",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=100)),
                ("name", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                ("domain_code", models.CharField(max_length=80)),
                ("calculation_code", models.CharField(max_length=120)),
                ("unit_code", models.CharField(default="count", max_length=40)),
                ("data_classification", models.CharField(choices=[("internal", "Internal"), ("confidential", "Confidential"), ("restricted", "Restricted")], default="internal", max_length=20)),
                ("is_active", models.BooleanField(default=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="tenant.company")),
            ],
            options={
                "db_table": "reporting_metric_definition",
                "ordering": ["domain_code", "name"],
                "indexes": [models.Index(fields=["company", "domain_code", "is_active"], name="rpt_metric_domain_idx")],
                "constraints": [
                    models.UniqueConstraint(fields=("company", "code", "version"), name="rpt_metric_version_uq"),
                    models.UniqueConstraint(condition=models.Q(("is_active", True)), fields=("company", "code"), name="rpt_metric_active_uq"),
                ],
            },
        ),
        migrations.CreateModel(
            name="SavedReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=100)),
                ("name", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                ("report_type", models.CharField(max_length=80)),
                ("metric_codes", models.JSONField(default=list)),
                ("filters", models.JSONField(default=dict)),
                ("columns", models.JSONField(default=list)),
                ("visibility", models.CharField(choices=[("private", "Private"), ("company", "Company"), ("role", "Role")], default="private", max_length=20)),
                ("role_public_ids", models.JSONField(default=list)),
                ("owner_user_public_id", models.UUIDField()),
                ("default_export_format", models.CharField(choices=[("csv", "CSV"), ("xlsx", "Excel"), ("pdf", "PDF")], default="csv", max_length=10)),
                ("schedule_expression", models.CharField(blank=True, max_length=120)),
                ("next_run_at", models.DateTimeField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("version", models.PositiveBigIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="tenant.company")),
            ],
            options={
                "db_table": "reporting_saved_report",
                "ordering": ["name"],
                "indexes": [
                    models.Index(fields=["company", "is_active", "next_run_at"], name="rpt_saved_schedule_idx"),
                    models.Index(fields=["company", "owner_user_public_id", "visibility"], name="rpt_saved_owner_idx"),
                ],
                "constraints": [models.UniqueConstraint(fields=("company", "code"), name="rpt_saved_code_uq")],
            },
        ),
        migrations.CreateModel(
            name="ReportRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("report_code", models.CharField(max_length=100)),
                ("requested_by_public_id", models.UUIDField()),
                ("idempotency_key", models.CharField(max_length=120)),
                ("status", models.CharField(choices=[("queued", "Queued"), ("running", "Running"), ("completed", "Completed"), ("failed", "Failed"), ("cancelled", "Cancelled"), ("expired", "Expired")], default="queued", max_length=20)),
                ("export_format", models.CharField(choices=[("csv", "CSV"), ("xlsx", "Excel"), ("pdf", "PDF")], default="csv", max_length=10)),
                ("parameters", models.JSONField(default=dict)),
                ("metric_snapshot", models.JSONField(default=dict)),
                ("row_count", models.PositiveIntegerField(default=0)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("error_message", models.CharField(blank=True, max_length=1000)),
                ("version", models.PositiveBigIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="tenant.company")),
                ("saved_report", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="runs", to="reporting.savedreport")),
            ],
            options={
                "db_table": "reporting_report_run",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["company", "status", "created_at"], name="rpt_run_status_idx"),
                    models.Index(fields=["company", "requested_by_public_id", "created_at"], name="rpt_run_requester_idx"),
                ],
                "constraints": [models.UniqueConstraint(fields=("company", "idempotency_key"), name="rpt_run_idempotency_uq")],
            },
        ),
        migrations.CreateModel(
            name="ExportArtifact",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("file_name", models.CharField(max_length=240)),
                ("content_type", models.CharField(max_length=120)),
                ("sha256", models.CharField(max_length=64)),
                ("byte_size", models.PositiveBigIntegerField()),
                ("data_classification", models.CharField(choices=[("internal", "Internal"), ("confidential", "Confidential"), ("restricted", "Restricted")], default="internal", max_length=20)),
                ("created_by_public_id", models.UUIDField()),
                ("expires_at", models.DateTimeField()),
                ("download_count", models.PositiveIntegerField(default=0)),
                ("last_downloaded_at", models.DateTimeField(blank=True, null=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="tenant.company")),
                ("run", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="artifact", to="reporting.reportrun")),
            ],
            options={
                "db_table": "reporting_export_artifact",
                "indexes": [models.Index(fields=["company", "expires_at"], name="rpt_artifact_expiry_idx")],
            },
        ),
    ]
