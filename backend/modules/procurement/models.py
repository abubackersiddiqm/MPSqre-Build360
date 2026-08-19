from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from modules.platform.models import TenantOwnedModel
from modules.vendor.models import SupplyStage


class PurchaseRequest(TenantOwnedModel):
    request_number = models.CharField(max_length=80)
    title = models.CharField(max_length=250)
    description = models.TextField(blank=True)
    project = models.ForeignKey("projects.Project", on_delete=models.PROTECT, null=True, blank=True, related_name="purchase_requests")
    stage = models.ForeignKey(SupplyStage, on_delete=models.PROTECT, related_name="purchase_requests")
    requester_membership_public_id = models.UUIDField()
    required_by_date = models.DateField(null=True, blank=True)
    delivery_location = models.JSONField(default=dict)
    currency = models.CharField(max_length=3)
    estimated_total = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "procurement_purchase_request"
        constraints = [models.UniqueConstraint(fields=["company", "request_number"], name="pr_company_number_uniq")]
        indexes = [models.Index(fields=["company", "stage", "created_at"], name="pr_stage_time_idx")]

    def clean(self) -> None:
        super().clean()
        if self.project_id and self.project.company_id != self.company_id:
            raise ValidationError("Purchase request project cannot cross companies")
        if self.stage_id and (self.stage.company_id != self.company_id or self.stage.entity_type != SupplyStage.EntityType.PURCHASE_REQUEST):
            raise ValidationError("Purchase request stage is invalid")


class PurchaseRequestLine(TenantOwnedModel):
    request = models.ForeignKey(PurchaseRequest, on_delete=models.PROTECT, related_name="lines")
    line_number = models.PositiveIntegerField()
    item = models.ForeignKey("inventory.InventoryItem", on_delete=models.PROTECT, null=True, blank=True, related_name="purchase_request_lines")
    item_code = models.CharField(max_length=80)
    description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=20, decimal_places=4)
    unit_code = models.CharField(max_length=30)
    estimated_unit_rate = models.DecimalField(max_digits=20, decimal_places=4, default=0)

    class Meta:
        db_table = "procurement_request_line"
        constraints = [
            models.UniqueConstraint(fields=["request", "line_number"], name="pr_line_number_uniq"),
            models.CheckConstraint(condition=Q(quantity__gt=0), name="pr_line_quantity_positive"),
            models.CheckConstraint(condition=Q(estimated_unit_rate__gte=0), name="pr_line_rate_nonnegative"),
        ]

    def clean(self) -> None:
        super().clean()
        if self.request_id and self.request.company_id != self.company_id:
            raise ValidationError("Request line cannot cross companies")
        if self.item_id and self.item.company_id != self.company_id:
            raise ValidationError("Request item cannot cross companies")

    @property
    def estimated_total(self) -> Decimal:
        return self.quantity * self.estimated_unit_rate


class RequestForQuotation(TenantOwnedModel):
    rfq_number = models.CharField(max_length=80)
    purchase_request = models.ForeignKey(PurchaseRequest, on_delete=models.PROTECT, related_name="rfqs")
    title = models.CharField(max_length=250)
    stage = models.ForeignKey(SupplyStage, on_delete=models.PROTECT, related_name="rfqs")
    issue_at = models.DateTimeField(null=True, blank=True)
    close_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "procurement_rfq"
        constraints = [models.UniqueConstraint(fields=["company", "rfq_number"], name="rfq_company_number_uniq")]
        indexes = [models.Index(fields=["company", "stage", "close_at"], name="rfq_stage_close_idx")]

    def clean(self) -> None:
        super().clean()
        if self.purchase_request_id and self.purchase_request.company_id != self.company_id:
            raise ValidationError("RFQ request cannot cross companies")
        if self.stage_id and (self.stage.company_id != self.company_id or self.stage.entity_type != SupplyStage.EntityType.RFQ):
            raise ValidationError("RFQ stage is invalid")
        if self.issue_at and self.close_at and self.close_at <= self.issue_at:
            raise ValidationError("RFQ close time must be after issue time")


class RfqVendor(TenantOwnedModel):
    rfq = models.ForeignKey(RequestForQuotation, on_delete=models.PROTECT, related_name="vendor_invitations")
    vendor = models.ForeignKey("vendor.VendorProfile", on_delete=models.PROTECT, related_name="rfq_invitations")
    invited_at = models.DateTimeField()

    class Meta:
        db_table = "procurement_rfq_vendor"
        constraints = [models.UniqueConstraint(fields=["rfq", "vendor"], name="rfq_vendor_uniq")]


class VendorQuote(TenantOwnedModel):
    rfq = models.ForeignKey(RequestForQuotation, on_delete=models.PROTECT, related_name="quotes")
    vendor = models.ForeignKey("vendor.VendorProfile", on_delete=models.PROTECT, related_name="quotes")
    quote_number = models.CharField(max_length=80)
    stage = models.ForeignKey(SupplyStage, on_delete=models.PROTECT, related_name="quotes")
    currency = models.CharField(max_length=3)
    subtotal = models.DecimalField(max_digits=20, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    freight_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=20, decimal_places=2)
    valid_until = models.DateField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "procurement_vendor_quote"
        constraints = [
            models.UniqueConstraint(fields=["rfq", "vendor"], name="rfq_vendor_quote_uniq"),
            models.UniqueConstraint(fields=["company", "quote_number"], name="quote_company_number_uniq"),
            models.CheckConstraint(condition=Q(subtotal__gte=0) & Q(tax_amount__gte=0) & Q(freight_amount__gte=0) & Q(total_amount__gte=0), name="quote_amounts_nonnegative"),
        ]
        indexes = [models.Index(fields=["company", "rfq", "total_amount"], name="quote_compare_lookup_idx")]

    def clean(self) -> None:
        super().clean()
        if self.rfq_id and self.rfq.company_id != self.company_id:
            raise ValidationError("Quote RFQ cannot cross companies")
        if self.vendor_id and self.vendor.company_id != self.company_id:
            raise ValidationError("Quote vendor cannot cross companies")
        if self.stage_id and (self.stage.company_id != self.company_id or self.stage.entity_type != SupplyStage.EntityType.QUOTE):
            raise ValidationError("Quote stage is invalid")
        expected = self.subtotal + self.tax_amount + self.freight_amount
        if self.total_amount != expected:
            raise ValidationError("Quote total must equal subtotal, tax and freight")


