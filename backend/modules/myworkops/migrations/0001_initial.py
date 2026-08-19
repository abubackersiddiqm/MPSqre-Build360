# Generated for MPSqre Build360 Phase 31.

import uuid

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("tenant", "0001_initial"),
        ("employee", "0001_initial"),
        ("workops", "0003_grant_existing_admin_roles"),
    ]

    operations = [
        migrations.CreateModel(
            name="PersonalNotification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("source_key", models.CharField(max_length=200)),
                ("notification_type_code", models.CharField(max_length=100)),
                ("severity_code", models.CharField(default="INFO", max_length=50)),
                ("title", models.CharField(max_length=250)),
                ("message", models.TextField(blank=True)),
                ("action_url", models.CharField(blank=True, max_length=500)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("dismissed_at", models.DateTimeField(blank=True, null=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="mywork_notifications", to="tenant.company")),
                ("employee", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="mywork_notifications", to="employee.employee")),
                ("work_item", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="mywork_notifications", to="workops.workitem")),
            ],
            options={
                "db_table": "myworkops_notification",
                "constraints": [
                    models.UniqueConstraint(fields=("company", "employee", "source_key"), name="mywork_notify_source_uq")
                ],
                "indexes": [
                    models.Index(fields=["company", "employee", "read_at"], name="mywork_notify_unread_idx"),
                    models.Index(fields=["company", "severity_code", "created_at"], name="mywork_notify_severity_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="OfflineDraft",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("client_draft_id", models.UUIDField(default=uuid.uuid4)),
                ("device_id", models.UUIDField()),
                ("draft_type_code", models.CharField(max_length=100)),
                ("payload", models.JSONField(default=dict)),
                ("status_code", models.CharField(default="DRAFT", max_length=50)),
                ("client_updated_at", models.DateTimeField()),
                ("synced_at", models.DateTimeField(blank=True, null=True)),
                ("conflict_reason", models.TextField(blank=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="mywork_offline_drafts", to="tenant.company")),
                ("employee", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="mywork_offline_drafts", to="employee.employee")),
                ("work_item", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="mywork_offline_drafts", to="workops.workitem")),
            ],
            options={
                "db_table": "myworkops_offline_draft",
                "constraints": [
                    models.UniqueConstraint(fields=("company", "employee", "client_draft_id"), name="mywork_draft_client_uq")
                ],
                "indexes": [
                    models.Index(fields=["company", "employee", "status_code", "client_updated_at"], name="mywork_draft_state_idx")
                ],
            },
        ),
        migrations.CreateModel(
            name="WorkActivity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("activity_type_code", models.CharField(max_length=100)),
                ("summary", models.CharField(max_length=500)),
                ("occurred_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("actor_public_id", models.UUIDField()),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="mywork_activity", to="tenant.company")),
                ("employee", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="mywork_activity", to="employee.employee")),
                ("work_item", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="mywork_activity", to="workops.workitem")),
            ],
            options={
                "db_table": "myworkops_activity",
                "indexes": [
                    models.Index(fields=["company", "employee", "occurred_at"], name="mywork_activity_emp_idx"),
                    models.Index(fields=["company", "work_item", "occurred_at"], name="mywork_activity_work_idx"),
                ],
            },
        ),
    ]
