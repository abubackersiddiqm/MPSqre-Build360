from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from modules.platform.models import PublicIdModel, TimestampedModel
from modules.tenant.models import Company


class GoLivePolicyVersion(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="go_live_policies")
    version = models.PositiveIntegerField(default=1)
    status_code = models.CharField(max_length=30, default="DRAFT")
    migration_error_tolerance_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    minimum_training_completion_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("100.00"))
    cutover_freeze_hours = models.PositiveIntegerField(default=24)
    hypercare_days = models.PositiveIntegerField(default=14)
    configuration = models.JSONField(default=dict, blank=True)
    effective_from = models.DateTimeField(null=True, blank=True)
    effective_to = models.DateTimeField(null=True, blank=True)
    published_by_public_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "goliveops_policy_version"
        constraints = [
            models.UniqueConstraint(fields=["company", "version"], name="go_policy_version_uq"),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_from__isnull=True)
                | models.Q(effective_to__gt=models.F("effective_from")),
                name="go_policy_dates_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(migration_error_tolerance_percent__gte=0)
                & models.Q(migration_error_tolerance_percent__lte=100),
                name="go_policy_error_tol_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(minimum_training_completion_percent__gte=0)
                & models.Q(minimum_training_completion_percent__lte=100),
                name="go_policy_training_ck",
            ),
        ]
        indexes = [models.Index(fields=["company", "status_code"], name="go_policy_status_idx")]


