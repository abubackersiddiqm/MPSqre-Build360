import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [("tenant", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="FileObject",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("purpose_code", models.CharField(max_length=100)),
                ("data_class", models.CharField(max_length=100)),
                ("status", models.CharField(choices=[("ACTIVE", "Active"), ("DELETED", "Deleted"), ("QUARANTINED", "Quarantined")], default="ACTIVE", max_length=20)),
                ("created_by_public_id", models.UUIDField()),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="file_objects", to="tenant.company")),
            ],
            options={
                "db_table": "files_file_object",
                "indexes": [models.Index(fields=["company", "purpose_code", "status"], name="files_company_purpose_idx")],
            },
        ),
        migrations.CreateModel(
            name="FileVersion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("version", models.PositiveIntegerField()),
                ("object_key", models.CharField(max_length=700, unique=True)),
                ("original_name", models.CharField(max_length=255)),
                ("content_type", models.CharField(max_length=150)),
                ("expected_size_bytes", models.PositiveBigIntegerField()),
                ("actual_size_bytes", models.PositiveBigIntegerField(blank=True, null=True)),
                ("expected_sha256", models.CharField(max_length=64)),
                ("actual_sha256", models.CharField(blank=True, max_length=64)),
                ("upload_status", models.CharField(choices=[("INITIATED", "Initiated"), ("UPLOADED", "Uploaded"), ("FINALIZED", "Finalized"), ("REJECTED", "Rejected")], default="INITIATED", max_length=20)),
                ("scan_status", models.CharField(choices=[("PENDING", "Pending"), ("CLEAN", "Clean"), ("INFECTED", "Infected"), ("FAILED", "Failed")], default="PENDING", max_length=20)),
                ("created_by_public_id", models.UUIDField()),
                ("finalized_at", models.DateTimeField(blank=True, null=True)),
                ("scan_completed_at", models.DateTimeField(blank=True, null=True)),
                ("rejection_reason", models.CharField(blank=True, max_length=200)),
                ("file_object", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="versions", to="files.fileobject")),
            ],
            options={
                "db_table": "files_file_version",
                "indexes": [models.Index(fields=["file_object", "upload_status", "scan_status"], name="files_version_state_idx")],
                "constraints": [
                    models.UniqueConstraint(fields=("file_object", "version"), name="files_object_version_unique"),
                    models.CheckConstraint(condition=models.Q(("actual_size_bytes__isnull", True), ("actual_size_bytes__gte", 0), _connector="OR"), name="files_actual_size_nonnegative"),
                ],
            },
        ),
    ]
