from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from modules.platform.models import PublicIdModel, TimestampedModel
from modules.tenant.models import Company


def normalize_code(value: str) -> str:
    return value.strip().upper().replace(" ", "_").replace("-", "_")


class RiskTransferPolicyVersion(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="risk_transfer_policies")
    version = models.PositiveIntegerField(default=1)
    status_code = models.CharField(max_length=30, default="DRAFT")
    expiry_alert_days = models.PositiveIntegerField(default=45)
    claim_notification_sla_days = models.PositiveIntegerField(default=7)
    minimum_coverage_percent = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal("100.0000"))
    configuration = models.JSONField(default=dict, blank=True)
    effective_from = models.DateTimeField(null=True, blank=True)
    effective_to = models.DateTimeField(null=True, blank=True)
    published_by_public_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "riskxfer_policy"
        constraints = [
            models.UniqueConstraint(fields=["company", "version"], name="rx_policy_ver_uq"),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_from__isnull=True)
                | models.Q(effective_to__gt=models.F("effective_from")),
                name="rx_policy_dates_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(minimum_coverage_percent__gte=0)
                & models.Q(minimum_coverage_percent__lte=500),
                name="rx_policy_cover_ck",
            ),
        ]
        indexes = [models.Index(fields=["company", "status_code"], name="rx_policy_status_idx")]

    def clean(self) -> None:
        super().clean()
        self.status_code = normalize_code(self.status_code)


