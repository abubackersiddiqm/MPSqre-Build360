# Generated for MPSqre Build360 Phase 35.

import decimal
import uuid

import django.db.models.deletion
from django.db import migrations, models


def common():
    return [
        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
        ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
        ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
        ("updated_at", models.DateTimeField(auto_now=True)),
    ]


class Migration(migrations.Migration):
    initial = True

    dependencies = [("tenant", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="GoLivePolicyVersion",
            fields=common() + [
                ("version", models.PositiveIntegerField(default=1)),
                ("status_code", models.CharField(default="DRAFT", max_length=30)),
                ("migration_error_tolerance_percent", models.DecimalField(decimal_places=2, default=decimal.Decimal("0.00"), max_digits=5)),
                ("minimum_training_completion_percent", models.DecimalField(decimal_places=2, default=decimal.Decimal("100.00"), max_digits=5)),
                ("cutover_freeze_hours", models.PositiveIntegerField(default=24)),
                ("hypercare_days", models.PositiveIntegerField(default=14)),
                ("configuration", models.JSONField(blank=True, default=dict)),
                ("effective_from", models.DateTimeField(blank=True, null=True)),
                ("effective_to", models.DateTimeField(blank=True, null=True)),
                ("published_by_public_id", models.UUIDField(blank=True, null=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="go_live_policies", to="tenant.company")),
            ],
            options={
                "db_table": "goliveops_policy_version",
                "constraints": [
                    models.UniqueConstraint(fields=("company", "version"), name="go_policy_version_uq"),
                    models.CheckConstraint(condition=models.Q(effective_to__isnull=True) | models.Q(effective_from__isnull=True) | models.Q(effective_to__gt=models.F("effective_from")), name="go_policy_dates_ck"),
                    models.CheckConstraint(condition=models.Q(migration_error_tolerance_percent__gte=0) & models.Q(migration_error_tolerance_percent__lte=100), name="go_policy_error_tol_ck"),
                    models.CheckConstraint(condition=models.Q(minimum_training_completion_percent__gte=0) & models.Q(minimum_training_completion_percent__lte=100), name="go_policy_training_ck"),
                ],
                "indexes": [models.Index(fields=["company", "status_code"], name="go_policy_status_idx")],
            },
        ),
        migrations.CreateModel(
            name="MigrationBatch",
            fields=common() + [
                ("code", models.CharField(max_length=80)),
                ("entity_code", models.CharField(max_length=80)),
                ("source_file_name", models.CharField(max_length=240)),
                ("source_checksum", models.CharField(blank=True, max_length=64)),
                ("status_code", models.CharField(default="DRAFT", max_length=30)),
                ("dry_run", models.BooleanField(default=True)),
                ("total_rows", models.PositiveIntegerField(default=0)),
                ("valid_rows", models.PositiveIntegerField(default=0)),
                ("invalid_rows", models.PositiveIntegerField(default=0)),
                ("warning_rows", models.PositiveIntegerField(default=0)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_by_public_id", models.UUIDField()),
                ("approved_by_public_id", models.UUIDField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="go_live_migration_batches", to="tenant.company")),
            ],
            options={
                "db_table": "goliveops_migration_batch",
                "constraints": [
                    models.UniqueConstraint(fields=("company", "code"), name="go_migration_code_uq"),
                    models.CheckConstraint(condition=models.Q(valid_rows__lte=models.F("total_rows")), name="go_migration_valid_ck"),
                    models.CheckConstraint(condition=models.Q(invalid_rows__lte=models.F("total_rows")), name="go_migration_invalid_ck"),
                    models.CheckConstraint(condition=models.Q(warning_rows__lte=models.F("total_rows")), name="go_migration_warning_ck"),
                ],
                "indexes": [
                    models.Index(fields=["company", "status_code", "entity_code"], name="go_migration_status_idx"),
                    models.Index(fields=["company", "created_at"], name="go_migration_created_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="TrainingCohort",
            fields=common() + [
                ("code", models.CharField(max_length=80)),
                ("title", models.CharField(max_length=220)),
                ("audience_code", models.CharField(default="ALL_USERS", max_length=80)),
                ("delivery_mode_code", models.CharField(default="ONLINE", max_length=30)),
                ("required", models.BooleanField(default=True)),
                ("starts_at", models.DateTimeField()),
                ("ends_at", models.DateTimeField()),
                ("minimum_score_percent", models.DecimalField(decimal_places=2, default=decimal.Decimal("80.00"), max_digits=5)),
                ("status_code", models.CharField(default="PLANNED", max_length=30)),
                ("facilitator_name", models.CharField(blank=True, max_length=160)),
                ("created_by_public_id", models.UUIDField()),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="go_live_training_cohorts", to="tenant.company")),
            ],
            options={
                "db_table": "goliveops_training_cohort",
                "constraints": [
                    models.UniqueConstraint(fields=("company", "code"), name="go_training_code_uq"),
                    models.CheckConstraint(condition=models.Q(ends_at__gt=models.F("starts_at")), name="go_training_dates_ck"),
                    models.CheckConstraint(condition=models.Q(minimum_score_percent__gte=0) & models.Q(minimum_score_percent__lte=100), name="go_training_score_ck"),
                ],
                "indexes": [models.Index(fields=["company", "status_code", "starts_at"], name="go_training_status_idx")],
            },
        ),
        migrations.CreateModel(
            name="CutoverPlan",
            fields=common() + [
                ("code", models.CharField(max_length=80)),
                ("name", models.CharField(max_length=220)),
                ("environment_code", models.CharField(default="PRODUCTION", max_length=40)),
                ("status_code", models.CharField(default="DRAFT", max_length=30)),
                ("planned_start_at", models.DateTimeField()),
                ("planned_go_live_at", models.DateTimeField()),
                ("actual_go_live_at", models.DateTimeField(blank=True, null=True)),
                ("rollback_deadline_at", models.DateTimeField(blank=True, null=True)),
                ("owner_public_id", models.UUIDField(blank=True, null=True)),
                ("created_by_public_id", models.UUIDField()),
                ("approved_by_public_id", models.UUIDField(blank=True, null=True)),
                ("approval_notes", models.TextField(blank=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="go_live_cutover_plans", to="tenant.company")),
            ],
            options={
                "db_table": "goliveops_cutover_plan",
                "constraints": [
                    models.UniqueConstraint(fields=("company", "code"), name="go_cutover_code_uq"),
                    models.CheckConstraint(condition=models.Q(planned_go_live_at__gt=models.F("planned_start_at")), name="go_cutover_dates_ck"),
                ],
                "indexes": [models.Index(fields=["company", "status_code", "planned_go_live_at"], name="go_cutover_status_idx")],
            },
        ),
        migrations.CreateModel(
            name="GoLiveGate",
            fields=common() + [
                ("code", models.CharField(max_length=80)),
                ("name", models.CharField(max_length=220)),
                ("category_code", models.CharField(default="GENERAL", max_length=60)),
                ("description", models.TextField(blank=True)),
                ("is_required", models.BooleanField(default=True)),
                ("status_code", models.CharField(default="PENDING", max_length=30)),
                ("evidence", models.JSONField(blank=True, default=dict)),
                ("notes", models.TextField(blank=True)),
                ("decided_at", models.DateTimeField(blank=True, null=True)),
                ("decided_by_public_id", models.UUIDField(blank=True, null=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="go_live_gates", to="tenant.company")),
            ],
            options={
                "db_table": "goliveops_gate",
                "constraints": [models.UniqueConstraint(fields=("company", "code"), name="go_gate_code_uq")],
                "indexes": [models.Index(fields=["company", "status_code", "is_required"], name="go_gate_status_idx")],
            },
        ),
        migrations.CreateModel(
            name="GoLiveWave",
            fields=common() + [
                ("code", models.CharField(max_length=80)),
                ("name", models.CharField(max_length=220)),
                ("scope", models.JSONField(blank=True, default=dict)),
                ("status_code", models.CharField(default="DRAFT", max_length=30)),
                ("planned_at", models.DateTimeField()),
                ("activated_at", models.DateTimeField(blank=True, null=True)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("created_by_public_id", models.UUIDField()),
                ("approved_by_public_id", models.UUIDField(blank=True, null=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="go_live_waves", to="tenant.company")),
                ("plan", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="waves", to="goliveops.cutoverplan")),
            ],
            options={
                "db_table": "goliveops_wave",
                "constraints": [models.UniqueConstraint(fields=("company", "code"), name="go_wave_code_uq")],
                "indexes": [models.Index(fields=["company", "status_code", "planned_at"], name="go_wave_status_idx")],
            },
        ),
        migrations.CreateModel(
            name="CutoverTask",
            fields=common() + [
                ("code", models.CharField(max_length=80)),
                ("title", models.CharField(max_length=240)),
                ("category_code", models.CharField(default="GENERAL", max_length=80)),
                ("owner_public_id", models.UUIDField(blank=True, null=True)),
                ("sequence", models.PositiveIntegerField(default=10)),
                ("critical", models.BooleanField(default=True)),
                ("status_code", models.CharField(default="PENDING", max_length=30)),
                ("due_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("evidence", models.JSONField(blank=True, default=dict)),
                ("notes", models.TextField(blank=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="go_live_cutover_tasks", to="tenant.company")),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="tasks", to="goliveops.cutoverplan")),
            ],
            options={
                "db_table": "goliveops_cutover_task",
                "constraints": [models.UniqueConstraint(fields=("plan", "code"), name="go_cutover_task_uq")],
                "indexes": [
                    models.Index(fields=["company", "status_code", "critical"], name="go_task_status_idx"),
                    models.Index(fields=["plan", "sequence"], name="go_task_sequence_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="HypercareIssue",
            fields=common() + [
                ("code", models.CharField(max_length=80)),
                ("title", models.CharField(max_length=240)),
                ("severity_code", models.CharField(default="P2", max_length=10)),
                ("status_code", models.CharField(default="OPEN", max_length=30)),
                ("area_code", models.CharField(default="GENERAL", max_length=80)),
                ("impact_summary", models.TextField(blank=True)),
                ("resolution_summary", models.TextField(blank=True)),
                ("owner_public_id", models.UUIDField(blank=True, null=True)),
                ("reported_by_public_id", models.UUIDField()),
                ("reported_at", models.DateTimeField()),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="go_live_hypercare_issues", to="tenant.company")),
                ("wave", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="hypercare_issues", to="goliveops.golivewave")),
            ],
            options={
                "db_table": "goliveops_hypercare_issue",
                "constraints": [models.UniqueConstraint(fields=("company", "code"), name="go_hypercare_code_uq")],
                "indexes": [
                    models.Index(fields=["company", "status_code", "severity_code"], name="go_hypercare_status_idx"),
                    models.Index(fields=["company", "reported_at"], name="go_hypercare_time_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="MigrationIssue",
            fields=common() + [
                ("row_number", models.PositiveIntegerField(default=1)),
                ("field_name", models.CharField(blank=True, max_length=120)),
                ("severity_code", models.CharField(default="ERROR", max_length=20)),
                ("issue_code", models.CharField(max_length=80)),
                ("message", models.TextField()),
                ("raw_value", models.TextField(blank=True)),
                ("resolved", models.BooleanField(default=False)),
                ("resolution_notes", models.TextField(blank=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("resolved_by_public_id", models.UUIDField(blank=True, null=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("batch", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="issues", to="goliveops.migrationbatch")),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="go_live_migration_issues", to="tenant.company")),
            ],
            options={
                "db_table": "goliveops_migration_issue",
                "constraints": [models.UniqueConstraint(fields=("batch", "row_number", "field_name", "issue_code"), name="go_migration_issue_uq")],
                "indexes": [
                    models.Index(fields=["company", "resolved", "severity_code"], name="go_issue_status_idx"),
                    models.Index(fields=["batch", "row_number"], name="go_issue_batch_row_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="TrainingEnrollment",
            fields=common() + [
                ("participant_public_id", models.UUIDField()),
                ("participant_name", models.CharField(max_length=180)),
                ("participant_email", models.EmailField(blank=True, max_length=254)),
                ("status_code", models.CharField(default="NOT_STARTED", max_length=30)),
                ("score_percent", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("evidence", models.JSONField(blank=True, default=dict)),
                ("version", models.PositiveIntegerField(default=1)),
                ("cohort", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="enrollments", to="goliveops.trainingcohort")),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="go_live_training_enrollments", to="tenant.company")),
            ],
            options={
                "db_table": "goliveops_training_enrollment",
                "constraints": [
                    models.UniqueConstraint(fields=("cohort", "participant_public_id"), name="go_enrollment_participant_uq"),
                    models.CheckConstraint(condition=models.Q(score_percent__isnull=True) | (models.Q(score_percent__gte=0) & models.Q(score_percent__lte=100)), name="go_enrollment_score_ck"),
                ],
                "indexes": [models.Index(fields=["company", "status_code"], name="go_enrollment_status_idx")],
            },
        ),
    ]
