from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import models

from modules.platform.models import PublicIdModel, TimestampedModel
from modules.tenant.models import Company


class PayrollPolicyVersion(PublicIdModel, TimestampedModel):
    """Versioned, tenant-owned payroll control policy.

    Country rules, transitions, approval controls and calculation-adapter
    references live in ``configuration``. The model deliberately does not
    hardcode statutory formulae or workflow states.
    """

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="payroll_policy_versions",
    )
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=200)
    version = models.PositiveIntegerField(default=1)
    status_code = models.CharField(max_length=80)
    locale_code = models.CharField(max_length=35, blank=True)
    currency = models.CharField(max_length=3)
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    retired_at = models.DateTimeField(null=True, blank=True)
    configuration = models.JSONField(default=dict)
    change_note = models.CharField(max_length=500, blank=True)

    class Meta:
        db_table = "payroll_policy_version"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code", "version"],
                name="paypol_company_code_ver_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gt=models.F("effective_from")),
                name="paypol_effective_range_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(retired_at__isnull=True)
                | models.Q(published_at__isnull=False),
                name="paypol_retired_publish_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "code", "status_code"],
                name="paypol_company_status_idx",
            ),
            models.Index(
                fields=["company", "effective_from", "effective_to"],
                name="paypol_effective_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.effective_to and self.effective_to <= self.effective_from:
            raise ValidationError("Policy effective_to must be after effective_from")
        configuration = self.configuration or {}
        if not isinstance(configuration, dict):
            raise ValidationError({"configuration": "Configuration must be an object"})
        initial_run_status = configuration.get("initial_run_status")
        if (
            not isinstance(initial_run_status, str)
            or not initial_run_status.strip()
        ):
            raise ValidationError(
                {"configuration": "initial_run_status must be a non-empty string"}
            )
        for list_key in (
            "immutable_statuses",
            "run_creation_period_statuses",
            "run_types",
        ):
            configured_values = configuration.get(list_key, [])
            if not isinstance(configured_values, list) or any(
                not isinstance(item, str) or not item.strip()
                for item in configured_values
            ):
                raise ValidationError(
                    {"configuration": f"{list_key} must be a list of codes"}
                )
        transitions = configuration.get("transitions")
        if not isinstance(transitions, list):
            raise ValidationError(
                {"configuration": "transitions must be a list in configuration"}
            )
        transition_pairs: set[tuple[str, str]] = set()
        for index, transition in enumerate(transitions):
            if not isinstance(transition, dict):
                raise ValidationError(
                    {"configuration": f"Transition {index + 1} must be an object"}
                )
            for key in ("from", "to", "permission"):
                if (
                    not isinstance(transition.get(key), str)
                    or not transition[key].strip()
                ):
                    raise ValidationError(
                        {
                            "configuration": (
                                f"Transition {index + 1} requires non-empty {key}"
                            )
                        }
                    )
            source = transition["from"].strip()
            target = transition["to"].strip()
            if source == target:
                raise ValidationError(
                    {"configuration": f"Transition {index + 1} cannot be a self-loop"}
                )
            pair = (source, target)
            if pair in transition_pairs:
                raise ValidationError(
                    {"configuration": f"Transition {source} to {target} is duplicated"}
                )
            transition_pairs.add(pair)
            required_approvals = transition.get("required_approvals", [])
            if not isinstance(required_approvals, list):
                raise ValidationError(
                    {
                        "configuration": (
                            f"Transition {index + 1} required_approvals must be a list"
                        )
                    }
                )
            for approval_index, requirement in enumerate(required_approvals):
                if not isinstance(requirement, dict):
                    raise ValidationError(
                        {
                            "configuration": (
                                f"Transition {index + 1} approval "
                                f"{approval_index + 1} must be an object"
                            )
                        }
                    )
                step_code = requirement.get("step_code")
                accepted_statuses = requirement.get("accepted_statuses")
                if (
                    not isinstance(step_code, str)
                    or not step_code.strip()
                    or not isinstance(accepted_statuses, list)
                    or not accepted_statuses
                    or any(
                        not isinstance(item, str) or not item.strip()
                        for item in accepted_statuses
                    )
                ):
                    raise ValidationError(
                        {
                            "configuration": (
                                f"Transition {index + 1} approval "
                                f"{approval_index + 1} is incomplete"
                            )
                        }
                    )
        decision_rules = configuration.get("approval_decisions", {})
        if not isinstance(decision_rules, dict) or any(
            not isinstance(code, str)
            or not code.strip()
            or not isinstance(status, str)
            or not status.strip()
            for code, status in decision_rules.items()
        ):
            raise ValidationError(
                {"configuration": "approval_decisions must map decision to status"}
            )


class PayComponentDefinition(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="pay_component_definitions",
    )
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=200)
    version = models.PositiveIntegerField(default=1)
    component_type_code = models.CharField(max_length=80)
    calculation_method_code = models.CharField(max_length=80)
    unit_code = models.CharField(max_length=50, blank=True)
    currency = models.CharField(max_length=3, blank=True)
    taxable_policy_code = models.CharField(max_length=80, blank=True)
    ledger_mapping_code = models.CharField(max_length=100, blank=True)
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "payroll_component_definition"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code", "version"],
                name="paycomp_company_code_ver_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gt=models.F("effective_from")),
                name="paycomp_effective_range_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "code", "is_active"],
                name="paycomp_lookup_idx",
            )
        ]


