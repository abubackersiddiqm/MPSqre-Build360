from __future__ import annotations

from collections.abc import Iterable
from typing import NoReturn

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.base import ModelBase

from modules.platform.models import TenantOwnedModel
from modules.tenant.models import Membership


class PilotProgram(TenantOwnedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PREPARING = "preparing", "Preparing"
        READY = "ready", "Ready"
        LIVE = "live", "Live"
        PAUSED = "paused", "Paused"
        COMPLETED = "completed", "Completed"

    cohort_code = models.CharField(max_length=80)
    name = models.CharField(max_length=220)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT)
    owner_membership = models.ForeignKey(
        Membership,
        on_delete=models.PROTECT,
        related_name="owned_pilot_programs",
    )
    target_start_date = models.DateField(null=True, blank=True)
    target_go_live_at = models.DateTimeField(null=True, blank=True)
    actual_go_live_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "pilotops_program"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "cohort_code"],
                name="pilot_program_code_uq",
            )
        ]
        indexes = [
            models.Index(fields=["company", "status"], name="pilot_program_status_idx")
        ]

    def clean(self) -> None:
        super().clean()
        if self.owner_membership_id and self.company_id != self.owner_membership.company_id:
            raise ValidationError("Pilot owner must belong to the same company")


class PilotChecklistItem(TenantOwnedModel):
    class Category(models.TextChoices):
        GOVERNANCE = "governance", "Governance"
        IDENTITY = "identity", "Identity and access"
        MASTER_DATA = "master_data", "Master data"
        TRAINING = "training", "Training"
        PROCESS = "process", "Business process"
        TECHNICAL = "technical", "Technical readiness"
        SECURITY = "security", "Security"
        DATA = "data", "Data readiness"
        GO_LIVE = "go_live", "Go-live"
        SUPPORT = "support", "Support"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        WAIVED = "waived", "Waived"
        BLOCKED = "blocked", "Blocked"

    program = models.ForeignKey(
        PilotProgram,
        on_delete=models.PROTECT,
        related_name="checklist_items",
    )
    code = models.CharField(max_length=100)
    category = models.CharField(max_length=30, choices=Category.choices)
    title = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    is_required = models.BooleanField(default=True)
    sequence = models.PositiveIntegerField(default=100)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.PENDING)
    owner_membership = models.ForeignKey(
        Membership,
        on_delete=models.PROTECT,
        related_name="pilot_checklist_items",
        null=True,
        blank=True,
    )
    due_at = models.DateTimeField(null=True, blank=True)
    completed_by_public_id = models.UUIDField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    evidence = models.JSONField(default=dict, blank=True)
    waiver_reason = models.CharField(max_length=500, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "pilotops_checklist_item"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "program", "code"],
                name="pilot_check_item_code_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "program", "status"],
                name="pilot_check_status_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.program_id and self.company_id != self.program.company_id:
            raise ValidationError("Checklist item cannot cross companies")
        if self.owner_membership_id and self.company_id != self.owner_membership.company_id:
            raise ValidationError("Checklist owner must belong to the same company")
        if self.status == self.Status.WAIVED and not self.waiver_reason.strip():
            raise ValidationError("Waived checklist items require a reason")


class MasterDataReadiness(TenantOwnedModel):
    class Status(models.TextChoices):
        NOT_STARTED = "not_started", "Not started"
        IN_PROGRESS = "in_progress", "In progress"
        READY = "ready", "Ready"
        BLOCKED = "blocked", "Blocked"

    program = models.ForeignKey(
        PilotProgram,
        on_delete=models.PROTECT,
        related_name="master_data_domains",
    )
    domain_code = models.CharField(max_length=100)
    domain_name = models.CharField(max_length=200)
    minimum_records = models.PositiveIntegerField(default=1)
    current_records = models.PositiveIntegerField(default=0)
    is_required = models.BooleanField(default=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.NOT_STARTED)
    validation_summary = models.JSONField(default=dict)
    last_validated_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "pilotops_master_data"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "program", "domain_code"],
                name="pilot_master_domain_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "program", "status"],
                name="pilot_master_status_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.program_id and self.company_id != self.program.company_id:
            raise ValidationError("Master-data readiness cannot cross companies")


class TrainingModule(TenantOwnedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        RETIRED = "retired", "Retired"

    program = models.ForeignKey(
        PilotProgram,
        on_delete=models.PROTECT,
        related_name="training_modules",
    )
    code = models.CharField(max_length=100)
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    audience_codes = models.JSONField(default=list)
    is_required = models.BooleanField(default=True)
    sequence = models.PositiveIntegerField(default=100)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT)
    content_url = models.URLField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "pilotops_training_module"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "program", "code"],
                name="pilot_training_code_uq",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.program_id and self.company_id != self.program.company_id:
            raise ValidationError("Training module cannot cross companies")


