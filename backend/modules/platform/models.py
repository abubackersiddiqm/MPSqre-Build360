import uuid
from collections.abc import Iterable
from typing import NoReturn

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.base import ModelBase


class PublicIdModel(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    class Meta:
        abstract = True


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TenantOwnedModel(PublicIdModel, TimestampedModel):
    """Shared tenant-owned persistence contract for new bounded contexts."""

    company = models.ForeignKey(
        "tenant.Company",
        on_delete=models.PROTECT,
    )

    class Meta:
        abstract = True


class AuditEvent(PublicIdModel):
    """Append-only security and business audit evidence."""

    company_public_id = models.UUIDField(null=True, blank=True)
    actor_type = models.CharField(max_length=50)
    actor_public_id = models.UUIDField(null=True, blank=True)
    action = models.CharField(max_length=200)
    entity_type = models.CharField(max_length=100)
    entity_public_id = models.UUIDField(null=True, blank=True)
    occurred_at = models.DateTimeField()
    request_id = models.UUIDField()
    correlation_id = models.UUIDField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    reason_code = models.CharField(max_length=100, blank=True)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)

    class Meta:
        db_table = "platform_audit_event"
        indexes = [
            models.Index(
                fields=["company_public_id", "occurred_at"],
                name="audit_company_time_idx",
            ),
            models.Index(
                fields=["entity_type", "entity_public_id", "occurred_at"],
                name="audit_entity_time_idx",
            ),
            models.Index(
                fields=["actor_public_id", "occurred_at"],
                name="audit_actor_time_idx",
            ),
            models.Index(fields=["correlation_id"], name="audit_correlation_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.action}:{self.public_id}"

    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        if self.pk:
            raise ValidationError("Audit events are append-only")
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    def delete(
        self,
        using: str | None = None,
        keep_parents: bool = False,
    ) -> NoReturn:
        raise ValidationError("Audit events are append-only")


class BusinessEventOutbox(PublicIdModel):
    """Committed fact awaiting publication. Payloads must exclude unnecessary PII."""

    company_public_id = models.UUIDField(null=True, blank=True)
    aggregate_type = models.CharField(max_length=100)
    aggregate_public_id = models.UUIDField()
    aggregate_version = models.PositiveBigIntegerField()
    event_type = models.CharField(max_length=200)
    event_version = models.PositiveSmallIntegerField(default=1)
    payload = models.JSONField(default=dict)
    occurred_at = models.DateTimeField()
    published_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    lock_token = models.UUIDField(null=True, blank=True)
    dead_lettered_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=1000, blank=True)
    correlation_id = models.UUIDField()
    causation_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "platform_business_event_outbox"
        indexes = [
            models.Index(
                fields=["published_at", "dead_lettered_at", "next_attempt_at"],
                name="outbox_publish_due_idx",
            ),
            models.Index(
                fields=["lock_token", "locked_at"],
                name="outbox_claim_lookup_idx",
            ),
            models.Index(
                fields=["aggregate_type", "aggregate_public_id", "aggregate_version"],
                name="outbox_aggregate_order_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "aggregate_type",
                    "aggregate_public_id",
                    "aggregate_version",
                    "event_type",
                    "event_version",
                ],
                name="outbox_unique_aggregate_fact",
            )
        ]

    def __str__(self) -> str:
        return f"{self.event_type}:{self.public_id}"
