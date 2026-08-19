from __future__ import annotations

import hashlib
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from modules.platform.models import TenantOwnedModel


class Department(TenantOwnedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    code = models.CharField(max_length=60)
    name = models.CharField(max_length=180)
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="children",
        null=True,
        blank=True,
    )
    manager_employee = models.ForeignKey(
        "employee.Employee",
        on_delete=models.PROTECT,
        related_name="managed_departments",
        null=True,
        blank=True,
    )
    cost_code = models.CharField(max_length=80, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "peopleops_department"
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="ppl_dept_code_uq",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "status"], name="ppl_dept_status_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        if self.parent_id and self.parent.company_id != self.company_id:
            raise ValidationError("A parent department cannot belong to another company")
        if self.manager_employee_id and self.manager_employee.company_id != self.company_id:
            raise ValidationError("A department manager cannot belong to another company")
        if self.parent_id and self.pk and self.parent_id == self.pk:
            raise ValidationError("A department cannot be its own parent")


class EmploymentContract(TenantOwnedModel):
    class EmploymentType(models.TextChoices):
        PERMANENT = "permanent", "Permanent"
        FIXED_TERM = "fixed_term", "Fixed term"
        CONSULTANT = "consultant", "Consultant"
        INTERN = "intern", "Intern"

    class PayFrequency(models.TextChoices):
        MONTHLY = "monthly", "Monthly"
        BIWEEKLY = "biweekly", "Biweekly"
        WEEKLY = "weekly", "Weekly"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        ENDED = "ended", "Ended"
        CANCELLED = "cancelled", "Cancelled"

    employee = models.ForeignKey(
        "employee.Employee",
        on_delete=models.PROTECT,
        related_name="employment_contracts",
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="employment_contracts",
    )
    contract_number = models.CharField(max_length=80)
    position_title = models.CharField(max_length=180)
    employment_type = models.CharField(max_length=20, choices=EmploymentType.choices)
    start_on = models.DateField()
    end_on = models.DateField(null=True, blank=True)
    currency = models.CharField(max_length=3)
    annual_compensation = models.DecimalField(max_digits=18, decimal_places=2)
    pay_frequency = models.CharField(max_length=20, choices=PayFrequency.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_by_user_public_id = models.UUIDField()
    approved_by_user_public_id = models.UUIDField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "peopleops_contract"
        ordering = ["-start_on", "contract_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "contract_number"],
                name="ppl_contract_number_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(end_on__isnull=True) | models.Q(end_on__gte=models.F("start_on")),
                name="ppl_contract_dates_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(annual_compensation__gte=0),
                name="ppl_contract_pay_ck",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "status", "start_on"], name="ppl_contract_status_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        if self.employee_id and self.employee.company_id != self.company_id:
            raise ValidationError("An employment contract cannot cross companies")
        if self.department_id and self.department.company_id != self.company_id:
            raise ValidationError("An employment contract cannot cross departments")
        if len(self.currency.strip()) != 3:
            raise ValidationError({"currency": "Use a three-letter currency code"})
        if self.status == self.Status.ACTIVE and not self.approved_by_user_public_id:
            raise ValidationError("An active contract requires independent approval evidence")
        if self.approved_by_user_public_id == self.created_by_user_public_id:
            raise ValidationError("Contract maker and approver must be different users")


class LeavePolicy(TenantOwnedModel):
    class LeaveType(models.TextChoices):
        ANNUAL = "annual", "Annual leave"
        SICK = "sick", "Sick leave"
        CASUAL = "casual", "Casual leave"
        PARENTAL = "parental", "Parental leave"
        UNPAID = "unpaid", "Unpaid leave"

    code = models.CharField(max_length=60)
    name = models.CharField(max_length=180)
    leave_type = models.CharField(max_length=20, choices=LeaveType.choices)
    annual_days = models.DecimalField(max_digits=6, decimal_places=2)
    carry_forward_days = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0"))
    requires_approval = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "peopleops_leave_policy"
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="ppl_leave_policy_uq"),
            models.CheckConstraint(condition=models.Q(annual_days__gte=0), name="ppl_leave_days_ck"),
            models.CheckConstraint(condition=models.Q(carry_forward_days__gte=0), name="ppl_leave_carry_ck"),
        ]


