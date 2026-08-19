from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from modules.integration.models import (
    ApiClientCredential,
    ConnectorProfile,
    DataMappingProfile,
    ExchangeRateSnapshot,
    LocalizationPack,
    SynchronizationRun,
    WebhookDelivery,
    WebhookSubscription,
)
from modules.platform.actors import RequestActor
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.tenant.models import Company


def _canonical_digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _audit(
    *,
    actor: RequestActor,
    company: Company,
    action: str,
    entity_type: str,
    entity_public_id: uuid.UUID,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason_code: str = "",
) -> None:
    append_audit(
        AuditRecord(
            action=action,
            entity_type=entity_type,
            entity_public_id=entity_public_id,
            actor_public_id=actor.user_public_id,
            company_public_id=company.public_id,
            request_id=actor.request_id,
            correlation_id=actor.request_id,
            ip_address=actor.ip_address,
            user_agent=actor.user_agent,
            before=before or {},
            after=after or {},
            reason_code=reason_code,
        )
    )


def _event(
    *,
    actor: RequestActor,
    company: Company,
    event_type: str,
    aggregate_type: str,
    aggregate_public_id: uuid.UUID,
    aggregate_version: int,
    payload: dict[str, Any],
) -> None:
    append_event(
        EventRecord(
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_public_id=aggregate_public_id,
            aggregate_version=aggregate_version,
            company_public_id=company.public_id,
            correlation_id=actor.request_id,
            payload=payload,
        )
    )


def integration_summary(company: Company) -> dict[str, int]:
    return {
        "published_localization_packs": LocalizationPack.objects.filter(
            company=company,
            status=LocalizationPack.Status.PUBLISHED,
        ).count(),
        "active_connectors": ConnectorProfile.objects.filter(
            company=company,
            status=ConnectorProfile.Status.ACTIVE,
        ).count(),
        "active_api_clients": ApiClientCredential.objects.filter(
            company=company,
            status=ApiClientCredential.Status.ACTIVE,
        ).count(),
        "active_webhooks": WebhookSubscription.objects.filter(
            company=company,
            status=WebhookSubscription.Status.ACTIVE,
        ).count(),
        "failed_deliveries": WebhookDelivery.objects.filter(
            subscription__company=company,
            status__in=[WebhookDelivery.Status.FAILED, WebhookDelivery.Status.DEAD_LETTER],
        ).count(),
        "open_sync_runs": SynchronizationRun.objects.filter(
            company=company,
            status__in=[SynchronizationRun.Status.QUEUED, SynchronizationRun.Status.RUNNING],
        ).count(),
    }


@transaction.atomic
def create_localization_pack(
    *,
    company: Company,
    actor: RequestActor,
    code: str,
    name: str,
    country_code: str,
    locale: str,
    currency: str,
    timezone_code: str,
    unit_system_code: str,
    date_format: str,
    time_format: str,
    number_format: dict[str, Any],
    address_schema: dict[str, Any],
    tax_schema: dict[str, Any],
    terminology: dict[str, Any],
    effective_from: Any,
    effective_to: Any = None,
    is_default: bool = False,
) -> LocalizationPack:
    latest = (
        LocalizationPack.objects.filter(
            company=company, code__iexact=code.strip()
        )
        .order_by("-version")
        .first()
    )
    item = LocalizationPack(
        company=company,
        code=code.strip().upper(),
        version=(latest.version + 1) if latest else 1,
        name=name.strip(),
        country_code=country_code.strip().upper(),
        locale=locale.strip(),
        currency=currency.strip().upper(),
        timezone=timezone_code.strip(),
        unit_system_code=unit_system_code.strip(),
        date_format=date_format.strip(),
        time_format=time_format.strip(),
        number_format=number_format,
        address_schema=address_schema,
        tax_schema=tax_schema,
        terminology=terminology,
        effective_from=effective_from,
        effective_to=effective_to,
        is_default=is_default,
    )
    item.full_clean()
    item.save()
    _audit(
        actor=actor,
        company=company,
        action="integration.localization.created",
        entity_type="localization_pack",
        entity_public_id=item.public_id,
        after={"code": item.code, "version": item.version, "country": item.country_code},
    )
    _event(
        actor=actor,
        company=company,
        event_type="integration.localization.created",
        aggregate_type="localization_pack",
        aggregate_public_id=item.public_id,
        aggregate_version=item.version,
        payload={"code": item.code, "country": item.country_code},
    )
    return item


