from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from modules.platform.models import TenantOwnedModel

_SHA256_CHARS = frozenset("0123456789abcdef")


def _validate_sha256(value: str, field_name: str) -> None:
    normalized = value.lower()
    if len(normalized) != 64 or any(char not in _SHA256_CHARS for char in normalized):
        raise ValidationError({field_name: "A SHA-256 digest is required"})


class CustomerSuccessAccount(TenantOwnedModel):
    class Segment(models.TextChoices):
        PILOT = "pilot", "Pilot"
        STANDARD = "standard", "Standard"
        ENTERPRISE = "enterprise", "Enterprise"
        STRATEGIC = "strategic", "Strategic"

    class Status(models.TextChoices):
        ONBOARDING = "onboarding", "Onboarding"
        ACTIVE = "active", "Active"
        AT_RISK = "at_risk", "At risk"
        PAUSED = "paused", "Paused"
        CHURNED = "churned", "Churned"

    class RiskLevel(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    code = models.CharField(max_length=80)
    display_name = models.CharField(max_length=180)
    segment = models.CharField(max_length=20, choices=Segment.choices)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ONBOARDING,
    )
    account_owner = models.ForeignKey(
        "tenant.Membership",
        on_delete=models.PROTECT,
        related_name="success_accounts",
    )
    customer_since = models.DateField(default=timezone.localdate)
    renewal_on = models.DateField(null=True, blank=True)
    health_score = models.PositiveSmallIntegerField(default=50)
    risk_level = models.CharField(
        max_length=20,
        choices=RiskLevel.choices,
        default=RiskLevel.MEDIUM,
    )
    desired_outcomes = models.JSONField(default=list)
    risk_summary = models.CharField(max_length=1000, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "successops_account"
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="suc_account_code_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(health_score__gte=0, health_score__lte=100),
                name="suc_account_health_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "status", "risk_level"],
                name="suc_account_status_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.account_owner_id and self.account_owner.company_id != self.company_id:
            raise ValidationError("An account owner cannot belong to another company")
        if not isinstance(self.desired_outcomes, list):
            raise ValidationError({"desired_outcomes": "Desired outcomes must be a list"})
        if self.renewal_on and self.renewal_on < self.customer_since:
            raise ValidationError("Renewal date cannot precede the customer start date")


class BillingProfile(TenantOwnedModel):
    class BillingCycle(models.TextChoices):
        MONTHLY = "monthly", "Monthly"
        QUARTERLY = "quarterly", "Quarterly"
        ANNUAL = "annual", "Annual"
        CUSTOM = "custom", "Custom"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ON_HOLD = "on_hold", "On hold"
        CLOSED = "closed", "Closed"

    account = models.OneToOneField(
        CustomerSuccessAccount,
        on_delete=models.PROTECT,
        related_name="billing_profile",
    )
    legal_name = models.CharField(max_length=220)
    billing_email = models.EmailField()
    tax_identifier_masked = models.CharField(max_length=80, blank=True)
    currency = models.CharField(max_length=3)
    billing_cycle = models.CharField(max_length=20, choices=BillingCycle.choices)
    payment_terms_days = models.PositiveSmallIntegerField(default=30)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "successops_billing_profile"
        indexes = [
            models.Index(
                fields=["company", "status", "billing_cycle"],
                name="suc_bill_profile_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.account_id and self.account.company_id != self.company_id:
            raise ValidationError("A billing profile cannot cross companies")
        if not 1 <= self.payment_terms_days <= 365:
            raise ValidationError({"payment_terms_days": "Use a value from 1 to 365"})
        if len(self.currency.strip()) != 3:
            raise ValidationError({"currency": "Use a three-letter currency code"})


class SubscriptionInvoice(TenantOwnedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ISSUED = "issued", "Issued"
        PARTIALLY_PAID = "partially_paid", "Partially paid"
        PAID = "paid", "Paid"
        OVERDUE = "overdue", "Overdue"
        VOID = "void", "Void"

    account = models.ForeignKey(
        CustomerSuccessAccount,
        on_delete=models.PROTECT,
        related_name="subscription_invoices",
    )
    invoice_number = models.CharField(max_length=100)
    period_start = models.DateField()
    period_end = models.DateField()
    issued_on = models.DateField(null=True, blank=True)
    due_on = models.DateField(null=True, blank=True)
    currency = models.CharField(max_length=3)
    subtotal = models.DecimalField(max_digits=18, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))
    total_amount = models.DecimalField(max_digits=18, decimal_places=2)
    outstanding_amount = models.DecimalField(max_digits=18, decimal_places=2)
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    external_reference = models.CharField(max_length=240, blank=True)
    evidence_sha256 = models.CharField(max_length=64, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "successops_invoice"
        ordering = ["-period_end", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "invoice_number"],
                name="suc_invoice_number_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(subtotal__gte=0),
                name="suc_invoice_subtotal_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(tax_amount__gte=0),
                name="suc_invoice_tax_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(total_amount__gte=0),
                name="suc_invoice_total_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(outstanding_amount__gte=0),
                name="suc_invoice_due_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "status", "due_on"],
                name="suc_invoice_status_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.account_id and self.account.company_id != self.company_id:
            raise ValidationError("An invoice cannot cross companies")
        if self.period_end < self.period_start:
            raise ValidationError("Invoice period end cannot precede period start")
        if self.total_amount != self.subtotal + self.tax_amount:
            raise ValidationError("Invoice total must equal subtotal plus tax")
        if self.outstanding_amount > self.total_amount:
            raise ValidationError("Outstanding amount cannot exceed the invoice total")
        if self.status != self.Status.DRAFT and (not self.issued_on or not self.due_on):
            raise ValidationError("A non-draft invoice requires issue and due dates")
        if self.issued_on and self.due_on and self.due_on < self.issued_on:
            raise ValidationError("Invoice due date cannot precede issue date")
        if self.evidence_sha256:
            _validate_sha256(self.evidence_sha256, "evidence_sha256")


class PaymentRecord(TenantOwnedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        VERIFIED = "verified", "Verified"
        REVERSED = "reversed", "Reversed"

    invoice = models.ForeignKey(
        SubscriptionInvoice,
        on_delete=models.PROTECT,
        related_name="payments",
    )
    reference = models.CharField(max_length=140)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    received_at = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    evidence_sha256 = models.CharField(max_length=64)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "successops_payment"
        ordering = ["-received_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "reference"],
                name="suc_payment_reference_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="suc_payment_amount_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "status", "received_at"],
                name="suc_payment_status_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.invoice_id and self.invoice.company_id != self.company_id:
            raise ValidationError("A payment cannot cross companies")
        if self.amount <= 0:
            raise ValidationError({"amount": "Payment amount must be positive"})
        _validate_sha256(self.evidence_sha256, "evidence_sha256")


class SupportSlaPolicy(TenantOwnedModel):
    class Severity(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    code = models.CharField(max_length=100)
    severity = models.CharField(max_length=20, choices=Severity.choices)
    first_response_minutes = models.PositiveIntegerField()
    resolution_minutes = models.PositiveIntegerField()
    escalation_minutes = models.PositiveIntegerField()
    business_hours_only = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "successops_sla_policy"
        ordering = ["severity"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="suc_sla_code_uq",
            ),
            models.UniqueConstraint(
                fields=["company", "severity"],
                condition=models.Q(is_active=True),
                name="suc_sla_active_uq",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.escalation_minutes > self.resolution_minutes:
            raise ValidationError("Escalation must occur before the resolution deadline")
        if self.first_response_minutes > self.resolution_minutes:
            raise ValidationError("First-response target cannot exceed resolution target")


class SupportTicket(TenantOwnedModel):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        TRIAGE = "triage", "Triage"
        IN_PROGRESS = "in_progress", "In progress"
        WAITING_CUSTOMER = "waiting_customer", "Waiting for customer"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"

    account = models.ForeignKey(
        CustomerSuccessAccount,
        on_delete=models.PROTECT,
        related_name="support_tickets",
    )
    ticket_number = models.CharField(max_length=100)
    subject = models.CharField(max_length=240)
    description = models.CharField(max_length=2000)
    category = models.CharField(max_length=100, default="general")
    severity = models.CharField(max_length=20, choices=SupportSlaPolicy.Severity.choices)
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.OPEN,
    )
    requester_user_public_id = models.UUIDField()
    assigned_membership = models.ForeignKey(
        "tenant.Membership",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="assigned_support_tickets",
    )
    opened_at = models.DateTimeField(default=timezone.now)
    first_responded_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    response_due_at = models.DateTimeField()
    resolution_due_at = models.DateTimeField()
    escalated_at = models.DateTimeField(null=True, blank=True)
    resolution_summary = models.CharField(max_length=2000, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "successops_ticket"
        ordering = ["-opened_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "ticket_number"],
                name="suc_ticket_number_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "status", "severity"],
                name="suc_ticket_status_idx",
            ),
            models.Index(
                fields=["company", "resolution_due_at"],
                name="suc_ticket_due_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.account_id and self.account.company_id != self.company_id:
            raise ValidationError("A support ticket cannot cross companies")
        if self.assigned_membership_id and self.assigned_membership.company_id != self.company_id:
            raise ValidationError("A support ticket assignee cannot cross companies")
        if self.resolution_due_at < self.response_due_at:
            raise ValidationError("Resolution deadline cannot precede response deadline")
        if self.status in [self.Status.RESOLVED, self.Status.CLOSED] and not self.resolved_at:
            raise ValidationError("Resolved or closed tickets require a resolution timestamp")
        if self.status == self.Status.CLOSED and not self.resolution_summary:
            raise ValidationError("Closed tickets require a resolution summary")


class SuccessPlan(TenantOwnedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        AT_RISK = "at_risk", "At risk"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    account = models.ForeignKey(
        CustomerSuccessAccount,
        on_delete=models.PROTECT,
        related_name="success_plans",
    )
    code = models.CharField(max_length=100)
    title = models.CharField(max_length=240)
    objectives = models.JSONField(default=list)
    owner_membership = models.ForeignKey(
        "tenant.Membership",
        on_delete=models.PROTECT,
        related_name="owned_success_plans",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    next_review_on = models.DateField(null=True, blank=True)
    renewal_on = models.DateField(null=True, blank=True)
    health_score = models.PositiveSmallIntegerField(default=50)
    risk_summary = models.CharField(max_length=1000, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "successops_plan"
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="suc_plan_code_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(health_score__gte=0, health_score__lte=100),
                name="suc_plan_health_ck",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.account_id and self.account.company_id != self.company_id:
            raise ValidationError("A success plan cannot cross companies")
        if self.owner_membership_id and self.owner_membership.company_id != self.company_id:
            raise ValidationError("A success-plan owner cannot cross companies")
        if not isinstance(self.objectives, list):
            raise ValidationError({"objectives": "Objectives must be a list"})


class AdoptionSnapshot(TenantOwnedModel):
    company = models.ForeignKey(
        "tenant.Company",
        on_delete=models.PROTECT,
        related_name="customer_success_adoption_snapshots",
    )
    captured_on = models.DateField(default=timezone.localdate)
    active_users = models.PositiveIntegerField(default=0)
    active_projects = models.PositiveIntegerField(default=0)
    support_ticket_count = models.PositiveIntegerField(default=0)
    feature_utilization = models.JSONField(default=dict)
    adoption_score = models.PositiveSmallIntegerField(default=0)
    engagement_score = models.PositiveSmallIntegerField(default=0)
    evidence_sha256 = models.CharField(max_length=64)

    class Meta:
        db_table = "successops_adoption"
        ordering = ["-captured_on"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "captured_on"],
                name="suc_adoption_date_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(adoption_score__gte=0, adoption_score__lte=100),
                name="suc_adoption_score_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(engagement_score__gte=0, engagement_score__lte=100),
                name="suc_engagement_score_ck",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if not isinstance(self.feature_utilization, dict):
            raise ValidationError({"feature_utilization": "Use an object of feature metrics"})
        _validate_sha256(self.evidence_sha256, "evidence_sha256")
