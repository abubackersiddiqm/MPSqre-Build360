import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [("tenant", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="WorkflowDefinition",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=150)),
                ("name", models.CharField(max_length=200)),
                ("description", models.CharField(blank=True, max_length=500)),
                ("is_active", models.BooleanField(default=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="workflow_definitions", to="tenant.company")),
            ],
            options={
                "db_table": "workflow_definition",
                "constraints": [models.UniqueConstraint(fields=("company", "code"), name="workflow_company_code_unique")],
            },
        ),
        migrations.CreateModel(
            name="WorkflowVersion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("version", models.PositiveIntegerField()),
                ("status", models.CharField(choices=[("DRAFT", "Draft"), ("PUBLISHED", "Published"), ("RETIRED", "Retired")], default="DRAFT", max_length=20)),
                ("initial_state_code", models.CharField(max_length=100)),
                ("states", models.JSONField(default=list)),
                ("transitions", models.JSONField(default=list)),
                ("created_by_public_id", models.UUIDField()),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("checksum", models.CharField(blank=True, max_length=64)),
                ("definition", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="versions", to="workflow.workflowdefinition")),
            ],
            options={
                "db_table": "workflow_version",
                "indexes": [models.Index(fields=["definition", "status", "version"], name="workflow_published_lookup_idx")],
                "constraints": [
                    models.UniqueConstraint(fields=("definition", "version"), name="workflow_definition_version_unique"),
                    models.CheckConstraint(condition=models.Q(models.Q(("published_at__isnull", True), ("status", "DRAFT")), models.Q(("published_at__isnull", False), ("status__in", ["PUBLISHED", "RETIRED"])), _connector="OR"), name="workflow_publish_state_valid"),
                ],
            },
        ),
        migrations.CreateModel(
            name="WorkflowInstance",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("subject_type", models.CharField(max_length=100)),
                ("subject_public_id", models.UUIDField()),
                ("current_state_code", models.CharField(max_length=100)),
                ("lock_version", models.PositiveBigIntegerField(default=1)),
                ("status", models.CharField(choices=[("ACTIVE", "Active"), ("COMPLETED", "Completed"), ("CANCELLED", "Cancelled")], default="ACTIVE", max_length=20)),
                ("started_by_public_id", models.UUIDField()),
                ("started_at", models.DateTimeField()),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="workflow_instances", to="tenant.company")),
                ("definition", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="instances", to="workflow.workflowdefinition")),
                ("workflow_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="instances", to="workflow.workflowversion")),
            ],
            options={
                "db_table": "workflow_instance",
                "indexes": [models.Index(fields=["company", "status", "current_state_code"], name="workflow_instance_state_idx")],
                "constraints": [models.UniqueConstraint(fields=("company", "definition", "subject_type", "subject_public_id"), name="workflow_subject_instance_unique")],
            },
        ),
        migrations.CreateModel(
            name="WorkflowTransitionLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("sequence", models.PositiveBigIntegerField()),
                ("transition_code", models.CharField(max_length=100)),
                ("from_state_code", models.CharField(max_length=100)),
                ("to_state_code", models.CharField(max_length=100)),
                ("actor_public_id", models.UUIDField()),
                ("occurred_at", models.DateTimeField()),
                ("correlation_id", models.UUIDField()),
                ("comment", models.CharField(blank=True, max_length=1000)),
                ("workflow_instance", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="transition_history", to="workflow.workflowinstance")),
            ],
            options={
                "db_table": "workflow_transition_log",
                "constraints": [models.UniqueConstraint(fields=("workflow_instance", "sequence"), name="workflow_transition_sequence_unique")],
            },
        ),
        migrations.CreateModel(
            name="ApprovalTask",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("transition_code", models.CharField(max_length=100)),
                ("from_state_code", models.CharField(max_length=100)),
                ("to_state_code", models.CharField(max_length=100)),
                ("approval_permission_code", models.CharField(default="workflow.approve", max_length=150)),
                ("assigned_role_public_id", models.UUIDField(blank=True, null=True)),
                ("assigned_user_public_id", models.UUIDField(blank=True, null=True)),
                ("requested_by_public_id", models.UUIDField()),
                ("due_at", models.DateTimeField(blank=True, null=True)),
                ("status", models.CharField(choices=[("PENDING", "Pending"), ("APPROVED", "Approved"), ("REJECTED", "Rejected"), ("CANCELLED", "Cancelled")], default="PENDING", max_length=20)),
                ("decided_by_public_id", models.UUIDField(blank=True, null=True)),
                ("decided_at", models.DateTimeField(blank=True, null=True)),
                ("comment", models.CharField(blank=True, max_length=1000)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="approval_tasks", to="tenant.company")),
                ("workflow_instance", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="approval_tasks", to="workflow.workflowinstance")),
            ],
            options={
                "db_table": "workflow_approval_task",
                "indexes": [models.Index(fields=["company", "status", "due_at"], name="workflow_approval_inbox_idx")],
                "constraints": [models.UniqueConstraint(condition=models.Q(("status", "PENDING")), fields=("workflow_instance", "transition_code"), name="workflow_pending_transition_unique")],
            },
        ),
    ]
