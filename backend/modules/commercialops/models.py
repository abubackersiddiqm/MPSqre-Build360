from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from modules.platform.models import PublicIdModel, TimestampedModel
from modules.tenant.models import Company

ZERO = Decimal("0")
HUNDRED = Decimal("100")


def _code(value: str) -> str:
    return value.strip().upper()


def _require_code(configuration: dict[str, Any], key: str) -> None:
    value = configuration.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError({"configuration": f"{key} must be a non-empty code"})


def _require_codes(configuration: dict[str, Any], key: str) -> None:
    value = configuration.get(key)
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ValidationError(
            {"configuration": f"{key} must be a list of non-empty codes"}
        )


def _require_transitions(configuration: dict[str, Any], key: str) -> None:
    value = configuration.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValidationError({"configuration": f"{key} must be a list of objects"})


class CommercialPolicyVersion(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="commercial_policy_versions",
    )
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=200)
    version = models.PositiveIntegerField()
    status_code = models.CharField(max_length=80)
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    retired_at = models.DateTimeField(null=True, blank=True)
    configuration = models.JSONField(default=dict)
    change_note = models.TextField(blank=True)
    created_by_membership_public_id = models.UUIDField(null=True, blank=True)
    published_by_membership_public_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "commercialops_policy_version"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code", "version"], name="cops_pol_code_ver_uq"
            ),
            models.CheckConstraint(
                condition=Q(effective_to__isnull=True)
                | Q(effective_to__gt=F("effective_from")),
                name="cops_pol_range_ck",
            ),
            models.CheckConstraint(
                condition=Q(retired_at__isnull=True)
                | Q(published_at__isnull=False),
                name="cops_pol_retire_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "code", "published_at", "retired_at"],
                name="cops_pol_active_ix",
            )
        ]

    def clean(self) -> None:
        super().clean()
        self.code = _code(self.code)
        self.status_code = _code(self.status_code)
        if not isinstance(self.configuration, dict):
            raise ValidationError(
                {"configuration": "Commercial policy must be an object"}
            )
        for key in (
            "initial_contract_status",
            "initial_milestone_status",
            "initial_variation_status",
            "initial_payment_status",
            "initial_claim_status",
            "initial_eot_status",
            "initial_approval_status",
            "initial_risk_status",
            "resolved_risk_status",
        ):
            _require_code(self.configuration, key)
        for key in (
            "active_contract_statuses",
            "open_milestone_statuses",
            "open_variation_statuses",
            "open_payment_statuses",
            "open_claim_statuses",
            "open_eot_statuses",
            "critical_claim_priority_codes",
            "critical_risk_severity_codes",
        ):
            _require_codes(self.configuration, key)
        for key in (
            "contract_transitions",
            "milestone_transitions",
            "variation_transitions",
            "payment_transitions",
            "claim_transitions",
            "eot_transitions",
        ):
            _require_transitions(self.configuration, key)
        decisions = self.configuration.get("approval_decisions", {})
        if not isinstance(decisions, dict) or not decisions:
            raise ValidationError(
                {"configuration": "approval_decisions must be a non-empty object"}
            )
        if self.effective_to and self.effective_to <= self.effective_from:
            raise ValidationError(
                {"effective_to": "Effective end must follow effective start"}
            )
        if self.retired_at and not self.published_at:
            raise ValidationError({"retired_at": "A draft policy cannot be retired"})


