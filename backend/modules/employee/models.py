from django.db import models

from modules.platform.models import PublicIdModel, TimestampedModel
from modules.tenant.models import Company, Membership


class Employee(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="employees")
    membership = models.OneToOneField(
        Membership,
        on_delete=models.PROTECT,
        related_name="employee",
    )
    employee_number = models.CharField(max_length=50)
    job_title = models.CharField(max_length=150)
    employment_start = models.DateField()
    employment_end = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "employee_employee"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "employee_number"],
                name="employee_company_number_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(employment_end__isnull=True)
                | models.Q(employment_end__gte=models.F("employment_start")),
                name="employee_employment_range_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "employee_number"],
                name="employee_company_lookup_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.membership_id and self.company_id != self.membership.company_id:
            from django.core.exceptions import ValidationError

            raise ValidationError("Employee membership must belong to the same company")


class ReportingLine(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="reporting_lines",
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="manager_history",
    )
    manager = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="report_history",
    )
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "employee_reporting_line"
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(employee=models.F("manager")),
                name="reporting_line_no_self_manager",
            ),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gte=models.F("effective_from")),
                name="reporting_line_range_valid",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if (
            self.employee_id
            and self.manager_id
            and (
                self.company_id != self.employee.company_id
                or self.company_id != self.manager.company_id
            )
        ):
            from django.core.exceptions import ValidationError

            raise ValidationError("Reporting-line records cannot cross companies")

