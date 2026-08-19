from __future__ import annotations

import uuid
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from modules.communication.application.services import create_request, dispatch_request
from modules.communication.models import CommunicationChannel, MessageTemplate
from modules.notifications.models import (
    Notification,
    NotificationDelivery,
    NotificationPreference,
    NotificationRule,
)
from modules.platform.actors import RequestActor
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.tenant.models import Company


def _audit(
    actor: RequestActor,
    company: Company,
    action: str,
    notification: Notification,
    *,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    append_audit(
        AuditRecord(
            action=action,
            entity_type="notification",
            entity_public_id=notification.public_id,
            actor_public_id=actor.user_public_id,
            company_public_id=company.public_id,
            request_id=actor.request_id,
            correlation_id=actor.request_id,
            ip_address=actor.ip_address,
            user_agent=actor.user_agent,
            before=before or {},
            after=after or {},
        )
    )


def _preference(
    *,
    company: Company,
    user_public_id: uuid.UUID,
    event_code: str,
    channel: str,
) -> NotificationPreference | None:
    return NotificationPreference.objects.filter(
        company=company,
        user_public_id=user_public_id,
        event_code=event_code,
        channel=channel,
    ).first()


def _is_channel_enabled(
    *,
    company: Company,
    user_public_id: uuid.UUID,
    event_code: str,
    channel: str,
) -> bool:
    preference = _preference(
        company=company,
        user_public_id=user_public_id,
        event_code=event_code,
        channel=channel,
    )
    if preference is None:
        return True
    return preference.enabled and preference.digest_mode != NotificationPreference.DigestMode.MUTED


@transaction.atomic
def upsert_preference(
    *,
    company: Company,
    actor: RequestActor,
    event_code: str,
    channel: str,
    enabled: bool,
    digest_mode: str,
    quiet_hours_start=None,
    quiet_hours_end=None,
    expected_version: int | None = None,
) -> NotificationPreference:
    preference = NotificationPreference.objects.select_for_update().filter(
        company=company,
        user_public_id=actor.user_public_id,
        event_code=event_code.strip().lower(),
        channel=channel,
    ).first()
    if preference is None:
        preference = NotificationPreference(
            company=company,
            user_public_id=actor.user_public_id,
            event_code=event_code.strip().lower(),
            channel=channel,
        )
    elif expected_version is not None and preference.version != expected_version:
        raise ValidationError("Notification preference changed; refresh before retrying")
    preference.enabled = enabled
    preference.digest_mode = digest_mode
    preference.quiet_hours_start = quiet_hours_start
    preference.quiet_hours_end = quiet_hours_end
    if preference.pk:
        preference.version += 1
    preference.full_clean()
    preference.save()
    append_audit(
        AuditRecord(
            action="notification.preference.updated",
            entity_type="notification_preference",
            entity_public_id=preference.public_id,
            actor_public_id=actor.user_public_id,
            company_public_id=company.public_id,
            request_id=actor.request_id,
            correlation_id=actor.request_id,
            ip_address=actor.ip_address,
            user_agent=actor.user_agent,
            after={
                "event_code": preference.event_code,
                "channel": preference.channel,
                "enabled": preference.enabled,
                "digest_mode": preference.digest_mode,
                "version": preference.version,
            },
        )
    )
    return preference


@transaction.atomic
def create_rule(
    *,
    company: Company,
    actor: RequestActor,
    event_code: str,
    name: str,
    default_title_template: str,
    default_body_template: str,
    severity: str,
    channels: list[str],
) -> NotificationRule:
    normalized_channels = list(dict.fromkeys(channels))
    for channel in normalized_channels:
        if channel not in CommunicationChannel.values:
            raise ValidationError("Notification rule contains an unsupported channel")
    rule, created = NotificationRule.objects.select_for_update().get_or_create(
        company=company,
        event_code=event_code.strip().lower(),
        defaults={
            "name": name.strip(),
            "default_title_template": default_title_template,
            "default_body_template": default_body_template,
            "severity": severity,
            "channels": normalized_channels,
        },
    )
    if not created:
        rule.name = name.strip()
        rule.default_title_template = default_title_template
        rule.default_body_template = default_body_template
        rule.severity = severity
        rule.channels = normalized_channels
        rule.version += 1
        rule.full_clean()
        rule.save()
    append_audit(
        AuditRecord(
            action="notification.rule.upserted",
            entity_type="notification_rule",
            entity_public_id=rule.public_id,
            actor_public_id=actor.user_public_id,
            company_public_id=company.public_id,
            request_id=actor.request_id,
            correlation_id=actor.request_id,
            ip_address=actor.ip_address,
            user_agent=actor.user_agent,
            after={
                "event_code": rule.event_code,
                "channels": rule.channels,
                "version": rule.version,
            },
        )
    )
    return rule


@transaction.atomic
def create_notification(
    *,
    company: Company,
    actor: RequestActor,
    user_public_id: uuid.UUID,
    event_code: str,
    title: str,
    body: str,
    severity: str = Notification.Severity.INFO,
    action_path: str = "",
    source_type: str = "",
    source_public_id: uuid.UUID | None = None,
    route_external: bool = False,
) -> Notification:
    normalized_event = event_code.strip().lower()
    rule = NotificationRule.objects.filter(
        company=company,
        event_code=normalized_event,
        is_active=True,
    ).first()
    notification = Notification(
        company=company,
        user_public_id=user_public_id,
        event_code=normalized_event,
        title=title.strip()[:250],
        body=body.strip(),
        severity=severity,
        action_path=action_path.strip(),
        source_type=source_type.strip().lower(),
        source_public_id=source_public_id,
    )
    notification.full_clean()
    notification.save()
    in_app_enabled = _is_channel_enabled(
        company=company,
        user_public_id=user_public_id,
        event_code=normalized_event,
        channel=CommunicationChannel.IN_APP,
    )
    NotificationDelivery.objects.create(
        company=company,
        notification=notification,
        channel=CommunicationChannel.IN_APP,
        status=(
            NotificationDelivery.Status.DELIVERED
            if in_app_enabled
            else NotificationDelivery.Status.SUPPRESSED
        ),
        attempted_at=timezone.now(),
        delivered_at=timezone.now() if in_app_enabled else None,
        failure_code="" if in_app_enabled else "user_preference",
    )
    if route_external and rule is not None:
        for channel in rule.channels:
            if channel == CommunicationChannel.IN_APP:
                continue
            if not _is_channel_enabled(
                company=company,
                user_public_id=user_public_id,
                event_code=normalized_event,
                channel=channel,
            ):
                NotificationDelivery.objects.create(
                    company=company,
                    notification=notification,
                    channel=channel,
                    status=NotificationDelivery.Status.SUPPRESSED,
                    attempted_at=timezone.now(),
                    failure_code="user_preference",
                )
                continue
            template = MessageTemplate.objects.filter(
                company=company,
                code=normalized_event.upper(),
                channel=channel,
                status=MessageTemplate.Status.PUBLISHED,
            ).order_by("-version").first()
            if template is None:
                NotificationDelivery.objects.create(
                    company=company,
                    notification=notification,
                    channel=channel,
                    status=NotificationDelivery.Status.SUPPRESSED,
                    attempted_at=timezone.now(),
                    failure_code="template_not_configured",
                )
                continue
            request = create_request(
                company=company,
                actor=actor,
                template_public_id=template.public_id,
                subject_type="user",
                subject_public_id=user_public_id,
                recipient_reference_type="user",
                recipient_reference_public_id=user_public_id,
                template_variables={
                    "title": notification.title,
                    "body": notification.body,
                    "company_name": company.display_name,
                },
                idempotency_key=f"notification:{notification.public_id}:{channel}",
            )
            if request.status in {
                request.Status.QUEUED,
                request.Status.PROCESSING,
            }:
                request = dispatch_request(
                    company=company,
                    actor=actor,
                    request_public_id=request.public_id,
                )
            mapped_status = {
                request.Status.SENT: NotificationDelivery.Status.SENT,
                request.Status.DELIVERED: NotificationDelivery.Status.DELIVERED,
                request.Status.FAILED: NotificationDelivery.Status.FAILED,
                request.Status.SUPPRESSED: NotificationDelivery.Status.SUPPRESSED,
            }.get(request.status, NotificationDelivery.Status.QUEUED)
            NotificationDelivery.objects.create(
                company=company,
                notification=notification,
                channel=channel,
                communication_request=request,
                status=mapped_status,
                attempted_at=timezone.now(),
                delivered_at=request.delivered_at,
                failure_code=request.suppression_reason,
            )
    _audit(
        actor,
        company,
        "notification.created",
        notification,
        after={
            "event_code": notification.event_code,
            "user_public_id": str(notification.user_public_id),
            "severity": notification.severity,
        },
    )
    append_event(
        EventRecord(
            event_type="notification.created",
            aggregate_type="notification",
            aggregate_public_id=notification.public_id,
            aggregate_version=1,
            company_public_id=company.public_id,
            correlation_id=actor.request_id,
            payload={
                "event_code": notification.event_code,
                "user_public_id": str(notification.user_public_id),
                "severity": notification.severity,
            },
        )
    )
    return notification


@transaction.atomic
def mark_read(
    *,
    company: Company,
    actor: RequestActor,
    notification_public_id: uuid.UUID,
) -> Notification:
    notification = Notification.objects.select_for_update().filter(
        company=company,
        public_id=notification_public_id,
        user_public_id=actor.user_public_id,
        archived_at__isnull=True,
    ).first()
    if notification is None:
        raise ValidationError("Notification was not found")
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at", "updated_at"])
        _audit(
            actor,
            company,
            "notification.read",
            notification,
            after={"read_at": notification.read_at.isoformat()},
        )
    return notification


@transaction.atomic
def mark_all_read(*, company: Company, actor: RequestActor) -> int:
    now = timezone.now()
    count = Notification.objects.filter(
        company=company,
        user_public_id=actor.user_public_id,
        read_at__isnull=True,
        archived_at__isnull=True,
    ).update(read_at=now, updated_at=now)
    append_audit(
        AuditRecord(
            action="notification.all_read",
            entity_type="notification_inbox",
            actor_public_id=actor.user_public_id,
            company_public_id=company.public_id,
            request_id=actor.request_id,
            correlation_id=actor.request_id,
            ip_address=actor.ip_address,
            user_agent=actor.user_agent,
            after={"count": count},
        )
    )
    return count