class CommercialContract(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="commercial_contracts"
    )
    policy = models.ForeignKey(
        CommercialPolicyVersion,
        on_delete=models.PROTECT,
        related_name="contracts",
    )
    contract_number = models.CharField(max_length=120)
    project_public_id = models.UUIDField(null=True, blank=True)
    parent_contract_public_id = models.UUIDField(null=True, blank=True)
    counterparty_public_id = models.UUIDField(null=True, blank=True)
    counterparty_name = models.CharField(max_length=250)
    contract_type_code = models.CharField(max_length=100)
    procurement_route_code = models.CharField(max_length=100, blank=True)
    title = models.CharField(max_length=300)
    status_code = models.CharField(max_length=80)
    currency_code = models.CharField(max_length=3)
    original_value = models.DecimalField(max_digits=20, decimal_places=2, default=ZERO)
    approved_variation_value = models.DecimalField(
        max_digits=20, decimal_places=2, default=ZERO
    )
    current_contract_value = models.DecimalField(
        max_digits=20, decimal_places=2, default=ZERO
    )
    retention_percent = models.DecimalField(
        max_digits=7, decimal_places=4, default=ZERO
    )
    start_date = models.DateField()
    planned_completion_date = models.DateField()
    actual_completion_date = models.DateField(null=True, blank=True)
    owner_membership_public_id = models.UUIDField(null=True, blank=True)
    attributes = models.JSONField(default=dict)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "commercialops_contract"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "contract_number"], name="cops_con_number_uq"
            ),
            models.CheckConstraint(
                condition=Q(original_value__gte=0), name="cops_con_orig_ck"
            ),
            models.CheckConstraint(
                condition=Q(approved_variation_value__gte=0),
                name="cops_con_var_ck",
            ),
            models.CheckConstraint(
                condition=Q(current_contract_value__gte=0), name="cops_con_curr_ck"
            ),
            models.CheckConstraint(
                condition=Q(retention_percent__gte=0)
                & Q(retention_percent__lte=100),
                name="cops_con_ret_ck",
            ),
            models.CheckConstraint(
                condition=Q(planned_completion_date__gte=F("start_date")),
                name="cops_con_dates_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "status_code", "planned_completion_date"],
                name="cops_con_status_ix",
            ),
            models.Index(
                fields=["company", "project_public_id", "contract_type_code"],
                name="cops_con_project_ix",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        for field in (
            "contract_number",
            "contract_type_code",
            "status_code",
            "currency_code",
        ):
            setattr(self, field, _code(getattr(self, field)))
        self.procurement_route_code = (
            _code(self.procurement_route_code) if self.procurement_route_code else ""
        )
        if self.policy_id and self.company_id and self.policy.company_id != self.company_id:
            raise ValidationError("Commercial policy cannot cross companies")
        if self.planned_completion_date < self.start_date:
            raise ValidationError(
                {"planned_completion_date": "Completion cannot precede start"}
            )
        if self.actual_completion_date and self.actual_completion_date < self.start_date:
            raise ValidationError(
                {"actual_completion_date": "Completion cannot precede start"}
            )
        for field in (
            "original_value",
            "approved_variation_value",
            "current_contract_value",
            "retention_percent",
        ):
            if getattr(self, field) < ZERO:
                raise ValidationError({field: "Value cannot be negative"})
        if self.retention_percent > HUNDRED:
            raise ValidationError({"retention_percent": "Retention cannot exceed 100"})
        if not isinstance(self.attributes, dict):
            raise ValidationError({"attributes": "Contract attributes must be an object"})


class ContractMilestone(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="commercial_milestones"
    )
    policy = models.ForeignKey(
        CommercialPolicyVersion,
        on_delete=models.PROTECT,
        related_name="milestones",
    )
    contract = models.ForeignKey(
        CommercialContract, on_delete=models.PROTECT, related_name="milestones"
    )
    milestone_number = models.CharField(max_length=120)
    title = models.CharField(max_length=300)
    status_code = models.CharField(max_length=80)
    due_date = models.DateField()
    achieved_at = models.DateTimeField(null=True, blank=True)
    currency_code = models.CharField(max_length=3)
    milestone_value = models.DecimalField(max_digits=20, decimal_places=2, default=ZERO)
    weight_percent = models.DecimalField(max_digits=7, decimal_places=4, default=ZERO)
    evidence_reference = models.CharField(max_length=500, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "commercialops_milestone"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "contract", "milestone_number"],
                name="cops_milestone_uq",
            ),
            models.CheckConstraint(
                condition=Q(milestone_value__gte=0), name="cops_mile_value_ck"
            ),
            models.CheckConstraint(
                condition=Q(weight_percent__gte=0) & Q(weight_percent__lte=100),
                name="cops_mile_weight_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "status_code", "due_date"],
                name="cops_mile_due_ix",
            )
        ]

    def clean(self) -> None:
        super().clean()
        for field in ("milestone_number", "status_code", "currency_code"):
            setattr(self, field, _code(getattr(self, field)))
        if self.contract_id and self.company_id and self.contract.company_id != self.company_id:
            raise ValidationError("Contract milestone cannot cross companies")
        if self.policy_id and self.company_id and self.policy.company_id != self.company_id:
            raise ValidationError("Commercial policy cannot cross companies")
        if self.contract_id and self.policy_id and self.contract.policy_id != self.policy_id:
            raise ValidationError("Milestone policy must match contract policy")
        if self.contract_id and self.currency_code != self.contract.currency_code:
            raise ValidationError({"currency_code": "Milestone currency must match contract"})
        if self.milestone_value < ZERO:
            raise ValidationError({"milestone_value": "Value cannot be negative"})
        if self.weight_percent < ZERO or self.weight_percent > HUNDRED:
            raise ValidationError({"weight_percent": "Weight must be between 0 and 100"})


