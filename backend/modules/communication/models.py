from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from modules.platform.models import TenantOwnedModel


class CommunicationChannel(models.TextChoices):
    IN_APP = "in_app", "In-app"
    EMAIL = "email", "Email"
    SMS = "sms", "SMS"
    WHATSAPP = "whatsapp", "WhatsApp"
    VOICE = "voice", "Voice"


class ChannelPolicy(TenantOwnedModel):
    channel = models.CharField(max_length=20, choices=CommunicationChannel.choices)
    is_enabled = models.BooleanField(default=False)
    consent_required = models.BooleanField(default=True)
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)
    timezone = models.CharField(max_length=64, default="UTC")
    retry_limit = models.PositiveSmallIntegerField(default=3)
    max_daily_per_subject = models.PositiveIntegerField(default=20)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "communication_channel_policy"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "channel"],
                name="com_policy_company_channel_uq",
            ),
            models.CheckConstraint(
                condition=Q(retry_limit__lte=10),
                name="com_policy_retry_limit_ok",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "channel", "is_enabled"],
                name="com_policy_active_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if (self.quiet_hours_start is None) != (self.quiet_hours_end is None):
            raise ValidationError(
                "Quiet-hours start and end must either both be set or both be empty"
            )


class ProviderConfiguration(TenantOwnedModel):
    channel = models.CharField(max_length=20, choices=CommunicationChannel.choices)
    code = models.CharField(max_length=80)
    display_name = models.CharField(max_length=160)
    adapter_code = models.CharField(max_length=80)
    secret_reference = models.CharField(max_length=250, blank=True)
    callback_key_id = models.CharField(max_length=100, blank=True)
    priority = models.PositiveSmallIntegerField(default=100)
    is_active = models.BooleanField(default=False)
    supports_inbound = models.BooleanField(default=False)
    supports_delivery_receipts = models.BooleanField(default=False)
    configuration = models.JSONField(default=dict)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "communication_provider_config"
        ordering = ["channel", "priority", "display_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="com_provider_company_code_uq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "channel", "is_active", "priority"],
                name="com_provider_active_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.channel == CommunicationChannel.IN_APP and self.adapter_code != "in_app":
            raise ValidationError("In-app providers must use the in_app adapter")


class MessageTemplate(TenantOwnedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        RETIRED = "retired", "Retired"

    code = models.CharField(max_length=100)
    name = models.CharField(max_length=200)
    channel = models.CharField(max_length=20, choices=CommunicationChannel.choices)
    locale = models.CharField(max_length=35, default="en")
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    subject_template = models.CharField(max_length=300, blank=True)
    body_template = models.TextField()
    variable_names = models.JSONField(default=list)
    purpose_code = models.CharField(max_length=100)
    created_by_public_id = models.UUIDField()
    published_by_public_id = models.UUIDField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "communication_message_template"
        ordering = ["code", "channel", "locale", "-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code", "channel", "locale", "version"],
                name="com_template_version_uq",
            ),
            models.UniqueConstraint(
                fields=["company", "code", "channel", "locale"],
                condition=Q(status="published"),
                name="com_template_published_uq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "channel", "status", "locale"],
                name="com_template_lookup_idx",
            )
        ]


class ConsentRecord(TenantOwnedModel):
    class Status(models.TextChoices):
        GRANTED = "granted", "Granted"
        WITHDRAWN = "withdrawn", "Withdrawn"
        DENIED = "denied", "Denied"

    subject_type = models.CharField(max_length=80)
    subject_public_id = models.UUIDField()
    channel = models.CharField(max_length=20, choices=CommunicationChannel.choices)
    purpose_code = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=Status.choices)
    source_code = models.CharField(max_length=100)
    proof_reference = models.CharField(max_length=250, blank=True)
    effective_at = models.DateTimeField()
    recorded_by_public_id = models.UUIDField()
    reason = models.CharField(max_length=500, blank=True)

    class Meta:
        db_table = "communication_consent_record"
        ordering = ["-effective_at", "-id"]
        indexes = [
            models.Index(
                fields=[
                    "company",
                    "subject_type",
                    "subject_public_id",
                    "channel",
                    "purpose_code",
                    "effective_at",
                ],
                name="com_consent_lookup_idx",
            )
        ]