class RiskCounterparty(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="risk_counterparties")
    counterparty_code = models.CharField(max_length=80)
    legal_name = models.CharField(max_length=240)
    counterparty_type_code = models.CharField(max_length=60, default="INSURER")
    jurisdiction_code = models.CharField(max_length=80, blank=True)
    financial_rating_code = models.CharField(max_length=30, default="UNRATED")
    contact_data = models.JSONField(default=dict, blank=True)
    status_code = models.CharField(max_length=30, default="PENDING")
    created_by_public_id = models.UUIDField()
    verified_by_public_id = models.UUIDField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_note = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "riskxfer_counterparty"
        constraints = [
            models.UniqueConstraint(fields=["company", "counterparty_code"], name="rx_party_code_uq"),
        ]
        indexes = [
            models.Index(fields=["company", "status_code"], name="rx_party_status_idx"),
            models.Index(fields=["company", "counterparty_type_code"], name="rx_party_type_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.counterparty_code = normalize_code(self.counterparty_code)
        self.counterparty_type_code = normalize_code(self.counterparty_type_code)
        self.financial_rating_code = normalize_code(self.financial_rating_code)
        self.status_code = normalize_code(self.status_code)
        if not isinstance(self.contact_data, dict):
            raise ValidationError({"contact_data": "Counterparty contact data must be a JSON object."})


class InsuranceProgram(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="risk_insurance_programs")
    program_code = models.CharField(max_length=80)
    name = models.CharField(max_length=240)
    program_type_code = models.CharField(max_length=60, default="CONSTRUCTION_RISK")
    project_public_id = models.UUIDField(null=True, blank=True)
    contract_public_id = models.UUIDField(null=True, blank=True)
    status_code = models.CharField(max_length=30, default="DRAFT")
    currency_code = models.CharField(max_length=3, default="INR")
    aggregate_exposure = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    owner_public_id = models.UUIDField()
    starts_on = models.DateField(null=True, blank=True)
    ends_on = models.DateField(null=True, blank=True)
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "riskxfer_program"
        constraints = [
            models.UniqueConstraint(fields=["company", "program_code"], name="rx_program_code_uq"),
            models.CheckConstraint(condition=models.Q(aggregate_exposure__gte=0), name="rx_program_exposure_ck"),
        ]
        indexes = [
            models.Index(fields=["company", "status_code", "ends_on"], name="rx_program_status_idx"),
            models.Index(fields=["company", "project_public_id"], name="rx_program_proj_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.program_code = normalize_code(self.program_code)
        self.program_type_code = normalize_code(self.program_type_code)
        self.status_code = normalize_code(self.status_code)
        self.currency_code = self.currency_code.strip().upper()
        if self.starts_on and self.ends_on and self.ends_on < self.starts_on:
            raise ValidationError({"ends_on": "Program end date cannot precede the start date."})


class InsuranceCoverage(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="risk_coverages")
    program = models.ForeignKey(InsuranceProgram, on_delete=models.PROTECT, related_name="coverages")
    counterparty = models.ForeignKey(RiskCounterparty, on_delete=models.PROTECT, related_name="coverages")
    policy_number = models.CharField(max_length=120)
    coverage_type_code = models.CharField(max_length=80, default="CONSTRUCTION_ALL_RISK")
    insured_subject_type_code = models.CharField(max_length=60, default="PROGRAM")
    insured_subject_public_id = models.UUIDField(null=True, blank=True)
    coverage_limit = models.DecimalField(max_digits=20, decimal_places=2)
    deductible_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    annual_premium = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    currency_code = models.CharField(max_length=3, default="INR")
    starts_on = models.DateField()
    ends_on = models.DateField()
    status_code = models.CharField(max_length=30, default="DRAFT")
    created_by_public_id = models.UUIDField()
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "riskxfer_coverage"
        constraints = [
            models.UniqueConstraint(fields=["company", "policy_number"], name="rx_coverage_policy_uq"),
            models.CheckConstraint(condition=models.Q(coverage_limit__gt=0), name="rx_coverage_limit_ck"),
            models.CheckConstraint(condition=models.Q(deductible_amount__gte=0), name="rx_coverage_deduct_ck"),
            models.CheckConstraint(condition=models.Q(annual_premium__gte=0), name="rx_coverage_premium_ck"),
        ]
        indexes = [
            models.Index(fields=["company", "status_code", "ends_on"], name="rx_coverage_status_idx"),
            models.Index(fields=["company", "coverage_type_code"], name="rx_coverage_type_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.policy_number = normalize_code(self.policy_number)
        self.coverage_type_code = normalize_code(self.coverage_type_code)
        self.insured_subject_type_code = normalize_code(self.insured_subject_type_code)
        self.status_code = normalize_code(self.status_code)
        self.currency_code = self.currency_code.strip().upper()
        if self.program_id and self.program.company_id != self.company_id:
            raise ValidationError("Insurance coverage cannot cross companies.")
        if self.counterparty_id and self.counterparty.company_id != self.company_id:
            raise ValidationError("Coverage counterparty cannot cross companies.")
        if self.currency_code != self.program.currency_code:
            raise ValidationError("Coverage currency must match the insurance program currency.")
        if self.ends_on < self.starts_on:
            raise ValidationError({"ends_on": "Coverage end date cannot precede the start date."})
        if self.deductible_amount > self.coverage_limit:
            raise ValidationError("Deductible cannot exceed the coverage limit.")


class PremiumSchedule(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="risk_premium_schedules")
    coverage = models.ForeignKey(InsuranceCoverage, on_delete=models.PROTECT, related_name="premium_schedules")
    installment_number = models.CharField(max_length=80)
    due_on = models.DateField()
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    currency_code = models.CharField(max_length=3, default="INR")
    status_code = models.CharField(max_length=30, default="DUE")
    paid_on = models.DateField(null=True, blank=True)
    payment_reference = models.CharField(max_length=160, blank=True)
    created_by_public_id = models.UUIDField()
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "riskxfer_premium"
        constraints = [
            models.UniqueConstraint(fields=["coverage", "installment_number"], name="rx_premium_inst_uq"),
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="rx_premium_amount_ck"),
            models.CheckConstraint(condition=models.Q(paid_amount__gte=0), name="rx_premium_paid_ck"),
        ]
        indexes = [models.Index(fields=["company", "status_code", "due_on"], name="rx_premium_status_idx")]

    def clean(self) -> None:
        super().clean()
        self.installment_number = normalize_code(self.installment_number)
        self.status_code = normalize_code(self.status_code)
        self.currency_code = self.currency_code.strip().upper()
        if self.coverage_id and self.coverage.company_id != self.company_id:
            raise ValidationError("Premium schedule cannot cross companies.")
        if self.currency_code != self.coverage.currency_code:
            raise ValidationError("Premium currency must match the coverage currency.")
        if self.paid_amount > self.amount:
            raise ValidationError("Paid premium cannot exceed the installment amount.")


class LossEvent(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="risk_loss_events")
    program = models.ForeignKey(InsuranceProgram, on_delete=models.PROTECT, related_name="loss_events")
    loss_number = models.CharField(max_length=80)
    occurrence_on = models.DateTimeField()
    reported_on = models.DateTimeField()
    loss_type_code = models.CharField(max_length=80, default="PROPERTY_DAMAGE")
    description = models.TextField()
    estimated_loss = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    currency_code = models.CharField(max_length=3, default="INR")
    severity_code = models.CharField(max_length=30, default="MEDIUM")
    status_code = models.CharField(max_length=30, default="OPEN")
    reporter_public_id = models.UUIDField()
    closed_by_public_id = models.UUIDField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closure_note = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "riskxfer_loss"
        constraints = [
            models.UniqueConstraint(fields=["company", "loss_number"], name="rx_loss_number_uq"),
            models.CheckConstraint(condition=models.Q(estimated_loss__gte=0), name="rx_loss_estimate_ck"),
        ]
        indexes = [
            models.Index(fields=["company", "status_code", "reported_on"], name="rx_loss_status_idx"),
            models.Index(fields=["company", "severity_code"], name="rx_loss_severity_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.loss_number = normalize_code(self.loss_number)
        self.loss_type_code = normalize_code(self.loss_type_code)
        self.severity_code = normalize_code(self.severity_code)
        self.status_code = normalize_code(self.status_code)
        self.currency_code = self.currency_code.strip().upper()
        if self.program_id and self.program.company_id != self.company_id:
            raise ValidationError("Loss event cannot cross companies.")
        if self.currency_code != self.program.currency_code:
            raise ValidationError("Loss-event currency must match the insurance program currency.")
        if self.reported_on < self.occurrence_on:
            raise ValidationError({"reported_on": "Loss reporting time cannot precede occurrence time."})


class InsuranceClaim(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="risk_insurance_claims")
    loss_event = models.ForeignKey(LossEvent, on_delete=models.PROTECT, related_name="claims")
    coverage = models.ForeignKey(InsuranceCoverage, on_delete=models.PROTECT, related_name="claims")
    claim_number = models.CharField(max_length=120)
    notified_on = models.DateField()
    claimed_amount = models.DecimalField(max_digits=20, decimal_places=2)
    reserved_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    recovered_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    currency_code = models.CharField(max_length=3, default="INR")
    status_code = models.CharField(max_length=30, default="DRAFT")
    adjuster_reference = models.CharField(max_length=160, blank=True)
    created_by_public_id = models.UUIDField()
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    settlement_reference = models.CharField(max_length=160, blank=True)
    settled_on = models.DateField(null=True, blank=True)
    decision_note = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "riskxfer_claim"
        constraints = [
            models.UniqueConstraint(fields=["company", "claim_number"], name="rx_claim_number_uq"),
            models.CheckConstraint(condition=models.Q(claimed_amount__gt=0), name="rx_claim_amount_ck"),
            models.CheckConstraint(condition=models.Q(reserved_amount__gte=0), name="rx_claim_reserved_ck"),
            models.CheckConstraint(condition=models.Q(recovered_amount__gte=0), name="rx_claim_recovered_ck"),
        ]
        indexes = [models.Index(fields=["company", "status_code", "notified_on"], name="rx_claim_status_idx")]

    def clean(self) -> None:
        super().clean()
        self.claim_number = normalize_code(self.claim_number)
        self.status_code = normalize_code(self.status_code)
        self.currency_code = self.currency_code.strip().upper()
        if self.loss_event_id and self.loss_event.company_id != self.company_id:
            raise ValidationError("Insurance claim cannot cross companies.")
        if self.coverage_id and self.coverage.company_id != self.company_id:
            raise ValidationError("Claim coverage cannot cross companies.")
        if self.loss_event_id and self.coverage_id and self.loss_event.program_id != self.coverage.program_id:
            raise ValidationError("Claim loss and coverage must belong to the same insurance program.")
        if self.currency_code != self.coverage.currency_code:
            raise ValidationError("Claim currency must match the coverage currency.")
        if self.claimed_amount > self.coverage.coverage_limit:
            raise ValidationError("Claimed amount cannot exceed the coverage limit.")
        if self.recovered_amount > self.claimed_amount:
            raise ValidationError("Recovered amount cannot exceed the claimed amount.")


class GuaranteeInstrument(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="risk_guarantee_instruments")
    program = models.ForeignKey(InsuranceProgram, on_delete=models.PROTECT, related_name="guarantee_instruments")
    counterparty = models.ForeignKey(RiskCounterparty, on_delete=models.PROTECT, related_name="guarantee_instruments")
    instrument_number = models.CharField(max_length=120)
    instrument_type_code = models.CharField(max_length=80, default="PERFORMANCE_BOND")
    beneficiary_name = models.CharField(max_length=240)
    applicant_name = models.CharField(max_length=240)
    secured_obligation_public_id = models.UUIDField(null=True, blank=True)
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    currency_code = models.CharField(max_length=3, default="INR")
    issued_on = models.DateField()
    expiry_on = models.DateField()
    auto_renew_flag = models.BooleanField(default=False)
    status_code = models.CharField(max_length=30, default="DRAFT")
    created_by_public_id = models.UUIDField()
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "riskxfer_instrument"
        constraints = [
            models.UniqueConstraint(fields=["company", "instrument_number"], name="rx_instr_number_uq"),
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="rx_instr_amount_ck"),
        ]
        indexes = [
            models.Index(fields=["company", "status_code", "expiry_on"], name="rx_instr_status_idx"),
            models.Index(fields=["company", "instrument_type_code"], name="rx_instr_type_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.instrument_number = normalize_code(self.instrument_number)
        self.instrument_type_code = normalize_code(self.instrument_type_code)
        self.status_code = normalize_code(self.status_code)
        self.currency_code = self.currency_code.strip().upper()
        if self.program_id and self.program.company_id != self.company_id:
            raise ValidationError("Guarantee instrument cannot cross companies.")
        if self.counterparty_id and self.counterparty.company_id != self.company_id:
            raise ValidationError("Guarantee counterparty cannot cross companies.")
        if self.currency_code != self.program.currency_code:
            raise ValidationError("Guarantee currency must match the insurance program currency.")
        if self.expiry_on < self.issued_on:
            raise ValidationError({"expiry_on": "Guarantee expiry cannot precede issue date."})


class InstrumentCall(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="risk_instrument_calls")
    instrument = models.ForeignKey(GuaranteeInstrument, on_delete=models.PROTECT, related_name="calls")
    call_number = models.CharField(max_length=120)
    called_on = models.DateField()
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    currency_code = models.CharField(max_length=3, default="INR")
    reason = models.TextField()
    status_code = models.CharField(max_length=30, default="DRAFT")
    created_by_public_id = models.UUIDField()
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    settlement_reference = models.CharField(max_length=160, blank=True)
    settled_on = models.DateField(null=True, blank=True)
    decision_note = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "riskxfer_call"
        constraints = [
            models.UniqueConstraint(fields=["company", "call_number"], name="rx_call_number_uq"),
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="rx_call_amount_ck"),
        ]
        indexes = [models.Index(fields=["company", "status_code", "called_on"], name="rx_call_status_idx")]

    def clean(self) -> None:
        super().clean()
        self.call_number = normalize_code(self.call_number)
        self.status_code = normalize_code(self.status_code)
        self.currency_code = self.currency_code.strip().upper()
        if self.instrument_id and self.instrument.company_id != self.company_id:
            raise ValidationError("Guarantee call cannot cross companies.")
        if self.currency_code != self.instrument.currency_code:
            raise ValidationError("Guarantee-call currency must match the instrument currency.")
        if self.amount > self.instrument.amount:
            raise ValidationError("Guarantee-call amount cannot exceed the instrument amount.")


class RiskTransferEvent(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="risk_transfer_events")
    program = models.ForeignKey(InsuranceProgram, on_delete=models.PROTECT, related_name="events", null=True, blank=True)
    event_type_code = models.CharField(max_length=80)
    event_on = models.DateTimeField()
    summary = models.CharField(max_length=500)
    evidence = models.JSONField(default=dict, blank=True)
    actor_public_id = models.UUIDField()

    class Meta:
        db_table = "riskxfer_event"
        indexes = [
            models.Index(fields=["company", "event_on"], name="rx_event_time_idx"),
            models.Index(fields=["company", "event_type_code"], name="rx_event_type_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.event_type_code = normalize_code(self.event_type_code)
        if self.program_id and self.program.company_id != self.company_id:
            raise ValidationError("Risk-transfer event cannot cross companies.")
        if not isinstance(self.evidence, dict):
            raise ValidationError({"evidence": "Event evidence must be a JSON object."})
