from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from modules.platform.models import TenantOwnedModel


class DeliveryStage(TenantOwnedModel):
    class EntityType(models.TextChoices):
        PROJECT = "project", "Project"
        TASK = "task", "Task"
        DESIGN_VERSION = "design_version", "Design version"
        ESTIMATE_VERSION = "estimate_version", "Estimate version"

    class Outcome(models.TextChoices):
        OPEN = "open", "Open"
        REVIEW = "review", "Under review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        ISSUED = "issued", "Issued"
        COMPLETE = "complete", "Complete"
        CANCELLED = "cancelled", "Cancelled"
        SUPERSEDED = "superseded", "Superseded"

    entity_type = models.CharField(max_length=30, choices=EntityType.choices)
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=160)
    outcome = models.CharField(max_length=30, choices=Outcome.choices, default=Outcome.OPEN)
    sort_order = models.PositiveIntegerField(default=100)
    allowed_next_codes = models.JSONField(default=list)
    is_initial = models.BooleanField(default=False)
    allows_baseline = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "project_delivery_stage"
        ordering = ["entity_type", "sort_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "entity_type", "code"],
                name="prj_stage_company_code_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gt=models.F("effective_from")),
                name="prj_stage_range_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "entity_type", "is_active", "sort_order"],
                name="prj_stage_active_idx",
            )
        ]


class Project(TenantOwnedModel):
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=250)
    description = models.TextField(blank=True)
    customer_public_id = models.UUIDField(null=True, blank=True)
    opportunity_public_id = models.UUIDField(null=True, blank=True)
    stage = models.ForeignKey(DeliveryStage, on_delete=models.PROTECT, related_name="projects")
    manager_membership_public_id = models.UUIDField()
    location = models.JSONField(default=dict, blank=True)
    planned_start_date = models.DateField(null=True, blank=True)
    planned_end_date = models.DateField(null=True, blank=True)
    actual_start_date = models.DateField(null=True, blank=True)
    actual_end_date = models.DateField(null=True, blank=True)
    currency = models.CharField(max_length=3)
    approved_budget = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        default=Decimal("0"),
    )
    version = models.PositiveBigIntegerField(default=1)
    baseline_version = models.PositiveIntegerField(default=0)
    baselined_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "project_project"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="prj_company_code_uq",
            ),
            models.UniqueConstraint(
                fields=["company", "opportunity_public_id"],
                condition=models.Q(opportunity_public_id__isnull=False),
                name="prj_company_opportunity_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(planned_end_date__isnull=True)
                | models.Q(planned_start_date__isnull=True)
                | models.Q(planned_end_date__gte=models.F("planned_start_date")),
                name="prj_plan_dates_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(approved_budget__gte=0),
                name="prj_budget_nonnegative",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "stage", "planned_end_date"], name="prj_stage_end_idx"),
            models.Index(
                fields=["company", "manager_membership_public_id", "stage"],
                name="prj_manager_stage_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.stage_id and self.stage.company_id != self.company_id:
            raise ValidationError("Project stage cannot cross companies")
        if self.stage_id and self.stage.entity_type != DeliveryStage.EntityType.PROJECT:
            raise ValidationError("Project requires a project delivery stage")


class ProjectStageHistory(TenantOwnedModel):
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="stage_history")
    from_stage_code = models.CharField(max_length=80, blank=True)
    to_stage_code = models.CharField(max_length=80)
    changed_by_public_id = models.UUIDField()
    changed_at = models.DateTimeField()
    reason_code = models.CharField(max_length=100, blank=True)
    project_version = models.PositiveBigIntegerField()

    class Meta:
        db_table = "project_stage_history"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "project", "project_version"],
                name="prj_stage_hist_version_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "project", "changed_at"],
                name="prj_stage_hist_lookup_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.project_id and self.project.company_id != self.company_id:
            raise ValidationError("Project stage history cannot cross companies")


class WbsNode(TenantOwnedModel):
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="wbs_nodes")
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="children",
        null=True,
        blank=True,
    )
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=250)
    description = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=100)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "project_wbs_node"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "project", "code"],
                name="prj_wbs_code_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "project", "parent", "sort_order"],
                name="prj_wbs_tree_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.project_id and self.project.company_id != self.company_id:
            raise ValidationError("WBS project cannot cross companies")
        if self.parent_id and (
            self.parent.company_id != self.company_id or self.parent.project_id != self.project_id
        ):
            raise ValidationError("WBS parent must belong to the same project")
        if self.pk and self.parent_id == self.pk:
            raise ValidationError("WBS node cannot be its own parent")


class ProjectTask(TenantOwnedModel):
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="tasks")
    wbs_node = models.ForeignKey(
        WbsNode,
        on_delete=models.PROTECT,
        related_name="tasks",
        null=True,
        blank=True,
    )
    code = models.CharField(max_length=80)
    title = models.CharField(max_length=250)
    description = models.TextField(blank=True)
    stage = models.ForeignKey(DeliveryStage, on_delete=models.PROTECT, related_name="tasks")
    assignee_membership_public_id = models.UUIDField(null=True, blank=True)
    planned_start_date = models.DateField(null=True, blank=True)
    planned_end_date = models.DateField(null=True, blank=True)
    progress_percent = models.PositiveSmallIntegerField(default=0)
    dependencies = models.JSONField(default=list, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "project_task"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "project", "code"],
                name="prj_task_code_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(progress_percent__lte=100),
                name="prj_task_progress_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(planned_end_date__isnull=True)
                | models.Q(planned_start_date__isnull=True)
                | models.Q(planned_end_date__gte=models.F("planned_start_date")),
                name="prj_task_dates_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "project", "stage"], name="prj_task_stage_idx"),
            models.Index(
                fields=["company", "assignee_membership_public_id", "stage"],
                name="prj_task_assignee_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.project_id and self.project.company_id != self.company_id:
            raise ValidationError("Task project cannot cross companies")
        if self.stage_id and (
            self.stage.company_id != self.company_id
            or self.stage.entity_type != DeliveryStage.EntityType.TASK
        ):
            raise ValidationError("Task requires a task stage from the same company")
        if self.wbs_node_id and (
            self.wbs_node.company_id != self.company_id
            or self.wbs_node.project_id != self.project_id
        ):
            raise ValidationError("Task WBS node must belong to the same project")


class ProjectBaseline(TenantOwnedModel):
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="baselines")
    baseline_number = models.PositiveIntegerField()
    source_project_version = models.PositiveBigIntegerField()
    snapshot = models.JSONField(default=dict)
    created_by_public_id = models.UUIDField()

    class Meta:
        db_table = "project_baseline"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "project", "baseline_number"],
                name="prj_baseline_number_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "project", "baseline_number"],
                name="prj_baseline_lookup_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.project_id and self.project.company_id != self.company_id:
            raise ValidationError("Project baseline cannot cross companies")
