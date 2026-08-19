from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from modules.platform.models import TenantOwnedModel


class CommercialStage(TenantOwnedModel):
    class EntityType(models.TextChoices):
        BUDGET = "budget", "Budget"
        VARIATION = "variation", "Variation"
        INVOICE = "invoice", "Invoice"
        PAYMENT = "payment", "Payment"
        RETENTION = "retention", "Retention release"

    class Outcome(models.TextChoices):
        OPEN = "open", "Open"
        REVIEW = "review", "Under review"
        APPROVED = "approved", "Approved"
        POSTED = "posted", "Posted"
        PAID = "paid", "Paid"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"
        REVERSED = "reversed", "Reversed"
        CLOSED = "closed", "Closed"

    entity_type = models.CharField(max_length=30, choices=EntityType.choices)
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=160)
    outcome = models.CharField(max_length=20, choices=Outcome.choices, default=Outcome.OPEN)
    sort_order = models.PositiveIntegerField(default=100)
    allowed_next_codes = models.JSONField(default=list)
    is_initial = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "finance_commercial_stage"
        ordering = ["entity_type", "sort_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "entity_type", "code"],
                name="fin_stage_company_code_uq",
            ),
            models.CheckConstraint(
                condition=Q(effective_to__isnull=True)
                | Q(effective_to__gt=models.F("effective_from")),
                name="fin_stage_range_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "entity_type", "is_active", "sort_order"],
                name="fin_stage_active_idx",
            )
        ]


class FinancePolicy(TenantOwnedModel):
    enforce_maker_checker = models.BooleanField(default=False)
    allow_backdated_posting = models.BooleanField(default=False)
    default_retention_percent = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        default=Decimal("0"),
    )
    tax_configuration = models.JSONField(default=dict)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "finance_policy"
        constraints = [
            models.UniqueConstraint(fields=["company"], name="fin_policy_company_uq"),
            models.CheckConstraint(
                condition=Q(default_retention_percent__gte=0)
                & Q(default_retention_percent__lte=100),
                name="fin_policy_retention_valid",
            ),
        ]


class FinancialPeriod(TenantOwnedModel):
    code = models.CharField(max_length=30)
    name = models.CharField(max_length=120)
    starts_on = models.DateField()
    ends_on = models.DateField()
    locked_at = models.DateTimeField(null=True, blank=True)
    locked_by_public_id = models.UUIDField(null=True, blank=True)
    lock_reason = models.CharField(max_length=250, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "finance_period"
        ordering = ["-starts_on"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="fin_period_code_uq"),
            models.CheckConstraint(condition=Q(ends_on__gte=models.F("starts_on")), name="fin_period_dates_valid"),
        ]
        indexes = [
            models.Index(fields=["company", "starts_on", "ends_on"], name="fin_period_lookup_idx"),
            models.Index(fields=["company", "locked_at"], name="fin_period_lock_idx"),
        ]


class ProjectBudget(TenantOwnedModel):
    project = models.ForeignKey("projects.Project", on_delete=models.PROTECT, related_name="finance_budgets")
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=250)
    currency = models.CharField(max_length=3)
    stage = models.ForeignKey(CommercialStage, on_delete=models.PROTECT, related_name="budgets")
    approved_total = models.DecimalField(max_digits=20, decimal_places=4, default=Decimal("0"))
    forecast_total = models.DecimalField(max_digits=20, decimal_places=4, default=Decimal("0"))
    created_by_public_id = models.UUIDField()
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "finance_project_budget"
        constraints = [
            models.UniqueConstraint(fields=["company", "project", "code"], name="fin_budget_project_code_uq"),
            models.CheckConstraint(
                condition=Q(approved_total__gte=0) & Q(forecast_total__gte=0),
                name="fin_budget_totals_valid",
            ),
        ]
        indexes = [models.Index(fields=["company", "project", "stage"], name="fin_budget_lookup_idx")]

    def clean(self) -> None:
        super().clean()
        if self.project_id and self.project.company_id != self.company_id:
            raise ValidationError("Budget project cannot cross companies")
        if self.stage_id and (
            self.stage.company_id != self.company_id
            or self.stage.entity_type != CommercialStage.EntityType.BUDGET
        ):
            raise ValidationError("Budget requires a company budget stage")