@transaction.atomic
def publish_localization_pack(
    *,
    company: Company,
    actor: RequestActor,
    public_id: uuid.UUID,
    expected_version: int,
) -> LocalizationPack:
    item = (
        LocalizationPack.objects.select_for_update()
        .filter(company=company, public_id=public_id)
        .first()
    )
    if item is None:
        raise ValidationError("Localization pack was not found")
    if item.version != expected_version:
        raise ValidationError("Localization pack was modified by another request")
    if item.status != LocalizationPack.Status.DRAFT:
        raise ValidationError("Only draft localization packs can be published")
    if item.is_default:
        LocalizationPack.objects.filter(company=company, is_default=True).exclude(
            pk=item.pk
        ).update(is_default=False)
    checksum = _canonical_digest(
        {
            "code": item.code,
            "version": item.version,
            "country_code": item.country_code,
            "locale": item.locale,
            "currency": item.currency,
            "timezone": item.timezone,
            "unit_system_code": item.unit_system_code,
            "date_format": item.date_format,
            "time_format": item.time_format,
            "number_format": item.number_format,
            "address_schema": item.address_schema,
            "tax_schema": item.tax_schema,
            "terminology": item.terminology,
        }
    )
    item.status = LocalizationPack.Status.PUBLISHED
    item.published_at = timezone.now()
    item.published_by_public_id = actor.user_public_id
    item.checksum_sha256 = checksum
    item.full_clean()
    item.save(
        update_fields=[
            "status",
            "published_at",
            "published_by_public_id",
            "checksum_sha256",
            "updated_at",
        ]
    )
    _audit(
        actor=actor,
        company=company,
        action="integration.localization.published",
        entity_type="localization_pack",
        entity_public_id=item.public_id,
        after={"code": item.code, "version": item.version, "checksum": checksum},
    )
    _event(
        actor=actor,
        company=company,
        event_type="integration.localization.published",
        aggregate_type="localization_pack",
        aggregate_public_id=item.public_id,
        aggregate_version=item.version,
        payload={"code": item.code, "checksum": checksum},
    )
    return item


@transaction.atomic
def record_exchange_rate(
    *,
    company: Company,
    actor: RequestActor,
    base_currency: str,
    quote_currency: str,
    rate: Decimal,
    effective_at: Any,
    source_code: str,
) -> ExchangeRateSnapshot:
    evidence = {
        "base_currency": base_currency.upper(),
        "quote_currency": quote_currency.upper(),
        "rate": str(rate),
        "effective_at": effective_at,
        "source_code": source_code,
    }
    item = ExchangeRateSnapshot(
        company=company,
        base_currency=base_currency.upper(),
        quote_currency=quote_currency.upper(),
        rate=rate,
        effective_at=effective_at,
        source_code=source_code.strip(),
        checksum_sha256=_canonical_digest(evidence),
        recorded_by_public_id=actor.user_public_id,
    )
    item.full_clean()
    item.save()
    _audit(
        actor=actor,
        company=company,
        action="integration.exchange_rate.recorded",
        entity_type="exchange_rate_snapshot",
        entity_public_id=item.public_id,
        after={"pair": f"{item.base_currency}/{item.quote_currency}", "rate": str(item.rate)},
    )
    return item


@transaction.atomic
def create_connector(
    *,
    company: Company,
    actor: RequestActor,
    code: str,
    name: str,
    connector_type: str,
    provider_code: str,
    direction: str,
    base_url: str = "",
    public_config: dict[str, Any] | None = None,
    secret_ref: str = "",
    allowed_data_classes: list[str] | None = None,
) -> ConnectorProfile:
    item = ConnectorProfile(
        company=company,
        code=code.strip().upper(),
        name=name.strip(),
        connector_type=connector_type,
        provider_code=provider_code.strip().upper(),
        direction=direction,
        base_url=base_url.strip(),
        public_config=public_config or {},
        secret_ref=secret_ref.strip(),
        allowed_data_classes=allowed_data_classes or [],
    )
    item.full_clean()
    item.save()
    _audit(
        actor=actor,
        company=company,
        action="integration.connector.created",
        entity_type="connector_profile",
        entity_public_id=item.public_id,
        after={"code": item.code, "type": item.connector_type, "provider": item.provider_code},
    )
    _event(
        actor=actor,
        company=company,
        event_type="integration.connector.created",
        aggregate_type="connector_profile",
        aggregate_public_id=item.public_id,
        aggregate_version=item.version,
        payload={"code": item.code, "type": item.connector_type},
    )
    return item


