from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from modules.platform.models import PublicIdModel, TimestampedModel
from modules.tenant.models import Company


def normalize_code(value: str) -> str:
    return value.strip().upper().replace(" ", "_").replace("-", "_")


class CapitalPolicyVersion(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="capital_policies")
    version = models.PositiveIntegerField(default=1)
    status_code = models.CharField(max_length=30, default="DRAFT")
    covenant_alert_days = models.PositiveIntegerField(default=30)
    commitment_expiry_alert_days = models.PositiveIntegerField(default=45)
    maximum_leverage_percent = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal("70.0000"))
    configuration = models.JSONField(default=dict, blank=True)
    effective_from = models.DateTimeField(null=True, blank=True)
    effective_to = models.DateTimeField(null=True, blank=True)
    published_by_public_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "capitalops_policy"
        constraints = [
            models.UniqueConstraint(fields=["company", "version"], name="cap_policy_ver_uq"),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_from__isnull=True)
                | models.Q(effective_to__gt=models.F("effective_from")),
                name="cap_policy_dates_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(maximum_leverage_percent__gte=0)
                & models.Q(maximum_leverage_percent__lte=100),
                name="cap_policy_lev_ck",
            ),
        ]
        indexes = [models.Index(fields=["company", "status_code"], name="cap_policy_status_idx")]

    def clean(self) -> None:
        super().clean()
        self.status_code = normalize_code(self.status_code)


