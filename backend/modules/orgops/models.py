from __future__ import annotations

from decimal import Decimal

from django.db import models

from modules.employee.models import Employee
from modules.platform.models import PublicIdModel, TimestampedModel
from modules.tenant.models import Company, Location


class Department(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="orgops_departments",
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="children",
        null=True,
        blank=True,
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name="orgops_departments",
        null=True,
        blank=True,
    )
    cost_center_code = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "orgops_department"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="orgops_dept_code_uq",
            ),
            models.CheckConstraint(
                condition=~models.Q(id=models.F("parent_id")),
                name="orgops_dept_no_self_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "is_active", "name"],
                name="orgops_dept_active_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        from django.core.exceptions import ValidationError

        if self.parent_id and self.parent.company_id != self.company_id:
            raise ValidationError("Department hierarchy cannot cross companies")
        if self.location_id and self.location.company_id != self.company_id:
            raise ValidationError("Department location cannot cross companies")


class Designation(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="orgops_designations",
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    level_code = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "orgops_designation"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="orgops_desig_code_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "is_active", "name"],
                name="orgops_desig_active_idx",
            )
        ]


class WorkCalendar(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="orgops_work_calendars",
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    timezone = models.CharField(max_length=64)
    working_days = models.JSONField(default=list)
    standard_hours_per_day = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal("8.00"),
    )
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "orgops_work_calendar"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="orgops_calendar_code_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(standard_hours_per_day__gt=0)
                & models.Q(standard_hours_per_day__lte=24),
                name="orgops_calendar_hours_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "is_active", "name"],
                name="orgops_calendar_active_idx",
            )
        ]


class EmployeeOrganizationProfile(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="orgops_employee_profiles",
    )
    employee = models.OneToOneField(
        Employee,
        on_delete=models.PROTECT,
        related_name="organization_profile",
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="employee_profiles",
        null=True,
        blank=True,
    )
    designation = models.ForeignKey(
        Designation,
        on_delete=models.PROTECT,
        related_name="employee_profiles",
        null=True,
        blank=True,
    )
    work_calendar = models.ForeignKey(
        WorkCalendar,
        on_delete=models.PROTECT,
        related_name="employee_profiles",
        null=True,
        blank=True,
    )
    employment_type_code = models.CharField(max_length=100, default="FULL_TIME")
    worker_category_code = models.CharField(max_length=100, blank=True)
    mobile = models.CharField(max_length=32, blank=True)
    emergency_contact = models.JSONField(default=dict, blank=True)
    status_code = models.CharField(max_length=100, default="ACTIVE")
    probation_end = models.DateField(null=True, blank=True)
    confirmation_date = models.DateField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "orgops_employee_profile"
        indexes = [
            models.Index(
                fields=["company", "department", "status_code"],
                name="orgops_profile_dept_idx",
            ),
            models.Index(
                fields=["company", "designation", "status_code"],
                name="orgops_profile_desig_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        from django.core.exceptions import ValidationError

        if self.employee_id and self.employee.company_id != self.company_id:
            raise ValidationError("Employee profile cannot cross companies")
        for value, label in (
            (self.department, "Department"),
            (self.designation, "Designation"),
            (self.work_calendar, "Work calendar"),
        ):
            if value is not None and value.company_id != self.company_id:
                raise ValidationError(f"{label} cannot cross companies")


class OrganizationAssignment(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="orgops_assignments",
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="organization_assignments",
    )
    assignment_type_code = models.CharField(max_length=100, default="PRIMARY")
    project_code = models.CharField(max_length=100, blank=True)
    site_code = models.CharField(max_length=100, blank=True)
    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name="orgops_assignments",
        null=True,
        blank=True,
    )
    work_package_code = models.CharField(max_length=100, blank=True)
    allocation_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("100.00"),
    )
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    is_primary = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "orgops_assignment"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gte=models.F("effective_from")),
                name="orgops_assign_range_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(allocation_percent__gt=0)
                & models.Q(allocation_percent__lte=100),
                name="orgops_assign_alloc_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "employee", "effective_from"],
                name="orgops_assign_employee_idx",
            ),
            models.Index(
                fields=["company", "project_code", "site_code"],
                name="orgops_assign_scope_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        from django.core.exceptions import ValidationError

        if self.employee_id and self.employee.company_id != self.company_id:
            raise ValidationError("Organization assignment cannot cross companies")
        if self.location_id and self.location.company_id != self.company_id:
            raise ValidationError("Assignment location cannot cross companies")


class LeaveType(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="orgops_leave_types",
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    unit_code = models.CharField(max_length=50, default="DAYS")
    requires_approval = models.BooleanField(default=True)
    is_paid = models.BooleanField(default=True)
    annual_entitlement = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "orgops_leave_type"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="orgops_leave_type_code_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(annual_entitlement__isnull=True)
                | models.Q(annual_entitlement__gte=0),
                name="orgops_leave_entitle_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "is_active", "name"],
                name="orgops_leave_type_active_idx",
            )
        ]