@transaction.atomic
def transition_connector_status(
    *,
    company: Company,
    actor: RequestActor,
    public_id: uuid.UUID,
    expected_version: int,
    target_status: str,
    reason: str = "",
) -> ConnectorProfile:
    item = (
        ConnectorProfile.objects.select_for_update()
        .filter(company=company, public_id=public_id)
        .first()
    )
    if item is None:
        raise ValidationError("Connector was not found")
    if item.version != expected_version:
        raise ValidationError("Connector was modified by another request")
    allowed = {value for value, _ in ConnectorProfile.Status.choices}
    if target_status not in allowed:
        raise ValidationError("Invalid connector status")
    if target_status == ConnectorProfile.Status.ACTIVE:
        local_provider = item.provider_code == "LOCAL"
        if not item.base_url and not local_provider:
            raise ValidationError("Active connectors require a base URL")
        if not item.secret_ref and not local_provider:
            raise ValidationError("Active connectors require a governed secret reference")
    before = {"status": item.status, "version": item.version}
    item.status = target_status
    item.version += 1
    item.save(update_fields=["status", "version", "updated_at"])
    _audit(
        actor=actor,
        company=company,
        action="integration.connector.status_changed",
        entity_type="connector_profile",
        entity_public_id=item.public_id,
        before=before,
        after={"status": item.status, "version": item.version},
        reason_code=reason.strip(),
    )
    _event(
        actor=actor,
        company=company,
        event_type="integration.connector.status_changed",
        aggregate_type="connector_profile",
        aggregate_public_id=item.public_id,
        aggregate_version=item.version,
        payload={"status": item.status},
    )
    return item


@transaction.atomic
def evaluate_connector_health(
    *,
    company: Company,
    actor: RequestActor,
    public_id: uuid.UUID,
    expected_version: int,
) -> ConnectorProfile:
    item = (
        ConnectorProfile.objects.select_for_update()
        .filter(company=company, public_id=public_id)
        .first()
    )
    if item is None:
        raise ValidationError("Connector was not found")
    if item.version != expected_version:
        raise ValidationError("Connector was modified by another request")
    configured = bool(item.base_url or item.connector_type == ConnectorProfile.ConnectorType.CUSTOM)
    secured = bool(item.secret_ref) or item.connector_type in {
        ConnectorProfile.ConnectorType.ANALYTICS,
        ConnectorProfile.ConnectorType.CUSTOM,
    }
    item.health_status = (
        ConnectorProfile.HealthStatus.HEALTHY
        if configured and secured
        else ConnectorProfile.HealthStatus.DEGRADED
    )
    item.last_health_checked_at = timezone.now()
    item.last_health_message = (
        "Configuration contract is complete; no external network request was executed."
        if item.health_status == ConnectorProfile.HealthStatus.HEALTHY
        else "Connector requires a base URL or governed secret reference."
    )
    item.version += 1
    item.save(
        update_fields=[
            "health_status",
            "last_health_checked_at",
            "last_health_message",
            "version",
            "updated_at",
        ]
    )
    _audit(
        actor=actor,
        company=company,
        action="integration.connector.health_evaluated",
        entity_type="connector_profile",
        entity_public_id=item.public_id,
        after={"status": item.health_status, "message": item.last_health_message},
    )
    return item


@transaction.atomic
def issue_api_client(
    *,
    company: Company,
    actor: RequestActor,
    name: str,
    scopes: list[str],
    allowed_ip_ranges: list[str] | None = None,
    expires_at: Any = None,
) -> tuple[ApiClientCredential, str]:
    raw_secret = secrets.token_urlsafe(48)
    client_key = f"b360_{company.code.lower()}_{secrets.token_hex(8)}"
    item = ApiClientCredential(
        company=company,
        name=name.strip(),
        client_key=client_key,
        secret_digest_sha256=hashlib.sha256(raw_secret.encode("utf-8")).hexdigest(),
        scopes=sorted(set(scopes)),
        allowed_ip_ranges=allowed_ip_ranges or [],
        expires_at=expires_at,
        created_by_public_id=actor.user_public_id,
    )
    item.full_clean()
    item.save()
    _audit(
        actor=actor,
        company=company,
        action="integration.api_client.issued",
        entity_type="api_client_credential",
        entity_public_id=item.public_id,
        after={"name": item.name, "client_key": item.client_key, "scopes": item.scopes},
    )
    _event(
        actor=actor,
        company=company,
        event_type="integration.api_client.issued",
        aggregate_type="api_client_credential",
        aggregate_public_id=item.public_id,
        aggregate_version=item.version,
        payload={"client_key": item.client_key, "scopes": item.scopes},
    )
    return item, raw_secret


