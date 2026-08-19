# Generated for MPSqre Build360 Phase 33.

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
            name="ReleasePolicyVersion",
            fields=common() + [
                ("version", models.PositiveIntegerField(default=1)),
                ("status_code", models.CharField(default="DRAFT", max_length=30)),
                ("require_all_gates", models.BooleanField(default=True)),
                ("require_all_uat", models.BooleanField(default=True)),
                ("require_backup", models.BooleanField(default=True)),
                ("require_separate_approver", models.BooleanField(default=True)),
                ("configuration", models.JSONField(blank=True, default=dict)),
                ("effective_from", models.DateTimeField(blank=True, null=True)),
                ("effective_to", models.DateTimeField(blank=True, null=True)),
                ("published_by_public_id", models.UUIDField(blank=True, null=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="release_policies", to="tenant.company")),
            ],
            options={
                "db_table": "releaseops_policy_version",
                "constraints": [
                    models.UniqueConstraint(fields=("company", "version"), name="ro_policy_version_uq"),
                    models.CheckConstraint(
                        condition=models.Q(effective_to__isnull=True)
                        | models.Q(effective_from__isnull=True)
                        | models.Q(effective_to__gt=models.F("effective_from")),
                        name="ro_policy_dates_ck",
                    ),
                ],
                "indexes": [models.Index(fields=["company", "status_code"], name="ro_policy_status_idx")],
            },
        ),
        migrations.CreateModel(
            name="DeploymentTarget",
            fields=common() + [
                ("code", models.CharField(max_length=60)),
                ("name", models.CharField(max_length=160)),
                ("environment_code", models.CharField(default="PRODUCTION", max_length=30)),
                ("frontend_url", models.URLField(max_length=500)),
                ("backend_url", models.URLField(max_length=500)),
                ("health_url", models.URLField(blank=True, max_length=500)),
                ("region_code", models.CharField(blank=True, max_length=80)),
                ("hosting_provider_code", models.CharField(blank=True, max_length=80)),
                ("status_code", models.CharField(default="ACTIVE", max_length=30)),
                ("configuration", models.JSONField(blank=True, default=dict)),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="deployment_targets", to="tenant.company")),
            ],
            options={
                "db_table": "releaseops_deployment_target",
                "constraints": [models.UniqueConstraint(fields=("company", "code"), name="ro_target_code_uq")],
                "indexes": [models.Index(fields=["company", "environment_code", "status_code"], name="ro_target_env_idx")],
            },
        ),
        migrations.CreateModel(
            name="ReleaseCandidate",
            fields=common() + [
                ("release_code", models.CharField(max_length=80)),
                ("version_label", models.CharField(default="v1.0.0", max_length=80)),
                ("title", models.CharField(max_length=220)),
                ("summary", models.TextField(blank=True)),
                ("status_code", models.CharField(default="DRAFT", max_length=40)),
                ("source_reference", models.CharField(blank=True, max_length=250)),
                ("artifact_reference", models.CharField(blank=True, max_length=500)),
                ("artifact_sha256", models.CharField(blank=True, max_length=64)),
                ("planned_at", models.DateTimeField(blank=True, null=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("approved_by_public_id", models.UUIDField(blank=True, null=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("published_by_public_id", models.UUIDField(blank=True, null=True)),
                ("created_by_public_id", models.UUIDField()),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="release_candidates", to="tenant.company")),
                ("target", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="release_candidates", to="releaseops.deploymenttarget")),
            ],
            options={
                "db_table": "releaseops_release_candidate",
                "constraints": [
                    models.UniqueConstraint(fields=("company", "release_code"), name="ro_release_code_uq"),
                    models.CheckConstraint(condition=models.Q(artifact_sha256="") | models.Q(artifact_sha256__regex=r"^[0-9a-fA-F]{64}$"), name="ro_release_sha_ck"),
                ],
                "indexes": [models.Index(fields=["company", "status_code", "planned_at"], name="ro_release_status_idx")],
            },
        ),
        migrations.CreateModel(
            name="ReleaseGate",
            fields=common() + [
                ("code", models.CharField(max_length=80)),
                ("name", models.CharField(max_length=200)),
                ("category_code", models.CharField(default="GENERAL", max_length=50)),
                ("description", models.TextField(blank=True)),
                ("is_required", models.BooleanField(default=True)),
                ("status_code", models.CharField(default="PENDING", max_length=30)),
                ("evidence", models.JSONField(blank=True, default=dict)),
                ("notes", models.TextField(blank=True)),
                ("decided_at", models.DateTimeField(blank=True, null=True)),
                ("decided_by_public_id", models.UUIDField(blank=True, null=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="release_gates", to="tenant.company")),
                ("release", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="gates", to="releaseops.releasecandidate")),
            ],
            options={
                "db_table": "releaseops_release_gate",
                "constraints": [models.UniqueConstraint(fields=("release", "code"), name="ro_gate_release_code_uq")],
                "indexes": [models.Index(fields=["company", "release", "status_code"], name="ro_gate_status_idx")],
            },
        ),
        migrations.CreateModel(
            name="UATScenario",
            fields=common() + [
                ("code", models.CharField(max_length=80)),
                ("title", models.CharField(max_length=240)),
                ("module_code", models.CharField(max_length=80)),
                ("persona_code", models.CharField(blank=True, max_length=80)),
                ("preconditions", models.TextField(blank=True)),
                ("steps", models.JSONField(default=list)),
                ("expected_result", models.TextField()),
                ("is_required", models.BooleanField(default=True)),
                ("status_code", models.CharField(default="ACTIVE", max_length=30)),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="uat_scenarios", to="tenant.company")),
            ],
            options={
                "db_table": "releaseops_uat_scenario",
                "constraints": [models.UniqueConstraint(fields=("company", "code", "version"), name="ro_uat_scenario_uq")],
                "indexes": [models.Index(fields=["company", "module_code", "status_code"], name="ro_uat_module_idx")],
            },
        ),
        migrations.CreateModel(
            name="UATExecution",
            fields=common() + [
                ("status_code", models.CharField(default="NOT_RUN", max_length=30)),
                ("tester_public_id", models.UUIDField(blank=True, null=True)),
                ("executed_at", models.DateTimeField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("evidence", models.JSONField(blank=True, default=dict)),
                ("defect_reference", models.CharField(blank=True, max_length=250)),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="uat_executions", to="tenant.company")),
                ("release", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="uat_executions", to="releaseops.releasecandidate")),
                ("scenario", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="executions", to="releaseops.uatscenario")),
            ],
            options={
                "db_table": "releaseops_uat_execution",
                "constraints": [models.UniqueConstraint(fields=("release", "scenario"), name="ro_uat_execution_uq")],
                "indexes": [models.Index(fields=["company", "release", "status_code"], name="ro_uat_exec_status_idx")],
            },
        ),
        migrations.CreateModel(
            name="BackupSnapshot",
            fields=common() + [
                ("reference", models.CharField(max_length=160)),
                ("backup_type_code", models.CharField(default="FULL", max_length=40)),
                ("status_code", models.CharField(default="AVAILABLE", max_length=30)),
                ("storage_reference", models.CharField(max_length=500)),
                ("checksum_sha256", models.CharField(blank=True, max_length=64)),
                ("database_included", models.BooleanField(default=True)),
                ("media_included", models.BooleanField(default=True)),
                ("configuration_included", models.BooleanField(default=True)),
                ("restore_tested", models.BooleanField(default=False)),
                ("restore_tested_at", models.DateTimeField(blank=True, null=True)),
                ("captured_at", models.DateTimeField()),
                ("retention_until", models.DateTimeField(blank=True, null=True)),
                ("captured_by_public_id", models.UUIDField()),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="release_backups", to="tenant.company")),
                ("release", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="backups", to="releaseops.releasecandidate")),
                ("target", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="backups", to="releaseops.deploymenttarget")),
            ],
            options={
                "db_table": "releaseops_backup_snapshot",
                "constraints": [
                    models.UniqueConstraint(fields=("company", "reference"), name="ro_backup_reference_uq"),
                    models.CheckConstraint(condition=models.Q(checksum_sha256="") | models.Q(checksum_sha256__regex=r"^[0-9a-fA-F]{64}$"), name="ro_backup_sha_ck"),
                ],
                "indexes": [models.Index(fields=["company", "status_code", "captured_at"], name="ro_backup_status_idx")],
            },
        ),
        migrations.CreateModel(
            name="ReadinessRun",
            fields=common() + [
                ("run_type_code", models.CharField(default="FULL", max_length=40)),
                ("status_code", models.CharField(default="RUNNING", max_length=30)),
                ("checks_total", models.PositiveIntegerField(default=0)),
                ("checks_passed", models.PositiveIntegerField(default=0)),
                ("checks_failed", models.PositiveIntegerField(default=0)),
                ("results", models.JSONField(default=list)),
                ("started_at", models.DateTimeField()),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("executed_by_public_id", models.UUIDField()),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="release_readiness_runs", to="tenant.company")),
                ("release", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="readiness_runs", to="releaseops.releasecandidate")),
            ],
            options={
                "db_table": "releaseops_readiness_run",
                "constraints": [
                    models.CheckConstraint(condition=models.Q(checks_passed__lte=models.F("checks_total")), name="ro_run_passed_total_ck"),
                    models.CheckConstraint(condition=models.Q(checks_failed__lte=models.F("checks_total")), name="ro_run_failed_total_ck"),
                ],
                "indexes": [models.Index(fields=["company", "status_code", "started_at"], name="ro_run_status_idx")],
            },
        ),
    ]
