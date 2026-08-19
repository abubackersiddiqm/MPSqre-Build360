from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.digitaltwinops.application.selectors import digital_twin_overview
from modules.digitaltwinops.application.services import (
    create_asset,
    create_clash,
    create_device,
    create_federation,
    create_issue,
    create_model,
    create_revision,
    record_telemetry,
    seed_defaults,
    transition_alert,
    transition_asset,
    transition_clash,
    transition_issue,
    transition_revision,
)
from modules.digitaltwinops.models import (
    BIMIssue,
    BIMModel,
    BIMRevision,
    ClashRecord,
    HandoverAssetRecord,
    IoTDevice,
    ModelFederation,
    SmartAlert,
)
from modules.tenant.api.base import TenantScopedAPIView

from .serializers import (
    AssetCreateSerializer,
    ClashCreateSerializer,
    ClashTransitionSerializer,
    DeviceCreateSerializer,
    FederationCreateSerializer,
    IssueCreateSerializer,
    LifecycleTransitionSerializer,
    ModelCreateSerializer,
    RevisionCreateSerializer,
    TelemetryCreateSerializer,
)


def correlation_id(request: Request) -> uuid.UUID:
    return getattr(request, "request_id", uuid.uuid4())


def translate(error: DjangoValidationError) -> ValidationError:
    if hasattr(error, "message_dict"):
        return ValidationError(error.message_dict)
    return ValidationError(getattr(error, "messages", [str(error)]))


def find(model, *, company, public_id, message):
    item = model.objects.filter(company=company, public_id=public_id).first()
    if item is None:
        raise NotFound(message)
    return item


class DigitalTwinAPIView(TenantScopedAPIView):
    required_permission = "digitaltwin.view"

    def initial(self, request: Request, *args: object, **kwargs: object) -> None:
        super().initial(request, *args, **kwargs)
        self.tenant_context.require(self.required_permission)

    @property
    def actor(self) -> uuid.UUID:
        return self.tenant_context.principal.user.public_id


class OverviewView(DigitalTwinAPIView):
    def get(self, request: Request) -> Response:
        seed_defaults(self.tenant_context.company)
        return Response(digital_twin_overview(self.tenant_context.company))


class ModelCreateView(DigitalTwinAPIView):
    required_permission = "digitaltwin.model"

    def post(self, request: Request) -> Response:
        serializer = ModelCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_model(
                company=self.tenant_context.company,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "code": item.code, "status": item.status_code}, status=201)


class RevisionCreateView(DigitalTwinAPIView):
    required_permission = "digitaltwin.model"

    def post(self, request: Request) -> Response:
        serializer = RevisionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        model = find(
            BIMModel,
            company=self.tenant_context.company,
            public_id=data.pop("model_public_id"),
            message="BIM model not found.",
        )
        try:
            item = create_revision(
                company=self.tenant_context.company,
                model=model,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "revision": item.revision_code, "status": item.status_code}, status=201)


class RevisionTransitionView(DigitalTwinAPIView):
    required_permission = "digitaltwin.approve"

    def post(self, request: Request, revision_id: uuid.UUID) -> Response:
        item = find(BIMRevision, company=self.tenant_context.company, public_id=revision_id, message="BIM revision not found.")
        serializer = LifecycleTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_revision(
                revision=item,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.status_code, "version": item.version})


class FederationCreateView(DigitalTwinAPIView):
    required_permission = "digitaltwin.coordinate"

    def post(self, request: Request) -> Response:
        serializer = FederationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_federation(
                company=self.tenant_context.company,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "code": item.code, "model_count": item.model_count}, status=201)


class ClashCreateView(DigitalTwinAPIView):
    required_permission = "digitaltwin.coordinate"

    def post(self, request: Request) -> Response:
        serializer = ClashCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        federation = find(
            ModelFederation,
            company=self.tenant_context.company,
            public_id=data.pop("federation_public_id"),
            message="Model federation not found.",
        )
        try:
            item = create_clash(
                company=self.tenant_context.company,
                federation=federation,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "clash_number": item.clash_number}, status=201)