@transaction.atomic
def rotate_api_client(
    *,
    company: Company,
    actor: RequestActor,
    public_id: uuid.UUID,
    expected_version: int,
) -> tuple[ApiClientCredential, str]:
    item = (
        ApiClientCredential.objects.select_for_update()
        .filter(company=company, public_id=public_id)
        .first()
    )
    if item is None:
        raise ValidationError("API client was not found")
    if item.version != expected_version:
        raise ValidationError("API client was modified by another request")
    if item.status == ApiClientCredential.Status.REVOKED:
        raise ValidationError("A revoked API client cannot be rotated")
    raw_secret = secrets.token_urlsafe(48)
    item.secret_digest_sha256 = hashlib.sha256(raw_secret.encode("utf-8")).hexdigest()
    item.rotated_at = timezone.now()
    item.version += 1
    item.save(update_fields=["secret_digest_sha256", "rotated_at", "version", "updated_at"])
    _audit(
        actor=actor,
        company=company,
        action="integration.api_client.rotated",
        entity_type="api_client_credential",
        entity_public_id=item.public_id,
        after={"client_key": item.client_key, "version": item.version},
    )
    return item, raw_secret


@transaction.atomic
def revoke_api_client(
    *,
    company: Company,
    actor: RequestActor,
    public_id: uuid.UUID,
    expected_version: int,
    reason: str,
) -> ApiClientCredential:
    item = (
        ApiClientCredential.objects.select_for_update()
        .filter(company=company, public_id=public_id)
        .first()
    )
    if item is None:
        raise ValidationError("API client was not found")
    if item.version != expected_version:
        raise ValidationError("API client was modified by another request")
    item.status = ApiClientCredential.Status.REVOKED
    item.revoked_at = timezone.now()
    item.version += 1
    item.save(update_fields=["status", "revoked_at", "version", "updated_at"])
    _audit(
        actor=actor,
        company=company,
        action="integration.api_client.revoked",
        entity_type="api_client_credential",
        entity_public_id=item.public_id,
        after={"client_key": item.client_key, "status": item.status},
        reason_code=reason.strip(),
    )
    return item


@transaction.atomic
def create_webhook_subscription(
    *,
    company: Company,
    actor: RequestActor,
    code: str,
    event_code: str,
    target_url: str,
    secret_ref: str,
    headers_public: dict[str, Any] | None = None,
    allowed_data_classes: list[str] | None = None,
) -> WebhookSubscription:
    item = WebhookSubscription(
        company=company,
        code=code.strip().upper(),
        event_code=event_code.strip(),
        target_url=target_url.strip(),
        secret_ref=secret_ref.strip(),
        headers_public=headers_public or {},
        allowed_data_classes=allowed_data_classes or [],
    )
    item.full_clean()
    item.save()
    _audit(
        actor=actor,
        company=company,
        action="integration.webhook.created",
        entity_type="webhook_subscription",
        entity_public_id=item.public_id,
        after={"code": item.code, "event_code": item.event_code, "status": item.status},
    )
    return item


@transaction.atomic
def transition_webhook_status(
    *,
    company: Company,
    actor: RequestActor,
    public_id: uuid.UUID,
    expected_version: int,
    target_status: str,
    reason: str = "",
) -> WebhookSubscription:
    item = (
        WebhookSubscription.objects.select_for_update()
        .filter(company=company, public_id=public_id)
        .first()
    )
    if item is None:
        raise ValidationError("Webhook subscription was not found")
    if item.version != expected_version:
        raise ValidationError("Webhook subscription was modified by another request")
    allowed = {value for value, _ in WebhookSubscription.Status.choices}
    if target_status not in allowed:
        raise ValidationError("Invalid webhook status")
    if target_status == WebhookSubscription.Status.ACTIVE:
        if not item.target_url.lower().startswith("https://"):
            raise ValidationError("Active webhooks require an HTTPS target")
        if not item.secret_ref:
            raise ValidationError("Active webhooks require a governed secret reference")
    before = {"status": item.status, "version": item.version}
    item.status = target_status
    item.version += 1
    item.save(update_fields=["status", "version", "updated_at"])
    _audit(
        actor=actor,
        company=company,
        action="integration.webhook.status_changed",
        entity_type="webhook_subscription",
        entity_public_id=item.public_id,
        before=before,
        after={"status": item.status, "version": item.version},
        reason_code=reason.strip(),
    )
    _event(
        actor=actor,
        company=company,
        event_type="integration.webhook.status_changed",
        aggregate_type="webhook_subscription",
        aggregate_public_id=item.public_id,
        aggregate_version=item.version,
        payload={"status": item.status},
    )
    return item


