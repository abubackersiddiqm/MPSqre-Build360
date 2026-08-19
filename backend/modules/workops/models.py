from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from modules.employee.models import Employee
from modules.platform.models import PublicIdModel, TimestampedModel
from modules.tenant.models import Company, Location


class Project(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="workops_projects")
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=250)
    description = models.TextField(blank=True)
    project_type_code = models.CharField(max_length=100, default="CONSTRUCTION")
    status_code = models.CharField(max_length=50, default="DRAFT")
    priority_code = models.CharField(max_length=50, default="NORMAL")
    manager = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="managed_workops_projects",
        null=True,
        blank=True,
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name="workops_projects",
        null=True,
        blank=True,
    )
    start_date = models.DateField()
    target_end_date = models.DateField()
    actual_end_date = models.DateField(null=True, blank=True)
    currency = models.CharField(max_length=3)
    budget = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "workops_project"
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="wk_project_code_uq"),
            models.CheckConstraint(
                condition=models.Q(target_end_date__gte=models.F("start_date")),
                name="wk_project_dates_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(actual_end_date__isnull=True)
                | models.Q(actual_end_date__gte=models.F("start_date")),
                name="wk_project_actual_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(budget__isnull=True) | models.Q(budget__gte=0),
                name="wk_project_budget_ck",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "status_code", "target_end_date"], name="wk_project_status_idx")
        ]

    def clean(self) -> None:
        super().clean()
        if self.manager_id and self.manager.company_id != self.company_id:
            raise ValidationError("Project manager cannot cross companies")
        if self.location_id and self.location.company_id != self.company_id:
            raise ValidationError("Project location cannot cross companies")


class ProjectSite(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="workops_sites")
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="sites")
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name="workops_sites",
        null=True,
        blank=True,
    )
    address = models.JSONField(default=dict, blank=True)
    status_code = models.CharField(max_length=50, default="ACTIVE")
    start_date = models.DateField(null=True, blank=True)
    target_end_date = models.DateField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "workops_project_site"
        constraints = [
            models.UniqueConstraint(fields=["project", "code"], name="wk_site_code_uq"),
            models.CheckConstraint(
                condition=models.Q(target_end_date__isnull=True)
                | models.Q(start_date__isnull=True)
                | models.Q(target_end_date__gte=models.F("start_date")),
                name="wk_site_dates_ck",
            ),
        ]
        indexes = [models.Index(fields=["company", "project", "status_code"], name="wk_site_status_idx")]

    def clean(self) -> None:
        super().clean()
        if self.project_id and self.project.company_id != self.company_id:
            raise ValidationError("Project site cannot cross companies")
        if self.location_id and self.location.company_id != self.company_id:
            raise ValidationError("Site location cannot cross companies")


class WBSNode(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="workops_wbs_nodes")
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="wbs_nodes")
    code = models.CharField(max_length=100)
    name = models.CharField(max_length=250)
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="children",
        null=True,
        blank=True,
    )
    sequence = models.PositiveIntegerField(default=1)
    level = models.PositiveSmallIntegerField(default=1)
    status_code = models.CharField(max_length=50, default="ACTIVE")
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "workops_wbs_node"
        constraints = [
            models.UniqueConstraint(fields=["project", "code"], name="wk_wbs_code_uq"),
            models.CheckConstraint(condition=~models.Q(id=models.F("parent_id")), name="wk_wbs_no_self_ck"),
        ]
        indexes = [models.Index(fields=["company", "project", "parent", "sequence"], name="wk_wbs_tree_idx")]

    def clean(self) -> None:
        super().clean()
        if self.project_id and self.project.company_id != self.company_id:
            raise ValidationError("WBS node cannot cross companies")
        if self.parent_id:
            if self.parent.company_id != self.company_id or self.parent.project_id != self.project_id:
                raise ValidationError("WBS hierarchy cannot cross projects")


