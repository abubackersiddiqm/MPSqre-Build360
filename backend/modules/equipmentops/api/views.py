from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework import status
from rest_framework.exceptions import ValidationError as ApiValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.equipmentops.api.serializers import (
    EquipmentApprovalDecisionSerializer,
    EquipmentApprovalRequestSerializer,
    EquipmentApprovalSerializer,
    EquipmentAssetCreateSerializer,
    EquipmentAssetSerializer,
    EquipmentDeploymentCreateSerializer,
    EquipmentDeploymentSerializer,
    EquipmentInspectionCreateSerializer,
    EquipmentInspectionSerializer,
    EquipmentMeterReadingCreateSerializer,
    EquipmentMeterReadingSerializer,
    EquipmentPolicySerializer,
    EquipmentRiskCreateSerializer,
    EquipmentRiskResolutionSerializer,
    EquipmentRiskSerializer,
    MaintenanceTransitionSerializer,
    MaintenanceWorkOrderCreateSerializer,
    MaintenanceWorkOrderSerializer,
)
from modules.equipmentops.application.selectors import equipment_overview
from modules.equipmentops.application.services import (
    RequestEvidence,
    create_asset,
    create_deployment,
    create_policy,
    create_risk,
    create_work_order,
    decide_approval,
    record_inspection,
    record_meter_reading,
    request_approval,
    resolve_risk,
    transition_work_order,
)
from modules.equipmentops.models import (
    EquipmentApproval,
    EquipmentAsset,
    EquipmentDeployment,
    EquipmentInspection,
    EquipmentMeterReading,
    EquipmentPolicyVersion,
    EquipmentRisk,
    MaintenanceWorkOrder,
)
from modules.platform.audit import request_metadata
from modules.tenant.api.base import TenantScopedAPIView


def _evidence(request: Request) -> RequestEvidence:
    request_id, ip_address, user_agent = request_metadata(request._request)
    return RequestEvidence(
        request_id=request_id,
        correlation_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )


def _api_validation(exc: DjangoValidationError) -> ApiValidationError:
    if hasattr(exc, "message_dict"):
        return ApiValidationError(exc.message_dict)
    return ApiValidationError({"non_field_errors": list(exc.messages)})


class EquipmentOverviewView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("equipment.view")
        return Response(equipment_overview(self.tenant_context.company))


class EquipmentPolicyListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("equipment.view")
        items = EquipmentPolicyVersion.objects.filter(
            company=self.tenant_context.company
        ).order_by("code", "-version")[:200]
        return Response(EquipmentPolicySerializer(items, many=True).data)

    def post(self, request: Request) -> Response:
        serializer = EquipmentPolicySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            policy = create_policy(
                context=self.tenant_context,
                evidence=_evidence(request),
                attributes=dict(serializer.validated_data),
            )
        except IntegrityError as exc:
            raise ApiValidationError(
                {"code": "An equipment policy with this code and version exists"}
            ) from exc
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(
            EquipmentPolicySerializer(policy).data,
            status=status.HTTP_201_CREATED,
        )


class EquipmentAssetListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("equipment.view")
        items = EquipmentAsset.objects.filter(company=self.tenant_context.company)
        status_code = request.query_params.get("status_code")
        category_code = request.query_params.get("category_code")
        if status_code:
            items = items.filter(status_code=status_code)
        if category_code:
            items = items.filter(category_code=category_code)
        items = items.select_related("policy").order_by("asset_code")[:500]
        return Response(EquipmentAssetSerializer(items, many=True).data)

    def post(self, request: Request) -> Response:
        serializer = EquipmentAssetCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attributes = dict(serializer.validated_data)
        policy_public_id = attributes.pop("policy_public_id")
        try:
            asset = create_asset(
                context=self.tenant_context,
                evidence=_evidence(request),
                policy_public_id=policy_public_id,
                attributes=attributes,
            )
        except IntegrityError as exc:
            raise ApiValidationError(
                {"asset_code": "This equipment asset code already exists"}
            ) from exc
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(
            EquipmentAssetSerializer(asset).data,
            status=status.HTTP_201_CREATED,
        )


class EquipmentDeploymentListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("equipment.view")
        items = EquipmentDeployment.objects.filter(company=self.tenant_context.company)
        asset_public_id = request.query_params.get("asset_public_id")
        if asset_public_id:
            try:
                items = items.filter(asset__public_id=uuid.UUID(asset_public_id))
            except ValueError as exc:
                raise ApiValidationError(
                    {"asset_public_id": "Enter a valid UUID"}
                ) from exc
        items = items.select_related("asset").order_by("-starts_at")[:500]
        return Response(EquipmentDeploymentSerializer(items, many=True).data)

    def post(self, request: Request) -> Response:
        serializer = EquipmentDeploymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attributes = dict(serializer.validated_data)
        asset_public_id = attributes.pop("asset_public_id")
        try:
            deployment = create_deployment(
                context=self.tenant_context,
                evidence=_evidence(request),
                asset_public_id=asset_public_id,
                attributes=attributes,
            )
        except IntegrityError as exc:
            raise ApiValidationError(
                {"deployment_code": "This deployment code already exists"}
            ) from exc
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(
            EquipmentDeploymentSerializer(deployment).data,
            status=status.HTTP_201_CREATED,
        )


class EquipmentMeterReadingListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("equipment.view")
        items = EquipmentMeterReading.objects.filter(company=self.tenant_context.company)
        asset_public_id = request.query_params.get("asset_public_id")
        if asset_public_id:
            try:
                items = items.filter(asset__public_id=uuid.UUID(asset_public_id))
            except ValueError as exc:
                raise ApiValidationError(
                    {"asset_public_id": "Enter a valid UUID"}
                ) from exc
        items = items.select_related("asset", "deployment").order_by("-reading_at")[:500]
        return Response(EquipmentMeterReadingSerializer(items, many=True).data)

    def post(self, request: Request) -> Response:
        serializer = EquipmentMeterReadingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            reading = record_meter_reading(
                context=self.tenant_context,
                evidence=_evidence(request),
                **serializer.validated_data,
            )
        except IntegrityError as exc:
            raise ApiValidationError(
                {"reading_at": "A reading already exists for this asset and time"}
            ) from exc
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(
            EquipmentMeterReadingSerializer(reading).data,
            status=status.HTTP_201_CREATED,
        )


class MaintenanceWorkOrderListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("equipment.view")
        items = MaintenanceWorkOrder.objects.filter(company=self.tenant_context.company)
        status_code = request.query_params.get("status_code")
        asset_public_id = request.query_params.get("asset_public_id")
        if status_code:
            items = items.filter(status_code=status_code)
        if asset_public_id:
            try:
                items = items.filter(asset__public_id=uuid.UUID(asset_public_id))
            except ValueError as exc:
                raise ApiValidationError(
                    {"asset_public_id": "Enter a valid UUID"}
                ) from exc
        items = items.select_related("asset").order_by("-reported_at")[:500]
        return Response(MaintenanceWorkOrderSerializer(items, many=True).data)

    def post(self, request: Request) -> Response:
        serializer = MaintenanceWorkOrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attributes = dict(serializer.validated_data)
        asset_public_id = attributes.pop("asset_public_id")
        try:
            work_order = create_work_order(
                context=self.tenant_context,
                evidence=_evidence(request),
                asset_public_id=asset_public_id,
                attributes=attributes,
            )
        except IntegrityError as exc:
            raise ApiValidationError(
                {"code": "This maintenance work-order code already exists"}
            ) from exc
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(
            MaintenanceWorkOrderSerializer(work_order).data,
            status=status.HTTP_201_CREATED,
        )


