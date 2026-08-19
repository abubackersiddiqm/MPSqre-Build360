from __future__ import annotations

from collections.abc import Iterable
from typing import NoReturn

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.base import ModelBase

from modules.platform.models import PublicIdModel, TimestampedModel
from modules.tenant.models import Company


class LocalizationPack(PublicIdModel, TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PUBLISHED = "PUBLISHED", "Published"
        RETIRED = "RETIRED", "Retired"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="localization_packs",
    )
    code = models.CharField(max_length=80)
    version = models.PositiveIntegerField(default=1)
    name = models.CharField(max_length=200)
    country_code = models.CharField(max_length=2)
    locale = models.CharField(max_length=35)
    currency = models.CharField(max_length=3)
    timezone = models.CharField(max_length=64)
    unit_system_code = models.CharField(max_length=50)
    date_format = models.CharField(max_length=50, default="DD/MM/YYYY")
    time_format = models.CharField(max_length=20, default="24h")
    number_format = models.JSONField(default=dict)
    address_schema = models.JSONField(default=dict)
    tax_schema = models.JSONField(default=dict)
    terminology = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    is_default = models.BooleanField(default=False)
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    published_by_public_id = models.UUIDField(null=True, blank=True)
    checksum_sha256 = models.CharField(max_length=64, blank=True)

    class Meta:
        db_table = "integration_localization_pack"
        ordering = ["company_id", "country_code", "code", "-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code", "version"],
                name="int_loc_code_ver_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gt=models.F("effective_from")),
                name="int_loc_range_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "status", "country_code"],
                name="int_loc_status_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        self.country_code = self.country_code.upper()
        self.currency = self.currency.upper()
        if self.status == self.Status.PUBLISHED and not self.checksum_sha256:
            raise ValidationError("A published localization pack requires a checksum")


class ExchangeRateSnapshot(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="exchange_rate_snapshots",
    )
    base_currency = models.CharField(max_length=3)
    quote_currency = models.CharField(max_length=3)
    rate = models.DecimalField(max_digits=20, decimal_places=8)
    effective_at = models.DateTimeField()
    source_code = models.CharField(max_length=100)
    checksum_sha256 = models.CharField(max_length=64)
    recorded_by_public_id = models.UUIDField()

    class Meta:
        db_table = "integration_exchange_rate"
        ordering = ["-effective_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "base_currency", "quote_currency", "effective_at"],
                name="int_fx_pair_time_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(rate__gt=0),
                name="int_fx_rate_positive",
            ),
            models.CheckConstraint(
                condition=~models.Q(base_currency=models.F("quote_currency")),
                name="int_fx_pair_distinct",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "base_currency", "quote_currency", "effective_at"],
                name="int_fx_lookup_idx",
            )
        ]

    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        if self.pk:
            raise ValidationError("Exchange-rate snapshots are append-only")
        self.base_currency = self.base_currency.upper()
        self.quote_currency = self.quote_currency.upper()
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    def delete(self, using: str | None = None, keep_parents: bool = False) -> NoReturn:
        raise ValidationError("Exchange-rate snapshots are append-only")


class ConnectorProfile(PublicIdModel, TimestampedModel):
    class ConnectorType(models.TextChoices):
        ACCOUNTING = "ACCOUNTING", "Accounting"
        IDENTITY = "IDENTITY", "Identity"
        STORAGE = "STORAGE", "Storage"
        COMMUNICATION = "COMMUNICATION", "Communication"
        ANALYTICS = "ANALYTICS", "Analytics"
        CUSTOM = "CUSTOM", "Custom"

    class Direction(models.TextChoices):
        INBOUND = "INBOUND", "Inbound"
        OUTBOUND = "OUTBOUND", "Outbound"
        BIDIRECTIONAL = "BIDIRECTIONAL", "Bidirectional"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ACTIVE = "ACTIVE", "Active"
        SUSPENDED = "SUSPENDED", "Suspended"
        RETIRED = "RETIRED", "Retired"

    class HealthStatus(models.TextChoices):
        UNKNOWN = "UNKNOWN", "Unknown"
        HEALTHY = "HEALTHY", "Healthy"
        DEGRADED = "DEGRADED", "Degraded"
        UNAVAILABLE = "UNAVAILABLE", "Unavailable"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="integration_connectors",
    )
    code = models.CharField(max_length=100)
    name = models.CharField(max_length=200)
    connector_type = models.CharField(max_length=30, choices=ConnectorType.choices)
    provider_code = models.CharField(max_length=100)
    direction = models.CharField(max_length=20, choices=Direction.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    base_url = models.URLField(max_length=500, blank=True)
    public_config = models.JSONField(default=dict, blank=True)
    secret_ref = models.CharField(max_length=500, blank=True)
    allowed_data_classes = models.JSONField(default=list, blank=True)
    health_status = models.CharField(
        max_length=20,
        choices=HealthStatus.choices,
        default=HealthStatus.UNKNOWN,
    )
    last_health_checked_at = models.DateTimeField(null=True, blank=True)
    last_health_message = models.CharField(max_length=500, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "integration_connector_profile"
        ordering = ["company_id", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="int_connector_code_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "status", "connector_type"],
                name="int_connector_status_idx",
            )
        ]


class ApiClientCredential(PublicIdModel, TimestampedModel):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        SUSPENDED = "SUSPENDED", "Suspended"
        REVOKED = "REVOKED", "Revoked"
        EXPIRED = "EXPIRED", "Expired"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="api_client_credentials",
    )
    name = models.CharField(max_length=200)
    client_key = models.CharField(max_length=100, unique=True)
    secret_digest_sha256 = models.CharField(max_length=64)
    scopes = models.JSONField(default=list)
    allowed_ip_ranges = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    rotated_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_by_public_id = models.UUIDField()
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "integration_api_client"
        ordering = ["company_id", "name"]
        indexes = [
            models.Index(
                fields=["company", "status", "expires_at"],
                name="int_client_status_idx",
            )
        ]