class WorkPackage(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="workops_packages")
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="work_packages")
    wbs_node = models.ForeignKey(WBSNode, on_delete=models.PROTECT, related_name="work_packages")
    code = models.CharField(max_length=100)
    name = models.CharField(max_length=250)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="owned_workops_packages",
        null=True,
        blank=True,
    )
    planned_start = models.DateField()
    planned_end = models.DateField()
    status_code = models.CharField(max_length=50, default="PLANNED")
    progress_weight = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("1.00"))
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "workops_work_package"
        constraints = [
            models.UniqueConstraint(fields=["project", "code"], name="wk_package_code_uq"),
            models.CheckConstraint(
                condition=models.Q(planned_end__gte=models.F("planned_start")),
                name="wk_package_dates_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(progress_weight__gt=0) & models.Q(progress_weight__lte=100),
                name="wk_package_weight_ck",
            ),
        ]
        indexes = [models.Index(fields=["company", "project", "status_code"], name="wk_package_status_idx")]

    def clean(self) -> None:
        super().clean()
        if self.project_id and self.project.company_id != self.company_id:
            raise ValidationError("Work package cannot cross companies")
        if self.wbs_node_id and self.wbs_node.project_id != self.project_id:
            raise ValidationError("Work package WBS node must belong to the project")
        if self.owner_id and self.owner.company_id != self.company_id:
            raise ValidationError("Work package owner cannot cross companies")


class Milestone(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="workops_milestones")
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="milestones")
    code = models.CharField(max_length=100)
    name = models.CharField(max_length=250)
    target_date = models.DateField()
    owner = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="owned_workops_milestones",
        null=True,
        blank=True,
    )
    status_code = models.CharField(max_length=50, default="PLANNED")
    achieved_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "workops_milestone"
        constraints = [models.UniqueConstraint(fields=["project", "code"], name="wk_milestone_code_uq")]
        indexes = [models.Index(fields=["company", "status_code", "target_date"], name="wk_milestone_due_idx")]

    def clean(self) -> None:
        super().clean()
        if self.project_id and self.project.company_id != self.company_id:
            raise ValidationError("Milestone cannot cross companies")
        if self.owner_id and self.owner.company_id != self.company_id:
            raise ValidationError("Milestone owner cannot cross companies")