class VariationOrder(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="commercial_variations"
    )
    policy = models.ForeignKey(
        CommercialPolicyVersion,
        on_delete=models.PROTECT,
        related_name="variations",
    )
    contract = models.ForeignKey(
        CommercialContract, on_delete=models.PROTECT, related_name="variations"
    )
    variation_number = models.CharField(max_length=120)
    title = models.CharField(max_length=300)
    reason_code = models.CharField(max_length=100)
    status_code = models.CharField(max_length=80)
    currency_code = models.CharField(max_length=3)
    submitted_value = models.DecimalField(max_digits=20, decimal_places=2, default=ZERO)
    approved_value = models.DecimalField(
        max_digits=20, decimal_places=2, null=True, blank=True
    )
    time_impact_days = models.IntegerField(default=0)
    submitted_at = models.DateTimeField(null=True, blank=True)
    decision_due_at = models.DateTimeField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    requested_by_membership_public_id = models.UUIDField(null=True, blank=True)
    decided_by_membership_public_id = models.UUIDField(null=True, blank=True)
    description = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "commercialops_variation"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "contract", "variation_number"],
                name="cops_var_number_uq",
            ),
            models.CheckConstraint(
                condition=Q(submitted_value__gte=0), name="cops_var_sub_ck"
            ),
            models.CheckConstraint(
                condition=Q(approved_value__isnull=True) | Q(approved_value__gte=0),
                name="cops_var_appr_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "status_code", "decision_due_at"],
                name="cops_var_status_ix",
            )
        ]

    def clean(self) -> None:
        super().clean()
        for field in (
            "variation_number",
            "reason_code",
            "status_code",
            "currency_code",
        ):
            setattr(self, field, _code(getattr(self, field)))
        if self.contract_id and self.company_id and self.contract.company_id != self.company_id:
            raise ValidationError("Variation cannot cross companies")
        if self.policy_id and self.company_id and self.policy.company_id != self.company_id:
            raise ValidationError("Commercial policy cannot cross companies")
        if self.contract_id and self.policy_id and self.contract.policy_id != self.policy_id:
            raise ValidationError("Variation policy must match contract policy")
        if self.contract_id and self.currency_code != self.contract.currency_code:
            raise ValidationError({"currency_code": "Variation currency must match contract"})
        if self.submitted_value < ZERO:
            raise ValidationError({"submitted_value": "Value cannot be negative"})
        if self.approved_value is not None and self.approved_value < ZERO:
            raise ValidationError({"approved_value": "Value cannot be negative"})


