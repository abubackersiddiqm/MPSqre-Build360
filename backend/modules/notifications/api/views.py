from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.notifications.api.serializers import (
    NotificationCreateSerializer,
    PreferenceSerializer,
    RuleSerializer,
)
from modules.notifications.application.services import (
    create_notification,
    create_rule,
    mark_all_read,
    mark_read,
    upsert_preference,
)
from modules.notifications.models import (
    Notification,
    NotificationDelivery,
    NotificationPreference,
    NotificationRule,
)
from modules.platform.actors import request_actor
from modules.tenant.api.base import TenantScopedAPIView


def _validation(exc: DjangoValidationError) -> ValidationError:
    return ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)


def _notification(item: Notification) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "event_code": item.event_code,
        "title": item.title,
        "body": item.body,
        "severity": item.severity,
        "action_path": item.action_path,
        "source_type": item.source_type,
        "source_public_id": str(item.source_public_id) if item.source_public_id else None,
        "read_at": item.read_at,
        "created_at": item.created_at,
        "deliveries": [
            {
                "channel": delivery.channel,
                "status": delivery.status,
                "failure_code": delivery.failure_code,
                "delivered_at": delivery.delivered_at,
            }
            for delivery in item.deliveries.all()
        ],
    }


def _preference(item: NotificationPreference) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "event_code": item.event_code,
        "channel": item.channel,
        "enabled": item.enabled,
        "digest_mode": item.digest_mode,
        "quiet_hours_start": item.quiet_hours_start,
        "quiet_hours_end": item.quiet_hours_end,
        "version": item.version,
    }


def _rule(item: NotificationRule) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "event_code": item.event_code,
        "name": item.name,
        "default_title_template": item.default_title_template,
        "default_body_template": item.default_body_template,
        "severity": item.severity,
        "channels": item.channels,
        "is_active": item.is_active,
        "version": item.version,
    }


class NotificationSummaryView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("notification.dashboard.read")
        company = self.tenant_context.company
        user_public_id = self.tenant_context.principal.user.public_id
        inbox = Notification.objects.filter(
            company=company,
            user_public_id=user_public_id,
            archived_at__isnull=True,
        )
        delivery_statuses = {
            row["status"]: row["count"]
            for row in NotificationDelivery.objects.filter(company=company)
            .values("status")
            .annotate(count=Count("id"))
        }
        return Response(
            {
                "total": inbox.count(),
                "unread": inbox.filter(read_at__isnull=True).count(),
                "critical_unread": inbox.filter(
                    read_at__isnull=True,
                    severity=Notification.Severity.CRITICAL,
                ).count(),
                "preferences": NotificationPreference.objects.filter(
                    company=company,
                    user_public_id=user_public_id,
                ).count(),
                "active_rules": NotificationRule.objects.filter(
                    company=company,
                    is_active=True,
                ).count(),
                "delivery_failures": delivery_statuses.get(
                    NotificationDelivery.Status.FAILED,
                    0,
                ),
                "delivery_suppressed": delivery_statuses.get(
                    NotificationDelivery.Status.SUPPRESSED,
                    0,
                ),
            }
        )


class NotificationListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("notification.read")
        items = (
            Notification.objects.prefetch_related("deliveries")
            .filter(
                company=self.tenant_context.company,
                user_public_id=self.tenant_context.principal.user.public_id,
                archived_at__isnull=True,
            )
            .order_by("-created_at")[:300]
        )
        return Response({"items": [_notification(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("notification.create")
        serializer = NotificationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        user_public_id = values.pop(
            "user_public_id",
            self.tenant_context.principal.user.public_id,
        )
        try:
            item = create_notification(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                user_public_id=user_public_id,
                **values,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        item = Notification.objects.prefetch_related("deliveries").get(pk=item.pk)
        return Response(_notification(item), status=201)


class NotificationReadView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("notification.mark_read")
        try:
            item = mark_read(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                notification_public_id=public_id,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        item = Notification.objects.prefetch_related("deliveries").get(pk=item.pk)
        return Response(_notification(item))


class NotificationReadAllView(TenantScopedAPIView):
    def post(self, request: Request) -> Response:
        self.tenant_context.require("notification.mark_read")
        count = mark_all_read(
            company=self.tenant_context.company,
            actor=request_actor(request, self.tenant_context),
        )
        return Response({"updated": count})


class PreferenceListUpdateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("notification.preference.read")
        items = NotificationPreference.objects.filter(
            company=self.tenant_context.company,
            user_public_id=self.tenant_context.principal.user.public_id,
        )
        return Response({"items": [_preference(item) for item in items]})

    def patch(self, request: Request) -> Response:
        self.tenant_context.require("notification.preference.manage")
        serializer = PreferenceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = upsert_preference(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_preference(item))


class RuleListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("notification.rule.read")
        items = NotificationRule.objects.filter(company=self.tenant_context.company)
        return Response({"items": [_rule(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("notification.rule.manage")
        serializer = RuleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_rule(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_rule(item), status=201)