class CompensationAssignment(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="compensation_assignments",
    )
    employee_public_id = models.UUIDField()
    employment_public_id = models.UUIDField(null=True, blank=True)
    compensation_plan_code = models.CharField(max_length=100)
    currency = models.CharField(max_length=3)
    annualized_cost = models.DecimalField(max_digits=18, decimal_places=2)
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(null=True, blank=True)
    source_reference = models.CharField(max_length=150, blank=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "payroll_comp_assignment"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "employee_public_id", "effective_from"],
                name="payassign_employee_from_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gt=models.F("effective_from")),
                name="payassign_effective_range_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(annualized_cost__gte=0),
                name="payassign_cost_nonneg_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "employee_public_id", "effective_from"],
                name="payassign_employee_idx",
            )
        ]


class PayrollPeriod(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="payroll_periods",
    )
    code = models.CharField(max_length=80)
    starts_on = models.DateField()
    ends_on = models.DateField()
    payment_due_on = models.DateField()
    status_code = models.CharField(max_length=80)
    lock_version = models.PositiveIntegerField(default=1)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "payroll_period"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="payperiod_company_code_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(ends_on__gte=models.F("starts_on")),
                name="payperiod_date_range_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(payment_due_on__gte=models.F("ends_on")),
                name="payperiod_due_date_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "starts_on", "ends_on"],
                name="payperiod_company_dates_idx",
            ),
            models.Index(
                fields=["company", "status_code"],
                name="payperiod_status_idx",
            ),
        ]


