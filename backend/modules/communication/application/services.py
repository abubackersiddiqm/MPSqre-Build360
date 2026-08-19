from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from string import Formatter
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from modules.communication.application.adapters import resolve_adapter
from modules.communication.models import (
    ChannelPolicy,
    CommunicationAttempt,
    CommunicationChannel,
    CommunicationRequest,
    ConsentRecord,
    MessageTemplate,
    ProviderConfiguration,
)
from modules.platform.actors import RequestActor
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.tenant.models import Company


def _audit(
    actor: RequestActor,
    company: Company,
    action: str,
    entity_type: str,
    entity_public_id: uuid.UUID,
    *,
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


def _strict_render(template: str, values: dict[str, object], allowed: set[str]) -> str:
    fields = {
        field_name
        for _, field_name, _, _ in Formatter().parse(template)
        if field_name
    }
    if not fields.issubset(allowed):
        unknown = ", ".join(sorted(fields - allowed))
        raise ValidationError(f"Template contains undeclared variables: {unknown}")
    missing = fields - values.keys()
    if missing:
        raise ValidationError(
            f"Template variables are missing: {', '.join(sorted(missing))}"
        )
    try:
        return template.format_map(values)
    except (KeyError, ValueError, AttributeError) as exc:
        raise ValidationError("Communication template could not be rendered") from exc


def _policy(company: Company, channel: str) -> ChannelPolicy:
    policy = ChannelPolicy.objects.filter(company=company, channel=channel).first()
    if policy is None:
        raise ValidationError("Communication channel policy is not configured")
    return policy


def _provider(company: Company, channel: str) -> ProviderConfiguration | None:
    return (
        ProviderConfiguration.objects.filter(
            company=company,
            channel=channel,
            is_active=True,
        )
        .order_by("priority", "id")
        .first()
    )


def _latest_consent(
    *,
    company: Company,
    subject_type: str,
    subject_public_id: uuid.UUID,
    channel: str,
    purpose_code: str,
) -> ConsentRecord | None:
    return (
        ConsentRecord.objects.filter(
            company=company,
            subject_type=subject_type,
            subject_public_id=subject_public_id,
            channel=channel,
            purpose_code=purpose_code,
            effective_at__lte=timezone.now(),
        )
        .order_by("-effective_at", "-id")
        .first()
    )


def _within_quiet_hours(policy: ChannelPolicy, now: datetime) -> bool:
    if policy.quiet_hours_start is None or policy.quiet_hours_end is None:
        return False
    current = now.timetz().replace(tzinfo=None)
    start = policy.quiet_hours_start
    end = policy.quiet_hours_end
    if start < end:
        return start <= current < end
    return current >= start or current < end


def _quiet_hours_end(policy: ChannelPolicy, now: datetime) -> datetime:
    if policy.quiet_hours_end is None:
        return now
    target = now.replace(
        hour=policy.quiet_hours_end.hour,
        minute=policy.quiet_hours_end.minute,
        second=0,
        microsecond=0,
    )
    if target <= now:
        target += timedelta(days=1)
    return target


@transaction.atomic
def update_channel_policy(
    *,
    company: Company,
    actor: RequestActor,
    channel: str,
    expected_version: int | None = None,
    **changes: Any,
) -> ChannelPolicy:
    policy = ChannelPolicy.objects.select_for_update().filter(
        company=company,
        channel=channel,
    ).first()
    if policy is None:
        policy = ChannelPolicy(company=company, channel=channel)
    elif expected_version is not None and policy.version != expected_version:
        raise ValidationError("Communication policy changed; refresh before retrying")
    before = {
        "is_enabled": policy.is_enabled,
        "consent_required": policy.consent_required,
        "version": policy.version,
    }
    for field in (
        "is_enabled",
        "consent_required",
        "quiet_hours_start",
        "quiet_hours_end",
        "timezone",
        "retry_limit",
        "max_daily_per_subject",
    ):
        if field in changes:
            setattr(policy, field, changes[field])
    if policy.pk:
        policy.version += 1
    policy.full_clean()
    policy.save()
    _audit(
        actor,
        company,
        "communication.policy.updated",
        "communication_policy",
        policy.public_id,
        before=before,
        after={
            "channel": policy.channel,
            "is_enabled": policy.is_enabled,
            "consent_required": policy.consent_required,
            "version": policy.version,
        },
    )
    return policy


@transaction.atomic
def create_provider(
    *,
    company: Company,
    actor: RequestActor,
    channel: str,
    code: str,
    display_name: str,
    adapter_code: str,
    secret_reference: str = "",
    callback_key_id: str = "",
    priority: int = 100,
    is_active: bool = False,
    supports_inbound: bool = False,
    supports_delivery_receipts: bool = False,
    configuration: dict[str, object] | None = None,
) -> ProviderConfiguration:
    provider = ProviderConfiguration(
        company=company,
        channel=channel,
        code=code.strip().upper(),
        display_name=display_name.strip(),
        adapter_code=adapter_code.strip(),
        secret_reference=secret_reference.strip(),
        callback_key_id=callback_key_id.strip(),
        priority=priority,
        is_active=is_active,
        supports_inbound=supports_inbound,
        supports_delivery_receipts=supports_delivery_receipts,
        configuration=configuration or {},
    )
    provider.full_clean()
    provider.save()
    _audit(
        actor,
        company,
        "communication.provider.created",
        "communication_provider",
        provider.public_id,
        after={
            "code": provider.code,
            "channel": provider.channel,
            "adapter_code": provider.adapter_code,
            "is_active": provider.is_active,
        },
    )
    return provider


@transaction.atomic
def create_template(
    *,
    company: Company,
    actor: RequestActor,
    code: str,
    name: str,
    channel: str,
    locale: str,
    subject_template: str,
    body_template: str,
    variable_names: list[str],
    purpose_code: str,
) -> MessageTemplate:
    normalized_variables = sorted({item.strip() for item in variable_names if item.strip()})
    latest = (
        MessageTemplate.objects.filter(
            company=company,
            code=code.strip().upper(),
            channel=channel,
            locale=locale.strip(),
        )
        .order_by("-version")
        .first()
    )
    template = MessageTemplate(
        company=company,
        code=code.strip().upper(),
        name=name.strip(),
        channel=channel,
        locale=locale.strip(),
        version=(latest.version + 1) if latest else 1,
        subject_template=subject_template,
        body_template=body_template,
        variable_names=normalized_variables,
        purpose_code=purpose_code.strip().lower(),
        created_by_public_id=actor.user_public_id,
    )
    _strict_render(subject_template, {key: "sample" for key in normalized_variables}, set(normalized_variables))
    _strict_render(body_template, {key: "sample" for key in normalized_variables}, set(normalized_variables))
    template.full_clean()
    template.save()
    _audit(
        actor,
        company,
        "communication.template.created",
        "message_template",
        template.public_id,
        after={
            "code": template.code,
            "channel": template.channel,
            "locale": template.locale,
            "version": template.version,
        },
    )
    return template


@transaction.atomic
def publish_template(
    *,
    company: Company,
    actor: RequestActor,
    template_public_id: uuid.UUID,
) -> MessageTemplate:
    template = MessageTemplate.objects.select_for_update().filter(
        company=company,
        public_id=template_public_id,
    ).first()
    if template is None:
        raise ValidationError("Communication template was not found")
    if template.status == MessageTemplate.Status.PUBLISHED:
        return template
    MessageTemplate.objects.filter(
        company=company,
        code=template.code,
        channel=template.channel,
        locale=template.locale,
        status=MessageTemplate.Status.PUBLISHED,
    ).update(status=MessageTemplate.Status.RETIRED)
    template.status = MessageTemplate.Status.PUBLISHED
    template.published_by_public_id = actor.user_public_id
    template.published_at = timezone.now()
    template.save(
        update_fields=[
            "status",
            "published_by_public_id",
            "published_at",
            "updated_at",
        ]
    )
    _audit(
        actor,
        company,
        "communication.template.published",
        "message_template",
        template.public_id,
        after={"code": template.code, "version": template.version},
    )
    _event(
        actor,
        company,
        "communication.template.published",
        "message_template",
        template.public_id,
        template.version,
        {"code": template.code, "channel": template.channel},
    )
    return template


@transaction.atomic
def record_consent(
    *,
    company: Company,
    actor: RequestActor,
    subject_type: str,
    subject_public_id: uuid.UUID,
    channel: str,
    purpose_code: str,
    status: str,
    source_code: str,
    proof_reference: str = "",
    reason: str = "",
) -> ConsentRecord:
    record = ConsentRecord(
        company=company,
        subject_type=subject_type.strip().lower(),
        subject_public_id=subject_public_id,
        channel=channel,
        purpose_code=purpose_code.strip().lower(),
        status=status,
        source_code=source_code.strip().lower(),
        proof_reference=proof_reference.strip(),
        effective_at=timezone.now(),
        recorded_by_public_id=actor.user_public_id,
        reason=reason.strip(),
    )
    record.full_clean()
    record.save()
    _audit(
        actor,
        company,
        "communication.consent.recorded",
        "communication_consent",
        record.public_id,
        after={
            "subject_type": record.subject_type,
            "subject_public_id": str(record.subject_public_id),
            "channel": record.channel,
            "purpose_code": record.purpose_code,
            "status": record.status,
        },
        reason_code=reason.strip(),
    )
    _event(
        actor,
        company,
        "communication.consent.changed",
        "communication_consent",
        record.public_id,
        1,
        {
            "subject_type": record.subject_type,
            "subject_public_id": str(record.subject_public_id),
            "channel": record.channel,
            "purpose_code": record.purpose_code,
            "status": record.status,
        },
    )
    return record


@transaction.atomic
def create_request(
    *,
    company: Company,
    actor: RequestActor,
    template_public_id: uuid.UUID,
    subject_type: str,
    subject_public_id: uuid.UUID,
    recipient_reference_type: str,
    recipient_reference_public_id: uuid.UUID,
    template_variables: dict[str, object],
    idempotency_key: str,
    scheduled_for: datetime | None = None,
) -> CommunicationRequest:
    existing = CommunicationRequest.objects.filter(
        company=company,
        idempotency_key=idempotency_key.strip(),
    ).first()
    if existing is not None:
        return existing
    template = MessageTemplate.objects.filter(
        company=company,
        public_id=template_public_id,
        status=MessageTemplate.Status.PUBLISHED,
    ).first()
    if template is None:
        raise ValidationError("A published communication template is required")
    policy = _policy(company, template.channel)
    provider = _provider(company, template.channel)
    allowed = set(template.variable_names)
    rendered_subject = _strict_render(template.subject_template, template_variables, allowed)
    rendered_body = _strict_render(template.body_template, template_variables, allowed)
    status = CommunicationRequest.Status.QUEUED
    suppression_reason = ""
    effective_schedule = scheduled_for
    if not policy.is_enabled:
        status = CommunicationRequest.Status.SUPPRESSED
        suppression_reason = "channel_disabled"
    elif policy.consent_required and template.channel != CommunicationChannel.IN_APP:
        consent = _latest_consent(
            company=company,
            subject_type=subject_type,
            subject_public_id=subject_public_id,
            channel=template.channel,
            purpose_code=template.purpose_code,
        )
        if consent is None or consent.status != ConsentRecord.Status.GRANTED:
            status = CommunicationRequest.Status.SUPPRESSED
            suppression_reason = "consent_not_granted"
    if status != CommunicationRequest.Status.SUPPRESSED:
        try:
            local_now = timezone.now().astimezone(ZoneInfo(policy.timezone))
        except ZoneInfoNotFoundError as exc:
            raise ValidationError("Communication policy timezone is invalid") from exc
        if _within_quiet_hours(policy, local_now):
            effective_schedule = _quiet_hours_end(policy, local_now).astimezone(
                timezone.get_current_timezone()
            )
            status = CommunicationRequest.Status.SCHEDULED
        elif effective_schedule and effective_schedule > timezone.now():
            status = CommunicationRequest.Status.SCHEDULED
        recent_count = CommunicationRequest.objects.filter(
            company=company,
            subject_type=subject_type,
            subject_public_id=subject_public_id,
            channel=template.channel,
            created_at__gte=timezone.now() - timedelta(days=1),
        ).exclude(status=CommunicationRequest.Status.CANCELLED).count()
        if recent_count >= policy.max_daily_per_subject:
            status = CommunicationRequest.Status.SUPPRESSED
            suppression_reason = "daily_subject_limit"
    request = CommunicationRequest(
        company=company,
        channel=template.channel,
        template=template,
        provider=provider,
        subject_type=subject_type.strip().lower(),
        subject_public_id=subject_public_id,
        recipient_reference_type=recipient_reference_type.strip().lower(),
        recipient_reference_public_id=recipient_reference_public_id,
        purpose_code=template.purpose_code,
        locale=template.locale,
        status=status,
        rendered_subject=rendered_subject,
        rendered_body=rendered_body,
        template_variables=template_variables,
        idempotency_key=idempotency_key.strip(),
        requested_by_public_id=actor.user_public_id,
        scheduled_for=effective_schedule,
        suppression_reason=suppression_reason,
    )
    request.full_clean()
    try:
        request.save()
    except IntegrityError:
        return CommunicationRequest.objects.get(
            company=company,
            idempotency_key=idempotency_key.strip(),
        )
    _audit(
        actor,
        company,
        "communication.request.created",
        "communication_request",
        request.public_id,
        after={
            "channel": request.channel,
            "status": request.status,
            "template_code": template.code,
            "subject_type": request.subject_type,
            "subject_public_id": str(request.subject_public_id),
        },
    )
    _event(
        actor,
        company,
        "communication.request.created",
        "communication_request",
        request.public_id,
        request.version,
        {
            "channel": request.channel,
            "status": request.status,
            "template_code": template.code,
        },
    )
    return request


@transaction.atomic
def dispatch_request(
    *,
    company: Company,
    actor: RequestActor,
    request_public_id: uuid.UUID,
) -> CommunicationRequest:
    request = (
        CommunicationRequest.objects.select_for_update(of=("self",))
        .select_related("provider", "template")
        .filter(company=company, public_id=request_public_id)
        .first()
    )
    if request is None:
        raise ValidationError("Communication request was not found")
    if request.status in {
        CommunicationRequest.Status.SENT,
        CommunicationRequest.Status.DELIVERED,
        CommunicationRequest.Status.SUPPRESSED,
        CommunicationRequest.Status.CANCELLED,
    }:
        return request
    if request.scheduled_for and request.scheduled_for > timezone.now():
        request.status = CommunicationRequest.Status.SCHEDULED
        request.save(update_fields=["status", "updated_at"])
        return request
    provider = request.provider or _provider(company, request.channel)
    if provider is None:
        request.status = CommunicationRequest.Status.FAILED
        request.failed_at = timezone.now()
        request.suppression_reason = "provider_not_configured"
        request.version += 1
        request.save()
        return request
    policy = _policy(company, request.channel)
    attempt_number = request.attempts.count() + 1
    if attempt_number > policy.retry_limit:
        raise ValidationError("Communication retry limit has been reached")
    attempt = CommunicationAttempt(
        company=company,
        request=request,
        provider=provider,
        attempt_number=attempt_number,
        status=CommunicationAttempt.Status.STARTED,
        started_at=timezone.now(),
    )
    attempt.full_clean()
    attempt.save()
    request.provider = provider
    request.status = CommunicationRequest.Status.PROCESSING
    request.version += 1
    request.save(update_fields=["provider", "status", "version", "updated_at"])
    adapter = resolve_adapter(provider.adapter_code)
    try:
        result = adapter.send(request=request, provider=provider)
    except ValidationError as exc:
        attempt.status = CommunicationAttempt.Status.FAILED
        attempt.error_code = "adapter_rejected"
        attempt.error_message = str(exc)[:500]
        attempt.finished_at = timezone.now()
        attempt.save()
        request.status = CommunicationRequest.Status.FAILED
        request.failed_at = timezone.now()
        request.version += 1
        request.save()
        _audit(
            actor,
            company,
            "communication.request.failed",
            "communication_request",
            request.public_id,
            after={"status": request.status, "error_code": attempt.error_code},
        )
        return request
    attempt.provider_message_id = result.provider_message_id
    attempt.response_metadata = result.metadata
    attempt.finished_at = timezone.now()
    request.provider_message_id = result.provider_message_id
    request.sent_at = timezone.now()
    if result.status == "delivered":
        attempt.status = CommunicationAttempt.Status.DELIVERED
        request.status = CommunicationRequest.Status.DELIVERED
        request.delivered_at = timezone.now()
    elif result.status == "accepted":
        attempt.status = CommunicationAttempt.Status.ACCEPTED
        request.status = CommunicationRequest.Status.SENT
    else:
        attempt.status = CommunicationAttempt.Status.FAILED
        attempt.error_code = result.error_code[:100]
        attempt.error_message = result.error_message[:500]
        request.status = CommunicationRequest.Status.FAILED
        request.failed_at = timezone.now()
    attempt.save()
    request.version += 1
    request.save()
    _audit(
        actor,
        company,
        "communication.request.dispatched",
        "communication_request",
        request.public_id,
        after={
            "status": request.status,
            "provider_code": provider.code,
            "attempt_number": attempt_number,
        },
    )
    _event(
        actor,
        company,
        "communication.request.status_changed",
        "communication_request",
        request.public_id,
        request.version,
        {"status": request.status, "channel": request.channel},
    )
    return request


@transaction.atomic
def cancel_request(
    *,
    company: Company,
    actor: RequestActor,
    request_public_id: uuid.UUID,
    expected_version: int,
    reason: str,
) -> CommunicationRequest:
    request = CommunicationRequest.objects.select_for_update().filter(
        company=company,
        public_id=request_public_id,
    ).first()
    if request is None:
        raise ValidationError("Communication request was not found")
    if request.version != expected_version:
        raise ValidationError("Communication request changed; refresh before retrying")
    if request.status not in {
        CommunicationRequest.Status.QUEUED,
        CommunicationRequest.Status.SCHEDULED,
        CommunicationRequest.Status.FAILED,
    }:
        raise ValidationError("This communication request cannot be cancelled")
    before = request.status
    request.status = CommunicationRequest.Status.CANCELLED
    request.suppression_reason = reason.strip()
    request.version += 1
    request.save()
    _audit(
        actor,
        company,
        "communication.request.cancelled",
        "communication_request",
        request.public_id,
        before={"status": before},
        after={"status": request.status, "version": request.version},
        reason_code=reason.strip(),
    )
    return request