class PaymentApplication(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="commercial_payments"
    )
    policy = models.ForeignKey(
        CommercialPolicyVersion,
        on_delete=models.PROTECT,
        related_name="payments",
    )
    contract = models.ForeignKey(
        CommercialContract, on_delete=models.PROTECT, related_name="payments"
    )
    application_number = models.CharField(max_length=120)
    period_start = models.DateField()
    period_end = models.DateField()
    status_code = models.CharField(max_length=80)
    currency_code = models.CharField(max_length=3)
    gross_claimed = models.DecimalField(max_digits=20, decimal_places=2, default=ZERO)
    certified_amount = models.DecimalField(
        max_digits=20, decimal_places=2, null=True, blank=True
    )
    retention_amount = models.DecimalField(max_digits=20, decimal_places=2, default=ZERO)
    deduction_amount = models.DecimalField(max_digits=20, decimal_places=2, default=ZERO)
    net_payable = models.DecimalField(
        max_digits=20, decimal_places=2, null=True, blank=True
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    certification_due_at = models.DateTimeField(null=True, blank=True)
    certified_at = models.DateTimeField(null=True, blank=True)
    applicant_membership_public_id = models.UUIDField(null=True, blank=True)
    certifier_membership_public_id = models.UUIDField(null=True, blank=True)
    description = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "commercialops_payment"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "contract", "application_number"],
                name="cops_pay_number_uq",
            ),
            models.CheckConstraint(
                condition=Q(period_end__gte=F("period_start")),
                name="cops_pay_period_ck",
            ),
            models.CheckConstraint(
                condition=Q(gross_claimed__gte=0), name="cops_pay_gross_ck"
            ),
            models.CheckConstraint(
                condition=Q(certified_amount__isnull=True)
                | Q(certified_amount__gte=0),
                name="cops_pay_cert_ck",
            ),
            models.CheckConstraint(
                condition=Q(retention_amount__gte=0), name="cops_pay_ret_ck"
            ),
            models.CheckConstraint(
                condition=Q(deduction_amount__gte=0), name="cops_pay_ded_ck"
            ),
            models.CheckConstraint(
                condition=Q(net_payable__isnull=True) | Q(net_payable__gte=0),
                name="cops_pay_net_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "status_code", "certification_due_at"],
                name="cops_pay_status_ix",
            )
        ]

    def clean(self) -> None:
        super().clean()
        for field in ("application_number", "status_code", "currency_code"):
            setattr(self, field, _code(getattr(self, field)))
        if self.contract_id and self.company_id and self.contract.company_id != self.company_id:
            raise ValidationError("Payment application cannot cross companies")
        if self.policy_id and self.company_id and self.policy.company_id != self.company_id:
            raise ValidationError("Commercial policy cannot cross companies")
        if self.contract_id and self.policy_id and self.contract.policy_id != self.policy_id:
            raise ValidationError("Payment policy must match contract policy")
        if self.contract_id and self.currency_code != self.contract.currency_code:
            raise ValidationError({"currency_code": "Payment currency must match contract"})
        if self.period_end < self.period_start:
            raise ValidationError({"period_end": "Period end cannot precede start"})
        for field in ("gross_claimed", "retention_amount", "deduction_amount"):
            if getattr(self, field) < ZERO:
                raise ValidationError({field: "Value cannot be negative"})
        for field in ("certified_amount", "net_payable"):
            value = getattr(self, field)
            if value is not None and value < ZERO:
                raise ValidationError({field: "Value cannot be negative"})
        if self.certified_amount is not None:
            expected = self.certified_amount - self.retention_amount - self.deduction_amount
            if expected < ZERO:
                raise ValidationError(
                    {"certified_amount": "Retention and deductions exceed certification"}
                )
            if self.net_payable is not None and self.net_payable != expected:
                raise ValidationError(
                    {"net_payable": "Net payable must equal certified less controls"}
                )


