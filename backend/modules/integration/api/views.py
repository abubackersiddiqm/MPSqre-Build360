from __future__ import annotations

import json
import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from modules.integration.api.serializers import (
    ApiClientActionSerializer,
    ApiClientCreateSerializer,
    ConnectorCreateSerializer,
    ExchangeRateCreateSerializer,
    LocalizationPackCreateSerializer,
    MappingCreateSerializer,
    MetaLeadConnectorCreateSerializer,
    MetaLeadRotateVerifyTokenSerializer,
    MetaLeadStatusSerializer,
    MetaLeadTestSerializer,
    PublishSerializer,
    StatusActionSerializer,
    SyncCompleteSerializer,
    SyncStartSerializer,
    WebhookCreateSerializer,
    WebhookSimulationSerializer,
)
from modules.integration.application.meta_leads import (
    META_PROVIDER_CODE,
    activate_meta_connector,
    create_meta_connector,
    meta_receipt_payload,
    process_meta_lead_receipt,
    record_webhook_payload,
    require_meta_ads_entitlement,
    rotate_verify_token,
    test_meta_connection,
    verify_webhook_challenge,
    verify_webhook_signature,
)
from modules.integration.application.meta_leads import (
    connector_payload as meta_connector_payload,
)
from modules.integration.application.services import (
    complete_synchronization_run,
    create_connector,
    create_localization_pack,
    create_mapping_profile,
    create_webhook_subscription,
    evaluate_connector_health,
    integration_summary,
    issue_api_client,
    publish_localization_pack,
    publish_mapping_profile,
    record_exchange_rate,
    revoke_api_client,
    rotate_api_client,
    simulate_webhook_delivery,
    start_synchronization_run,
    transition_connector_status,
    transition_webhook_status,
)
from modules.integration.models import (
    ApiClientCredential,
    ConnectorProfile,
    DataMappingProfile,
    ExchangeRateSnapshot,
    IntegrationProviderCatalog,
    LocalizationPack,
    MetaLeadReceipt,
    SynchronizationRun,
    WebhookDelivery,
    WebhookSubscription,
)
from modules.integration.tasks import process_meta_lead_receipt_task
from modules.platform.actors import request_actor
from modules.subscription.application.feature_control import feature_enabled
from modules.tenant.api.base import TenantScopedAPIView
from modules.tenant.models import Membership


def _validation(exc: DjangoValidationError) -> ValidationError:
    return ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)


def _require_api_access(company) -> None:
    if not feature_enabled(company=company, code="platform.api_access"):
        raise PermissionDenied("API Access is disabled for this company subscription")


def _localization(item: LocalizationPack) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "code": item.code,
        "version": item.version,
        "name": item.name,
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
        "status": item.status,
        "is_default": item.is_default,
        "effective_from": item.effective_from,
        "effective_to": item.effective_to,
        "published_at": item.published_at,
        "checksum_sha256": item.checksum_sha256,
    }


def _rate(item: ExchangeRateSnapshot) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "base_currency": item.base_currency,
        "quote_currency": item.quote_currency,
        "rate": str(item.rate),
        "effective_at": item.effective_at,
        "source_code": item.source_code,
        "checksum_sha256": item.checksum_sha256,
    }


def _connector(item: ConnectorProfile) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "code": item.code,
        "name": item.name,
        "connector_type": item.connector_type,
        "provider_code": item.provider_code,
        "direction": item.direction,
        "status": item.status,
        "base_url": item.base_url,
        "public_config": item.public_config,
        "has_secret_reference": bool(item.secret_ref),
        "allowed_data_classes": item.allowed_data_classes,
        "health_status": item.health_status,
        "last_health_checked_at": item.last_health_checked_at,
        "last_health_message": item.last_health_message,
        "version": item.version,
    }


def _api_client(item: ApiClientCredential) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "name": item.name,
        "client_key": item.client_key,
        "scopes": item.scopes,
        "allowed_ip_ranges": item.allowed_ip_ranges,
        "status": item.status,
        "expires_at": item.expires_at,
        "last_used_at": item.last_used_at,
        "rotated_at": item.rotated_at,
        "revoked_at": item.revoked_at,
        "version": item.version,
    }