class CommunicationRequest(TenantOwnedModel):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        SCHEDULED = "scheduled", "Scheduled"
        PROCESSING = "processing", "Processing"
        SENT = "sent", "Sent"
        DELIVERED = "delivered", "Delivered"
        FAILED = "failed", "Failed"
        SUPPRESSED = "suppressed", "Suppressed"
        CANCELLED = "cancelled", "Cancelled"

    channel = models.CharField(max_length=20, choices=CommunicationChannel.choices)
    template = models.ForeignKey(
        MessageTemplate,
        on_delete=models.PROTECT,
        related_name="requests",
    )
    provider = models.ForeignKey(
        ProviderConfiguration,
        on_delete=models.PROTECT,
        related_name="requests",
        null=True,
        blank=True,
    )
    subject_type = models.CharField(max_length=80)
    subject_public_id = models.UUIDField()
    recipient_reference_type = models.CharField(max_length=80)
    recipient_reference_public_id = models.UUIDField()
    purpose_code = models.CharField(max_length=100)
    locale = models.CharField(max_length=35, default="en")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    rendered_subject = models.CharField(max_length=300, blank=True)
    rendered_body = models.TextField()
    template_variables = models.JSONField(default=dict)
    idempotency_key = models.CharField(max_length=120)
    requested_by_public_id = models.UUIDField()
    scheduled_for = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    suppression_reason = models.CharField(max_length=250, blank=True)
    provider_message_id = models.CharField(max_length=250, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "communication_request"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "idempotency_key"],
                name="com_request_idempotency_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "status", "scheduled_for"],
                name="com_request_queue_idx",
            ),
            models.Index(
                fields=["company", "subject_type", "subject_public_id", "created_at"],
                name="com_request_subject_idx",
            ),
            models.Index(
                fields=["company", "provider_message_id"],
                name="com_request_provider_msg_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.template_id and self.template.company_id != self.company_id:
            raise ValidationError("Communication template cannot cross companies")
        if self.template_id and self.template.channel != self.channel:
            raise ValidationError("Communication channel must match the template")
        if self.provider_id and self.provider.company_id != self.company_id:
            raise ValidationError("Communication provider cannot cross companies")
        if self.provider_id and self.provider.channel != self.channel:
            raise ValidationError("Communication provider channel does not match")


class CommunicationAttempt(TenantOwnedModel):
    class Status(models.TextChoices):
        STARTED = "started", "Started"
        ACCEPTED = "accepted", "Accepted"
        DELIVERED = "delivered", "Delivered"
        FAILED = "failed", "Failed"

    request = models.ForeignKey(
        CommunicationRequest,
        on_delete=models.PROTECT,
        related_name="attempts",
    )
    provider = models.ForeignKey(
        ProviderConfiguration,
        on_delete=models.PROTECT,
        related_name="attempts",
    )
    attempt_number = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=20, choices=Status.choices)
    provider_message_id = models.CharField(max_length=250, blank=True)
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)
    error_code = models.CharField(max_length=100, blank=True)
    error_message = models.CharField(max_length=500, blank=True)
    response_metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "communication_attempt"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "request", "attempt_number"],
                name="com_attempt_number_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "request", "status"],
                name="com_attempt_request_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.request_id and self.request.company_id != self.company_id:
            raise ValidationError("Communication attempt cannot cross companies")
        if self.provider_id and self.provider.company_id != self.company_id:
            raise ValidationError("Communication provider cannot cross companies")


class CallbackReceipt(TenantOwnedModel):
    provider = models.ForeignKey(
        ProviderConfiguration,
        on_delete=models.PROTECT,
        related_name="callback_receipts",
    )
    request = models.ForeignKey(
        CommunicationRequest,
        on_delete=models.PROTECT,
        related_name="callback_receipts",
        null=True,
        blank=True,
    )
    provider_event_id = models.CharField(max_length=250)
    event_type = models.CharField(max_length=100)
    provider_message_id = models.CharField(max_length=250, blank=True)
    payload_digest = models.CharField(max_length=64)
    signature_valid = models.BooleanField(default=False)
    received_at = models.DateTimeField()
    processed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=250, blank=True)

    class Meta:
        db_table = "communication_callback_receipt"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "provider", "provider_event_id"],
                name="com_callback_event_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "provider", "received_at"],
                name="com_callback_lookup_idx",
            )
        ]


class InboundCommunication(TenantOwnedModel):
    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        CORRELATED = "correlated", "Correlated"
        REVIEW_REQUIRED = "review_required", "Review required"
        PROCESSED = "processed", "Processed"
        REJECTED = "rejected", "Rejected"

    provider = models.ForeignKey(
        ProviderConfiguration,
        on_delete=models.PROTECT,
        related_name="inbound_messages",
    )
    channel = models.CharField(max_length=20, choices=CommunicationChannel.choices)
    provider_message_id = models.CharField(max_length=250)
    sender_reference_hash = models.CharField(max_length=64, blank=True)
    subject_reference_type = models.CharField(max_length=80, blank=True)
    subject_reference_public_id = models.UUIDField(null=True, blank=True)
    summary = models.CharField(max_length=500)
    status = models.CharField(max_length=30, choices=Status.choices)
    received_at = models.DateTimeField()
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "communication_inbound"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "provider", "provider_message_id"],
                name="com_inbound_message_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "status", "received_at"],
                name="com_inbound_queue_idx",
            )
        ]
