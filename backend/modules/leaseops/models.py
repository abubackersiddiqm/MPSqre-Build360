from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from modules.platform.models import PublicIdModel, TimestampedModel
from modules.tenant.models import Company


def normalize_code(value: str) -> str:
    return value.strip().upper().replace(" ", "_").replace("-", "_")


class PropertyPolicyVersion(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="property_lease_policies")
    version = models.PositiveIntegerField(default=1)
    status_code = models.CharField(max_length=30, default="DRAFT")
    lease_expiry_alert_days = models.PositiveIntegerField(default=90)
    invoice_grace_days = models.PositiveIntegerField(default=5)
    case_response_minutes = models.PositiveIntegerField(default=240)
    case_resolution_minutes = models.PositiveIntegerField(default=2880)
    configuration = models.JSONField(default=dict, blank=True)
    effective_from = models.DateTimeField(null=True, blank=True)
    effective_to = models.DateTimeField(null=True, blank=True)
    published_by_public_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "leaseops_policy"
        constraints = [
            models.UniqueConstraint(fields=["company", "version"], name="lea_policy_ver_uq"),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_from__isnull=True)
                | models.Q(effective_to__gt=models.F("effective_from")),
                name="lea_policy_dates_ck",
            ),
        ]
        indexes = [models.Index(fields=["company", "status_code"], name="lea_policy_status_idx")]

    def clean(self) -> None:
        super().clean()
        self.status_code = normalize_code(self.status_code)