@transaction.atomic
def simulate_webhook_delivery(
    *,
    company: Company,
    actor: RequestActor,
    subscription_public_id: uuid.UUID,
    event_type: str,
    payload: dict[str, Any],
) -> WebhookDelivery:
    subscription = WebhookSubscription.objects.filter(
        company=company,
        public_id=subscription_public_id,
    ).first()
    if subscription is None:
        raise ValidationError("Webhook subscription was not found")
    event_public_id = uuid.uuid4()
    item = WebhookDelivery.objects.create(
        subscription=subscription,
        event_public_id=event_public_id,
        event_type=event_type.strip(),
        payload_digest_sha256=_canonical_digest(payload),
        status=(
            WebhookDelivery.Status.DELIVERED
            if subscription.status == WebhookSubscription.Status.ACTIVE
            else WebhookDelivery.Status.FAILED
        ),
        attempt_count=1,
        response_code=204 if subscription.status == WebhookSubscription.Status.ACTIVE else None,
        response_digest_sha256=_canonical_digest({"simulated": True}),
        error_summary=(
            ""
            if subscription.status == WebhookSubscription.Status.ACTIVE
            else "Subscription is not active; no external request was executed."
        ),
        delivered_at=(
            timezone.now()
            if subscription.status == WebhookSubscription.Status.ACTIVE
            else None
        ),
    )
    if item.status == WebhookDelivery.Status.DELIVERED:
        subscription.last_delivery_at = item.delivered_at
        subscription.failure_count = 0
    else:
        subscription.failure_count += 1
    subscription.version += 1
    subscription.save(update_fields=["last_delivery_at", "failure_count", "version", "updated_at"])
    _audit(
        actor=actor,
        company=company,
        action="integration.webhook.simulated",
        entity_type="webhook_delivery",
        entity_public_id=item.public_id,
        after={"status": item.status, "event_type": item.event_type},
    )
    return item


@transaction.atomic
def create_mapping_profile(
    *,
    company: Company,
    actor: RequestActor,
    connector_public_id: uuid.UUID,
    code: str,
    name: str,
    source_schema_code: str,
    target_schema_code: str,
    mappings: list[dict[str, Any]],
    transformations: list[dict[str, Any]] | None = None,
) -> DataMappingProfile:
    connector = ConnectorProfile.objects.filter(
        company=company, public_id=connector_public_id
    ).first()
    if connector is None:
        raise ValidationError("Connector was not found")
    latest = (
        DataMappingProfile.objects.filter(
            connector=connector, code__iexact=code.strip()
        )
        .order_by("-version")
        .first()
    )
    item = DataMappingProfile(
        connector=connector,
        code=code.strip().upper(),
        version=(latest.version + 1) if latest else 1,
        name=name.strip(),
        source_schema_code=source_schema_code.strip(),
        target_schema_code=target_schema_code.strip(),
        mappings=mappings,
        transformations=transformations or [],
    )
    item.full_clean()
    item.save()
    _audit(
        actor=actor,
        company=company,
        action="integration.mapping.created",
        entity_type="data_mapping_profile",
        entity_public_id=item.public_id,
        after={"code": item.code, "version": item.version, "connector": connector.code},
    )
    return item


@transaction.atomic
def publish_mapping_profile(
    *,
    company: Company,
    actor: RequestActor,
    public_id: uuid.UUID,
) -> DataMappingProfile:
    item = DataMappingProfile.objects.select_for_update().filter(
        connector__company=company,
        public_id=public_id,
    ).first()
    if item is None:
        raise ValidationError("Mapping profile was not found")
    if item.status != DataMappingProfile.Status.DRAFT:
        raise ValidationError("Only draft mapping profiles can be published")
    item.status = DataMappingProfile.Status.PUBLISHED
    item.published_at = timezone.now()
    item.published_by_public_id = actor.user_public_id
    item.checksum_sha256 = _canonical_digest(
        {
            "source": item.source_schema_code,
            "target": item.target_schema_code,
            "mappings": item.mappings,
            "transformations": item.transformations,
        }
    )
    item.save(
        update_fields=[
            "status",
            "published_at",
            "published_by_public_id",
            "checksum_sha256",
            "updated_at",
        ]
    )
    _audit(
        actor=actor,
        company=company,
        action="integration.mapping.published",
        entity_type="data_mapping_profile",
        entity_public_id=item.public_id,
        after={"code": item.code, "version": item.version, "checksum": item.checksum_sha256},
    )
    return item