class BudgetLine(TenantOwnedModel):
    budget = models.ForeignKey(ProjectBudget, on_delete=models.PROTECT, related_name="lines")
    cost_code = models.CharField(max_length=80)
    description = models.CharField(max_length=500)
    approved_amount = models.DecimalField(max_digits=20, decimal_places=4, default=Decimal("0"))
    committed_amount = models.DecimalField(max_digits=20, decimal_places=4, default=Decimal("0"))
    actual_amount = models.DecimalField(max_digits=20, decimal_places=4, default=Decimal("0"))
    accrued_amount = models.DecimalField(max_digits=20, decimal_places=4, default=Decimal("0"))
    forecast_amount = models.DecimalField(max_digits=20, decimal_places=4, default=Decimal("0"))

    class Meta:
        db_table = "finance_budget_line"
        constraints = [
            models.UniqueConstraint(fields=["company", "budget", "cost_code"], name="fin_budget_line_code_uq"),
            models.CheckConstraint(
                condition=Q(approved_amount__gte=0)
                & Q(committed_amount__gte=0)
                & Q(actual_amount__gte=0)
                & Q(accrued_amount__gte=0)
                & Q(forecast_amount__gte=0),
                name="fin_budget_line_values_ok",
            ),
        ]
        indexes = [models.Index(fields=["company", "budget", "cost_code"], name="fin_budget_line_idx")]

    def clean(self) -> None:
        super().clean()
        if self.budget_id and self.budget.company_id != self.company_id:
            raise ValidationError("Budget line cannot cross companies")


class Variation(TenantOwnedModel):
    class VariationType(models.TextChoices):
        CLIENT = "client", "Client variation"
        VENDOR = "vendor", "Vendor variation"
        INTERNAL = "internal", "Internal variation"

    project = models.ForeignKey("projects.Project", on_delete=models.PROTECT, related_name="variations")
    variation_number = models.CharField(max_length=80)
    title = models.CharField(max_length=250)
    variation_type = models.CharField(max_length=20, choices=VariationType.choices)
    stage = models.ForeignKey(CommercialStage, on_delete=models.PROTECT, related_name="variations")
    currency = models.CharField(max_length=3)
    amount_ex_tax = models.DecimalField(max_digits=20, decimal_places=4)
    tax_amount = models.DecimalField(max_digits=20, decimal_places=4, default=Decimal("0"))
    total_amount = models.DecimalField(max_digits=20, decimal_places=4)
    reason = models.TextField(blank=True)
    created_by_public_id = models.UUIDField()
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "finance_variation"
        constraints = [
            models.UniqueConstraint(fields=["company", "variation_number"], name="fin_variation_number_uq"),
            models.CheckConstraint(
                condition=Q(amount_ex_tax__gte=0) & Q(tax_amount__gte=0) & Q(total_amount__gte=0),
                name="fin_variation_amounts_valid",
            ),
        ]
        indexes = [models.Index(fields=["company", "project", "stage"], name="fin_variation_lookup_idx")]

    def clean(self) -> None:
        super().clean()
        if self.project_id and self.project.company_id != self.company_id:
            raise ValidationError("Variation project cannot cross companies")
        if self.stage_id and (
            self.stage.company_id != self.company_id
            or self.stage.entity_type != CommercialStage.EntityType.VARIATION
        ):
            raise ValidationError("Variation requires a company variation stage")
        if self.total_amount != self.amount_ex_tax + self.tax_amount:
            raise ValidationError("Variation total must equal amount plus tax")