class PayrollRun(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="payroll_runs",
    )
    period = models.ForeignKey(
        PayrollPeriod,
        on_delete=models.PROTECT,
        related_name="runs",
    )
    policy = models.ForeignKey(
        PayrollPolicyVersion,
        on_delete=models.PROTECT,
        related_name="runs",
    )
    run_number = models.PositiveIntegerField(default=1)
    run_type_code = models.CharField(max_length=80)
    status_code = models.CharField(max_length=80)
    currency = models.CharField(max_length=3)
    version = models.PositiveIntegerField(default=1)
    initiated_by_public_id = models.UUIDField()
    calculated_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    gross_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    deduction_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    employer_cost_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    employee_count = models.PositiveIntegerField(default=0)
    exception_count = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "payroll_run"
        constraints = [
            models.UniqueConstraint(
                fields=["period", "run_number"],
                name="payrun_period_number_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(gross_amount__gte=0)
                & models.Q(deduction_amount__gte=0)
                & models.Q(employer_cost_amount__gte=0)
                & models.Q(net_amount__gte=0),
                name="payrun_amounts_nonneg_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    net_amount=models.F("gross_amount")
                    - models.F("deduction_amount")
                ),
                name="payrun_net_formula_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "status_code", "created_at"],
                name="payrun_company_status_idx",
            ),
            models.Index(
                fields=["company", "period", "run_number"],
                name="payrun_period_lookup_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.period_id and self.period.company_id != self.company_id:
            raise ValidationError("Payroll run period cannot cross companies")
        if self.policy_id and self.policy.company_id != self.company_id:
            raise ValidationError("Payroll run policy cannot cross companies")
        if self.policy_id and self.currency != self.policy.currency:
            raise ValidationError("Payroll run currency must match its policy currency")
        if self.net_amount != self.gross_amount - self.deduction_amount:
            raise ValidationError("Net amount must equal gross amount minus deductions")
        if not isinstance(self.metadata, dict):
            raise ValidationError({"metadata": "Payroll run metadata must be an object"})


class PayrollRunLine(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="payroll_run_lines",
    )
    run = models.ForeignKey(
        PayrollRun,
        on_delete=models.PROTECT,
        related_name="lines",
    )
    employee_public_id = models.UUIDField()
    employment_public_id = models.UUIDField(null=True, blank=True)
    currency = models.CharField(max_length=3)
    gross_amount = models.DecimalField(max_digits=18, decimal_places=2)
    deduction_amount = models.DecimalField(max_digits=18, decimal_places=2)
    employer_cost_amount = models.DecimalField(max_digits=18, decimal_places=2)
    net_amount = models.DecimalField(max_digits=18, decimal_places=2)
    status_code = models.CharField(max_length=80)
    exception_codes = models.JSONField(default=list, blank=True)
    component_breakdown = models.JSONField(default=list, blank=True)
    calculation_trace = models.JSONField(default=dict, blank=True)
    source_reference = models.CharField(max_length=150, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "payroll_run_line"
        constraints = [
            models.UniqueConstraint(
                fields=["run", "employee_public_id"],
                name="payline_run_employee_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(gross_amount__gte=0)
                & models.Q(deduction_amount__gte=0)
                & models.Q(employer_cost_amount__gte=0)
                & models.Q(net_amount__gte=0),
                name="payline_amounts_nonneg_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    net_amount=models.F("gross_amount")
                    - models.F("deduction_amount")
                ),
                name="payline_net_formula_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "employee_public_id", "created_at"],
                name="payline_employee_idx",
            ),
            models.Index(
                fields=["company", "status_code"],
                name="payline_status_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.run_id and self.run.company_id != self.company_id:
            raise ValidationError("Payroll line cannot cross companies")
        if self.run_id and self.currency != self.run.currency:
            raise ValidationError("Payroll line currency must match its run currency")
        if self.net_amount != self.gross_amount - self.deduction_amount:
            raise ValidationError("Net amount must equal gross amount minus deductions")
        if not isinstance(self.component_breakdown, list):
            raise ValidationError({"component_breakdown": "Must be a list"})
        if not isinstance(self.exception_codes, list):
            raise ValidationError({"exception_codes": "Must be a list"})
        if not isinstance(self.calculation_trace, dict):
            raise ValidationError({"calculation_trace": "Must be an object"})


class PayrollException(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="payroll_exceptions",
    )
    run = models.ForeignKey(
        PayrollRun,
        on_delete=models.PROTECT,
        related_name="exceptions",
    )
    employee_public_id = models.UUIDField(null=True, blank=True)
    exception_code = models.CharField(max_length=100)
    severity_code = models.CharField(max_length=80)
    status_code = models.CharField(max_length=80)
    message = models.CharField(max_length=500)
    owner_membership_public_id = models.UUIDField(null=True, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by_public_id = models.UUIDField(null=True, blank=True)
    resolution_note = models.CharField(max_length=500, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "payroll_exception"
        indexes = [
            models.Index(
                fields=["company", "status_code", "severity_code"],
                name="payexc_status_severity_idx",
            ),
            models.Index(
                fields=["company", "due_at", "resolved_at"],
                name="payexc_due_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.run_id and self.run.company_id != self.company_id:
            raise ValidationError("Payroll exception cannot cross companies")
        if self.resolved_at and not self.resolved_by_public_id:
            raise ValidationError("Resolved exceptions require a resolving actor")


class PayrollApproval(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="payroll_approvals",
    )
    run = models.ForeignKey(
        PayrollRun,
        on_delete=models.PROTECT,
        related_name="approvals",
    )
    step_code = models.CharField(max_length=100)
    status_code = models.CharField(max_length=80)
    requested_from_membership_public_id = models.UUIDField()
    requested_by_public_id = models.UUIDField()
    requested_at = models.DateTimeField()
    due_at = models.DateTimeField(null=True, blank=True)
    decided_by_public_id = models.UUIDField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_code = models.CharField(max_length=80, blank=True)
    decision_reason = models.CharField(max_length=500, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "payroll_approval"
        constraints = [
            models.UniqueConstraint(
                fields=["run", "step_code"],
                name="payapproval_run_step_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "status_code", "requested_at"],
                name="payapproval_status_idx",
            ),
            models.Index(
                fields=["company", "due_at", "decided_at"],
                name="payapproval_due_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.run_id and self.run.company_id != self.company_id:
            raise ValidationError("Payroll approval cannot cross companies")
        if self.decided_at and not self.decided_by_public_id:
            raise ValidationError("Decided approvals require a deciding actor")


class PayrollExportBatch(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="payroll_export_batches",
    )
    run = models.ForeignKey(
        PayrollRun,
        on_delete=models.PROTECT,
        related_name="export_batches",
    )
    export_type_code = models.CharField(max_length=100)
    provider_code = models.CharField(max_length=100, blank=True)
    status_code = models.CharField(max_length=80)
    object_key = models.CharField(max_length=500, blank=True)
    checksum_sha256 = models.CharField(max_length=64, blank=True)
    row_count = models.PositiveIntegerField(default=0)
    generated_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    released_by_public_id = models.UUIDField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "payroll_export_batch"
        constraints = [
            models.UniqueConstraint(
                fields=["run", "export_type_code", "provider_code"],
                name="payexport_run_type_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "status_code", "created_at"],
                name="payexport_status_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.run_id and self.run.company_id != self.company_id:
            raise ValidationError("Payroll export cannot cross companies")
        if self.released_at and not self.released_by_public_id:
            raise ValidationError("Released exports require a releasing actor")
        if self.checksum_sha256 and len(self.checksum_sha256) != 64:
            raise ValidationError({"checksum_sha256": "Expected a SHA-256 checksum"})


def decimal_string(value: Decimal | int | str) -> str:
    return f"{Decimal(value):.2f}"


def safe_metadata(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
