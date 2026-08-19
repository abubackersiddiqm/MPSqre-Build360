from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from modules.platform.models import TenantOwnedModel


class InventoryItem(TenantOwnedModel):
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=250)
    category_code = models.CharField(max_length=80, blank=True)
    base_unit_code = models.CharField(max_length=30)
    description = models.TextField(blank=True)
    track_inventory = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "inventory_item"
        constraints = [models.UniqueConstraint(fields=["company", "code"], name="inv_item_company_code_uniq")]
        indexes = [models.Index(fields=["company", "is_active", "name"], name="inv_item_lookup_idx")]


class Warehouse(TenantOwnedModel):
    code = models.CharField(max_length=60)
    name = models.CharField(max_length=200)
    project = models.ForeignKey("projects.Project", on_delete=models.PROTECT, null=True, blank=True, related_name="warehouses")
    location = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "inventory_warehouse"
        constraints = [models.UniqueConstraint(fields=["company", "code"], name="warehouse_company_code_uniq")]
        indexes = [models.Index(fields=["company", "is_active", "name"], name="warehouse_lookup_idx")]

    def clean(self) -> None:
        super().clean()
        if self.project_id and self.project.company_id != self.company_id:
            raise ValidationError("Warehouse project cannot cross companies")


class StockBalance(TenantOwnedModel):
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="balances")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="balances")
    quantity_on_hand = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    quantity_reserved = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    average_unit_cost = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "inventory_stock_balance"
        constraints = [
            models.UniqueConstraint(fields=["company", "item", "warehouse"], name="stock_balance_uniq"),
            models.CheckConstraint(condition=Q(quantity_reserved__gte=0), name="stock_reserved_nonnegative"),
        ]
        indexes = [models.Index(fields=["company", "warehouse", "item"], name="stock_balance_lookup_idx")]

    def clean(self) -> None:
        super().clean()
        if self.item_id and self.item.company_id != self.company_id:
            raise ValidationError("Stock item cannot cross companies")
        if self.warehouse_id and self.warehouse.company_id != self.company_id:
            raise ValidationError("Warehouse cannot cross companies")
        if self.quantity_reserved > self.quantity_on_hand:
            raise ValidationError("Reserved quantity cannot exceed on-hand quantity")


class StockLedgerEntry(TenantOwnedModel):
    class MovementType(models.TextChoices):
        RECEIPT = "receipt", "Receipt"
        ISSUE = "issue", "Issue"
        RETURN = "return", "Return"
        TRANSFER_IN = "transfer_in", "Transfer in"
        TRANSFER_OUT = "transfer_out", "Transfer out"
        ADJUSTMENT = "adjustment", "Adjustment"
        REVERSAL = "reversal", "Reversal"

    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="ledger_entries")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="ledger_entries")
    movement_type = models.CharField(max_length=30, choices=MovementType.choices)
    quantity = models.DecimalField(max_digits=20, decimal_places=4)
    unit_cost = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    balance_after = models.DecimalField(max_digits=20, decimal_places=4)
    source_type = models.CharField(max_length=80)
    source_public_id = models.UUIDField()
    source_line_key = models.CharField(max_length=120, blank=True)
    occurred_at = models.DateTimeField()
    posted_by_public_id = models.UUIDField()
    reason_code = models.CharField(max_length=100, blank=True)
    reversal_of = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="reversals")

    class Meta:
        db_table = "inventory_stock_ledger"
        ordering = ["-occurred_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["company", "source_type", "source_public_id", "source_line_key"], name="stock_source_fact_uniq"),
            models.CheckConstraint(condition=~Q(quantity=0), name="stock_quantity_nonzero"),
        ]
        indexes = [
            models.Index(fields=["company", "warehouse", "item", "occurred_at"], name="stock_ledger_lookup_idx"),
            models.Index(fields=["company", "source_type", "source_public_id"], name="stock_source_lookup_idx"),
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk:
            raise ValidationError("Stock ledger entries are append-only")
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("Stock ledger entries are append-only")
