from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from modules.fieldops.models import FieldStage
from modules.platform.models import TenantOwnedModel


class WorkerProfile(TenantOwnedModel):
    class WorkerType(models.TextChoices):
        EMPLOYEE = "employee", "Employee"
        CONTRACT = "contract", "Contract labour"
        SUBCONTRACT = "subcontract", "Subcontract labour"

    code = models.CharField(max_length=80)
    display_name = models.CharField(max_length=200)
    worker_type = models.CharField(max_length=30, choices=WorkerType.choices)
    employee_public_id = models.UUIDField(null=True, blank=True)
    vendor_public_id = models.UUIDField(null=True, blank=True)
    trade_code = models.CharField(max_length=80)
    skill_codes = models.JSONField(default=list, blank=True)
    daily_rate = models.DecimalField(max_digits=19, decimal_places=4, default=Decimal("0"))
    currency = models.CharField(max_length=3)
    joined_on = models.DateField()
    exited_on = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "labour_worker_profile"
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="lab_worker_code_uq"),
            models.CheckConstraint(
                condition=models.Q(daily_rate__gte=0),
                name="lab_worker_rate_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(exited_on__isnull=True)
                | models.Q(exited_on__gte=models.F("joined_on")),
                name="lab_worker_dates_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "trade_code", "is_active"], name="lab_worker_trade_idx")
        ]


class WorkforceAllocation(TenantOwnedModel):
    worker = models.ForeignKey(WorkerProfile, on_delete=models.PROTECT, related_name="allocations")
    project = models.ForeignKey("projects.Project", on_delete=models.PROTECT, related_name="labour_allocations")
    task = models.ForeignKey(
        "projects.ProjectTask",
        on_delete=models.PROTECT,
        related_name="labour_allocations",
        null=True,
        blank=True,
    )
    stage = models.ForeignKey(FieldStage, on_delete=models.PROTECT, related_name="labour_allocations")
    allocated_from = models.DateField()
    allocated_to = models.DateField(null=True, blank=True)
    planned_hours = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("8"))
    supervisor_membership_public_id = models.UUIDField(null=True, blank=True)
    notes = models.TextField(blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "labour_workforce_allocation"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(allocated_to__isnull=True)
                | models.Q(allocated_to__gte=models.F("allocated_from")),
                name="lab_alloc_dates_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(planned_hours__gt=0),
                name="lab_alloc_hours_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "project", "stage"], name="lab_alloc_project_idx"),
            models.Index(fields=["company", "worker", "allocated_from"], name="lab_alloc_worker_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        if self.worker_id and self.worker.company_id != self.company_id:
            raise ValidationError("Worker allocation cannot cross companies")
        if self.project_id and self.project.company_id != self.company_id:
            raise ValidationError("Project allocation cannot cross companies")
        if self.task_id and (
            self.task.company_id != self.company_id or self.task.project_id != self.project_id
        ):
            raise ValidationError("Task must belong to the allocated project")
        if self.stage_id and (
            self.stage.company_id != self.company_id
            or self.stage.entity_type != FieldStage.EntityType.LABOUR_ALLOCATION
        ):
            raise ValidationError("Allocation requires a labour-allocation stage")


class AttendanceRecord(TenantOwnedModel):
    class EntrySource(models.TextChoices):
        WEB = "web", "Web"
        MOBILE = "mobile", "Mobile"
        OFFLINE = "offline", "Offline"
        IMPORT = "import", "Import"

    worker = models.ForeignKey(WorkerProfile, on_delete=models.PROTECT, related_name="attendance")
    project = models.ForeignKey("projects.Project", on_delete=models.PROTECT, related_name="attendance")
    stage = models.ForeignKey(FieldStage, on_delete=models.PROTECT, related_name="attendance_records")
    work_date = models.DateField()
    clock_in = models.DateTimeField(null=True, blank=True)
    clock_out = models.DateTimeField(null=True, blank=True)
    regular_hours = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0"))
    overtime_hours = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0"))
    source = models.CharField(max_length=20, choices=EntrySource.choices, default=EntrySource.WEB)
    operation_id = models.UUIDField(null=True, blank=True)
    evidence_file_public_ids = models.JSONField(default=list, blank=True)
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    correction_reason = models.TextField(blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "labour_attendance_record"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "worker", "project", "work_date"],
                name="lab_attendance_day_uq",
            ),
            models.UniqueConstraint(
                fields=["company", "operation_id"],
                condition=models.Q(operation_id__isnull=False),
                name="lab_attendance_operation_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(clock_out__isnull=True)
                | models.Q(clock_in__isnull=True)
                | models.Q(clock_out__gte=models.F("clock_in")),
                name="lab_attendance_time_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(regular_hours__gte=0) & models.Q(overtime_hours__gte=0),
                name="lab_attendance_hours_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "project", "work_date"], name="lab_attendance_project_idx"),
            models.Index(fields=["company", "worker", "work_date"], name="lab_attendance_worker_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        if self.worker_id and self.worker.company_id != self.company_id:
            raise ValidationError("Attendance worker cannot cross companies")
        if self.project_id and self.project.company_id != self.company_id:
            raise ValidationError("Attendance project cannot cross companies")
        if self.stage_id and (
            self.stage.company_id != self.company_id
            or self.stage.entity_type != FieldStage.EntityType.ATTENDANCE
        ):
            raise ValidationError("Attendance requires an attendance stage")