@transaction.atomic
def start_synchronization_run(
    *,
    company: Company,
    actor: RequestActor,
    connector_public_id: uuid.UUID,
    direction: str,
    idempotency_key: str,
    mapping_public_id: uuid.UUID | None = None,
) -> SynchronizationRun:
    existing = SynchronizationRun.objects.filter(
        company=company, idempotency_key=idempotency_key.strip()
    ).first()
    if existing:
        return existing
    connector = ConnectorProfile.objects.filter(
        company=company, public_id=connector_public_id
    ).first()
    if connector is None:
        raise ValidationError("Connector was not found")
    mapping = None
    if mapping_public_id:
        mapping = DataMappingProfile.objects.filter(
            connector=connector,
            public_id=mapping_public_id,
            status=DataMappingProfile.Status.PUBLISHED,
        ).first()
        if mapping is None:
            raise ValidationError("Published mapping profile was not found")
    item = SynchronizationRun(
        company=company,
        connector=connector,
        mapping_profile=mapping,
        direction=direction,
        idempotency_key=idempotency_key.strip(),
        status=SynchronizationRun.Status.RUNNING,
        started_at=timezone.now(),
        initiated_by_public_id=actor.user_public_id,
    )
    item.full_clean()
    item.save()
    _audit(
        actor=actor,
        company=company,
        action="integration.sync.started",
        entity_type="synchronization_run",
        entity_public_id=item.public_id,
        after={"connector": connector.code, "direction": item.direction},
    )
    _event(
        actor=actor,
        company=company,
        event_type="integration.sync.started",
        aggregate_type="synchronization_run",
        aggregate_public_id=item.public_id,
        aggregate_version=item.version,
        payload={"connector": connector.code, "direction": item.direction},
    )
    return item


@transaction.atomic
def complete_synchronization_run(
    *,
    company: Company,
    actor: RequestActor,
    public_id: uuid.UUID,
    expected_version: int,
    status: str,
    records_read: int,
    records_written: int,
    records_rejected: int,
    error_summary: str = "",
) -> SynchronizationRun:
    item = (
        SynchronizationRun.objects.select_for_update()
        .filter(company=company, public_id=public_id)
        .first()
    )
    if item is None:
        raise ValidationError("Synchronization run was not found")
    if item.version != expected_version:
        raise ValidationError("Synchronization run was modified by another request")
    if item.status not in {SynchronizationRun.Status.QUEUED, SynchronizationRun.Status.RUNNING}:
        raise ValidationError("Synchronization run is already terminal")
    if status not in {
        SynchronizationRun.Status.COMPLETED,
        SynchronizationRun.Status.PARTIAL,
        SynchronizationRun.Status.FAILED,
        SynchronizationRun.Status.CANCELLED,
    }:
        raise ValidationError("Invalid terminal synchronization status")
    evidence = {
        "records_read": records_read,
        "records_written": records_written,
        "records_rejected": records_rejected,
        "status": status,
        "error_summary": error_summary,
    }
    item.status = status
    item.records_read = records_read
    item.records_written = records_written
    item.records_rejected = records_rejected
    item.error_summary = error_summary.strip()
    item.evidence_checksum_sha256 = _canonical_digest(evidence)
    item.completed_at = timezone.now()
    item.version += 1
    item.save(
        update_fields=[
            "status",
            "records_read",
            "records_written",
            "records_rejected",
            "error_summary",
            "evidence_checksum_sha256",
            "completed_at",
            "version",
            "updated_at",
        ]
    )
    _audit(
        actor=actor,
        company=company,
        action="integration.sync.completed",
        entity_type="synchronization_run",
        entity_public_id=item.public_id,
        after=evidence,
    )
    _event(
        actor=actor,
        company=company,
        event_type="integration.sync.completed",
        aggregate_type="synchronization_run",
        aggregate_public_id=item.public_id,
        aggregate_version=item.version,
        payload=evidence,
    )
    return item
