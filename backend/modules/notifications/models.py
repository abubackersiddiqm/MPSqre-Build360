from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from modules.communication.models import CommunicationChannel
from modules.platform.models import TenantOwnedModel


class NotificationPreference(TenantOwnedModel):
    class DigestMode(models.TextChoices):
        IMMEDIATE = "immediate", "Immediate"
        DAILY = "daily", "Daily digest"
        WEEKLY = "weekly", "Weekly digest"
        MUTED = "muted", "Muted"

    user_public_id = models.UUIDField()
    event_code = models.CharField(max_length=120)
    channel = models.CharField(max_length=20, choices=CommunicationChannel.choices)
    enabled = models.BooleanField(default=True)
    digest_mode = models.CharField(
        max_length=20,
        choices=DigestMode.choices,
        default=DigestMode.IMMEDIATE,
    )
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "notification_preference"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "user_public_id", "event_code", "channel"],
                name="not_pref_user_event_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "user_public_id", "enabled"],
                name="not_pref_user_active_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if (self.quiet_hours_start is None) != (self.quiet_hours_end is None):
            raise ValidationError(
                "Notification quiet-hours start and end must both be set or both be empty"
            )


class NotificationRule(TenantOwnedModel):
    event_code = models.CharField(max_length=120)
    name = models.CharField(max_length=200)
    default_title_template = models.CharField(max_length=250)
    default_body_template = models.TextField()
    severity = models.CharField(
        max_length=20,
        choices=[
            ("info", "Information"),
            ("success", "Success"),
            ("warning", "Warning"),
            ("critical", "Critical"),
        ],
        default="info",
    )
    channels = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "notification_rule"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "event_code"],
                name="not_rule_company_event_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "is_active", "event_code"],
                name="not_rule_active_idx",
            )
        ]


class Notification(TenantOwnedModel):
    class Severity(models.TextChoices):
        INFO = "info", "Information"
        SUCCESS = "success", "Success"
        WARNING = "warning", "Warning"
        CRITICAL = "critical", "Critical"

    user_public_id = models.UUIDField()
    event_code = models.CharField(max_length=120)
    title = models.CharField(max_length=250)
    body = models.TextField()
    severity = models.CharField(
        max_length=20,
        choices=Severity.choices,
        default=Severity.INFO,
    )
    action_path = models.CharField(max_length=300, blank=True)
    source_type = models.CharField(max_length=100, blank=True)
    source_public_id = models.UUIDField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notification_item"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["company", "user_public_id", "read_at", "created_at"],
                name="not_item_inbox_idx",
            ),
            models.Index(
                fields=["company", "event_code", "created_at"],
                name="not_item_event_idx",
            ),
        ]


class NotificationDelivery(TenantOwnedModel):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        SENT = "sent", "Sent"
        DELIVERED = "delivered", "Delivered"
        FAILED = "failed", "Failed"
        SUPPRESSED = "suppressed", "Suppressed"

    notification = models.ForeignKey(
        Notification,
        on_delete=models.PROTECT,
        related_name="deliveries",
    )
    channel = models.CharField(max_length=20, choices=CommunicationChannel.choices)
    communication_request = models.ForeignKey(
        "communication.CommunicationRequest",
        on_delete=models.PROTECT,
        related_name="notification_deliveries",
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=20, choices=Status.choices)
    attempted_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    failure_code = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = "notification_delivery"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "notification", "channel"],
                name="not_delivery_channel_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "status", "attempted_at"],
                name="not_delivery_queue_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.notification_id and self.notification.company_id != self.company_id:
            raise ValidationError("Notification delivery cannot cross companies")
        if (
            self.communication_request_id
            and self.communication_request.company_id != self.company_id
        ):
            raise ValidationError("Communication request cannot cross companies")