class TrainingCompletion(TenantOwnedModel):
    class Status(models.TextChoices):
        ASSIGNED = "assigned", "Assigned"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        WAIVED = "waived", "Waived"

    module = models.ForeignKey(
        TrainingModule,
        on_delete=models.PROTECT,
        related_name="completions",
    )
    membership = models.ForeignKey(
        Membership,
        on_delete=models.PROTECT,
        related_name="training_completions",
    )
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.ASSIGNED)
    score_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    assigned_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    evidence = models.JSONField(default=dict)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "pilotops_training_completion"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "module", "membership"],
                name="pilot_training_member_uq",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(score_percent__isnull=True)
                    | (
                        models.Q(score_percent__gte=0)
                        & models.Q(score_percent__lte=100)
                    )
                ),
                name="pilot_training_score_ck",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.module_id and self.company_id != self.module.company_id:
            raise ValidationError("Training completion cannot cross companies")
        if self.membership_id and self.company_id != self.membership.company_id:
            raise ValidationError("Training participant must belong to the same company")


class ReadinessAssessment(TenantOwnedModel):
    program = models.ForeignKey(
        PilotProgram,
        on_delete=models.PROTECT,
        related_name="readiness_assessments",
    )
    assessed_at = models.DateTimeField()
    assessed_by_public_id = models.UUIDField()
    score_percent = models.PositiveSmallIntegerField()
    critical_blockers = models.JSONField(default=list)
    warnings = models.JSONField(default=list)
    metrics = models.JSONField(default=dict)
    checksum_sha256 = models.CharField(max_length=64)

    class Meta:
        db_table = "pilotops_readiness_assessment"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(score_percent__lte=100),
                name="pilot_readiness_score_ck",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "program", "assessed_at"],
                name="pilot_readiness_time_idx",
            )
        ]

    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        if self.pk:
            raise ValidationError("Readiness assessments are append-only")
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    def delete(self, using: str | None = None, keep_parents: bool = False) -> NoReturn:
        raise ValidationError("Readiness assessments are append-only")


class GoLivePlan(TenantOwnedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        IN_REVIEW = "in_review", "In review"
        APPROVED = "approved", "Approved"
        IN_PROGRESS = "in_progress", "In progress"
        LIVE = "live", "Live"
        ROLLED_BACK = "rolled_back", "Rolled back"
        CANCELLED = "cancelled", "Cancelled"

    program = models.OneToOneField(
        PilotProgram,
        on_delete=models.PROTECT,
        related_name="go_live_plan",
    )
    target_at = models.DateTimeField(null=True, blank=True)
    cutover_window_minutes = models.PositiveIntegerField(default=120)
    support_window_hours = models.PositiveIntegerField(default=72)
    rollback_reference = models.CharField(max_length=300, blank=True)
    cutover_steps = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT)
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "pilotops_go_live_plan"
        indexes = [
            models.Index(fields=["company", "status"], name="pilot_golive_status_idx")
        ]

    def clean(self) -> None:
        super().clean()
        if self.program_id and self.company_id != self.program.company_id:
            raise ValidationError("Go-live plan cannot cross companies")


class GoLiveSignoff(TenantOwnedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        WAIVED = "waived", "Waived"

    plan = models.ForeignKey(
        GoLivePlan,
        on_delete=models.PROTECT,
        related_name="signoffs",
    )
    code = models.CharField(max_length=100)
    area = models.CharField(max_length=100)
    title = models.CharField(max_length=220)
    is_required = models.BooleanField(default=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.PENDING)
    signer_membership = models.ForeignKey(
        Membership,
        on_delete=models.PROTECT,
        related_name="go_live_signoffs",
        null=True,
        blank=True,
    )
    signed_by_public_id = models.UUIDField(null=True, blank=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    evidence = models.JSONField(default=dict)
    reason = models.CharField(max_length=500, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "pilotops_go_live_signoff"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "plan", "code"],
                name="pilot_golive_signoff_uq",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.plan_id and self.company_id != self.plan.company_id:
            raise ValidationError("Go-live sign-off cannot cross companies")
        if self.signer_membership_id and self.company_id != self.signer_membership.company_id:
            raise ValidationError("Go-live signer must belong to the same company")
        if self.status == self.Status.WAIVED and not self.reason.strip():
            raise ValidationError("Waived sign-offs require a reason")


class AdoptionSnapshot(TenantOwnedModel):
    program = models.ForeignKey(
        PilotProgram,
        on_delete=models.PROTECT,
        related_name="adoption_snapshots",
    )
    period_start = models.DateField()
    period_end = models.DateField()
    active_users = models.PositiveIntegerField(default=0)
    total_users = models.PositiveIntegerField(default=0)
    training_completion_percent = models.DecimalField(max_digits=5, decimal_places=2)
    completed_checklist_items = models.PositiveIntegerField(default=0)
    total_checklist_items = models.PositiveIntegerField(default=0)
    key_activity_count = models.PositiveIntegerField(default=0)
    metrics = models.JSONField(default=dict)
    generated_at = models.DateTimeField()
    checksum_sha256 = models.CharField(max_length=64)

    class Meta:
        db_table = "pilotops_adoption_snapshot"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "program", "period_end"],
                name="pilot_adoption_period_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(period_end__gte=models.F("period_start")),
                name="pilot_adoption_period_ck",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(training_completion_percent__gte=0)
                    & models.Q(training_completion_percent__lte=100)
                ),
                name="pilot_adoption_training_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "program", "period_end"],
                name="pilot_adoption_time_idx",
            )
        ]

    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        if self.pk:
            raise ValidationError("Adoption snapshots are append-only")
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    def delete(self, using: str | None = None, keep_parents: bool = False) -> NoReturn:
        raise ValidationError("Adoption snapshots are append-only")