class FundingProgram(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="capital_programs")
    program_code = models.CharField(max_length=80)
    name = models.CharField(max_length=240)
    program_type_code = models.CharField(max_length=60, default="PROJECT_FINANCE")
    project_public_id = models.UUIDField(null=True, blank=True)
    land_opportunity_public_id = models.UUIDField(null=True, blank=True)
    status_code = models.CharField(max_length=30, default="DRAFT")
    currency_code = models.CharField(max_length=3, default="INR")
    target_capital = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    target_equity = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    target_debt = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    sponsor_public_id = models.UUIDField()
    committee_public_id = models.UUIDField(null=True, blank=True)
    start_on = models.DateField(null=True, blank=True)
    target_close_on = models.DateField(null=True, blank=True)
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "capitalops_program"
        constraints = [
            models.UniqueConstraint(fields=["company", "program_code"], name="cap_program_code_uq"),
            models.CheckConstraint(condition=models.Q(target_capital__gte=0), name="cap_program_total_ck"),
            models.CheckConstraint(condition=models.Q(target_equity__gte=0), name="cap_program_equity_ck"),
            models.CheckConstraint(condition=models.Q(target_debt__gte=0), name="cap_program_debt_ck"),
        ]
        indexes = [
            models.Index(fields=["company", "status_code", "target_close_on"], name="cap_program_status_idx"),
            models.Index(fields=["company", "project_public_id"], name="cap_program_proj_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.program_code = normalize_code(self.program_code)
        self.program_type_code = normalize_code(self.program_type_code)
        self.status_code = normalize_code(self.status_code)
        self.currency_code = self.currency_code.strip().upper()
        if self.target_equity + self.target_debt > self.target_capital and self.target_capital > 0:
            raise ValidationError("Equity and debt targets cannot exceed the total capital target.")
        if self.start_on and self.target_close_on and self.target_close_on < self.start_on:
            raise ValidationError({"target_close_on": "Target close date cannot precede the program start date."})


class InvestorProfile(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="capital_investors")
    investor_code = models.CharField(max_length=80)
    legal_name = models.CharField(max_length=240)
    investor_type_code = models.CharField(max_length=60, default="INSTITUTIONAL")
    jurisdiction_code = models.CharField(max_length=80, blank=True)
    contact_data = models.JSONField(default=dict, blank=True)
    kyc_status_code = models.CharField(max_length=30, default="PENDING")
    risk_rating_code = models.CharField(max_length=30, default="MEDIUM")
    accredited_flag = models.BooleanField(default=False)
    created_by_public_id = models.UUIDField()
    verified_by_public_id = models.UUIDField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_note = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "capitalops_investor"
        constraints = [models.UniqueConstraint(fields=["company", "investor_code"], name="cap_investor_code_uq")]
        indexes = [
            models.Index(fields=["company", "kyc_status_code"], name="cap_investor_kyc_idx"),
            models.Index(fields=["company", "risk_rating_code"], name="cap_investor_risk_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.investor_code = normalize_code(self.investor_code)
        self.investor_type_code = normalize_code(self.investor_type_code)
        self.kyc_status_code = normalize_code(self.kyc_status_code)
        self.risk_rating_code = normalize_code(self.risk_rating_code)
        if not isinstance(self.contact_data, dict):
            raise ValidationError({"contact_data": "Investor contact data must be a JSON object."})


class JointVentureArrangement(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="capital_joint_ventures")
    program = models.ForeignKey(FundingProgram, on_delete=models.PROTECT, related_name="joint_ventures")
    venture_code = models.CharField(max_length=80)
    partner_name = models.CharField(max_length=240)
    partner_reference = models.UUIDField(null=True, blank=True)
    ownership_percent = models.DecimalField(max_digits=7, decimal_places=4)
    profit_share_percent = models.DecimalField(max_digits=7, decimal_places=4)
    governance = models.JSONField(default=dict, blank=True)
    status_code = models.CharField(max_length=30, default="DRAFT")
    created_by_public_id = models.UUIDField()
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "capitalops_joint_venture"
        constraints = [
            models.UniqueConstraint(fields=["program", "venture_code"], name="cap_jv_code_uq"),
            models.CheckConstraint(
                condition=models.Q(ownership_percent__gt=0) & models.Q(ownership_percent__lte=100),
                name="cap_jv_owner_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(profit_share_percent__gte=0) & models.Q(profit_share_percent__lte=100),
                name="cap_jv_profit_ck",
            ),
        ]
        indexes = [models.Index(fields=["company", "status_code"], name="cap_jv_status_idx")]

    def clean(self) -> None:
        super().clean()
        self.venture_code = normalize_code(self.venture_code)
        self.status_code = normalize_code(self.status_code)
        if self.program_id and self.program.company_id != self.company_id:
            raise ValidationError("Joint venture cannot cross companies.")
        if not isinstance(self.governance, dict):
            raise ValidationError({"governance": "Joint-venture governance must be a JSON object."})


class CapitalCommitment(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="capital_commitments")
    program = models.ForeignKey(FundingProgram, on_delete=models.PROTECT, related_name="commitments")
    investor = models.ForeignKey(InvestorProfile, on_delete=models.PROTECT, related_name="commitments", null=True, blank=True)
    joint_venture = models.ForeignKey(JointVentureArrangement, on_delete=models.PROTECT, related_name="commitments", null=True, blank=True)
    commitment_number = models.CharField(max_length=80)
    commitment_type_code = models.CharField(max_length=60, default="EQUITY")
    committed_amount = models.DecimalField(max_digits=20, decimal_places=2)
    called_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    funded_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    currency_code = models.CharField(max_length=3, default="INR")
    committed_on = models.DateField()
    expiry_on = models.DateField(null=True, blank=True)
    status_code = models.CharField(max_length=30, default="DRAFT")
    created_by_public_id = models.UUIDField()
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "capitalops_commitment"
        constraints = [
            models.UniqueConstraint(fields=["company", "commitment_number"], name="cap_commitment_no_uq"),
            models.CheckConstraint(condition=models.Q(committed_amount__gt=0), name="cap_commit_amount_ck"),
            models.CheckConstraint(condition=models.Q(called_amount__gte=0), name="cap_commit_called_ck"),
            models.CheckConstraint(condition=models.Q(funded_amount__gte=0), name="cap_commit_funded_ck"),
            models.CheckConstraint(
                condition=(models.Q(investor__isnull=False) & models.Q(joint_venture__isnull=True))
                | (models.Q(investor__isnull=True) & models.Q(joint_venture__isnull=False)),
                name="cap_commit_party_ck",
            ),
        ]
        indexes = [models.Index(fields=["company", "status_code", "expiry_on"], name="cap_commit_status_idx")]

    def clean(self) -> None:
        super().clean()
        self.commitment_number = normalize_code(self.commitment_number)
        self.commitment_type_code = normalize_code(self.commitment_type_code)
        self.status_code = normalize_code(self.status_code)
        self.currency_code = self.currency_code.strip().upper()
        if self.program_id and self.program.company_id != self.company_id:
            raise ValidationError("Capital commitment cannot cross companies.")
        if self.investor_id and self.investor.company_id != self.company_id:
            raise ValidationError("Investor cannot cross companies.")
        if self.joint_venture_id and self.joint_venture.company_id != self.company_id:
            raise ValidationError("Joint venture cannot cross companies.")
        if self.currency_code != self.program.currency_code:
            raise ValidationError("Commitment currency must match the funding program currency.")
        if self.called_amount > self.committed_amount:
            raise ValidationError("Called amount cannot exceed committed amount.")
        if self.funded_amount > self.called_amount:
            raise ValidationError("Funded amount cannot exceed called amount.")
        if self.expiry_on and self.expiry_on < self.committed_on:
            raise ValidationError({"expiry_on": "Commitment expiry cannot precede the commitment date."})


class DebtFacility(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="capital_debt_facilities")
    program = models.ForeignKey(FundingProgram, on_delete=models.PROTECT, related_name="debt_facilities")
    facility_code = models.CharField(max_length=80)
    lender_name = models.CharField(max_length=240)
    facility_type_code = models.CharField(max_length=60, default="TERM_LOAN")
    principal_limit = models.DecimalField(max_digits=20, decimal_places=2)
    currency_code = models.CharField(max_length=3, default="INR")
    interest_rate_percent = models.DecimalField(max_digits=9, decimal_places=6, default=0)
    tenor_months = models.PositiveIntegerField(default=12)
    start_on = models.DateField(null=True, blank=True)
    maturity_on = models.DateField(null=True, blank=True)
    status_code = models.CharField(max_length=30, default="DRAFT")
    security_summary = models.TextField(blank=True)
    covenants = models.JSONField(default=dict, blank=True)
    created_by_public_id = models.UUIDField()
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "capitalops_debt_facility"
        constraints = [
            models.UniqueConstraint(fields=["company", "facility_code"], name="cap_facility_code_uq"),
            models.CheckConstraint(condition=models.Q(principal_limit__gt=0), name="cap_facility_limit_ck"),
            models.CheckConstraint(condition=models.Q(interest_rate_percent__gte=0), name="cap_facility_rate_ck"),
        ]
        indexes = [models.Index(fields=["company", "status_code", "maturity_on"], name="cap_facility_status_idx")]

    def clean(self) -> None:
        super().clean()
        self.facility_code = normalize_code(self.facility_code)
        self.facility_type_code = normalize_code(self.facility_type_code)
        self.status_code = normalize_code(self.status_code)
        self.currency_code = self.currency_code.strip().upper()
        if self.program_id and self.program.company_id != self.company_id:
            raise ValidationError("Debt facility cannot cross companies.")
        if self.currency_code != self.program.currency_code:
            raise ValidationError("Facility currency must match the funding program currency.")
        if self.start_on and self.maturity_on and self.maturity_on <= self.start_on:
            raise ValidationError({"maturity_on": "Maturity date must be after the facility start date."})
        if not isinstance(self.covenants, dict):
            raise ValidationError({"covenants": "Facility covenants must be a JSON object."})


class DrawdownRequest(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="capital_drawdowns")
    program = models.ForeignKey(FundingProgram, on_delete=models.PROTECT, related_name="drawdowns")
    debt_facility = models.ForeignKey(DebtFacility, on_delete=models.PROTECT, related_name="drawdowns", null=True, blank=True)
    commitment = models.ForeignKey(CapitalCommitment, on_delete=models.PROTECT, related_name="drawdowns", null=True, blank=True)
    request_number = models.CharField(max_length=80)
    request_type_code = models.CharField(max_length=60, default="DEBT_DRAWDOWN")
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    currency_code = models.CharField(max_length=3, default="INR")
    requested_on = models.DateField()
    required_by = models.DateField(null=True, blank=True)
    purpose = models.TextField(blank=True)
    status_code = models.CharField(max_length=30, default="DRAFT")
    requested_by_public_id = models.UUIDField()
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    disbursed_on = models.DateField(null=True, blank=True)
    disbursement_reference = models.CharField(max_length=160, blank=True)
    decision_note = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "capitalops_drawdown"
        constraints = [
            models.UniqueConstraint(fields=["company", "request_number"], name="cap_drawdown_no_uq"),
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="cap_drawdown_amount_ck"),
            models.CheckConstraint(
                condition=(models.Q(debt_facility__isnull=False) & models.Q(commitment__isnull=True))
                | (models.Q(debt_facility__isnull=True) & models.Q(commitment__isnull=False)),
                name="cap_drawdown_source_ck",
            ),
        ]
        indexes = [models.Index(fields=["company", "status_code", "required_by"], name="cap_draw_status_idx")]

    def clean(self) -> None:
        super().clean()
        self.request_number = normalize_code(self.request_number)
        self.request_type_code = normalize_code(self.request_type_code)
        self.status_code = normalize_code(self.status_code)
        self.currency_code = self.currency_code.strip().upper()
        if self.program_id and self.program.company_id != self.company_id:
            raise ValidationError("Drawdown cannot cross companies.")
        if self.debt_facility_id:
            if self.debt_facility.company_id != self.company_id or self.debt_facility.program_id != self.program_id:
                raise ValidationError("Debt facility must belong to the same company and program.")
            if self.currency_code != self.debt_facility.currency_code:
                raise ValidationError("Drawdown currency must match the debt facility currency.")
        if self.commitment_id:
            if self.commitment.company_id != self.company_id or self.commitment.program_id != self.program_id:
                raise ValidationError("Commitment must belong to the same company and program.")
            if self.currency_code != self.commitment.currency_code:
                raise ValidationError("Drawdown currency must match the commitment currency.")
        if self.required_by and self.required_by < self.requested_on:
            raise ValidationError({"required_by": "Required-by date cannot precede requested date."})


class CovenantTest(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="capital_covenant_tests")
    debt_facility = models.ForeignKey(DebtFacility, on_delete=models.PROTECT, related_name="covenant_tests")
    test_number = models.CharField(max_length=80)
    covenant_code = models.CharField(max_length=80)
    tested_on = models.DateField()
    metric_value = models.DecimalField(max_digits=20, decimal_places=6)
    threshold_operator = models.CharField(max_length=10, default="LTE")
    threshold_value = models.DecimalField(max_digits=20, decimal_places=6)
    compliant = models.BooleanField(default=True)
    status_code = models.CharField(max_length=30, default="OPEN")
    evidence = models.JSONField(default=dict, blank=True)
    tested_by_public_id = models.UUIDField()
    reviewed_by_public_id = models.UUIDField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "capitalops_covenant"
        constraints = [models.UniqueConstraint(fields=["company", "test_number"], name="cap_covenant_no_uq")]
        indexes = [
            models.Index(fields=["company", "status_code", "tested_on"], name="cap_cov_status_idx"),
            models.Index(fields=["company", "compliant"], name="cap_cov_comp_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.test_number = normalize_code(self.test_number)
        self.covenant_code = normalize_code(self.covenant_code)
        self.threshold_operator = normalize_code(self.threshold_operator)
        self.status_code = normalize_code(self.status_code)
        if self.debt_facility_id and self.debt_facility.company_id != self.company_id:
            raise ValidationError("Covenant test cannot cross companies.")
        if self.threshold_operator not in {"LT", "LTE", "GT", "GTE", "EQ"}:
            raise ValidationError({"threshold_operator": "Unsupported covenant threshold operator."})
        if not isinstance(self.evidence, dict):
            raise ValidationError({"evidence": "Covenant evidence must be a JSON object."})


class InvestorDistribution(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="capital_distributions")
    program = models.ForeignKey(FundingProgram, on_delete=models.PROTECT, related_name="distributions")
    investor = models.ForeignKey(InvestorProfile, on_delete=models.PROTECT, related_name="distributions", null=True, blank=True)
    joint_venture = models.ForeignKey(JointVentureArrangement, on_delete=models.PROTECT, related_name="distributions", null=True, blank=True)
    distribution_number = models.CharField(max_length=80)
    distribution_type_code = models.CharField(max_length=60, default="RETURN_OF_CAPITAL")
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    currency_code = models.CharField(max_length=3, default="INR")
    declared_on = models.DateField()
    payable_on = models.DateField(null=True, blank=True)
    paid_on = models.DateField(null=True, blank=True)
    payment_reference = models.CharField(max_length=160, blank=True)
    status_code = models.CharField(max_length=30, default="DRAFT")
    created_by_public_id = models.UUIDField()
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "capitalops_distribution"
        constraints = [
            models.UniqueConstraint(fields=["company", "distribution_number"], name="cap_distribution_no_uq"),
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="cap_distribution_amt_ck"),
            models.CheckConstraint(
                condition=(models.Q(investor__isnull=False) & models.Q(joint_venture__isnull=True))
                | (models.Q(investor__isnull=True) & models.Q(joint_venture__isnull=False)),
                name="cap_distribution_party_ck",
            ),
        ]
        indexes = [models.Index(fields=["company", "status_code", "payable_on"], name="cap_dist_status_idx")]

    def clean(self) -> None:
        super().clean()
        self.distribution_number = normalize_code(self.distribution_number)
        self.distribution_type_code = normalize_code(self.distribution_type_code)
        self.status_code = normalize_code(self.status_code)
        self.currency_code = self.currency_code.strip().upper()
        if self.program_id and self.program.company_id != self.company_id:
            raise ValidationError("Distribution cannot cross companies.")
        if self.investor_id and self.investor.company_id != self.company_id:
            raise ValidationError("Investor cannot cross companies.")
        if self.joint_venture_id and self.joint_venture.company_id != self.company_id:
            raise ValidationError("Joint venture cannot cross companies.")
        if self.currency_code != self.program.currency_code:
            raise ValidationError("Distribution currency must match the funding program currency.")
        if self.payable_on and self.payable_on < self.declared_on:
            raise ValidationError({"payable_on": "Payable date cannot precede the declaration date."})


class CapitalEvent(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="capital_events")
    program = models.ForeignKey(FundingProgram, on_delete=models.PROTECT, related_name="events")
    event_type_code = models.CharField(max_length=60)
    event_on = models.DateTimeField()
    summary = models.CharField(max_length=500)
    evidence = models.JSONField(default=dict, blank=True)
    actor_public_id = models.UUIDField()

    class Meta:
        db_table = "capitalops_event"
        indexes = [models.Index(fields=["company", "program", "event_on"], name="cap_event_program_idx")]

    def clean(self) -> None:
        super().clean()
        self.event_type_code = normalize_code(self.event_type_code)
        if self.program_id and self.program.company_id != self.company_id:
            raise ValidationError("Capital event cannot cross companies.")
        if not isinstance(self.evidence, dict):
            raise ValidationError({"evidence": "Capital event evidence must be a JSON object."})
