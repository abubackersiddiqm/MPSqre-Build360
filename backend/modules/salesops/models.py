from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from modules.platform.models import PublicIdModel, TimestampedModel
from modules.tenant.models import Company


def normalize_code(value: str) -> str:
    return value.strip().upper().replace(" ", "_").replace("-", "_")


class SalesPolicyVersion(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="development_sales_policies")
    version = models.PositiveIntegerField(default=1)
    status_code = models.CharField(max_length=30, default="DRAFT")
    reservation_expiry_hours = models.PositiveIntegerField(default=72)
    collection_grace_days = models.PositiveIntegerField(default=7)
    handover_alert_days = models.PositiveIntegerField(default=30)
    configuration = models.JSONField(default=dict, blank=True)
    effective_from = models.DateTimeField(null=True, blank=True)
    effective_to = models.DateTimeField(null=True, blank=True)
    published_by_public_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "salesops_policy"
        constraints = [
            models.UniqueConstraint(fields=["company", "version"], name="sal_policy_ver_uq"),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_from__isnull=True)
                | models.Q(effective_to__gt=models.F("effective_from")),
                name="sal_policy_dates_ck",
            ),
        ]
        indexes = [models.Index(fields=["company", "status_code"], name="sal_policy_status_idx")]

    def clean(self) -> None:
        super().clean()
        self.status_code = normalize_code(self.status_code)