class WebhookSubscription(PublicIdModel, TimestampedModel):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        PAUSED = "PAUSED", "Paused"
        DISABLED = "DISABLED", "Disabled"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="webhook_subscriptions",
    )
    code = models.CharField(max_length=100)
    event_code = models.CharField(max_length=200)
    target_url = models.URLField(max_length=500)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PAUSED)
    secret_ref = models.CharField(max_length=500)
    headers_public = models.JSONField(default=dict)
    allowed_data_classes = models.JSONField(default=list)
    failure_count = models.PositiveIntegerField(default=0)
    last_delivery_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "integration_webhook_subscription"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="int_webhook_code_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "status", "event_code"],
                name="int_webhook_event_idx",
            )
        ]


class WebhookDelivery(PublicIdModel, TimestampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        DELIVERED = "DELIVERED", "Delivered"
        FAILED = "FAILED", "Failed"
        DEAD_LETTER = "DEAD_LETTER", "Dead letter"

    subscription = models.ForeignKey(
        WebhookSubscription,
        on_delete=models.PROTECT,
        related_name="deliveries",
    )
    event_public_id = models.UUIDField()
    event_type = models.CharField(max_length=200)
    payload_digest_sha256 = models.CharField(max_length=64)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    attempt_count = models.PositiveIntegerField(default=0)
    response_code = models.PositiveSmallIntegerField(null=True, blank=True)
    response_digest_sha256 = models.CharField(max_length=64, blank=True)
    error_summary = models.CharField(max_length=500, blank=True)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "integration_webhook_delivery"
        constraints = [
            models.UniqueConstraint(
                fields=["subscription", "event_public_id"],
                name="int_webhook_event_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["subscription", "status", "next_retry_at"],
                name="int_delivery_retry_idx",
            )
        ]


class DataMappingProfile(PublicIdModel, TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PUBLISHED = "PUBLISHED", "Published"
        RETIRED = "RETIRED", "Retired"

    connector = models.ForeignKey(
        ConnectorProfile,
        on_delete=models.PROTECT,
        related_name="mapping_profiles",
    )
    code = models.CharField(max_length=100)
    version = models.PositiveIntegerField(default=1)
    name = models.CharField(max_length=200)
    source_schema_code = models.CharField(max_length=150)
    target_schema_code = models.CharField(max_length=150)
    mappings = models.JSONField(default=list)
    transformations = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)
    published_by_public_id = models.UUIDField(null=True, blank=True)
    checksum_sha256 = models.CharField(max_length=64, blank=True)

    class Meta:
        db_table = "integration_data_mapping"
        constraints = [
            models.UniqueConstraint(
                fields=["connector", "code", "version"],
                name="int_mapping_code_ver_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["connector", "status", "code"],
                name="int_mapping_status_idx",
            )
        ]


class SynchronizationRun(PublicIdModel, TimestampedModel):
    class Status(models.TextChoices):
        QUEUED = "QUEUED", "Queued"
        RUNNING = "RUNNING", "Running"
        COMPLETED = "COMPLETED", "Completed"
        PARTIAL = "PARTIAL", "Partial"
        FAILED = "FAILED", "Failed"
        CANCELLED = "CANCELLED", "Cancelled"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="synchronization_runs",
    )
    connector = models.ForeignKey(
        ConnectorProfile,
        on_delete=models.PROTECT,
        related_name="synchronization_runs",
    )
    mapping_profile = models.ForeignKey(
        DataMappingProfile,
        on_delete=models.PROTECT,
        related_name="synchronization_runs",
        null=True,
        blank=True,
    )
    direction = models.CharField(max_length=20, choices=ConnectorProfile.Direction.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    idempotency_key = models.CharField(max_length=150)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    records_read = models.PositiveBigIntegerField(default=0)
    records_written = models.PositiveBigIntegerField(default=0)
    records_rejected = models.PositiveBigIntegerField(default=0)
    evidence_checksum_sha256 = models.CharField(max_length=64, blank=True)
    error_summary = models.CharField(max_length=500, blank=True)
    initiated_by_public_id = models.UUIDField()
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "integration_sync_run"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "idempotency_key"],
                name="int_sync_idempotency_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "status", "created_at"],
                name="int_sync_status_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.connector_id and self.company_id != self.connector.company_id:
            raise ValidationError("Synchronization connector cannot cross companies")
        if self.mapping_profile_id and self.mapping_profile.connector_id != self.connector_id:
            raise ValidationError("Synchronization mapping must belong to the selected connector")