class MaintenanceWorkOrderTransitionView(TenantScopedAPIView):
    def post(self, request: Request, work_order_id: uuid.UUID) -> Response:
        serializer = MaintenanceTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            work_order = transition_work_order(
                context=self.tenant_context,
                evidence=_evidence(request),
                work_order_public_id=work_order_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(MaintenanceWorkOrderSerializer(work_order).data)


class EquipmentInspectionListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("equipment.view")
        items = EquipmentInspection.objects.filter(company=self.tenant_context.company)
        asset_public_id = request.query_params.get("asset_public_id")
        if asset_public_id:
            try:
                items = items.filter(asset__public_id=uuid.UUID(asset_public_id))
            except ValueError as exc:
                raise ApiValidationError(
                    {"asset_public_id": "Enter a valid UUID"}
                ) from exc
        items = items.select_related("asset").order_by("-inspected_at")[:500]
        return Response(EquipmentInspectionSerializer(items, many=True).data)

    def post(self, request: Request) -> Response:
        serializer = EquipmentInspectionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attributes = dict(serializer.validated_data)
        asset_public_id = attributes.pop("asset_public_id")
        try:
            inspection = record_inspection(
                context=self.tenant_context,
                evidence=_evidence(request),
                asset_public_id=asset_public_id,
                attributes=attributes,
            )
        except IntegrityError as exc:
            raise ApiValidationError(
                {"inspection_code": "This inspection code already exists"}
            ) from exc
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(
            EquipmentInspectionSerializer(inspection).data,
            status=status.HTTP_201_CREATED,
        )


class EquipmentApprovalListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("equipment.view")
        items = EquipmentApproval.objects.filter(company=self.tenant_context.company)
        pending_only = request.query_params.get("pending") == "true"
        if pending_only:
            items = items.filter(decided_at__isnull=True)
        items = items.select_related("work_order").order_by("-requested_at")[:500]
        return Response(EquipmentApprovalSerializer(items, many=True).data)

    def post(self, request: Request) -> Response:
        serializer = EquipmentApprovalRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            approval = request_approval(
                context=self.tenant_context,
                evidence=_evidence(request),
                **serializer.validated_data,
            )
        except IntegrityError as exc:
            raise ApiValidationError(
                {"step_code": "This approval step already exists for the work order"}
            ) from exc
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(
            EquipmentApprovalSerializer(approval).data,
            status=status.HTTP_201_CREATED,
        )


class EquipmentApprovalDecisionView(TenantScopedAPIView):
    def post(self, request: Request, approval_id: uuid.UUID) -> Response:
        serializer = EquipmentApprovalDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            approval = decide_approval(
                context=self.tenant_context,
                evidence=_evidence(request),
                approval_public_id=approval_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(EquipmentApprovalSerializer(approval).data)


class EquipmentRiskListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("equipment.view")
        items = EquipmentRisk.objects.filter(company=self.tenant_context.company)
        open_only = request.query_params.get("open") == "true"
        if open_only:
            items = items.filter(resolved_at__isnull=True)
        items = items.select_related("asset", "work_order").order_by("-created_at")[:500]
        return Response(EquipmentRiskSerializer(items, many=True).data)

    def post(self, request: Request) -> Response:
        serializer = EquipmentRiskCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attributes = dict(serializer.validated_data)
        asset_public_id = attributes.pop("asset_public_id")
        try:
            risk = create_risk(
                context=self.tenant_context,
                evidence=_evidence(request),
                asset_public_id=asset_public_id,
                attributes=attributes,
            )
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(
            EquipmentRiskSerializer(risk).data,
            status=status.HTTP_201_CREATED,
        )


class EquipmentRiskResolveView(TenantScopedAPIView):
    def post(self, request: Request, risk_id: uuid.UUID) -> Response:
        serializer = EquipmentRiskResolutionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            risk = resolve_risk(
                context=self.tenant_context,
                evidence=_evidence(request),
                risk_public_id=risk_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(EquipmentRiskSerializer(risk).data)