class LeaveBalance(TenantOwnedModel):
    employee = models.ForeignKey(
        "employee.Employee",
        on_delete=models.PROTECT,
        related_name="leave_balances",
    )
    policy = models.ForeignKey(LeavePolicy, on_delete=models.PROTECT, related_name="balances")
    period_year = models.PositiveSmallIntegerField()
    opening_days = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("0"))
    accrued_days = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("0"))
    taken_days = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("0"))
    adjustment_days = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("0"))
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "peopleops_leave_balance"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "employee", "policy", "period_year"],
                name="ppl_leave_balance_uq",
            ),
            models.CheckConstraint(condition=models.Q(taken_days__gte=0), name="ppl_leave_taken_ck"),
        ]
        indexes = [
            models.Index(fields=["company", "employee", "period_year"], name="ppl_leave_balance_idx"),
        ]

    @property
    def available_days(self) -> Decimal:
        return self.opening_days + self.accrued_days + self.adjustment_days - self.taken_days

    def clean(self) -> None:
        super().clean()
        if self.employee_id and self.employee.company_id != self.company_id:
            raise ValidationError("A leave balance cannot cross companies")
        if self.policy_id and self.policy.company_id != self.company_id:
            raise ValidationError("A leave balance cannot cross companies")
        if self.available_days < 0:
            raise ValidationError("Leave balance cannot become negative")