class WorkItem(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="workops_items")
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="work_items")
    site = models.ForeignKey(ProjectSite, on_delete=models.PROTECT, related_name="work_items", null=True, blank=True)
    work_package = models.ForeignKey(
        WorkPackage,
        on_delete=models.PROTECT,
        related_name="work_items",
        null=True,
        blank=True,
    )
    code = models.CharField(max_length=100)
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    work_type_code = models.CharField(max_length=100, default="TASK")
    status_code = models.CharField(max_length=50, default="BACKLOG")
    priority_code = models.CharField(max_length=50, default="NORMAL")
    planned_start = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    actual_start = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    progress_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    estimated_hours = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    primary_assignee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="primary_workops_items",
        null=True,
        blank=True,
    )
    reviewer = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="review_workops_items",
        null=True,
        blank=True,
    )
    created_by_public_id = models.UUIDField()
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "workops_work_item"
        constraints = [
            models.UniqueConstraint(fields=["project", "code"], name="wk_item_code_uq"),
            models.CheckConstraint(
                condition=models.Q(progress_percent__gte=0) & models.Q(progress_percent__lte=100),
                name="wk_item_progress_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(estimated_hours__isnull=True) | models.Q(estimated_hours__gte=0),
                name="wk_item_hours_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(due_date__isnull=True)
                | models.Q(planned_start__isnull=True)
                | models.Q(due_date__gte=models.F("planned_start")),
                name="wk_item_dates_ck",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "status_code", "due_date"], name="wk_item_status_idx"),
            models.Index(fields=["company", "primary_assignee", "status_code"], name="wk_item_assignee_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        if self.project_id and self.project.company_id != self.company_id:
            raise ValidationError("Work item cannot cross companies")
        if self.site_id and self.site.project_id != self.project_id:
            raise ValidationError("Work item site must belong to the project")
        if self.work_package_id and self.work_package.project_id != self.project_id:
            raise ValidationError("Work item package must belong to the project")
        for employee, label in ((self.primary_assignee, "Assignee"), (self.reviewer, "Reviewer")):
            if employee is not None and employee.company_id != self.company_id:
                raise ValidationError(f"{label} cannot cross companies")


class WorkDependency(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="workops_dependencies")
    predecessor = models.ForeignKey(WorkItem, on_delete=models.PROTECT, related_name="successor_links")
    successor = models.ForeignKey(WorkItem, on_delete=models.PROTECT, related_name="predecessor_links")
    dependency_type_code = models.CharField(max_length=50, default="FINISH_TO_START")
    lag_days = models.IntegerField(default=0)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "workops_dependency"
        constraints = [
            models.UniqueConstraint(fields=["predecessor", "successor"], name="wk_dependency_uq"),
            models.CheckConstraint(condition=~models.Q(predecessor=models.F("successor")), name="wk_dependency_self_ck"),
        ]

    def clean(self) -> None:
        super().clean()
        if self.predecessor_id and self.successor_id:
            if self.predecessor.company_id != self.company_id or self.successor.company_id != self.company_id:
                raise ValidationError("Dependency cannot cross companies")
            if self.predecessor.project_id != self.successor.project_id:
                raise ValidationError("Dependency cannot cross projects")


class WorkAssignment(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="workops_assignments")
    work_item = models.ForeignKey(WorkItem, on_delete=models.PROTECT, related_name="assignments")
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="workops_assignments")
    assignment_role_code = models.CharField(max_length=50, default="ASSIGNEE")
    allocation_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("100.00"))
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    status_code = models.CharField(max_length=50, default="ACTIVE")
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "workops_assignment"
        constraints = [
            models.UniqueConstraint(
                fields=["work_item", "employee", "assignment_role_code", "effective_from"],
                name="wk_assignment_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(allocation_percent__gt=0) & models.Q(allocation_percent__lte=100),
                name="wk_assignment_alloc_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gte=models.F("effective_from")),
                name="wk_assignment_dates_ck",
            ),
        ]
        indexes = [models.Index(fields=["company", "employee", "status_code"], name="wk_assignment_emp_idx")]

    def clean(self) -> None:
        super().clean()
        if self.work_item_id and self.work_item.company_id != self.company_id:
            raise ValidationError("Work assignment cannot cross companies")
        if self.employee_id and self.employee.company_id != self.company_id:
            raise ValidationError("Assigned employee cannot cross companies")


class ChecklistItem(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="workops_checklists")
    work_item = models.ForeignKey(WorkItem, on_delete=models.PROTECT, related_name="checklist_items")
    sequence = models.PositiveIntegerField(default=1)
    title = models.CharField(max_length=300)
    is_required = models.BooleanField(default=True)
    is_completed = models.BooleanField(default=False)
    completed_by_public_id = models.UUIDField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "workops_checklist_item"
        constraints = [models.UniqueConstraint(fields=["work_item", "sequence"], name="wk_checklist_seq_uq")]
        indexes = [models.Index(fields=["company", "work_item", "is_completed"], name="wk_checklist_open_idx")]

    def clean(self) -> None:
        super().clean()
        if self.work_item_id and self.work_item.company_id != self.company_id:
            raise ValidationError("Checklist item cannot cross companies")