class LeaveRequest(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="orgops_leave_requests",
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="organization_leave_requests",
    )
    leave_type = models.ForeignKey(
        LeaveType,
        on_delete=models.PROTECT,
        related_name="requests",
    )
    start_date = models.DateField()
    end_date = models.DateField()
    quantity = models.DecimalField(max_digits=8, decimal_places=2)
    reason = models.TextField(blank=True)
    status_code = models.CharField(max_length=100, default="SUBMITTED")
    requested_by_public_id = models.UUIDField()
    reviewed_by_public_id = models.UUIDField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "orgops_leave_request"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="orgops_leave_range_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="orgops_leave_qty_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "status_code", "start_date"],
                name="orgops_leave_state_idx",
            ),
            models.Index(
                fields=["company", "employee", "start_date"],
                name="orgops_leave_employee_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        from django.core.exceptions import ValidationError

        if self.employee_id and self.employee.company_id != self.company_id:
            raise ValidationError("Leave request cannot cross companies")
        if self.leave_type_id and self.leave_type.company_id != self.company_id:
            raise ValidationError("Leave type cannot cross companies")


class AttendanceEntry(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="orgops_attendance_entries",
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="organization_attendance_entries",
    )
    work_date = models.DateField()
    status_code = models.CharField(max_length=100, default="PRESENT")
    hours_worked = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    source_code = models.CharField(max_length=100, default="MANUAL")
    check_in_at = models.DateTimeField(null=True, blank=True)
    check_out_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    recorded_by_public_id = models.UUIDField()
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "orgops_attendance_entry"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "employee", "work_date"],
                name="orgops_attendance_day_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(hours_worked__gte=0)
                & models.Q(hours_worked__lte=24),
                name="orgops_attendance_hours_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(check_out_at__isnull=True)
                | models.Q(check_in_at__isnull=True)
                | models.Q(check_out_at__gte=models.F("check_in_at")),
                name="orgops_attendance_time_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "work_date", "status_code"],
                name="orgops_attendance_daily_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        from django.core.exceptions import ValidationError

        if self.employee_id and self.employee.company_id != self.company_id:
            raise ValidationError("Attendance entry cannot cross companies")


class PeopleImportJob(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="orgops_import_jobs",
    )
    source_name = models.CharField(max_length=250)
    status_code = models.CharField(max_length=100, default="PROCESSING")
    total_rows = models.PositiveIntegerField(default=0)
    success_rows = models.PositiveIntegerField(default=0)
    failed_rows = models.PositiveIntegerField(default=0)
    error_rows = models.JSONField(default=list)
    created_by_public_id = models.UUIDField()
    completed_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "orgops_import_job"
        indexes = [
            models.Index(
                fields=["company", "status_code", "created_at"],
                name="orgops_import_job_state_idx",
            )
        ]