class MetaLeadReceipt(PublicIdModel, TimestampedModel):
    class Status(models.TextChoices):
        RECEIVED = "RECEIVED", "Received"
        PROCESSING = "PROCESSING", "Processing"
        PROCESSED = "PROCESSED", "Processed"
        DUPLICATE = "DUPLICATE", "Duplicate/reused"
        IGNORED = "IGNORED", "Ignored"
        FAILED = "FAILED", "Failed"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="meta_lead_receipts",
    )
    connector = models.ForeignKey(
        ConnectorProfile,
        on_delete=models.PROTECT,
        related_name="meta_lead_receipts",
    )
    external_lead_id = models.CharField(max_length=160)
    page_id = models.CharField(max_length=160, blank=True)
    form_id = models.CharField(max_length=160, blank=True)
    ad_id = models.CharField(max_length=160, blank=True)
    adset_id = models.CharField(max_length=160, blank=True)
    campaign_id = models.CharField(max_length=160, blank=True)
    source_created_at = models.DateTimeField(null=True, blank=True)
    field_names = models.JSONField(default=list, blank=True)
    payload_digest_sha256 = models.CharField(max_length=64)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.RECEIVED)
    contact_public_id = models.UUIDField(null=True, blank=True)
    lead_public_id = models.UUIDField(null=True, blank=True)
    attempt_count = models.PositiveIntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    error_summary = models.CharField(max_length=500, blank=True)

    class Meta:
        db_table = "integration_meta_lead_receipt"
        constraints = [
            models.UniqueConstraint(
                fields=["connector", "external_lead_id"],
                name="int_meta_lead_ext_uq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "status", "created_at"],
                name="int_meta_lead_status_idx",
            ),
            models.Index(
                fields=["connector", "form_id", "created_at"],
                name="int_meta_lead_form_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.connector_id and self.company_id != self.connector.company_id:
            raise ValidationError("Meta lead receipt cannot cross companies")


class IntegrationProviderCatalog(PublicIdModel, TimestampedModel):
    class Category(models.TextChoices):
        COMMUNICATION = "COMMUNICATION", "Communication"
        ACCOUNTING = "ACCOUNTING", "Accounting"
        PAYMENTS = "PAYMENTS", "Payments"
        STORAGE = "STORAGE", "Files & storage"
        IDENTITY = "IDENTITY", "Identity"
        DESIGN = "DESIGN", "Design & BIM"
        AUTOMATION = "AUTOMATION", "Automation & API"
        ANALYTICS = "ANALYTICS", "Analytics"

    code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=160)
    category = models.CharField(max_length=30, choices=Category.choices)
    connector_type = models.CharField(max_length=30, choices=ConnectorProfile.ConnectorType.choices)
    provider_code = models.CharField(max_length=100, unique=True)
    adapter_code = models.CharField(max_length=120, blank=True)
    description = models.CharField(max_length=500)
    capabilities = models.JSONField(default=list)
    configuration_schema = models.JSONField(default=dict)
    docs_url = models.URLField(max_length=500, blank=True)
    recommended = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=100)

    class Meta:
        db_table = "integration_provider_catalog"
        ordering = ["sort_order", "category", "name"]
        indexes = [
            models.Index(fields=["is_active", "category", "sort_order"], name="int_catalog_active_idx")
        ]