class CommercialClaim(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="commercial_claims"
    )
    policy = models.ForeignKey(
        CommercialPolicyVersion,
        on_delete=models.PROTECT,
        related_name="claims",
    )
    contract = models.ForeignKey(
        CommercialContract, on_delete=models.PROTECT, related_name="claims"
    )
    claim_number = models.CharField(max_length=120)
    claim_type_code = models.CharField(max_length=100)
    priority_code = models.CharField(max_length=80)
    cause_code = models.CharField(max_length=100)
    title = models.CharField(max_length=300)
    status_code = models.CharField(max_length=80)
    currency_code = models.CharField(max_length=3)
    claimed_amount = models.DecimalField(max_digits=20, decimal_places=2, default=ZERO)
    assessed_amount = models.DecimalField(
        max_digits=20, decimal_places=2, null=True, blank=True
    )
    event_date = models.DateField()
    notice_date = models.DateField(null=True, blank=True)
    response_due_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    claimant_party_public_id = models.UUIDField(null=True, blank=True)
    owner_membership_public_id = models.UUIDField(null=True, blank=True)
    description = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "commercialops_claim"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "contract", "claim_number"],
                name="cops_claim_number_uq",
            ),
            models.CheckConstraint(
                condition=Q(claimed_amount__gte=0), name="cops_claim_value_ck"
            ),
            models.CheckConstraint(
                condition=Q(assessed_amount__isnull=True)
                | Q(assessed_amount__gte=0),
                name="cops_claim_assess_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "status_code", "response_due_at"],
                name="cops_claim_status_ix",
            ),
            models.Index(
                fields=["company", "priority_code", "event_date"],
                name="cops_claim_priority_ix",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        for field in (
            "claim_number",
            "claim_type_code",
            "priority_code",
            "cause_code",
            "status_code",
            "currency_code",
        ):
            setattr(self, field, _code(getattr(self, field)))
        if self.contract_id and self.company_id and self.contract.company_id != self.company_id:
            raise ValidationError("Claim cannot cross companies")
        if self.policy_id and self.company_id and self.policy.company_id != self.company_id:
            raise ValidationError("Commercial policy cannot cross companies")
        if self.contract_id and self.policy_id and self.contract.policy_id != self.policy_id:
            raise ValidationError("Claim policy must match contract policy")
        if self.contract_id and self.currency_code != self.contract.currency_code:
            raise ValidationError({"currency_code": "Claim currency must match contract"})
        if self.claimed_amount < ZERO:
            raise ValidationError({"claimed_amount": "Value cannot be negative"})
        if self.assessed_amount is not None and self.assessed_amount < ZERO:
            raise ValidationError({"assessed_amount": "Value cannot be negative"})
        if self.notice_date and self.notice_date < self.event_date:
            raise ValidationError({"notice_date": "Notice cannot precede event"})


class ExtensionOfTime(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="commercial_eot_requests"
    )
    policy = models.ForeignKey(
        CommercialPolicyVersion,
        on_delete=models.PROTECT,
        related_name="eot_requests",
    )
    contract = models.ForeignKey(
        CommercialContract, on_delete=models.PROTECT, related_name="eot_requests"
    )
    claim = models.ForeignKey(
        CommercialClaim,
        on_delete=models.PROTECT,
        related_name="eot_requests",
        null=True,
        blank=True,
    )
    eot_number = models.CharField(max_length=120)
    reason_code = models.CharField(max_length=100)
    status_code = models.CharField(max_length=80)
    requested_days = models.PositiveIntegerField(default=0)
    assessed_days = models.PositiveIntegerField(null=True, blank=True)
    approved_days = models.PositiveIntegerField(null=True, blank=True)
    impact_start_date = models.DateField(null=True, blank=True)
    impact_end_date = models.DateField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    decision_due_at = models.DateTimeField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    requested_by_membership_public_id = models.UUIDField(null=True, blank=True)
    decided_by_membership_public_id = models.UUIDField(null=True, blank=True)
    description = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "commercialops_eot"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "contract", "eot_number"],
                name="cops_eot_number_uq",
            ),
            models.CheckConstraint(
                condition=Q(impact_end_date__isnull=True)
                | Q(impact_start_date__isnull=True)
                | Q(impact_end_date__gte=F("impact_start_date")),
                name="cops_eot_impact_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "status_code", "decision_due_at"],
                name="cops_eot_status_ix",
            )
        ]

    def clean(self) -> None:
        super().clean()
        for field in ("eot_number", "reason_code", "status_code"):
            setattr(self, field, _code(getattr(self, field)))
        if self.contract_id and self.company_id and self.contract.company_id != self.company_id:
            raise ValidationError("EOT request cannot cross companies")
        if self.policy_id and self.company_id and self.policy.company_id != self.company_id:
            raise ValidationError("Commercial policy cannot cross companies")
        if self.contract_id and self.policy_id and self.contract.policy_id != self.policy_id:
            raise ValidationError("EOT policy must match contract policy")
        if self.claim_id:
            if self.claim.company_id != self.company_id or self.claim.contract_id != self.contract_id:
                raise ValidationError("Linked claim must belong to the same tenant contract")
        if self.impact_start_date and self.impact_end_date:
            if self.impact_end_date < self.impact_start_date:
                raise ValidationError(
                    {"impact_end_date": "Impact end cannot precede impact start"}
                )