class ClashTransitionView(DigitalTwinAPIView):
    required_permission = "digitaltwin.coordinate"

    def post(self, request: Request, clash_id: uuid.UUID) -> Response:
        item = find(ClashRecord, company=self.tenant_context.company, public_id=clash_id, message="Clash record not found.")
        serializer = ClashTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_clash(
                clash=item,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.status_code, "version": item.version})


class IssueCreateView(DigitalTwinAPIView):
    required_permission = "digitaltwin.issue"

    def post(self, request: Request) -> Response:
        serializer = IssueCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        model = None
        revision = None
        if data.get("model_public_id"):
            model = find(BIMModel, company=self.tenant_context.company, public_id=data.pop("model_public_id"), message="BIM model not found.")
        else:
            data.pop("model_public_id", None)
        if data.get("revision_public_id"):
            revision = find(BIMRevision, company=self.tenant_context.company, public_id=data.pop("revision_public_id"), message="BIM revision not found.")
        else:
            data.pop("revision_public_id", None)
        try:
            item = create_issue(
                company=self.tenant_context.company,
                model=model,
                revision=revision,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "issue_code": item.issue_code}, status=201)


class IssueTransitionView(DigitalTwinAPIView):
    required_permission = "digitaltwin.issue"

    def post(self, request: Request, issue_id: uuid.UUID) -> Response:
        item = find(BIMIssue, company=self.tenant_context.company, public_id=issue_id, message="BIM issue not found.")
        serializer = LifecycleTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_issue(
                issue=item,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.status_code, "version": item.version})


class DeviceCreateView(DigitalTwinAPIView):
    required_permission = "digitaltwin.device"

    def post(self, request: Request) -> Response:
        serializer = DeviceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_device(
                company=self.tenant_context.company,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "code": item.code}, status=201)


class TelemetryCreateView(DigitalTwinAPIView):
    required_permission = "digitaltwin.telemetry"

    def post(self, request: Request) -> Response:
        serializer = TelemetryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        device = find(
            IoTDevice,
            company=self.tenant_context.company,
            public_id=data.pop("device_public_id"),
            message="Smart-site device not found.",
        )
        if not data.get("metric_code"):
            data["metric_code"] = device.metric_code
        if not data.get("unit_code"):
            data["unit_code"] = device.unit_code
        try:
            reading, alert = record_telemetry(
                company=self.tenant_context.company,
                device=device,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response(
            {
                "public_id": str(reading.public_id),
                "alert_public_id": str(alert.public_id) if alert else None,
                "alert_triggered": bool(alert),
            },
            status=201,
        )


class AlertTransitionView(DigitalTwinAPIView):
    required_permission = "digitaltwin.alert"

    def post(self, request: Request, alert_id: uuid.UUID) -> Response:
        item = find(SmartAlert, company=self.tenant_context.company, public_id=alert_id, message="Smart-site alert not found.")
        serializer = LifecycleTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_alert(
                alert=item,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.status_code, "version": item.version})


class AssetCreateView(DigitalTwinAPIView):
    required_permission = "digitaltwin.handover"

    def post(self, request: Request) -> Response:
        serializer = AssetCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        model = None
        if data.get("model_public_id"):
            model = find(BIMModel, company=self.tenant_context.company, public_id=data.pop("model_public_id"), message="BIM model not found.")
        else:
            data.pop("model_public_id", None)
        try:
            item = create_asset(
                company=self.tenant_context.company,
                model=model,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "asset_tag": item.asset_tag}, status=201)


class AssetTransitionView(DigitalTwinAPIView):
    required_permission = "digitaltwin.approve"

    def post(self, request: Request, asset_id: uuid.UUID) -> Response:
        item = find(HandoverAssetRecord, company=self.tenant_context.company, public_id=asset_id, message="Handover asset not found.")
        serializer = LifecycleTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_asset(
                asset=item,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.operation_status_code, "version": item.version})
