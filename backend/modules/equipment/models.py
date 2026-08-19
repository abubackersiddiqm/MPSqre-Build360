from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from modules.fieldops.models import FieldStage
from modules.platform.models import TenantOwnedModel


class EquipmentAsset(TenantOwnedModel):
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=200)
    category_code = models.CharField(max_length=80)
    ownership_type = models.CharField(max_length=30, default="owned")
    serial_number = models.CharField(max_length=120, blank=True)
    registration_number = models.CharField(max_length=120, blank=True)
    stage = models.ForeignKey(FieldStage, on_delete=models.PROTECT, related_name="equipment_assets")
    acquisition_date = models.DateField(null=True, blank=True)
    hourly_cost = models.DecimalField(max_digits=19, decimal_places=4, default=Decimal("0"))
    currency = models.CharField(max_length=3)
    current_meter = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    meter_unit = models.CharField(max_length=20, default="hours")
    version = models.PositiveBigIntegerField(default=1)
    retired_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "equipment_asset"
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="eqp_asset_code_uq"),
            models.CheckConstraint(
                condition=models.Q(hourly_cost__gte=0), name="eqp_hourly_cost_valid"
            ),
            models.CheckConstraint(
                condition=models.Q(current_meter__gte=0), name="eqp_meter_nonnegative"
            ),
        ]
        indexes = [
            models.Index(fields=["company", "stage", "category_code"], name="eqp_asset_stage_idx")
        ]

    def clean(self) -> None:
        super().clean()
        if self.stage_id and (
            self.stage.company_id != self.company_id
            or self.stage.entity_type != FieldStage.EntityType.EQUIPMENT
        ):
            raise ValidationError("Equipment requires an equipment stage")


class EquipmentAllocation(TenantOwnedModel):
    equipment = models.ForeignKey(
        EquipmentAsset, on_delete=models.PROTECT, related_name="allocations"
    )
    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, related_name="equipment_allocations"
    )
    stage = models.ForeignKey(
        FieldStage, on_delete=models.PROTECT, related_name="equipment_allocations"
    )
    allocated_from = models.DateTimeField()
    allocated_to = models.DateTimeField(null=True, blank=True)
    custodian_membership_public_id = models.UUIDField(null=True, blank=True)
    planned_meter_usage = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    notes = models.TextField(blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "equipment_allocation"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(allocated_to__isnull=True)
                | models.Q(allocated_to__gte=models.F("allocated_from")),
                name="eqp_alloc_dates_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(planned_meter_usage__gte=0), name="eqp_alloc_usage_valid"
            ),
        ]
        indexes = [
            models.Index(fields=["company", "project", "stage"], name="eqp_alloc_project_idx")
        ]

    def clean(self) -> None:
        super().clean()
        if self.equipment_id and self.equipment.company_id != self.company_id:
            raise ValidationError("Equipment allocation cannot cross companies")
        if self.project_id and self.project.company_id != self.company_id:
            raise ValidationError("Equipment project cannot cross companies")
        if self.stage_id and (
            self.stage.company_id != self.company_id
            or self.stage.entity_type != FieldStage.EntityType.EQUIPMENT_ALLOCATION
        ):
            raise ValidationError("Allocation requires an equipment-allocation stage")


class MeterReading(TenantOwnedModel):
    equipment = models.ForeignKey(
        EquipmentAsset, on_delete=models.PROTECT, related_name="meter_readings"
    )
    reading = models.DecimalField(max_digits=14, decimal_places=2)
    reading_at = models.DateTimeField()
    source = models.CharField(max_length=20, default="web")
    operation_id = models.UUIDField(null=True, blank=True)
    recorded_by_public_id = models.UUIDField()

    class Meta:
        db_table = "equipment_meter_reading"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "operation_id"],
                condition=models.Q(operation_id__isnull=False),
                name="eqp_meter_operation_uq",
            ),
            models.CheckConstraint(condition=models.Q(reading__gte=0), name="eqp_reading_valid"),
        ]
        indexes = [
            models.Index(fields=["company", "equipment", "reading_at"], name="eqp_meter_lookup_idx")
        ]

    def clean(self) -> None:
        super().clean()
        if self.equipment_id and self.equipment.company_id != self.company_id:
            raise ValidationError("Meter reading cannot cross companies")


class MaintenanceWorkOrder(TenantOwnedModel):
    equipment = models.ForeignKey(
        EquipmentAsset, on_delete=models.PROTECT, related_name="maintenance_orders"
    )
    stage = models.ForeignKey(
        FieldStage, on_delete=models.PROTECT, related_name="maintenance_orders"
    )
    work_order_number = models.CharField(max_length=80)
    maintenance_type = models.CharField(max_length=40)
    summary = models.CharField(max_length=250)
    description = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)
    opened_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    meter_at_open = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    cost = models.DecimalField(max_digits=19, decimal_places=4, default=Decimal("0"))
    currency = models.CharField(max_length=3)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "equipment_maintenance_order"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "work_order_number"], name="eqp_work_order_uq"
            ),
            models.CheckConstraint(
                condition=models.Q(cost__gte=0), name="eqp_maintenance_cost_valid"
            ),
        ]
        indexes = [
            models.Index(fields=["company", "stage", "due_date"], name="eqp_maintenance_due_idx")
        ]

    def clean(self) -> None:
        super().clean()
        if self.equipment_id and self.equipment.company_id != self.company_id:
            raise ValidationError("Maintenance order cannot cross companies")
        if self.stage_id and (
            self.stage.company_id != self.company_id
            or self.stage.entity_type != FieldStage.EntityType.MAINTENANCE
        ):
            raise ValidationError("Maintenance order requires a maintenance stage")