class ManagedProperty(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="managed_properties")
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=240)
    property_type_code = models.CharField(max_length=60, default="RESIDENTIAL")
    facility_public_id = models.UUIDField(null=True, blank=True)
    project_public_id = models.UUIDField(null=True, blank=True)
    external_reference = models.CharField(max_length=160, blank=True)
    address = models.JSONField(default=dict, blank=True)
    timezone = models.CharField(max_length=80, blank=True)
    gross_area = models.DecimalField(max_digits=18, decimal_places=3, null=True, blank=True)
    area_unit_code = models.CharField(max_length=30, default="SQ_M")
    ownership_code = models.CharField(max_length=40, default="OWNED")
    status_code = models.CharField(max_length=30, default="ACTIVE")
    manager_public_id = models.UUIDField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "leaseops_property"
        constraints = [models.UniqueConstraint(fields=["company", "code"], name="lea_property_code_uq")]
        indexes = [
            models.Index(fields=["company", "status_code"], name="lea_property_status_idx"),
            models.Index(fields=["company", "facility_public_id"], name="lea_property_fac_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.code = normalize_code(self.code)
        self.property_type_code = normalize_code(self.property_type_code)
        self.area_unit_code = normalize_code(self.area_unit_code)
        self.ownership_code = normalize_code(self.ownership_code)
        self.status_code = normalize_code(self.status_code)
        if not isinstance(self.address, dict):
            raise ValidationError({"address": "Property address must be a JSON object."})


class LeaseableUnit(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="leaseable_units")
    property = models.ForeignKey(ManagedProperty, on_delete=models.PROTECT, related_name="units")
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=240)
    unit_type_code = models.CharField(max_length=60, default="APARTMENT")
    floor_reference = models.CharField(max_length=80, blank=True)
    area = models.DecimalField(max_digits=18, decimal_places=3, null=True, blank=True)
    area_unit_code = models.CharField(max_length=30, default="SQ_M")
    bedroom_count = models.PositiveSmallIntegerField(null=True, blank=True)
    parking_count = models.PositiveSmallIntegerField(default=0)
    market_rent = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    currency_code = models.CharField(max_length=3, default="INR")
    status_code = models.CharField(max_length=30, default="AVAILABLE")
    attributes = models.JSONField(default=dict, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "leaseops_unit"
        constraints = [
            models.UniqueConstraint(fields=["property", "code"], name="lea_unit_code_uq"),
            models.CheckConstraint(
                condition=models.Q(market_rent__isnull=True) | models.Q(market_rent__gte=0),
                name="lea_unit_rent_ck",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "status_code"], name="lea_unit_status_idx"),
            models.Index(fields=["company", "property", "unit_type_code"], name="lea_unit_type_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.code = normalize_code(self.code)
        self.unit_type_code = normalize_code(self.unit_type_code)
        self.area_unit_code = normalize_code(self.area_unit_code)
        self.currency_code = normalize_code(self.currency_code)
        self.status_code = normalize_code(self.status_code)
        if self.property_id and self.property.company_id != self.company_id:
            raise ValidationError("Leaseable unit cannot cross companies.")
        if not isinstance(self.attributes, dict):
            raise ValidationError({"attributes": "Unit attributes must be supplied as a JSON object."})


class TenantAccount(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="tenant_accounts")
    account_code = models.CharField(max_length=80)
    legal_name = models.CharField(max_length=240)
    display_name = models.CharField(max_length=240)
    tenant_type_code = models.CharField(max_length=40, default="ORGANIZATION")
    contact_name = models.CharField(max_length=160, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=40, blank=True)
    tax_reference = models.CharField(max_length=120, blank=True)
    billing_address = models.JSONField(default=dict, blank=True)
    status_code = models.CharField(max_length=30, default="ACTIVE")
    owner_public_id = models.UUIDField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "leaseops_tenant"
        constraints = [models.UniqueConstraint(fields=["company", "account_code"], name="lea_tenant_code_uq")]
        indexes = [models.Index(fields=["company", "status_code"], name="lea_tenant_status_idx")]

    def clean(self) -> None:
        super().clean()
        self.account_code = normalize_code(self.account_code)
        self.tenant_type_code = normalize_code(self.tenant_type_code)
        self.status_code = normalize_code(self.status_code)
        if not isinstance(self.billing_address, dict):
            raise ValidationError({"billing_address": "Billing address must be a JSON object."})


class LeaseAgreement(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="lease_agreements")
    property = models.ForeignKey(ManagedProperty, on_delete=models.PROTECT, related_name="leases")
    unit = models.ForeignKey(LeaseableUnit, on_delete=models.PROTECT, related_name="leases")
    tenant = models.ForeignKey(TenantAccount, on_delete=models.PROTECT, related_name="leases")
    lease_number = models.CharField(max_length=80)
    lease_type_code = models.CharField(max_length=40, default="STANDARD")
    start_on = models.DateField()
    end_on = models.DateField()
    billing_cycle_code = models.CharField(max_length=30, default="MONTHLY")
    base_rent = models.DecimalField(max_digits=18, decimal_places=2)
    currency_code = models.CharField(max_length=3, default="INR")
    security_deposit = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    escalation_percent = models.DecimalField(max_digits=7, decimal_places=4, default=0)
    escalation_frequency_months = models.PositiveIntegerField(default=12)
    notice_days = models.PositiveIntegerField(default=30)
    status_code = models.CharField(max_length=30, default="DRAFT")
    created_by_public_id = models.UUIDField()
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    terminated_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "leaseops_lease"
        constraints = [
            models.UniqueConstraint(fields=["company", "lease_number"], name="lea_lease_no_uq"),
            models.CheckConstraint(condition=models.Q(end_on__gt=models.F("start_on")), name="lea_lease_dates_ck"),
            models.CheckConstraint(condition=models.Q(base_rent__gte=0), name="lea_lease_rent_ck"),
            models.CheckConstraint(condition=models.Q(security_deposit__gte=0), name="lea_lease_deposit_ck"),
        ]
        indexes = [
            models.Index(fields=["company", "status_code", "end_on"], name="lea_lease_status_idx"),
            models.Index(fields=["company", "tenant", "status_code"], name="lea_lease_tenant_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.lease_number = normalize_code(self.lease_number)
        self.lease_type_code = normalize_code(self.lease_type_code)
        self.billing_cycle_code = normalize_code(self.billing_cycle_code)
        self.currency_code = normalize_code(self.currency_code)
        self.status_code = normalize_code(self.status_code)
        if self.property_id and self.property.company_id != self.company_id:
            raise ValidationError("Lease property cannot cross companies.")
        if self.unit_id and (self.unit.company_id != self.company_id or self.unit.property_id != self.property_id):
            raise ValidationError("Lease unit must belong to the same company and property.")
        if self.tenant_id and self.tenant.company_id != self.company_id:
            raise ValidationError("Lease tenant cannot cross companies.")


class LeaseCharge(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="lease_charges")
    lease = models.ForeignKey(LeaseAgreement, on_delete=models.PROTECT, related_name="charges")
    charge_code = models.CharField(max_length=80)
    charge_type_code = models.CharField(max_length=60, default="RENT")
    description = models.CharField(max_length=240)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    currency_code = models.CharField(max_length=3, default="INR")
    frequency_code = models.CharField(max_length=30, default="MONTHLY")
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    tax_code = models.CharField(max_length=60, blank=True)
    recoverable = models.BooleanField(default=True)
    status_code = models.CharField(max_length=30, default="ACTIVE")
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "leaseops_charge"
        constraints = [
            models.UniqueConstraint(fields=["lease", "charge_code", "effective_from"], name="lea_charge_period_uq"),
            models.CheckConstraint(condition=models.Q(amount__gte=0), name="lea_charge_amount_ck"),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=models.F("effective_from")),
                name="lea_charge_dates_ck",
            ),
        ]
        indexes = [models.Index(fields=["company", "lease", "status_code"], name="lea_charge_status_idx")]

    def clean(self) -> None:
        super().clean()
        self.charge_code = normalize_code(self.charge_code)
        self.charge_type_code = normalize_code(self.charge_type_code)
        self.currency_code = normalize_code(self.currency_code)
        self.frequency_code = normalize_code(self.frequency_code)
        self.tax_code = normalize_code(self.tax_code) if self.tax_code else ""
        self.status_code = normalize_code(self.status_code)
        if self.lease_id and self.lease.company_id != self.company_id:
            raise ValidationError("Lease charge cannot cross companies.")


class OccupancyRecord(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="occupancy_records")
    lease = models.ForeignKey(LeaseAgreement, on_delete=models.PROTECT, related_name="occupancies")
    unit = models.ForeignKey(LeaseableUnit, on_delete=models.PROTECT, related_name="occupancies")
    occupant_reference = models.CharField(max_length=200, blank=True)
    move_in_on = models.DateField(null=True, blank=True)
    move_out_on = models.DateField(null=True, blank=True)
    occupant_count = models.PositiveIntegerField(default=1)
    key_handover_evidence = models.JSONField(default=dict, blank=True)
    meter_readings = models.JSONField(default=dict, blank=True)
    status_code = models.CharField(max_length=30, default="DRAFT")
    captured_by_public_id = models.UUIDField()
    verified_by_public_id = models.UUIDField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "leaseops_occupancy"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(move_out_on__isnull=True)
                | models.Q(move_in_on__isnull=True)
                | models.Q(move_out_on__gte=models.F("move_in_on")),
                name="lea_occ_dates_ck",
            )
        ]
        indexes = [
            models.Index(fields=["company", "status_code"], name="lea_occ_status_idx"),
            models.Index(fields=["company", "unit", "move_in_on"], name="lea_occ_unit_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.status_code = normalize_code(self.status_code)
        if self.lease_id and self.lease.company_id != self.company_id:
            raise ValidationError("Occupancy record cannot cross companies.")
        if self.unit_id and (self.unit.company_id != self.company_id or self.unit_id != self.lease.unit_id):
            raise ValidationError("Occupancy unit must match the lease unit.")
        if not isinstance(self.key_handover_evidence, dict) or not isinstance(self.meter_readings, dict):
            raise ValidationError("Occupancy evidence and meter readings must be JSON objects.")


class RentInvoice(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="rent_invoices")
    lease = models.ForeignKey(LeaseAgreement, on_delete=models.PROTECT, related_name="invoices")
    invoice_number = models.CharField(max_length=80)
    period_start = models.DateField()
    period_end = models.DateField()
    issue_date = models.DateField()
    due_date = models.DateField()
    gross_amount = models.DecimalField(max_digits=18, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    currency_code = models.CharField(max_length=3, default="INR")
    status_code = models.CharField(max_length=30, default="DRAFT")
    external_finance_reference = models.CharField(max_length=200, blank=True)
    created_by_public_id = models.UUIDField()
    issued_by_public_id = models.UUIDField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "leaseops_invoice"
        constraints = [
            models.UniqueConstraint(fields=["company", "invoice_number"], name="lea_invoice_no_uq"),
            models.CheckConstraint(condition=models.Q(period_end__gte=models.F("period_start")), name="lea_inv_period_ck"),
            models.CheckConstraint(condition=models.Q(due_date__gte=models.F("issue_date")), name="lea_inv_due_ck"),
            models.CheckConstraint(condition=models.Q(gross_amount__gte=0), name="lea_inv_gross_ck"),
            models.CheckConstraint(condition=models.Q(tax_amount__gte=0), name="lea_inv_tax_ck"),
            models.CheckConstraint(condition=models.Q(paid_amount__gte=0), name="lea_inv_paid_ck"),
        ]
        indexes = [
            models.Index(fields=["company", "status_code", "due_date"], name="lea_inv_status_idx"),
            models.Index(fields=["company", "lease", "period_start"], name="lea_inv_lease_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.invoice_number = normalize_code(self.invoice_number)
        self.currency_code = normalize_code(self.currency_code)
        self.status_code = normalize_code(self.status_code)
        if self.lease_id and self.lease.company_id != self.company_id:
            raise ValidationError("Rent invoice cannot cross companies.")
        if self.paid_amount > self.gross_amount + self.tax_amount:
            raise ValidationError("Paid amount cannot exceed the invoice total.")


class TenantExperienceCase(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="tenant_experience_cases")
    tenant = models.ForeignKey(TenantAccount, on_delete=models.PROTECT, related_name="experience_cases")
    property = models.ForeignKey(ManagedProperty, on_delete=models.PROTECT, related_name="experience_cases")
    unit = models.ForeignKey(LeaseableUnit, on_delete=models.PROTECT, related_name="experience_cases", null=True, blank=True)
    case_number = models.CharField(max_length=80)
    category_code = models.CharField(max_length=60, default="SERVICE")
    priority_code = models.CharField(max_length=30, default="NORMAL")
    channel_code = models.CharField(max_length=30, default="PORTAL")
    title = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    status_code = models.CharField(max_length=30, default="NEW")
    assigned_to_public_id = models.UUIDField(null=True, blank=True)
    response_due_at = models.DateTimeField(null=True, blank=True)
    resolution_due_at = models.DateTimeField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    satisfaction_score = models.PositiveSmallIntegerField(null=True, blank=True)
    resolution_note = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "leaseops_case"
        constraints = [
            models.UniqueConstraint(fields=["company", "case_number"], name="lea_case_no_uq"),
            models.CheckConstraint(
                condition=models.Q(satisfaction_score__isnull=True)
                | (models.Q(satisfaction_score__gte=1) & models.Q(satisfaction_score__lte=5)),
                name="lea_case_score_ck",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "status_code", "priority_code"], name="lea_case_status_idx"),
            models.Index(fields=["company", "resolution_due_at"], name="lea_case_due_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.case_number = normalize_code(self.case_number)
        self.category_code = normalize_code(self.category_code)
        self.priority_code = normalize_code(self.priority_code)
        self.channel_code = normalize_code(self.channel_code)
        self.status_code = normalize_code(self.status_code)
        if self.tenant_id and self.tenant.company_id != self.company_id:
            raise ValidationError("Tenant experience case cannot cross companies.")
        if self.property_id and self.property.company_id != self.company_id:
            raise ValidationError("Tenant experience property cannot cross companies.")
        if self.unit_id and (self.unit.company_id != self.company_id or self.unit.property_id != self.property_id):
            raise ValidationError("Tenant experience unit must belong to the same property.")


class LeaseLifecycleEvent(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="lease_lifecycle_events")
    lease = models.ForeignKey(LeaseAgreement, on_delete=models.PROTECT, related_name="lifecycle_events")
    event_type_code = models.CharField(max_length=60)
    occurred_at = models.DateTimeField()
    from_status_code = models.CharField(max_length=30, blank=True)
    to_status_code = models.CharField(max_length=30, blank=True)
    summary = models.CharField(max_length=300)
    amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    currency_code = models.CharField(max_length=3, blank=True)
    event_metadata = models.JSONField(default=dict, blank=True)
    recorded_by_public_id = models.UUIDField()

    class Meta:
        db_table = "leaseops_event"
        indexes = [
            models.Index(fields=["company", "lease", "occurred_at"], name="lea_event_lease_idx"),
            models.Index(fields=["company", "event_type_code"], name="lea_event_type_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.event_type_code = normalize_code(self.event_type_code)
        self.from_status_code = normalize_code(self.from_status_code) if self.from_status_code else ""
        self.to_status_code = normalize_code(self.to_status_code) if self.to_status_code else ""
        self.currency_code = normalize_code(self.currency_code) if self.currency_code else ""
        if self.lease_id and self.lease.company_id != self.company_id:
            raise ValidationError("Lease lifecycle event cannot cross companies.")
        if not isinstance(self.event_metadata, dict):
            raise ValidationError({"event_metadata": "Lease event metadata must be supplied as a JSON object."})
