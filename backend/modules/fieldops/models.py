from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from modules.platform.models import TenantOwnedModel


class FieldStage(TenantOwnedModel):
    class EntityType(models.TextChoices):
        LABOUR_ALLOCATION = "labour_allocation", "Labour allocation"
        ATTENDANCE = "attendance", "Attendance"
        EQUIPMENT = "equipment", "Equipment"
        EQUIPMENT_ALLOCATION = "equipment_allocation", "Equipment allocation"
        MAINTENANCE = "maintenance", "Maintenance"
        INSPECTION = "inspection", "Inspection"
        NCR = "ncr", "Non-conformance"
        INCIDENT = "incident", "Safety incident"
        OFFLINE_OPERATION = "offline_operation", "Offline operation"

    class Outcome(models.TextChoices):
        OPEN = "open", "Open"
        REVIEW = "review", "Under review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        ACTIVE = "active", "Active"
        COMPLETE = "complete", "Complete"
        CANCELLED = "cancelled", "Cancelled"
        BLOCKED = "blocked", "Blocked"

    entity_type = models.CharField(max_length=40, choices=EntityType.choices)
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=160)
    outcome = models.CharField(max_length=30, choices=Outcome.choices, default=Outcome.OPEN)
    sort_order = models.PositiveIntegerField(default=100)
    allowed_next_codes = models.JSONField(default=list)
    is_initial = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "fieldops_stage"
        ordering = ["entity_type", "sort_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "entity_type", "code"],
                name="fld_stage_company_code_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gt=models.F("effective_from")),
                name="fld_stage_range_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "entity_type", "is_active", "sort_order"],
                name="fld_stage_active_idx",
            )
        ]


class OfflineOperation(TenantOwnedModel):
    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        APPLIED = "applied", "Applied"
        CONFLICT = "conflict", "Conflict"
        REJECTED = "rejected", "Rejected"

    operation_id = models.UUIDField()
    device_id = models.UUIDField()
    actor_membership_public_id = models.UUIDField()
    operation_type = models.CharField(max_length=100)
    aggregate_type = models.CharField(max_length=80)
    aggregate_public_id = models.UUIDField(null=True, blank=True)
    expected_version = models.PositiveBigIntegerField(null=True, blank=True)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RECEIVED)
    result = models.JSONField(default=dict)
    rejection_code = models.CharField(max_length=100, blank=True)
    received_at = models.DateTimeField()
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "fieldops_offline_operation"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "operation_id"],
                name="fld_offline_operation_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "device_id", "received_at"],
                name="fld_offline_device_idx",
            ),
            models.Index(
                fields=["company", "status", "received_at"],
                name="fld_offline_status_idx",
            ),
        ]


class SyncCheckpoint(TenantOwnedModel):
    device_id = models.UUIDField()
    actor_membership_public_id = models.UUIDField()
    last_operation_received_at = models.DateTimeField(null=True, blank=True)
    last_server_sequence = models.PositiveBigIntegerField(default=0)
    last_successful_sync_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "fieldops_sync_checkpoint"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "device_id", "actor_membership_public_id"],
                name="fld_checkpoint_device_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "actor_membership_public_id", "revoked_at"],
                name="fld_checkpoint_actor_idx",
            )
        ]


class SyncConflict(TenantOwnedModel):
    operation = models.OneToOneField(
        OfflineOperation,
        on_delete=models.PROTECT,
        related_name="conflict",
    )
    conflict_code = models.CharField(max_length=100)
    server_version = models.PositiveBigIntegerField(null=True, blank=True)
    client_version = models.PositiveBigIntegerField(null=True, blank=True)
    server_snapshot = models.JSONField(default=dict)
    resolution = models.JSONField(default=dict)
    resolved_by_public_id = models.UUIDField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "fieldops_sync_conflict"
        indexes = [
            models.Index(
                fields=["company", "resolved_at", "created_at"],
                name="fld_conflict_open_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.operation_id and self.operation.company_id != self.company_id:
            raise ValidationError("Sync conflict cannot cross companies")