def _webhook(item: WebhookSubscription) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "code": item.code,
        "event_code": item.event_code,
        "target_url": item.target_url,
        "status": item.status,
        "has_secret_reference": bool(item.secret_ref),
        "headers_public": item.headers_public,
        "allowed_data_classes": item.allowed_data_classes,
        "failure_count": item.failure_count,
        "last_delivery_at": item.last_delivery_at,
        "version": item.version,
    }


def _delivery(item: WebhookDelivery) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "subscription_public_id": str(item.subscription.public_id),
        "event_public_id": str(item.event_public_id),
        "event_type": item.event_type,
        "payload_digest_sha256": item.payload_digest_sha256,
        "status": item.status,
        "attempt_count": item.attempt_count,
        "response_code": item.response_code,
        "error_summary": item.error_summary,
        "delivered_at": item.delivered_at,
    }


def _mapping(item: DataMappingProfile) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "connector_public_id": str(item.connector.public_id),
        "connector_code": item.connector.code,
        "code": item.code,
        "version": item.version,
        "name": item.name,
        "source_schema_code": item.source_schema_code,
        "target_schema_code": item.target_schema_code,
        "mappings": item.mappings,
        "transformations": item.transformations,
        "status": item.status,
        "published_at": item.published_at,
        "checksum_sha256": item.checksum_sha256,
    }


def _sync(item: SynchronizationRun) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "connector_public_id": str(item.connector.public_id),
        "connector_code": item.connector.code,
        "mapping_public_id": str(item.mapping_profile.public_id) if item.mapping_profile else None,
        "direction": item.direction,
        "status": item.status,
        "idempotency_key": item.idempotency_key,
        "started_at": item.started_at,
        "completed_at": item.completed_at,
        "records_read": item.records_read,
        "records_written": item.records_written,
        "records_rejected": item.records_rejected,
        "evidence_checksum_sha256": item.evidence_checksum_sha256,
        "error_summary": item.error_summary,
        "version": item.version,
    }


class IntegrationSummaryView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("integration.dashboard.read")
        return Response(integration_summary(self.tenant_context.company))


class IntegrationProviderCatalogView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("integration.dashboard.read")
        company = self.tenant_context.company
        connectors = ConnectorProfile.objects.filter(company=company)
        by_provider = {}
        for connector in connectors:
            current = by_provider.get(connector.provider_code)
            if current is None or connector.status == ConnectorProfile.Status.ACTIVE:
                by_provider[connector.provider_code] = connector
        items = []
        for provider in IntegrationProviderCatalog.objects.filter(is_active=True):
            connector = by_provider.get(provider.provider_code)
            items.append(
                {
                    "public_id": str(provider.public_id),
                    "code": provider.code,
                    "name": provider.name,
                    "category": provider.category,
                    "connector_type": provider.connector_type,
                    "provider_code": provider.provider_code,
                    "adapter_code": provider.adapter_code,
                    "description": provider.description,
                    "capabilities": provider.capabilities,
                    "configuration_schema": provider.configuration_schema,
                    "docs_url": provider.docs_url,
                    "recommended": provider.recommended,
                    "connection": (
                        {
                            "public_id": str(connector.public_id),
                            "code": connector.code,
                            "name": connector.name,
                            "status": connector.status,
                            "health_status": connector.health_status,
                        }
                        if connector
                        else None
                    ),
                }
            )
        return Response({"items": items})


class LocalizationPackListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("integration.localization.read")
        items = LocalizationPack.objects.filter(company=self.tenant_context.company)[:250]
        return Response({"items": [_localization(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("integration.localization.manage")
        serializer = LocalizationPackCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_localization_pack(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_localization(item), status=201)


class LocalizationPublishView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("integration.localization.publish")
        serializer = PublishSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = publish_localization_pack(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_localization(item))


class ExchangeRateListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("integration.currency.read")
        items = ExchangeRateSnapshot.objects.filter(company=self.tenant_context.company)[:250]
        return Response({"items": [_rate(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("integration.currency.manage")
        serializer = ExchangeRateCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = record_exchange_rate(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_rate(item), status=201)


class ConnectorListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("integration.connector.read")
        items = ConnectorProfile.objects.filter(company=self.tenant_context.company)[:250]
        return Response({"items": [_connector(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("integration.connector.manage")
        serializer = ConnectorCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_connector(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_connector(item), status=201)


class ConnectorStatusView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("integration.connector.manage")
        serializer = StatusActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_connector_status(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_connector(item))


class ConnectorHealthView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("integration.connector.health")
        serializer = PublishSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = evaluate_connector_health(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_connector(item))


class ApiClientListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        _require_api_access(self.tenant_context.company)
        self.tenant_context.require("integration.api_client.read")
        items = ApiClientCredential.objects.filter(company=self.tenant_context.company)[:250]
        return Response({"items": [_api_client(item) for item in items]})

    def post(self, request: Request) -> Response:
        _require_api_access(self.tenant_context.company)
        self.tenant_context.require("integration.api_client.manage")
        serializer = ApiClientCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item, raw_secret = issue_api_client(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response({**_api_client(item), "client_secret": raw_secret}, status=201)


class ApiClientRotateView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        _require_api_access(self.tenant_context.company)
        self.tenant_context.require("integration.api_client.rotate")
        serializer = ApiClientActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item, raw_secret = rotate_api_client(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                public_id=public_id,
                expected_version=serializer.validated_data["expected_version"],
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response({**_api_client(item), "client_secret": raw_secret})


class ApiClientRevokeView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        _require_api_access(self.tenant_context.company)
        self.tenant_context.require("integration.api_client.revoke")
        serializer = ApiClientActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = revoke_api_client(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                public_id=public_id,
                expected_version=serializer.validated_data["expected_version"],
                reason=serializer.validated_data.get("reason", ""),
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_api_client(item))


class WebhookListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("integration.webhook.read")
        items = WebhookSubscription.objects.filter(company=self.tenant_context.company)[:250]
        return Response({"items": [_webhook(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("integration.webhook.manage")
        serializer = WebhookCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_webhook_subscription(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_webhook(item), status=201)


class WebhookStatusView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("integration.webhook.manage")
        serializer = StatusActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_webhook_status(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_webhook(item))


class WebhookSimulationView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("integration.webhook.test")
        serializer = WebhookSimulationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = simulate_webhook_delivery(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                subscription_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_delivery(item), status=201)


class MappingListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("integration.mapping.read")
        items = DataMappingProfile.objects.select_related("connector").filter(
            connector__company=self.tenant_context.company
        )[:250]
        return Response({"items": [_mapping(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("integration.mapping.manage")
        serializer = MappingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_mapping_profile(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_mapping(item), status=201)


class MappingPublishView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("integration.mapping.publish")
        try:
            item = publish_mapping_profile(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                public_id=public_id,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_mapping(item))


class SyncRunListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("integration.sync.read")
        items = SynchronizationRun.objects.select_related("connector", "mapping_profile").filter(
            company=self.tenant_context.company
        )[:250]
        return Response({"items": [_sync(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("integration.sync.run")
        serializer = SyncStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = start_synchronization_run(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_sync(item), status=201)


class SyncRunCompleteView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("integration.sync.run")
        serializer = SyncCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = complete_synchronization_run(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_sync(item))



class MetaLeadConnectorListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("integration.meta_leads.read")
        require_meta_ads_entitlement(self.tenant_context.company)
        connectors = ConnectorProfile.objects.filter(
            company=self.tenant_context.company,
            provider_code=META_PROVIDER_CODE,
        ).order_by("-created_at")
        receipts = (
            MetaLeadReceipt.objects.select_related("connector")
            .filter(company=self.tenant_context.company)
            .order_by("-created_at")[:100]
        )
        now = timezone.now()
        owners = (
            Membership.objects.select_related("user")
            .filter(
                company=self.tenant_context.company,
                suspended_at__isnull=True,
                terminated_at__isnull=True,
                effective_from__lte=now,
                user__is_active=True,
            )
            .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now))
            .order_by("user__display_name", "user__email")
        )
        return Response(
            {
                "connectors": [meta_connector_payload(item) for item in connectors],
                "receipts": [meta_receipt_payload(item) for item in receipts],
                "owners": [
                    {
                        "membership_public_id": str(item.public_id),
                        "user_public_id": str(item.user.public_id),
                        "display_name": item.user.display_name or item.user.email,
                        "email": item.user.email,
                    }
                    for item in owners
                ],
            }
        )

    def post(self, request: Request) -> Response:
        self.tenant_context.require("integration.meta_leads.manage")
        serializer = MetaLeadConnectorCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            connector, verify_token = create_meta_connector(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except (DjangoValidationError, PermissionDenied) as exc:
            if isinstance(exc, DjangoValidationError):
                raise _validation(exc) from exc
            raise
        return Response(
            {
                **meta_connector_payload(connector),
                "webhook_verify_token": verify_token,
                "verify_token_shown_once": True,
            },
            status=201,
        )


class MetaLeadConnectorStatusView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("integration.meta_leads.manage")
        serializer = MetaLeadStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            connector = activate_meta_connector(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                connector_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(meta_connector_payload(connector))


class MetaLeadVerifyTokenRotateView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("integration.meta_leads.manage")
        serializer = MetaLeadRotateVerifyTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            connector, raw = rotate_verify_token(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                connector_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(
            {
                **meta_connector_payload(connector),
                "webhook_verify_token": raw,
                "verify_token_shown_once": True,
            }
        )


class MetaLeadConnectorTestView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("integration.meta_leads.manage")
        serializer = MetaLeadTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        connector = ConnectorProfile.objects.filter(
            company=self.tenant_context.company,
            public_id=public_id,
            provider_code=META_PROVIDER_CODE,
        ).first()
        if connector is None:
            raise ValidationError("Meta connector was not found")
        if connector.version != serializer.validated_data["expected_version"]:
            raise ValidationError("Connector changed; refresh before testing")
        try:
            result = test_meta_connection(connector)
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response({"ok": True, **result})


class MetaLeadReceiptRetryView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("integration.meta_leads.retry")
        require_meta_ads_entitlement(self.tenant_context.company)
        receipt = MetaLeadReceipt.objects.filter(
            company=self.tenant_context.company,
            public_id=public_id,
        ).first()
        if receipt is None:
            raise ValidationError("Meta lead receipt was not found")
        if receipt.status not in [MetaLeadReceipt.Status.FAILED, MetaLeadReceipt.Status.RECEIVED]:
            raise ValidationError("Only failed or unprocessed Meta lead receipts can be retried")
        result = process_meta_lead_receipt(receipt.public_id)
        return Response(meta_receipt_payload(result))


class MetaLeadWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def _connector(self, public_id: uuid.UUID) -> ConnectorProfile:
        connector = ConnectorProfile.objects.select_related("company").filter(
            public_id=public_id,
            provider_code=META_PROVIDER_CODE,
            status=ConnectorProfile.Status.ACTIVE,
            company__is_active=True,
        ).first()
        if connector is None:
            raise ValidationError("Webhook endpoint is not active")
        return connector

    def get(self, request: Request, public_id: uuid.UUID) -> HttpResponse:
        try:
            connector = self._connector(public_id)
            challenge = verify_webhook_challenge(
                connector=connector,
                mode=str(request.query_params.get("hub.mode") or ""),
                verify_token=str(request.query_params.get("hub.verify_token") or ""),
                challenge=str(request.query_params.get("hub.challenge") or ""),
            )
        except (DjangoValidationError, PermissionDenied, ValidationError):
            return HttpResponse("verification failed", status=403, content_type="text/plain")
        return HttpResponse(challenge, status=200, content_type="text/plain")

    def post(self, request: Request, public_id: uuid.UUID) -> HttpResponse:
        try:
            connector = self._connector(public_id)
            raw_body = request.body
            verify_webhook_signature(
                connector=connector,
                raw_body=raw_body,
                signature=str(request.headers.get("X-Hub-Signature-256") or ""),
            )
            payload = json.loads(raw_body.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("payload is not an object")
            receipt_ids = record_webhook_payload(connector=connector, payload=payload)
            for receipt_id in receipt_ids:
                transaction.on_commit(
                    lambda value=str(receipt_id): process_meta_lead_receipt_task.delay(value),
                    robust=True,
                )
        except (DjangoValidationError, PermissionDenied, ValidationError, ValueError, json.JSONDecodeError):
            return HttpResponse("rejected", status=403, content_type="text/plain")
        return HttpResponse("EVENT_RECEIVED", status=200, content_type="text/plain")