class Invoice(TenantOwnedModel):
    class InvoiceType(models.TextChoices):
        CLIENT = "client", "Client invoice"
        VENDOR = "vendor", "Vendor invoice"

    project = models.ForeignKey("projects.Project", on_delete=models.PROTECT, related_name="finance_invoices")
    period = models.ForeignKey(FinancialPeriod, on_delete=models.PROTECT, related_name="invoices")
    invoice_number = models.CharField(max_length=80)
    invoice_type = models.CharField(max_length=20, choices=InvoiceType.choices)
    counterparty_name = models.CharField(max_length=250)
    counterparty_reference = models.CharField(max_length=120, blank=True)
    stage = models.ForeignKey(CommercialStage, on_delete=models.PROTECT, related_name="invoices")
    currency = models.CharField(max_length=3)
    invoice_date = models.DateField()
    due_date = models.DateField()
    subtotal = models.DecimalField(max_digits=20, decimal_places=4)
    tax_amount = models.DecimalField(max_digits=20, decimal_places=4, default=Decimal("0"))
    retention_amount = models.DecimalField(max_digits=20, decimal_places=4, default=Decimal("0"))
    total_amount = models.DecimalField(max_digits=20, decimal_places=4)
    outstanding_amount = models.DecimalField(max_digits=20, decimal_places=4)
    source_type = models.CharField(max_length=80, blank=True)
    source_public_id = models.UUIDField(null=True, blank=True)
    created_by_public_id = models.UUIDField()
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)
    reversed_at = models.DateTimeField(null=True, blank=True)
    reversal_of = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="reversals")
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "finance_invoice"
        constraints = [
            models.UniqueConstraint(fields=["company", "invoice_type", "invoice_number"], name="fin_invoice_number_uq"),
            models.CheckConstraint(
                condition=Q(subtotal__gte=0)
                & Q(tax_amount__gte=0)
                & Q(retention_amount__gte=0)
                & Q(total_amount__gte=0)
                & Q(outstanding_amount__gte=0),
                name="fin_invoice_amounts_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "project", "stage"], name="fin_invoice_lookup_idx"),
            models.Index(fields=["company", "due_date", "outstanding_amount"], name="fin_invoice_ageing_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        if self.project_id and self.project.company_id != self.company_id:
            raise ValidationError("Invoice project cannot cross companies")
        if self.period_id and self.period.company_id != self.company_id:
            raise ValidationError("Invoice period cannot cross companies")
        if self.stage_id and (
            self.stage.company_id != self.company_id
            or self.stage.entity_type != CommercialStage.EntityType.INVOICE
        ):
            raise ValidationError("Invoice requires a company invoice stage")
        if self.due_date < self.invoice_date:
            raise ValidationError("Invoice due date cannot precede invoice date")
        if self.total_amount != self.subtotal + self.tax_amount:
            raise ValidationError("Invoice total must equal subtotal plus tax")
        if self.retention_amount > self.total_amount:
            raise ValidationError("Retention cannot exceed invoice total")
        if self.outstanding_amount > self.total_amount:
            raise ValidationError("Outstanding amount cannot exceed invoice total")


class InvoiceLine(TenantOwnedModel):
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="lines")
    line_number = models.PositiveIntegerField()
    cost_code = models.CharField(max_length=80)
    description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=20, decimal_places=4)
    unit_rate = models.DecimalField(max_digits=20, decimal_places=4)
    tax_rate_percent = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal("0"))
    amount = models.DecimalField(max_digits=20, decimal_places=4)
    tax_amount = models.DecimalField(max_digits=20, decimal_places=4)
    total_amount = models.DecimalField(max_digits=20, decimal_places=4)

    class Meta:
        db_table = "finance_invoice_line"
        constraints = [
            models.UniqueConstraint(fields=["company", "invoice", "line_number"], name="fin_invoice_line_number_uq"),
            models.CheckConstraint(
                condition=Q(quantity__gte=0)
                & Q(unit_rate__gte=0)
                & Q(tax_rate_percent__gte=0)
                & Q(tax_rate_percent__lte=100)
                & Q(amount__gte=0)
                & Q(tax_amount__gte=0)
                & Q(total_amount__gte=0),
                name="fin_invoice_line_values_ok",
            ),
        ]
        indexes = [models.Index(fields=["company", "invoice", "line_number"], name="fin_invoice_line_idx")]

    def clean(self) -> None:
        super().clean()
        if self.invoice_id and self.invoice.company_id != self.company_id:
            raise ValidationError("Invoice line cannot cross companies")


class Payment(TenantOwnedModel):
    class PaymentType(models.TextChoices):
        STANDARD = "standard", "Standard payment"
        RETENTION_RELEASE = "retention_release", "Retention release"

    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="payments")
    period = models.ForeignKey(FinancialPeriod, on_delete=models.PROTECT, related_name="payments")
    payment_number = models.CharField(max_length=80)
    payment_type = models.CharField(max_length=30, choices=PaymentType.choices, default=PaymentType.STANDARD)
    stage = models.ForeignKey(CommercialStage, on_delete=models.PROTECT, related_name="payments")
    currency = models.CharField(max_length=3)
    amount = models.DecimalField(max_digits=20, decimal_places=4)
    paid_on = models.DateField()
    reference = models.CharField(max_length=160, blank=True)
    created_by_public_id = models.UUIDField()
    posted_by_public_id = models.UUIDField(null=True, blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)
    reversed_at = models.DateTimeField(null=True, blank=True)
    reversal_of = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="reversals")
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "finance_payment"
        constraints = [
            models.UniqueConstraint(fields=["company", "payment_number"], name="fin_payment_number_uq"),
            models.CheckConstraint(condition=Q(amount__gt=0), name="fin_payment_amount_positive"),
        ]
        indexes = [models.Index(fields=["company", "invoice", "stage"], name="fin_payment_lookup_idx")]

    def clean(self) -> None:
        super().clean()
        if self.invoice_id and self.invoice.company_id != self.company_id:
            raise ValidationError("Payment invoice cannot cross companies")
        if self.period_id and self.period.company_id != self.company_id:
            raise ValidationError("Payment period cannot cross companies")
        if self.stage_id and (
            self.stage.company_id != self.company_id
            or self.stage.entity_type != CommercialStage.EntityType.PAYMENT
        ):
            raise ValidationError("Payment requires a company payment stage")
        if self.currency != self.invoice.currency:
            raise ValidationError("Payment currency must match invoice currency")


