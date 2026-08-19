from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from modules.platform.models import PublicIdModel, TimestampedModel
from modules.tenant.models import Company


class ReleasePolicyVersion(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="release_policies")
    version = models.PositiveIntegerField(default=1)
    status_code = models.CharField(max_length=30, default="DRAFT")
    require_all_gates = models.BooleanField(default=True)
    require_all_uat = models.BooleanField(default=True)
    require_backup = models.BooleanField(default=True)
    require_separate_approver = models.BooleanField(default=True)
    configuration = models.JSONField(default=dict, blank=True)
    effective_from = models.DateTimeField(null=True, blank=True)
    effective_to = models.DateTimeField(null=True, blank=True)
    published_by_public_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "releaseops_policy_version"
        constraints = [
            models.UniqueConstraint(fields=["company", "version"], name="ro_policy_version_uq"),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_from__isnull=True)
                | models.Q(effective_to__gt=models.F("effective_from")),
                name="ro_policy_dates_ck",
            ),
        ]
        indexes = [models.Index(fields=["company", "status_code"], name="ro_policy_status_idx")]


class DeploymentTarget(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="deployment_targets")
    code = models.CharField(max_length=60)
    name = models.CharField(max_length=160)
    environment_code = models.CharField(max_length=30, default="PRODUCTION")
    frontend_url = models.URLField(max_length=500)
    backend_url = models.URLField(max_length=500)
    health_url = models.URLField(max_length=500, blank=True)
    region_code = models.CharField(max_length=80, blank=True)
    hosting_provider_code = models.CharField(max_length=80, blank=True)
    status_code = models.CharField(max_length=30, default="ACTIVE")
    configuration = models.JSONField(default=dict, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "releaseops_deployment_target"
        constraints = [models.UniqueConstraint(fields=["company", "code"], name="ro_target_code_uq")]
        indexes = [models.Index(fields=["company", "environment_code", "status_code"], name="ro_target_env_idx")]


class ReleaseCandidate(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="release_candidates")
    target = models.ForeignKey(
        DeploymentTarget,
        on_delete=models.PROTECT,
        related_name="release_candidates",
        null=True,
        blank=True,
    )
    release_code = models.CharField(max_length=80)
    version_label = models.CharField(max_length=80, default="v1.0.0")
    title = models.CharField(max_length=220)
    summary = models.TextField(blank=True)
    status_code = models.CharField(max_length=40, default="DRAFT")
    source_reference = models.CharField(max_length=250, blank=True)
    artifact_reference = models.CharField(max_length=500, blank=True)
    artifact_sha256 = models.CharField(max_length=64, blank=True)
    planned_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    published_by_public_id = models.UUIDField(null=True, blank=True)
    created_by_public_id = models.UUIDField()
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "releaseops_release_candidate"
        constraints = [
            models.UniqueConstraint(fields=["company", "release_code"], name="ro_release_code_uq"),
            models.CheckConstraint(
                condition=models.Q(artifact_sha256="") | models.Q(artifact_sha256__regex=r"^[0-9a-fA-F]{64}$"),
                name="ro_release_sha_ck",
            ),
        ]
        indexes = [models.Index(fields=["company", "status_code", "planned_at"], name="ro_release_status_idx")]

    def clean(self) -> None:
        super().clean()
        if self.target_id and self.target.company_id != self.company_id:
            raise ValidationError("Deployment target cannot cross companies")


class ReleaseGate(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="release_gates")
    release = models.ForeignKey(ReleaseCandidate, on_delete=models.PROTECT, related_name="gates")
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=200)
    category_code = models.CharField(max_length=50, default="GENERAL")
    description = models.TextField(blank=True)
    is_required = models.BooleanField(default=True)
    status_code = models.CharField(max_length=30, default="PENDING")
    evidence = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by_public_id = models.UUIDField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "releaseops_release_gate"
        constraints = [models.UniqueConstraint(fields=["release", "code"], name="ro_gate_release_code_uq")]
        indexes = [models.Index(fields=["company", "release", "status_code"], name="ro_gate_status_idx")]

    def clean(self) -> None:
        super().clean()
        if self.release_id and self.release.company_id != self.company_id:
            raise ValidationError("Release gate cannot cross companies")