class PurchaseOrder(TenantOwnedModel):
    po_number = models.CharField(max_length=80)
    purchase_request = models.ForeignKey(PurchaseRequest, on_delete=models.PROTECT, related_name="purchase_orders")
    rfq = models.ForeignKey(RequestForQuotation, on_delete=models.PROTECT, related_name="purchase_orders")
    awarded_quote = models.OneToOneField(VendorQuote, on_delete=models.PROTECT, related_name="purchase_order")
    vendor = models.ForeignKey("vendor.VendorProfile", on_delete=models.PROTECT, related_name="purchase_orders")
    stage = models.ForeignKey(SupplyStage, on_delete=models.PROTECT, related_name="purchase_orders")
    currency = models.CharField(max_length=3)
    total_amount = models.DecimalField(max_digits=20, decimal_places=2)
    issued_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "procurement_purchase_order"
        constraints = [models.UniqueConstraint(fields=["company", "po_number"], name="po_company_number_uniq")]
        indexes = [models.Index(fields=["company", "stage", "created_at"], name="po_stage_time_idx")]

    def clean(self) -> None:
        super().clean()
        for related in (self.purchase_request, self.rfq, self.awarded_quote, self.vendor):
            if related.pk and related.company_id != self.company_id:
                raise ValidationError("Purchase order relationships cannot cross companies")
        if self.stage_id and (self.stage.company_id != self.company_id or self.stage.entity_type != SupplyStage.EntityType.PURCHASE_ORDER):
            raise ValidationError("Purchase order stage is invalid")


class PurchaseOrderLine(TenantOwnedModel):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name="lines")
    request_line = models.ForeignKey(PurchaseRequestLine, on_delete=models.PROTECT, related_name="purchase_order_lines")
    line_number = models.PositiveIntegerField()
    item = models.ForeignKey("inventory.InventoryItem", on_delete=models.PROTECT, null=True, blank=True, related_name="purchase_order_lines")
    description = models.CharField(max_length=500)
    quantity_ordered = models.DecimalField(max_digits=20, decimal_places=4)
    quantity_received = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    unit_code = models.CharField(max_length=30)
    unit_rate = models.DecimalField(max_digits=20, decimal_places=4)

    class Meta:
        db_table = "procurement_po_line"
        constraints = [
            models.UniqueConstraint(fields=["purchase_order", "line_number"], name="po_line_number_uniq"),
            models.CheckConstraint(condition=Q(quantity_ordered__gt=0) & Q(quantity_received__gte=0), name="po_line_quantities_valid"),
        ]


class GoodsReceipt(TenantOwnedModel):
    receipt_number = models.CharField(max_length=80)
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name="receipts")
    warehouse = models.ForeignKey("inventory.Warehouse", on_delete=models.PROTECT, related_name="goods_receipts")
    stage = models.ForeignKey(SupplyStage, on_delete=models.PROTECT, related_name="receipts")
    received_at = models.DateTimeField()
    posted_at = models.DateTimeField(null=True, blank=True)
    received_by_membership_public_id = models.UUIDField()
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "procurement_goods_receipt"
        constraints = [models.UniqueConstraint(fields=["company", "receipt_number"], name="grn_company_number_uniq")]
        indexes = [models.Index(fields=["company", "stage", "received_at"], name="grn_stage_time_idx")]

    def clean(self) -> None:
        super().clean()
        if self.purchase_order_id and self.purchase_order.company_id != self.company_id:
            raise ValidationError("Receipt purchase order cannot cross companies")
        if self.warehouse_id and self.warehouse.company_id != self.company_id:
            raise ValidationError("Receipt warehouse cannot cross companies")
        if self.stage_id and (self.stage.company_id != self.company_id or self.stage.entity_type != SupplyStage.EntityType.RECEIPT):
            raise ValidationError("Receipt stage is invalid")


class GoodsReceiptLine(TenantOwnedModel):
    receipt = models.ForeignKey(GoodsReceipt, on_delete=models.PROTECT, related_name="lines")
    purchase_order_line = models.ForeignKey(PurchaseOrderLine, on_delete=models.PROTECT, related_name="receipt_lines")
    line_number = models.PositiveIntegerField()
    quantity_received = models.DecimalField(max_digits=20, decimal_places=4)
    quantity_accepted = models.DecimalField(max_digits=20, decimal_places=4)
    quantity_rejected = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    notes = models.CharField(max_length=500, blank=True)

    class Meta:
        db_table = "procurement_goods_receipt_line"
        constraints = [
            models.UniqueConstraint(fields=["receipt", "line_number"], name="grn_line_number_uniq"),
            models.CheckConstraint(condition=Q(quantity_received__gt=0) & Q(quantity_accepted__gte=0) & Q(quantity_rejected__gte=0), name="grn_quantities_nonnegative"),
        ]

    def clean(self) -> None:
        super().clean()
        if self.quantity_accepted + self.quantity_rejected != self.quantity_received:
            raise ValidationError("Accepted and rejected quantities must equal received quantity")