class CommercialAdjustment(TenantOwnedModel):
    class EntryType(models.TextChoices):
        COMMITMENT = "commitment", "Commitment"
        ACTUAL = "actual", "Actual"
        ACCRUAL = "accrual", "Accrual"
        FORECAST = "forecast", "Forecast"

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.PROTECT,
        related_name="commercial_adjustments",
    )
    period = models.ForeignKey(
        FinancialPeriod,
        on_delete=models.PROTECT,
        related_name="adjustments",
    )
    posting_number = models.CharField(max_length=80)
    entry_type = models.CharField(max_length=30, choices=EntryType.choices)
    cost_code = models.CharField(max_length=80)
    amount = models.DecimalField(max_digits=20, decimal_places=4)
    currency = models.CharField(max_length=3)
    description = models.CharField(max_length=500)
    created_by_public_id = models.UUIDField()
    posted_at = models.DateTimeField()
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "finance_commercial_adjustment"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "posting_number"],
                name="fin_adjustment_number_uq",
            ),
            models.CheckConstraint(
                condition=~Q(amount=0),
                name="fin_adjustment_nonzero",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "project", "period", "entry_type"],
                name="fin_adjustment_lookup_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.project_id and self.project.company_id != self.company_id:
            raise ValidationError("Commercial adjustment project cannot cross companies")
        if self.period_id and self.period.company_id != self.company_id:
            raise ValidationError("Commercial adjustment period cannot cross companies")


class CommercialLedgerEntry(TenantOwnedModel):
    class EntryType(models.TextChoices):
        BUDGET = "budget", "Budget"
        COMMITMENT = "commitment", "Commitment"
        ACTUAL = "actual", "Actual"
        ACCRUAL = "accrual", "Accrual"
        FORECAST = "forecast", "Forecast"
        VARIATION = "variation", "Variation"
        INVOICE = "invoice", "Invoice"
        PAYMENT = "payment", "Payment"
        RETENTION = "retention", "Retention"
        REVERSAL = "reversal", "Reversal"

    project = models.ForeignKey("projects.Project", on_delete=models.PROTECT, related_name="commercial_ledger")
    period = models.ForeignKey(FinancialPeriod, on_delete=models.PROTECT, related_name="ledger_entries")
    entry_type = models.CharField(max_length=30, choices=EntryType.choices)
    cost_code = models.CharField(max_length=80, blank=True)
    amount = models.DecimalField(max_digits=20, decimal_places=4)
    currency = models.CharField(max_length=3)
    source_type = models.CharField(max_length=80)
    source_public_id = models.UUIDField()
    source_line_key = models.CharField(max_length=120, blank=True)
    occurred_at = models.DateTimeField()
    posted_by_public_id = models.UUIDField()
    description = models.CharField(max_length=500, blank=True)
    reversal_of = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="reversals")

    class Meta:
        db_table = "finance_commercial_ledger"
        ordering = ["-occurred_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "source_type", "source_public_id", "source_line_key", "entry_type"],
                name="fin_ledger_source_fact_uq",
            ),
            models.CheckConstraint(condition=~Q(amount=0), name="fin_ledger_amount_nonzero"),
        ]
        indexes = [
            models.Index(fields=["company", "project", "period", "entry_type"], name="fin_ledger_project_idx"),
            models.Index(fields=["company", "source_type", "source_public_id"], name="fin_ledger_source_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        if self.project_id and self.project.company_id != self.company_id:
            raise ValidationError("Ledger project cannot cross companies")
        if self.period_id and self.period.company_id != self.company_id:
            raise ValidationError("Ledger period cannot cross companies")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk:
            raise ValidationError("Commercial ledger entries are append-only")
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("Commercial ledger entries are append-only")
