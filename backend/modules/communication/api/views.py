from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from modules.communication.api.serializers import (
    ChannelPolicySerializer,
    CommunicationCancelSerializer,
    CommunicationRequestCreateSerializer,
    ConsentCreateSerializer,
    ProviderCreateSerializer,
    TemplateCreateSerializer,
)
from modules.communication.application.callbacks import process_callback
from modules.communication.application.services import (
    cancel_request,
    create_provider,
    create_request,
    create_template,
    dispatch_request,
    publish_template,
    record_consent,
    update_channel_policy,
)
from modules.communication.models import (
    CallbackReceipt,
    ChannelPolicy,
    CommunicationRequest,
    ConsentRecord,
    InboundCommunication,
    MessageTemplate,
    ProviderConfiguration,
)
from modules.platform.actors import request_actor
from modules.tenant.api.base import TenantScopedAPIView


def _validation(exc: DjangoValidationError) -> ValidationError:
    return ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)


def _policy(item: ChannelPolicy) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "channel": item.channel,
        "is_enabled": item.is_enabled,
        "consent_required": item.consent_required,
        "quiet_hours_start": item.quiet_hours_start,
        "quiet_hours_end": item.quiet_hours_end,
        "timezone": item.timezone,
        "retry_limit": item.retry_limit,
        "max_daily_per_subject": item.max_daily_per_subject,
        "version": item.version,
    }


def _provider(item: ProviderConfiguration) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "channel": item.channel,
        "code": item.code,
        "display_name": item.display_name,
        "adapter_code": item.adapter_code,
        "secret_reference": item.secret_reference,
        "callback_key_id": item.callback_key_id,
        "priority": item.priority,
        "is_active": item.is_active,
        "supports_inbound": item.supports_inbound,
        "supports_delivery_receipts": item.supports_delivery_receipts,
        "configuration": item.configuration,
        "version": item.version,
    }


def _template(item: MessageTemplate) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "code": item.code,
        "name": item.name,
        "channel": item.channel,
        "locale": item.locale,
        "version": item.version,
        "status": item.status,
        "subject_template": item.subject_template,
        "body_template": item.body_template,
        "variable_names": item.variable_names,
        "purpose_code": item.purpose_code,
        "published_at": item.published_at,
    }


def _consent(item: ConsentRecord) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "subject_type": item.subject_type,
        "subject_public_id": str(item.subject_public_id),
        "channel": item.channel,
        "purpose_code": item.purpose_code,
        "status": item.status,
        "source_code": item.source_code,
        "proof_reference": item.proof_reference,
        "effective_at": item.effective_at,
        "reason": item.reason,
    }


def _request(item: CommunicationRequest) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "channel": item.channel,
        "template": {
            "public_id": str(item.template.public_id),
            "code": item.template.code,
            "name": item.template.name,
            "version": item.template.version,
        },
        "provider": (
            {
                "public_id": str(item.provider.public_id),
                "code": item.provider.code,
                "display_name": item.provider.display_name,
            }
            if item.provider
            else None
        ),
        "subject_type": item.subject_type,
        "subject_public_id": str(item.subject_public_id),
        "recipient_reference_type": item.recipient_reference_type,
        "recipient_reference_public_id": str(item.recipient_reference_public_id),
        "purpose_code": item.purpose_code,
        "status": item.status,
        "rendered_subject": item.rendered_subject,
        "rendered_body": item.rendered_body,
        "scheduled_for": item.scheduled_for,
        "sent_at": item.sent_at,
        "delivered_at": item.delivered_at,
        "suppression_reason": item.suppression_reason,
        "provider_message_id": item.provider_message_id,
        "attempt_count": item.attempts.count(),
        "version": item.version,
        "created_at": item.created_at,
    }


class CommunicationSummaryView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("communication.dashboard.read")
        company = self.tenant_context.company
        statuses = {
            row["status"]: row["count"]
            for row in CommunicationRequest.objects.filter(company=company)
            .values("status")
            .annotate(count=Count("id"))
        }
        return Response(
            {
                "policies": ChannelPolicy.objects.filter(company=company).count(),
                "enabled_channels": ChannelPolicy.objects.filter(
                    company=company,
                    is_enabled=True,
                ).count(),
                "active_providers": ProviderConfiguration.objects.filter(
                    company=company,
                    is_active=True,
                ).count(),
                "published_templates": MessageTemplate.objects.filter(
                    company=company,
                    status=MessageTemplate.Status.PUBLISHED,
                ).count(),
                "queued": statuses.get(CommunicationRequest.Status.QUEUED, 0)
                + statuses.get(CommunicationRequest.Status.SCHEDULED, 0),
                "sent": statuses.get(CommunicationRequest.Status.SENT, 0),
                "delivered": statuses.get(CommunicationRequest.Status.DELIVERED, 0),
                "failed": statuses.get(CommunicationRequest.Status.FAILED, 0),
                "suppressed": statuses.get(CommunicationRequest.Status.SUPPRESSED, 0),
                "inbound_review": InboundCommunication.objects.filter(
                    company=company,
                    status=InboundCommunication.Status.REVIEW_REQUIRED,
                ).count(),
            }
        )


class ChannelPolicyListUpdateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("communication.policy.read")
        items = ChannelPolicy.objects.filter(company=self.tenant_context.company)
        return Response({"items": [_policy(item) for item in items]})

    def patch(self, request: Request) -> Response:
        self.tenant_context.require("communication.policy.manage")
        serializer = ChannelPolicySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        channel = values.pop("channel")
        expected_version = values.pop("expected_version", None)
        try:
            item = update_channel_policy(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                channel=channel,
                expected_version=expected_version,
                **values,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_policy(item))


class ProviderListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("communication.provider.read")
        items = ProviderConfiguration.objects.filter(company=self.tenant_context.company)
        return Response({"items": [_provider(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("communication.provider.manage")
        serializer = ProviderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_provider(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_provider(item), status=201)


class TemplateListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("communication.template.read")
        items = MessageTemplate.objects.filter(company=self.tenant_context.company)[:300]
        return Response({"items": [_template(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("communication.template.manage")
        serializer = TemplateCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_template(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_template(item), status=201)


class TemplatePublishView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("communication.template.publish")
        try:
            item = publish_template(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                template_public_id=public_id,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_template(item))


class ConsentListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("communication.consent.read")
        items = ConsentRecord.objects.filter(company=self.tenant_context.company)[:300]
        return Response({"items": [_consent(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("communication.consent.manage")
        serializer = ConsentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = record_consent(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_consent(item), status=201)


class CommunicationRequestListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("communication.request.read")
        items = (
            CommunicationRequest.objects.select_related("template", "provider")
            .filter(company=self.tenant_context.company)
            .order_by("-created_at")[:300]
        )
        return Response({"items": [_request(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("communication.request.create")
        serializer = CommunicationRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        current_user_public_id = self.tenant_context.principal.user.public_id
        values.setdefault("subject_public_id", current_user_public_id)
        values.setdefault("recipient_reference_public_id", current_user_public_id)
        try:
            item = create_request(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **values,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_request(item), status=201)


class CommunicationDispatchView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("communication.request.dispatch")
        try:
            item = dispatch_request(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                request_public_id=public_id,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_request(item))


class CommunicationCancelView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("communication.request.cancel")
        serializer = CommunicationCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = cancel_request(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                request_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_request(item))


class CallbackReceiptListView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("communication.callback.read")
        items = CallbackReceipt.objects.select_related("provider", "request").filter(
            company=self.tenant_context.company
        )[:300]
        return Response(
            {
                "items": [
                    {
                        "public_id": str(item.public_id),
                        "provider_code": item.provider.code,
                        "provider_event_id": item.provider_event_id,
                        "event_type": item.event_type,
                        "provider_message_id": item.provider_message_id,
                        "signature_valid": item.signature_valid,
                        "received_at": item.received_at,
                        "processed_at": item.processed_at,
                        "rejection_reason": item.rejection_reason,
                    }
                    for item in items
                ]
            }
        )


class InboundCommunicationListView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("communication.inbound.read")
        items = InboundCommunication.objects.select_related("provider").filter(
            company=self.tenant_context.company
        )[:300]
        return Response(
            {
                "items": [
                    {
                        "public_id": str(item.public_id),
                        "provider_code": item.provider.code,
                        "channel": item.channel,
                        "provider_message_id": item.provider_message_id,
                        "subject_reference_type": item.subject_reference_type,
                        "subject_reference_public_id": (
                            str(item.subject_reference_public_id)
                            if item.subject_reference_public_id
                            else None
                        ),
                        "summary": item.summary,
                        "status": item.status,
                        "received_at": item.received_at,
                    }
                    for item in items
                ]
            }
        )


class ProviderCallbackView(APIView):
    authentication_classes: list[type] = []
    permission_classes = [AllowAny]

    def post(self, request: Request, provider_public_id: uuid.UUID) -> Response:
        signature = request.headers.get("X-Build360-Signature", "")
        try:
            receipt = process_callback(
                provider_public_id=provider_public_id,
                raw_body=request.body,
                signature=signature,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        if not receipt.signature_valid:
            return Response(
                {
                    "code": "COMMUNICATION-CALLBACK-SIGNATURE-INVALID",
                    "message": "Callback signature validation failed.",
                },
                status=401,
            )
        return Response(
            {
                "public_id": str(receipt.public_id),
                "event_type": receipt.event_type,
                "processed_at": receipt.processed_at,
            },
            status=202,
        )