class UATScenario(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="uat_scenarios")
    code = models.CharField(max_length=80)
    title = models.CharField(max_length=240)
    module_code = models.CharField(max_length=80)
    persona_code = models.CharField(max_length=80, blank=True)
    preconditions = models.TextField(blank=True)
    steps = models.JSONField(default=list)
    expected_result = models.TextField()
    is_required = models.BooleanField(default=True)
    status_code = models.CharField(max_length=30, default="ACTIVE")
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "releaseops_uat_scenario"
        constraints = [models.UniqueConstraint(fields=["company", "code", "version"], name="ro_uat_scenario_uq")]
        indexes = [models.Index(fields=["company", "module_code", "status_code"], name="ro_uat_module_idx")]


class UATExecution(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="uat_executions")
    release = models.ForeignKey(ReleaseCandidate, on_delete=models.PROTECT, related_name="uat_executions")
    scenario = models.ForeignKey(UATScenario, on_delete=models.PROTECT, related_name="executions")
    status_code = models.CharField(max_length=30, default="NOT_RUN")
    tester_public_id = models.UUIDField(null=True, blank=True)
    executed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    evidence = models.JSONField(default=dict, blank=True)
    defect_reference = models.CharField(max_length=250, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "releaseops_uat_execution"
        constraints = [models.UniqueConstraint(fields=["release", "scenario"], name="ro_uat_execution_uq")]
        indexes = [models.Index(fields=["company", "release", "status_code"], name="ro_uat_exec_status_idx")]

    def clean(self) -> None:
        super().clean()
        if self.release_id and self.release.company_id != self.company_id:
            raise ValidationError("UAT execution release cannot cross companies")
        if self.scenario_id and self.scenario.company_id != self.company_id:
            raise ValidationError("UAT execution scenario cannot cross companies")


class BackupSnapshot(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="release_backups")
    release = models.ForeignKey(
        ReleaseCandidate,
        on_delete=models.PROTECT,
        related_name="backups",
        null=True,
        blank=True,
    )
    target = models.ForeignKey(
        DeploymentTarget,
        on_delete=models.PROTECT,
        related_name="backups",
        null=True,
        blank=True,
    )
    reference = models.CharField(max_length=160)
    backup_type_code = models.CharField(max_length=40, default="FULL")
    status_code = models.CharField(max_length=30, default="AVAILABLE")
    storage_reference = models.CharField(max_length=500)
    checksum_sha256 = models.CharField(max_length=64, blank=True)
    database_included = models.BooleanField(default=True)
    media_included = models.BooleanField(default=True)
    configuration_included = models.BooleanField(default=True)
    restore_tested = models.BooleanField(default=False)
    restore_tested_at = models.DateTimeField(null=True, blank=True)
    captured_at = models.DateTimeField()
    retention_until = models.DateTimeField(null=True, blank=True)
    captured_by_public_id = models.UUIDField()
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "releaseops_backup_snapshot"
        constraints = [
            models.UniqueConstraint(fields=["company", "reference"], name="ro_backup_reference_uq"),
            models.CheckConstraint(
                condition=models.Q(checksum_sha256="") | models.Q(checksum_sha256__regex=r"^[0-9a-fA-F]{64}$"),
                name="ro_backup_sha_ck",
            ),
        ]
        indexes = [models.Index(fields=["company", "status_code", "captured_at"], name="ro_backup_status_idx")]

    def clean(self) -> None:
        super().clean()
        if self.release_id and self.release.company_id != self.company_id:
            raise ValidationError("Backup release cannot cross companies")
        if self.target_id and self.target.company_id != self.company_id:
            raise ValidationError("Backup target cannot cross companies")


class ReadinessRun(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="release_readiness_runs")
    release = models.ForeignKey(
        ReleaseCandidate,
        on_delete=models.PROTECT,
        related_name="readiness_runs",
        null=True,
        blank=True,
    )
    run_type_code = models.CharField(max_length=40, default="FULL")
    status_code = models.CharField(max_length=30, default="RUNNING")
    checks_total = models.PositiveIntegerField(default=0)
    checks_passed = models.PositiveIntegerField(default=0)
    checks_failed = models.PositiveIntegerField(default=0)
    results = models.JSONField(default=list)
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    executed_by_public_id = models.UUIDField()
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "releaseops_readiness_run"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(checks_passed__lte=models.F("checks_total")),
                name="ro_run_passed_total_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(checks_failed__lte=models.F("checks_total")),
                name="ro_run_failed_total_ck",
            ),
        ]
        indexes = [models.Index(fields=["company", "status_code", "started_at"], name="ro_run_status_idx")]

    def clean(self) -> None:
        super().clean()
        if self.release_id and self.release.company_id != self.company_id:
            raise ValidationError("Readiness run cannot cross companies")