class DevelopmentInventory(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="development_sales_inventories")
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=240)
    project_public_id = models.UUIDField(null=True, blank=True)
    property_public_id = models.UUIDField(null=True, blank=True)
    development_type_code = models.CharField(max_length=60, default="RESIDENTIAL")
    location = models.JSONField(default=dict, blank=True)
    launch_on = models.DateField(null=True, blank=True)
    currency_code = models.CharField(max_length=3, default="INR")
    status_code = models.CharField(max_length=30, default="PLANNING")
    manager_public_id = models.UUIDField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "salesops_inventory"
        constraints = [models.UniqueConstraint(fields=["company", "code"], name="sal_inventory_code_uq")]
        indexes = [
            models.Index(fields=["company", "status_code"], name="sal_inventory_status_idx"),
            models.Index(fields=["company", "project_public_id"], name="sal_inventory_proj_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.code = normalize_code(self.code)
        self.development_type_code = normalize_code(self.development_type_code)
        self.currency_code = normalize_code(self.currency_code)
        self.status_code = normalize_code(self.status_code)
        if not isinstance(self.location, dict):
            raise ValidationError({"location": "Development location must be a JSON object."})


class SaleableUnit(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="development_saleable_units")
    inventory = models.ForeignKey(DevelopmentInventory, on_delete=models.PROTECT, related_name="units")
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=240)
    unit_type_code = models.CharField(max_length=60, default="APARTMENT")
    tower_reference = models.CharField(max_length=80, blank=True)
    floor_reference = models.CharField(max_length=80, blank=True)
    carpet_area = models.DecimalField(max_digits=18, decimal_places=3, null=True, blank=True)
    saleable_area = models.DecimalField(max_digits=18, decimal_places=3, null=True, blank=True)
    area_unit_code = models.CharField(max_length=30, default="SQ_M")
    list_price = models.DecimalField(max_digits=18, decimal_places=2)
    currency_code = models.CharField(max_length=3, default="INR")
    tax_code = models.CharField(max_length=60, blank=True)
    status_code = models.CharField(max_length=30, default="DRAFT")
    attributes = models.JSONField(default=dict, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "salesops_unit"
        constraints = [
            models.UniqueConstraint(fields=["inventory", "code"], name="sal_unit_code_uq"),
            models.CheckConstraint(condition=models.Q(list_price__gte=0), name="sal_unit_price_ck"),
        ]
        indexes = [
            models.Index(fields=["company", "status_code"], name="sal_unit_status_idx"),
            models.Index(fields=["company", "inventory", "unit_type_code"], name="sal_unit_type_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.code = normalize_code(self.code)
        self.unit_type_code = normalize_code(self.unit_type_code)
        self.area_unit_code = normalize_code(self.area_unit_code)
        self.currency_code = normalize_code(self.currency_code)
        self.status_code = normalize_code(self.status_code)
        if self.inventory_id and self.inventory.company_id != self.company_id:
            raise ValidationError("Saleable unit cannot cross companies.")
        if self.carpet_area is not None and self.carpet_area < 0:
            raise ValidationError({"carpet_area": "Carpet area cannot be negative."})
        if self.saleable_area is not None and self.saleable_area < 0:
            raise ValidationError({"saleable_area": "Saleable area cannot be negative."})
        if not isinstance(self.attributes, dict):
            raise ValidationError({"attributes": "Unit attributes must be a JSON object."})


class BuyerAccount(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="development_sales_buyers")
    account_code = models.CharField(max_length=80)
    legal_name = models.CharField(max_length=240)
    display_name = models.CharField(max_length=240)
    buyer_type_code = models.CharField(max_length=40, default="INDIVIDUAL")
    contact_name = models.CharField(max_length=160, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=40, blank=True)
    tax_reference = models.CharField(max_length=120, blank=True)
    address = models.JSONField(default=dict, blank=True)
    crm_party_public_id = models.UUIDField(null=True, blank=True)
    status_code = models.CharField(max_length=30, default="ACTIVE")
    owner_public_id = models.UUIDField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "salesops_buyer"
        constraints = [models.UniqueConstraint(fields=["company", "account_code"], name="sal_buyer_code_uq")]
        indexes = [models.Index(fields=["company", "status_code"], name="sal_buyer_status_idx")]

    def clean(self) -> None:
        super().clean()
        self.account_code = normalize_code(self.account_code)
        self.buyer_type_code = normalize_code(self.buyer_type_code)
        self.status_code = normalize_code(self.status_code)
        if not isinstance(self.address, dict):
            raise ValidationError({"address": "Buyer address must be a JSON object."})


class UnitReservation(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="development_unit_reservations")
    unit = models.ForeignKey(SaleableUnit, on_delete=models.PROTECT, related_name="reservations")
    buyer = models.ForeignKey(BuyerAccount, on_delete=models.PROTECT, related_name="reservations")
    reservation_number = models.CharField(max_length=80)
    reserved_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    token_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    currency_code = models.CharField(max_length=3, default="INR")
    status_code = models.CharField(max_length=30, default="ACTIVE")
    source_code = models.CharField(max_length=60, default="DIRECT")
    created_by_public_id = models.UUIDField()
    converted_booking_public_id = models.UUIDField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "salesops_reservation"
        constraints = [
            models.UniqueConstraint(fields=["company", "reservation_number"], name="sal_reservation_no_uq"),
            models.CheckConstraint(condition=models.Q(expires_at__gt=models.F("reserved_at")), name="sal_reservation_dates_ck"),
            models.CheckConstraint(condition=models.Q(token_amount__gte=0), name="sal_reservation_token_ck"),
        ]
        indexes = [
            models.Index(fields=["company", "status_code", "expires_at"], name="sal_reservation_status_idx"),
            models.Index(fields=["company", "unit", "status_code"], name="sal_reservation_unit_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.reservation_number = normalize_code(self.reservation_number)
        self.currency_code = normalize_code(self.currency_code)
        self.status_code = normalize_code(self.status_code)
        self.source_code = normalize_code(self.source_code)
        if self.unit_id and self.unit.company_id != self.company_id:
            raise ValidationError("Reservation unit cannot cross companies.")
        if self.buyer_id and self.buyer.company_id != self.company_id:
            raise ValidationError("Reservation buyer cannot cross companies.")


class BookingAgreement(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="development_bookings")
    unit = models.ForeignKey(SaleableUnit, on_delete=models.PROTECT, related_name="bookings")
    buyer = models.ForeignKey(BuyerAccount, on_delete=models.PROTECT, related_name="bookings")
    reservation = models.ForeignKey(UnitReservation, on_delete=models.PROTECT, related_name="bookings", null=True, blank=True)
    booking_number = models.CharField(max_length=80)
    booking_date = models.DateField()
    agreement_date = models.DateField(null=True, blank=True)
    base_price = models.DecimalField(max_digits=18, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    other_charges = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_consideration = models.DecimalField(max_digits=18, decimal_places=2)
    currency_code = models.CharField(max_length=3, default="INR")
    status_code = models.CharField(max_length=30, default="DRAFT")
    created_by_public_id = models.UUIDField()
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "salesops_booking"
        constraints = [
            models.UniqueConstraint(fields=["company", "booking_number"], name="sal_booking_no_uq"),
            models.CheckConstraint(condition=models.Q(base_price__gte=0), name="sal_booking_base_ck"),
            models.CheckConstraint(condition=models.Q(discount_amount__gte=0), name="sal_booking_discount_ck"),
            models.CheckConstraint(condition=models.Q(tax_amount__gte=0), name="sal_booking_tax_ck"),
            models.CheckConstraint(condition=models.Q(other_charges__gte=0), name="sal_booking_other_ck"),
            models.CheckConstraint(condition=models.Q(total_consideration__gte=0), name="sal_booking_total_ck"),
        ]
        indexes = [
            models.Index(fields=["company", "status_code", "booking_date"], name="sal_booking_status_idx"),
            models.Index(fields=["company", "buyer", "status_code"], name="sal_booking_buyer_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.booking_number = normalize_code(self.booking_number)
        self.currency_code = normalize_code(self.currency_code)
        self.status_code = normalize_code(self.status_code)
        if self.unit_id and self.unit.company_id != self.company_id:
            raise ValidationError("Booking unit cannot cross companies.")
        if self.buyer_id and self.buyer.company_id != self.company_id:
            raise ValidationError("Booking buyer cannot cross companies.")
        expected = self.base_price - self.discount_amount + self.tax_amount + self.other_charges
        if self.total_consideration != expected:
            raise ValidationError({"total_consideration": "Total consideration must equal base price minus discount plus tax and other charges."})
        if self.reservation_id:
            if self.reservation.company_id != self.company_id:
                raise ValidationError("Booking reservation cannot cross companies.")
            if self.reservation.unit_id != self.unit_id or self.reservation.buyer_id != self.buyer_id:
                raise ValidationError("Booking must use the reservation unit and buyer.")


class PaymentMilestone(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="development_payment_milestones")
    booking = models.ForeignKey(BookingAgreement, on_delete=models.PROTECT, related_name="payment_milestones")
    sequence = models.PositiveIntegerField()
    milestone_code = models.CharField(max_length=80)
    description = models.CharField(max_length=240)
    due_on = models.DateField()
    percentage = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    status_code = models.CharField(max_length=30, default="SCHEDULED")
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "salesops_milestone"
        constraints = [
            models.UniqueConstraint(fields=["booking", "sequence"], name="sal_milestone_seq_uq"),
            models.UniqueConstraint(fields=["booking", "milestone_code"], name="sal_milestone_code_uq"),
            models.CheckConstraint(condition=models.Q(amount__gte=0), name="sal_milestone_amt_ck"),
            models.CheckConstraint(condition=models.Q(tax_amount__gte=0), name="sal_milestone_tax_ck"),
            models.CheckConstraint(condition=models.Q(paid_amount__gte=0), name="sal_milestone_paid_ck"),
            models.CheckConstraint(condition=models.Q(percentage__isnull=True) | (models.Q(percentage__gte=0) & models.Q(percentage__lte=100)), name="sal_milestone_pct_ck"),
        ]
        indexes = [
            models.Index(fields=["company", "status_code", "due_on"], name="sal_milestone_due_idx"),
            models.Index(fields=["company", "booking", "sequence"], name="sal_milestone_book_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.milestone_code = normalize_code(self.milestone_code)
        self.status_code = normalize_code(self.status_code)
        if self.booking_id and self.booking.company_id != self.company_id:
            raise ValidationError("Payment milestone cannot cross companies.")
        if self.paid_amount > self.amount + self.tax_amount:
            raise ValidationError({"paid_amount": "Paid amount cannot exceed the milestone total."})


class CollectionReceipt(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="development_collection_receipts")
    booking = models.ForeignKey(BookingAgreement, on_delete=models.PROTECT, related_name="receipts")
    milestone = models.ForeignKey(PaymentMilestone, on_delete=models.PROTECT, related_name="receipts", null=True, blank=True)
    receipt_number = models.CharField(max_length=80)
    receipt_date = models.DateField()
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    currency_code = models.CharField(max_length=3, default="INR")
    payment_method_code = models.CharField(max_length=40, default="BANK_TRANSFER")
    payment_reference = models.CharField(max_length=160, blank=True)
    finance_reference = models.CharField(max_length=160, blank=True)
    status_code = models.CharField(max_length=30, default="DRAFT")
    created_by_public_id = models.UUIDField()
    confirmed_by_public_id = models.UUIDField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "salesops_receipt"
        constraints = [
            models.UniqueConstraint(fields=["company", "receipt_number"], name="sal_receipt_no_uq"),
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="sal_receipt_amt_ck"),
        ]
        indexes = [
            models.Index(fields=["company", "status_code", "receipt_date"], name="sal_receipt_status_idx"),
            models.Index(fields=["company", "booking", "receipt_date"], name="sal_receipt_book_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.receipt_number = normalize_code(self.receipt_number)
        self.currency_code = normalize_code(self.currency_code)
        self.payment_method_code = normalize_code(self.payment_method_code)
        self.status_code = normalize_code(self.status_code)
        if self.booking_id and self.booking.company_id != self.company_id:
            raise ValidationError("Collection receipt cannot cross companies.")
        if self.milestone_id:
            if self.milestone.company_id != self.company_id or self.milestone.booking_id != self.booking_id:
                raise ValidationError("Receipt milestone must belong to the same booking and company.")


class BrokerCommission(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="development_broker_commissions")
    booking = models.ForeignKey(BookingAgreement, on_delete=models.PROTECT, related_name="broker_commissions")
    broker_reference = models.CharField(max_length=160)
    broker_name = models.CharField(max_length=240)
    commission_percent = models.DecimalField(max_digits=7, decimal_places=4, default=0)
    commission_amount = models.DecimalField(max_digits=18, decimal_places=2)
    currency_code = models.CharField(max_length=3, default="INR")
    status_code = models.CharField(max_length=30, default="DRAFT")
    created_by_public_id = models.UUIDField()
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "salesops_commission"
        constraints = [
            models.UniqueConstraint(fields=["booking", "broker_reference"], name="sal_commission_broker_uq"),
            models.CheckConstraint(condition=models.Q(commission_percent__gte=0) & models.Q(commission_percent__lte=100), name="sal_commission_pct_ck"),
            models.CheckConstraint(condition=models.Q(commission_amount__gte=0), name="sal_commission_amt_ck"),
        ]
        indexes = [models.Index(fields=["company", "status_code"], name="sal_commission_status_idx")]

    def clean(self) -> None:
        super().clean()
        self.currency_code = normalize_code(self.currency_code)
        self.status_code = normalize_code(self.status_code)
        if self.booking_id and self.booking.company_id != self.company_id:
            raise ValidationError("Broker commission cannot cross companies.")


class CustomerHandover(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="development_customer_handovers")
    booking = models.OneToOneField(BookingAgreement, on_delete=models.PROTECT, related_name="handover")
    unit = models.ForeignKey(SaleableUnit, on_delete=models.PROTECT, related_name="customer_handovers")
    planned_on = models.DateField(null=True, blank=True)
    offered_on = models.DateField(null=True, blank=True)
    possession_on = models.DateField(null=True, blank=True)
    checklist = models.JSONField(default=dict, blank=True)
    evidence = models.JSONField(default=dict, blank=True)
    open_defect_count = models.PositiveIntegerField(default=0)
    status_code = models.CharField(max_length=30, default="DRAFT")
    created_by_public_id = models.UUIDField()
    verified_by_public_id = models.UUIDField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "salesops_handover"
        indexes = [
            models.Index(fields=["company", "status_code", "planned_on"], name="sal_handover_status_idx"),
            models.Index(fields=["company", "unit"], name="sal_handover_unit_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.status_code = normalize_code(self.status_code)
        if self.booking_id and self.booking.company_id != self.company_id:
            raise ValidationError("Customer handover cannot cross companies.")
        if self.unit_id and self.unit.company_id != self.company_id:
            raise ValidationError("Customer handover unit cannot cross companies.")
        if self.booking_id and self.unit_id and self.booking.unit_id != self.unit_id:
            raise ValidationError("Customer handover unit must match the booked unit.")
        if self.possession_on and self.offered_on and self.possession_on < self.offered_on:
            raise ValidationError({"possession_on": "Possession date cannot be earlier than the offer date."})
        if not isinstance(self.checklist, dict) or not isinstance(self.evidence, dict):
            raise ValidationError("Handover checklist and evidence must be JSON objects.")