class MigrationBatch(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="go_live_migration_batches")
    code = models.CharField(max_length=80)
    entity_code = models.CharField(max_length=80)
    source_file_name = models.CharField(max_length=240)
    source_checksum = models.CharField(max_length=64, blank=True)
    status_code = models.CharField(max_length=30, default="DRAFT")
    dry_run = models.BooleanField(default=True)
    total_rows = models.PositiveIntegerField(default=0)
    valid_rows = models.PositiveIntegerField(default=0)
    invalid_rows = models.PositiveIntegerField(default=0)
    warning_rows = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by_public_id = models.UUIDField()
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    notes = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "goliveops_migration_batch"
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="go_migration_code_uq"),
            models.CheckConstraint(condition=models.Q(valid_rows__lte=models.F("total_rows")), name="go_migration_valid_ck"),
            models.CheckConstraint(condition=models.Q(invalid_rows__lte=models.F("total_rows")), name="go_migration_invalid_ck"),
            models.CheckConstraint(condition=models.Q(warning_rows__lte=models.F("total_rows")), name="go_migration_warning_ck"),
        ]
        indexes = [
            models.Index(fields=["company", "status_code", "entity_code"], name="go_migration_status_idx"),
            models.Index(fields=["company", "created_at"], name="go_migration_created_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.code = self.code.strip().upper().replace(" ", "_")
        self.entity_code = self.entity_code.strip().upper().replace(" ", "_")
        if self.source_checksum and len(self.source_checksum) != 64:
            raise ValidationError({"source_checksum": "SHA-256 checksum must contain 64 hexadecimal characters."})
        if self.source_checksum and any(character not in "0123456789abcdefABCDEF" for character in self.source_checksum):
            raise ValidationError({"source_checksum": "SHA-256 checksum must be hexadecimal."})


class MigrationIssue(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="go_live_migration_issues")
    batch = models.ForeignKey(MigrationBatch, on_delete=models.PROTECT, related_name="issues")
    row_number = models.PositiveIntegerField(default=1)
    field_name = models.CharField(max_length=120, blank=True)
    severity_code = models.CharField(max_length=20, default="ERROR")
    issue_code = models.CharField(max_length=80)
    message = models.TextField()
    raw_value = models.TextField(blank=True)
    resolved = models.BooleanField(default=False)
    resolution_notes = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by_public_id = models.UUIDField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "goliveops_migration_issue"
        constraints = [
            models.UniqueConstraint(
                fields=["batch", "row_number", "field_name", "issue_code"],
                name="go_migration_issue_uq",
            )
        ]
        indexes = [
            models.Index(fields=["company", "resolved", "severity_code"], name="go_issue_status_idx"),
            models.Index(fields=["batch", "row_number"], name="go_issue_batch_row_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        if self.batch_id and self.batch.company_id != self.company_id:
            raise ValidationError("Migration issue cannot cross companies")
        if self.severity_code not in {"WARNING", "ERROR", "BLOCKER"}:
            raise ValidationError({"severity_code": "Severity must be WARNING, ERROR or BLOCKER."})
        self.issue_code = self.issue_code.strip().upper().replace(" ", "_")


class TrainingCohort(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="go_live_training_cohorts")
    code = models.CharField(max_length=80)
    title = models.CharField(max_length=220)
    audience_code = models.CharField(max_length=80, default="ALL_USERS")
    delivery_mode_code = models.CharField(max_length=30, default="ONLINE")
    required = models.BooleanField(default=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    minimum_score_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("80.00"))
    status_code = models.CharField(max_length=30, default="PLANNED")
    facilitator_name = models.CharField(max_length=160, blank=True)
    created_by_public_id = models.UUIDField()
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "goliveops_training_cohort"
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="go_training_code_uq"),
            models.CheckConstraint(condition=models.Q(ends_at__gt=models.F("starts_at")), name="go_training_dates_ck"),
            models.CheckConstraint(
                condition=models.Q(minimum_score_percent__gte=0) & models.Q(minimum_score_percent__lte=100),
                name="go_training_score_ck",
            ),
        ]
        indexes = [models.Index(fields=["company", "status_code", "starts_at"], name="go_training_status_idx")]

    def clean(self) -> None:
        super().clean()
        self.code = self.code.strip().upper().replace(" ", "_")
        self.audience_code = self.audience_code.strip().upper().replace(" ", "_")
        self.delivery_mode_code = self.delivery_mode_code.strip().upper()


class TrainingEnrollment(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="go_live_training_enrollments")
    cohort = models.ForeignKey(TrainingCohort, on_delete=models.PROTECT, related_name="enrollments")
    participant_public_id = models.UUIDField()
    participant_name = models.CharField(max_length=180)
    participant_email = models.EmailField(blank=True)
    status_code = models.CharField(max_length=30, default="NOT_STARTED")
    score_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    evidence = models.JSONField(default=dict, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "goliveops_training_enrollment"
        constraints = [
            models.UniqueConstraint(fields=["cohort", "participant_public_id"], name="go_enrollment_participant_uq"),
            models.CheckConstraint(
                condition=models.Q(score_percent__isnull=True)
                | (models.Q(score_percent__gte=0) & models.Q(score_percent__lte=100)),
                name="go_enrollment_score_ck",
            ),
        ]
        indexes = [models.Index(fields=["company", "status_code"], name="go_enrollment_status_idx")]

    def clean(self) -> None:
        super().clean()
        if self.cohort_id and self.cohort.company_id != self.company_id:
            raise ValidationError("Training enrollment cannot cross companies")


class CutoverPlan(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="go_live_cutover_plans")
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=220)
    environment_code = models.CharField(max_length=40, default="PRODUCTION")
    status_code = models.CharField(max_length=30, default="DRAFT")
    planned_start_at = models.DateTimeField()
    planned_go_live_at = models.DateTimeField()
    actual_go_live_at = models.DateTimeField(null=True, blank=True)
    rollback_deadline_at = models.DateTimeField(null=True, blank=True)
    owner_public_id = models.UUIDField(null=True, blank=True)
    created_by_public_id = models.UUIDField()
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    approval_notes = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "goliveops_cutover_plan"
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="go_cutover_code_uq"),
            models.CheckConstraint(condition=models.Q(planned_go_live_at__gt=models.F("planned_start_at")), name="go_cutover_dates_ck"),
        ]
        indexes = [models.Index(fields=["company", "status_code", "planned_go_live_at"], name="go_cutover_status_idx")]

    def clean(self) -> None:
        super().clean()
        self.code = self.code.strip().upper().replace(" ", "_")
        self.environment_code = self.environment_code.strip().upper()