class DailyProgress(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="workops_progress")
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="daily_progress")
    site = models.ForeignKey(ProjectSite, on_delete=models.PROTECT, related_name="daily_progress", null=True, blank=True)
    work_item = models.ForeignKey(WorkItem, on_delete=models.PROTECT, related_name="daily_progress", null=True, blank=True)
    progress_date = models.DateField()
    quantity_completed = models.DecimalField(max_digits=18, decimal_places=3, default=Decimal("0.000"))
    unit_code = models.CharField(max_length=50, blank=True)
    progress_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    hours_worked = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))
    note = models.TextField(blank=True)
    blockers = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="recorded_workops_progress",
        null=True,
        blank=True,
    )
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "workops_daily_progress"
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity_completed__gte=0), name="wk_progress_qty_ck"),
            models.CheckConstraint(condition=models.Q(hours_worked__gte=0), name="wk_progress_hours_ck"),
            models.CheckConstraint(
                condition=models.Q(progress_percent__isnull=True)
                | (models.Q(progress_percent__gte=0) & models.Q(progress_percent__lte=100)),
                name="wk_progress_pct_ck",
            ),
        ]
        indexes = [models.Index(fields=["company", "project", "progress_date"], name="wk_progress_date_idx")]

    def clean(self) -> None:
        super().clean()
        if self.project_id and self.project.company_id != self.company_id:
            raise ValidationError("Progress entry cannot cross companies")
        if self.site_id and self.site.project_id != self.project_id:
            raise ValidationError("Progress site must belong to the project")
        if self.work_item_id and self.work_item.project_id != self.project_id:
            raise ValidationError("Progress work item must belong to the project")
        if self.recorded_by_id and self.recorded_by.company_id != self.company_id:
            raise ValidationError("Progress recorder cannot cross companies")


class TimesheetEntry(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="workops_timesheets")
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="workops_timesheets")
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="timesheets")
    work_item = models.ForeignKey(WorkItem, on_delete=models.PROTECT, related_name="timesheets", null=True, blank=True)
    work_date = models.DateField()
    hours = models.DecimalField(max_digits=5, decimal_places=2)
    description = models.TextField(blank=True)
    status_code = models.CharField(max_length=50, default="DRAFT")
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by_public_id = models.UUIDField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "workops_timesheet"
        constraints = [
            models.CheckConstraint(condition=models.Q(hours__gt=0) & models.Q(hours__lte=24), name="wk_timesheet_hours_ck")
        ]
        indexes = [
            models.Index(fields=["company", "employee", "work_date"], name="wk_timesheet_emp_idx"),
            models.Index(fields=["company", "status_code", "work_date"], name="wk_timesheet_status_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        if self.employee_id and self.employee.company_id != self.company_id:
            raise ValidationError("Timesheet employee cannot cross companies")
        if self.project_id and self.project.company_id != self.company_id:
            raise ValidationError("Timesheet project cannot cross companies")
        if self.work_item_id and self.work_item.project_id != self.project_id:
            raise ValidationError("Timesheet work item must belong to the project")


class WorkApproval(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="workops_approvals")
    work_item = models.ForeignKey(WorkItem, on_delete=models.PROTECT, related_name="approvals")
    approval_type_code = models.CharField(max_length=100, default="WORK_COMPLETION")
    requested_by_public_id = models.UUIDField()
    reviewer = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="workops_approvals")
    status_code = models.CharField(max_length=50, default="PENDING")
    request_note = models.TextField(blank=True)
    decision_note = models.TextField(blank=True)
    requested_at = models.DateTimeField()
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by_public_id = models.UUIDField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "workops_approval"
        constraints = [
            models.UniqueConstraint(
                fields=["work_item", "approval_type_code", "reviewer", "requested_at"],
                name="wk_approval_request_uq",
            )
        ]
        indexes = [models.Index(fields=["company", "status_code", "reviewer"], name="wk_approval_pending_idx")]

    def clean(self) -> None:
        super().clean()
        if self.work_item_id and self.work_item.company_id != self.company_id:
            raise ValidationError("Approval cannot cross companies")
        if self.reviewer_id and self.reviewer.company_id != self.company_id:
            raise ValidationError("Approval reviewer cannot cross companies")
