from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from modules.platform.models import TenantOwnedModel


class SupplyStage(TenantOwnedModel):
    class EntityType(models.TextChoices):
        VENDOR = "vendor", "Vendor"
        PURCHASE_REQUEST = "purchase_request", "Purchase request"
        RFQ = "rfq", "Request for quotation"
        QUOTE = "quote", "Vendor quote"
        PURCHASE_ORDER = "purchase_order", "Purchase order"
        RECEIPT = "receipt", "Goods receipt"

    class Outcome(models.TextChoices):
        OPEN = "open", "Open"
        REVIEW = "review", "Review"
        APPROVED = "approved", "Approved"
        ISSUED = "issued", "Issued"
        COMPLETE = "complete", "Complete"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    entity_type = models.CharField(max_length=40, choices=EntityType.choices)
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=120)
    outcome = models.CharField(max_length=20, choices=Outcome.choices, default=Outcome.OPEN)
    sort_order = models.PositiveIntegerField(default=100)
    allowed_next_codes = models.JSONField(default=list)
    is_initial = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "vendor_supply_stage"
        ordering = ["entity_type", "sort_order", "code"]
        constraints = [
            models.UniqueConstraint(fields=["company", "entity_type", "code"], name="supply_stage_code_uniq"),
            models.UniqueConstraint(fields=["company", "entity_type"], condition=Q(is_initial=True), name="supply_initial_stage_uniq"),
            models.CheckConstraint(condition=Q(effective_to__isnull=True) | Q(effective_to__gt=models.F("effective_from")), name="supply_stage_range_valid"),
        ]
        indexes = [models.Index(fields=["company", "entity_type", "is_active"], name="supply_stage_lookup_idx")]


class VendorProfile(TenantOwnedModel):
    code = models.CharField(max_length=50)
    legal_name = models.CharField(max_length=250)
    display_name = models.CharField(max_length=250)
    stage = models.ForeignKey(SupplyStage, on_delete=models.PROTECT, related_name="vendors")
    categories = models.JSONField(default=list)
    service_regions = models.JSONField(default=list)
    tax_reference_masked = models.CharField(max_length=80, blank=True)
    primary_contact_name = models.CharField(max_length=150, blank=True)
    primary_contact_email = models.EmailField(blank=True)
    primary_contact_phone = models.CharField(max_length=40, blank=True)
    version = models.PositiveBigIntegerField(default=1)
    qualified_at = models.DateTimeField(null=True, blank=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    retired_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "vendor_profile"
        constraints = [models.UniqueConstraint(fields=["company", "code"], name="vendor_company_code_uniq")]
        indexes = [
            models.Index(fields=["company", "stage", "created_at"], name="vendor_stage_time_idx"),
            models.Index(fields=["company", "display_name"], name="vendor_name_lookup_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        if self.stage_id and (self.stage.company_id != self.company_id or self.stage.entity_type != SupplyStage.EntityType.VENDOR):
            raise ValidationError("Vendor stage must belong to the same company and vendor lifecycle")


class VendorQualification(TenantOwnedModel):
    class Decision(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    vendor = models.ForeignKey(VendorProfile, on_delete=models.PROTECT, related_name="qualifications")
    checklist_version = models.PositiveIntegerField(default=1)
    score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    decision = models.CharField(max_length=20, choices=Decision.choices, default=Decision.PENDING)
    notes = models.TextField(blank=True)
    decided_by_public_id = models.UUIDField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "vendor_qualification"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["company", "vendor", "decision"], name="vendor_qual_lookup_idx")]

    def clean(self) -> None:
        super().clean()
        if self.vendor_id and self.vendor.company_id != self.company_id:
            raise ValidationError("Qualification cannot cross companies")
        if self.score < 0 or self.score > 100:
            raise ValidationError("Qualification score must be between 0 and 100")