class CommercialApproval(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="commercial_approvals"
    )
    policy = models.ForeignKey(
        CommercialPolicyVersion,
        on_delete=models.PROTECT,
        related_name="approvals",
    )
    entity_type_code = models.CharField(max_length=100)
    entity_public_id = models.UUIDField()
    step_code = models.CharField(max_length=100)
    status_code = models.CharField(max_length=80)
    requested_by_membership_public_id = models.UUIDField()
    approver_membership_public_id = models.UUIDField(null=True, blank=True)
    requested_at = models.DateTimeField()
    due_at = models.DateTimeField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_code = models.CharField(max_length=80, blank=True)
    reason = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "commercialops_approval"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "entity_type_code", "entity_public_id", "step_code"],
                name="cops_approval_step_uq",
            ),
            models.CheckConstraint(
                condition=Q(decided_at__isnull=True) | ~Q(decision_code=""),
                name="cops_approval_dec_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "status_code", "due_at"],
                name="cops_approval_due_ix",
            )
        ]

    def clean(self) -> None:
        super().clean()
        for field in ("entity_type_code", "step_code", "status_code"):
            setattr(self, field, _code(getattr(self, field)))
        self.decision_code = _code(self.decision_code) if self.decision_code else ""
        if self.policy_id and self.company_id and self.policy.company_id != self.company_id:
            raise ValidationError("Commercial approval cannot cross companies")
        if self.decided_at and not self.decision_code:
            raise ValidationError({"decision_code": "Decision is required"})
        if (
            self.approver_membership_public_id
            and self.approver_membership_public_id
            == self.requested_by_membership_public_id
        ):
            raise ValidationError("Requester cannot approve their own commercial action")


class CommercialRisk(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="commercial_risks"
    )
    policy = models.ForeignKey(
        CommercialPolicyVersion,
        on_delete=models.PROTECT,
        related_name="risks",
    )
    contract = models.ForeignKey(
        CommercialContract,
        on_delete=models.PROTECT,
        related_name="commercial_risks",
        null=True,
        blank=True,
    )
    linked_entity_type_code = models.CharField(max_length=100)
    linked_entity_public_id = models.UUIDField(null=True, blank=True)
    risk_code = models.CharField(max_length=100)
    severity_code = models.CharField(max_length=80)
    status_code = models.CharField(max_length=80)
    message = models.TextField()
    due_at = models.DateTimeField(null=True, blank=True)
    assigned_membership_public_id = models.UUIDField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by_membership_public_id = models.UUIDField(null=True, blank=True)
    resolution_note = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "commercialops_risk"
        indexes = [
            models.Index(
                fields=["company", "status_code", "severity_code", "due_at"],
                name="cops_risk_open_ix",
            ),
            models.Index(
                fields=["company", "linked_entity_type_code", "linked_entity_public_id"],
                name="cops_risk_entity_ix",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        for field in (
            "linked_entity_type_code",
            "risk_code",
            "severity_code",
            "status_code",
        ):
            setattr(self, field, _code(getattr(self, field)))
        if self.policy_id and self.company_id and self.policy.company_id != self.company_id:
            raise ValidationError("Commercial risk cannot cross companies")
        if self.contract_id and self.company_id and self.contract.company_id != self.company_id:
            raise ValidationError("Commercial risk cannot cross companies")
        if self.contract_id and self.policy_id and self.contract.policy_id != self.policy_id:
            raise ValidationError("Risk policy must match contract policy")
        if self.resolved_at and not self.resolution_note.strip():
            raise ValidationError({"resolution_note": "Resolution note is required"})