class CutoverTask(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="go_live_cutover_tasks")
    plan = models.ForeignKey(CutoverPlan, on_delete=models.PROTECT, related_name="tasks")
    code = models.CharField(max_length=80)
    title = models.CharField(max_length=240)
    category_code = models.CharField(max_length=80, default="GENERAL")
    owner_public_id = models.UUIDField(null=True, blank=True)
    sequence = models.PositiveIntegerField(default=10)
    critical = models.BooleanField(default=True)
    status_code = models.CharField(max_length=30, default="PENDING")
    due_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    evidence = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "goliveops_cutover_task"
        constraints = [models.UniqueConstraint(fields=["plan", "code"], name="go_cutover_task_uq")]
        indexes = [
            models.Index(fields=["company", "status_code", "critical"], name="go_task_status_idx"),
            models.Index(fields=["plan", "sequence"], name="go_task_sequence_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        if self.plan_id and self.plan.company_id != self.company_id:
            raise ValidationError("Cutover task cannot cross companies")
        self.code = self.code.strip().upper().replace(" ", "_")
        self.category_code = self.category_code.strip().upper().replace(" ", "_")


class GoLiveWave(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="go_live_waves")
    plan = models.ForeignKey(CutoverPlan, on_delete=models.PROTECT, related_name="waves", null=True, blank=True)
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=220)
    scope = models.JSONField(default=dict, blank=True)
    status_code = models.CharField(max_length=30, default="DRAFT")
    planned_at = models.DateTimeField()
    activated_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_by_public_id = models.UUIDField()
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "goliveops_wave"
        constraints = [models.UniqueConstraint(fields=["company", "code"], name="go_wave_code_uq")]
        indexes = [models.Index(fields=["company", "status_code", "planned_at"], name="go_wave_status_idx")]

    def clean(self) -> None:
        super().clean()
        if self.plan_id and self.plan.company_id != self.company_id:
            raise ValidationError("Go-live wave cannot cross companies")
        self.code = self.code.strip().upper().replace(" ", "_")


class HypercareIssue(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="go_live_hypercare_issues")
    wave = models.ForeignKey(GoLiveWave, on_delete=models.PROTECT, related_name="hypercare_issues", null=True, blank=True)
    code = models.CharField(max_length=80)
    title = models.CharField(max_length=240)
    severity_code = models.CharField(max_length=10, default="P2")
    status_code = models.CharField(max_length=30, default="OPEN")
    area_code = models.CharField(max_length=80, default="GENERAL")
    impact_summary = models.TextField(blank=True)
    resolution_summary = models.TextField(blank=True)
    owner_public_id = models.UUIDField(null=True, blank=True)
    reported_by_public_id = models.UUIDField()
    reported_at = models.DateTimeField()
    resolved_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "goliveops_hypercare_issue"
        constraints = [models.UniqueConstraint(fields=["company", "code"], name="go_hypercare_code_uq")]
        indexes = [
            models.Index(fields=["company", "status_code", "severity_code"], name="go_hypercare_status_idx"),
            models.Index(fields=["company", "reported_at"], name="go_hypercare_time_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        if self.wave_id and self.wave.company_id != self.company_id:
            raise ValidationError("Hypercare issue cannot cross companies")
        if self.severity_code not in {"P0", "P1", "P2", "P3"}:
            raise ValidationError({"severity_code": "Severity must be P0, P1, P2 or P3."})
        self.code = self.code.strip().upper().replace(" ", "_")
        self.area_code = self.area_code.strip().upper().replace(" ", "_")


class GoLiveGate(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="go_live_gates")
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=220)
    category_code = models.CharField(max_length=60, default="GENERAL")
    description = models.TextField(blank=True)
    is_required = models.BooleanField(default=True)
    status_code = models.CharField(max_length=30, default="PENDING")
    evidence = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by_public_id = models.UUIDField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "goliveops_gate"
        constraints = [models.UniqueConstraint(fields=["company", "code"], name="go_gate_code_uq")]
        indexes = [models.Index(fields=["company", "status_code", "is_required"], name="go_gate_status_idx")]

    def clean(self) -> None:
        super().clean()
        self.code = self.code.strip().upper().replace(" ", "_")
        self.category_code = self.category_code.strip().upper().replace(" ", "_")