class LeaveRequest(TenantOwnedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    employee = models.ForeignKey(
        "employee.Employee",
        on_delete=models.PROTECT,
        related_name="leave_requests",
    )
    policy = models.ForeignKey(LeavePolicy, on_delete=models.PROTECT, related_name="requests")
    start_on = models.DateField()
    end_on = models.DateField()
    requested_days = models.DecimalField(max_digits=6, decimal_places=2)
    reason = models.CharField(max_length=1000, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    requester_user_public_id = models.UUIDField()
    approver_membership = models.ForeignKey(
        "tenant.Membership",
        on_delete=models.PROTECT,
        related_name="leave_decisions",
        null=True,
        blank=True,
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.CharField(max_length=1000, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "peopleops_leave_request"
        ordering = ["-start_on", "-created_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(end_on__gte=models.F("start_on")), name="ppl_leave_dates_ck"),
            models.CheckConstraint(condition=models.Q(requested_days__gt=0), name="ppl_leave_request_days_ck"),
        ]
        indexes = [
            models.Index(fields=["company", "status", "start_on"], name="ppl_leave_request_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        if self.employee_id and self.employee.company_id != self.company_id:
            raise ValidationError("A leave request cannot cross companies")
        if self.policy_id and self.policy.company_id != self.company_id:
            raise ValidationError("A leave request cannot cross companies")
        if self.approver_membership_id and self.approver_membership.company_id != self.company_id:
            raise ValidationError("A leave approver cannot belong to another company")
        max_days = Decimal((self.end_on - self.start_on).days + 1)
        if self.requested_days > max_days:
            raise ValidationError("Requested leave days cannot exceed the calendar range")
        if self.status in {self.Status.APPROVED, self.Status.REJECTED} and not self.decided_at:
            raise ValidationError("A decided leave request requires decision evidence")


class Timesheet(TenantOwnedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    employee = models.ForeignKey(
        "employee.Employee",
        on_delete=models.PROTECT,
        related_name="timesheets",
    )
    week_start = models.DateField()
    total_hours = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("0"))
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    approver_membership = models.ForeignKey(
        "tenant.Membership",
        on_delete=models.PROTECT,
        related_name="timesheet_decisions",
        null=True,
        blank=True,
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.CharField(max_length=1000, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "peopleops_timesheet"
        ordering = ["-week_start", "employee_id"]
        constraints = [
            models.UniqueConstraint(fields=["company", "employee", "week_start"], name="ppl_timesheet_week_uq"),
            models.CheckConstraint(condition=models.Q(total_hours__gte=0), name="ppl_timesheet_hours_ck"),
        ]
        indexes = [
            models.Index(fields=["company", "status", "week_start"], name="ppl_timesheet_status_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        if self.employee_id and self.employee.company_id != self.company_id:
            raise ValidationError("A timesheet cannot cross companies")
        if self.approver_membership_id and self.approver_membership.company_id != self.company_id:
            raise ValidationError("A timesheet approver cannot belong to another company")
        if self.week_start.weekday() != 0:
            raise ValidationError({"week_start": "Timesheet week must start on Monday"})
        if self.total_hours > Decimal("168"):
            raise ValidationError("Weekly timesheet hours cannot exceed 168")


class TimesheetLine(TenantOwnedModel):
    timesheet = models.ForeignKey(Timesheet, on_delete=models.CASCADE, related_name="lines")
    work_date = models.DateField()
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.PROTECT,
        related_name="people_timesheet_lines",
        null=True,
        blank=True,
    )
    hours = models.DecimalField(max_digits=5, decimal_places=2)
    description = models.CharField(max_length=500, blank=True)

    class Meta:
        db_table = "peopleops_timesheet_line"
        constraints = [
            models.CheckConstraint(condition=models.Q(hours__gt=0) & models.Q(hours__lte=24), name="ppl_time_line_hours_ck"),
        ]
        indexes = [
            models.Index(fields=["company", "work_date"], name="ppl_time_line_date_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        if self.timesheet_id and self.timesheet.company_id != self.company_id:
            raise ValidationError("A timesheet line cannot cross companies")
        if self.project_id and self.project.company_id != self.company_id:
            raise ValidationError("A timesheet line project cannot cross companies")
        if self.timesheet_id:
            offset = (self.work_date - self.timesheet.week_start).days
            if not 0 <= offset <= 6:
                raise ValidationError("Timesheet line date must fall inside the selected week")


class PayrollRun(TenantOwnedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        LOCKED = "locked", "Locked"
        APPROVED = "approved", "Approved"
        POSTED = "posted", "Posted"
        CANCELLED = "cancelled", "Cancelled"

    code = models.CharField(max_length=80)
    period_start = models.DateField()
    period_end = models.DateField()
    currency = models.CharField(max_length=3)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    gross_total = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0"))
    deduction_total = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0"))
    net_total = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0"))
    created_by_user_public_id = models.UUIDField()
    approved_by_user_public_id = models.UUIDField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)
    evidence_sha256 = models.CharField(max_length=64, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "peopleops_payroll_run"
        ordering = ["-period_end", "code"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="ppl_payroll_code_uq"),
            models.CheckConstraint(condition=models.Q(period_end__gte=models.F("period_start")), name="ppl_payroll_dates_ck"),
            models.CheckConstraint(condition=models.Q(gross_total__gte=0), name="ppl_payroll_gross_ck"),
            models.CheckConstraint(condition=models.Q(deduction_total__gte=0), name="ppl_payroll_deduct_ck"),
            models.CheckConstraint(condition=models.Q(net_total__gte=0), name="ppl_payroll_net_ck"),
        ]
        indexes = [
            models.Index(fields=["company", "status", "period_end"], name="ppl_payroll_status_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        if len(self.currency.strip()) != 3:
            raise ValidationError({"currency": "Use a three-letter currency code"})
        if self.net_total != self.gross_total - self.deduction_total:
            raise ValidationError("Payroll net total must equal gross less deductions")
        if self.approved_by_user_public_id == self.created_by_user_public_id:
            raise ValidationError("Payroll maker and approver must be different users")
        if self.status in {self.Status.APPROVED, self.Status.POSTED} and not self.approved_at:
            raise ValidationError("Approved payroll requires approval evidence")
        if self.status == self.Status.POSTED and not self.posted_at:
            raise ValidationError("Posted payroll requires posting evidence")
        if self.evidence_sha256 and (len(self.evidence_sha256) != 64 or any(ch not in "0123456789abcdef" for ch in self.evidence_sha256.lower())):
            raise ValidationError({"evidence_sha256": "Use a lowercase SHA-256 digest"})


class PayrollEntry(TenantOwnedModel):
    payroll_run = models.ForeignKey(PayrollRun, on_delete=models.PROTECT, related_name="entries")
    employee = models.ForeignKey("employee.Employee", on_delete=models.PROTECT, related_name="payroll_entries")
    gross_amount = models.DecimalField(max_digits=18, decimal_places=2)
    deduction_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))
    net_amount = models.DecimalField(max_digits=18, decimal_places=2)
    components = models.JSONField(default=dict)
    evidence_sha256 = models.CharField(max_length=64)

    class Meta:
        db_table = "peopleops_payroll_entry"
        constraints = [
            models.UniqueConstraint(fields=["company", "payroll_run", "employee"], name="ppl_payroll_entry_uq"),
            models.CheckConstraint(condition=models.Q(gross_amount__gte=0), name="ppl_entry_gross_ck"),
            models.CheckConstraint(condition=models.Q(deduction_amount__gte=0), name="ppl_entry_deduct_ck"),
            models.CheckConstraint(condition=models.Q(net_amount__gte=0), name="ppl_entry_net_ck"),
        ]

    def clean(self) -> None:
        super().clean()
        if self.payroll_run_id and self.payroll_run.company_id != self.company_id:
            raise ValidationError("A payroll entry cannot cross companies")
        if self.employee_id and self.employee.company_id != self.company_id:
            raise ValidationError("A payroll entry cannot cross companies")
        if self.net_amount != self.gross_amount - self.deduction_amount:
            raise ValidationError("Payroll entry net must equal gross less deductions")
        if len(self.evidence_sha256) != 64:
            raise ValidationError({"evidence_sha256": "Use a SHA-256 digest"})


def payroll_entry_digest(*, run_code: str, employee_number: str, gross: Decimal, deductions: Decimal) -> str:
    payload = f"{run_code}:{employee_number}:{gross:.2f}:{deductions:.2f}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
