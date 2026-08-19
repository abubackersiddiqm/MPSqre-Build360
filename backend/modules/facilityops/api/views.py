from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.facilityops.application.selectors import facility_overview
from modules.facilityops.application.services import (
    create_asset,
    create_facility,
    create_inspection,
    create_plan,
    create_service_request,
    create_space,
    create_warranty_claim,
    create_work_order,
    record_lifecycle_event,
    seed_defaults,
    transition_asset,
    transition_inspection,
    transition_service_request,
    transition_warranty_claim,
    transition_work_order,
)
from modules.facilityops.models import (
    ConditionInspection,
    Facility,
    FacilitySpace,
    FacilityWorkOrder,
    MaintenancePlan,
    OperationalAsset,
    ServiceRequest,
    WarrantyClaim,
)
from modules.tenant.api.base import TenantScopedAPIView

from .serializers import (
    AssetCreateSerializer,
    FacilityCreateSerializer,
    InspectionCreateSerializer,
    LifecycleEventCreateSerializer,
    LifecycleTransitionSerializer,
    PlanCreateSerializer,
    ServiceRequestCreateSerializer,
    SpaceCreateSerializer,
    WarrantyClaimCreateSerializer,
    WarrantyTransitionSerializer,
    WorkOrderCreateSerializer,
    WorkOrderTransitionSerializer,
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


class FacilityAPIView(TenantScopedAPIView):
    required_permission = "facility.view"

    def initial(self, request: Request, *args: object, **kwargs: object) -> None:
        super().initial(request, *args, **kwargs)
        self.tenant_context.require(self.required_permission)

    @property
    def actor(self) -> uuid.UUID:
        return self.tenant_context.principal.user.public_id


class OverviewView(FacilityAPIView):
    def get(self, request: Request) -> Response:
        seed_defaults(self.tenant_context.company)
        return Response(facility_overview(self.tenant_context.company))


class FacilityCreateView(FacilityAPIView):
    required_permission = "facility.facility"

    def post(self, request: Request) -> Response:
        serializer = FacilityCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_facility(
                company=self.tenant_context.company,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "code": item.code, "status": item.status_code}, status=201)


class SpaceCreateView(FacilityAPIView):
    required_permission = "facility.space"

    def post(self, request: Request) -> Response:
        serializer = SpaceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        facility = find(Facility, company=self.tenant_context.company, public_id=data.pop("facility_public_id"), message="Facility not found.")
        parent = None
        parent_id = data.pop("parent_public_id", None)
        if parent_id:
            parent = find(FacilitySpace, company=self.tenant_context.company, public_id=parent_id, message="Parent space not found.")
        try:
            item = create_space(
                company=self.tenant_context.company,
                facility=facility,
                parent=parent,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "code": item.code}, status=201)


class AssetCreateView(FacilityAPIView):
    required_permission = "facility.asset"

    def post(self, request: Request) -> Response:
        serializer = AssetCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        facility = find(Facility, company=self.tenant_context.company, public_id=data.pop("facility_public_id"), message="Facility not found.")
        space = None
        space_id = data.pop("space_public_id", None)
        if space_id:
            space = find(FacilitySpace, company=self.tenant_context.company, public_id=space_id, message="Facility space not found.")
        try:
            item = create_asset(
                company=self.tenant_context.company,
                facility=facility,
                space=space,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "asset_tag": item.asset_tag}, status=201)


class AssetTransitionView(FacilityAPIView):
    required_permission = "facility.approve"

    def post(self, request: Request, asset_id: uuid.UUID) -> Response:
        item = find(OperationalAsset, company=self.tenant_context.company, public_id=asset_id, message="Operational asset not found.")
        serializer = LifecycleTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_asset(asset=item, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.operation_status_code, "version": item.version})


class PlanCreateView(FacilityAPIView):
    required_permission = "facility.maintenance"

    def post(self, request: Request) -> Response:
        serializer = PlanCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        asset = find(OperationalAsset, company=self.tenant_context.company, public_id=data.pop("asset_public_id"), message="Operational asset not found.")
        try:
            item = create_plan(company=self.tenant_context.company, asset=asset, actor_public_id=self.actor, correlation_id=correlation_id(request), **data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "code": item.code}, status=201)


class ServiceRequestCreateView(FacilityAPIView):
    required_permission = "facility.service"

    def post(self, request: Request) -> Response:
        serializer = ServiceRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        facility = find(Facility, company=self.tenant_context.company, public_id=data.pop("facility_public_id"), message="Facility not found.")
        space = None
        asset = None
        space_id = data.pop("space_public_id", None)
        asset_id = data.pop("asset_public_id", None)
        if space_id:
            space = find(FacilitySpace, company=self.tenant_context.company, public_id=space_id, message="Facility space not found.")
        if asset_id:
            asset = find(OperationalAsset, company=self.tenant_context.company, public_id=asset_id, message="Operational asset not found.")
        try:
            item = create_service_request(
                company=self.tenant_context.company,
                facility=facility,
                space=space,
                asset=asset,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "request_number": item.request_number}, status=201)


class ServiceRequestTransitionView(FacilityAPIView):
    required_permission = "facility.service"

    def post(self, request: Request, request_id: uuid.UUID) -> Response:
        item = find(ServiceRequest, company=self.tenant_context.company, public_id=request_id, message="Service request not found.")
        serializer = LifecycleTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_service_request(request_item=item, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.status_code, "version": item.version})


class WorkOrderCreateView(FacilityAPIView):
    required_permission = "facility.maintenance"

    def post(self, request: Request) -> Response:
        serializer = WorkOrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        asset = find(OperationalAsset, company=self.tenant_context.company, public_id=data.pop("asset_public_id"), message="Operational asset not found.")
        plan = None
        service_request = None
        plan_id = data.pop("plan_public_id", None)
        service_request_id = data.pop("service_request_public_id", None)
        if plan_id:
            plan = find(MaintenancePlan, company=self.tenant_context.company, public_id=plan_id, message="Maintenance plan not found.")
        if service_request_id:
            service_request = find(ServiceRequest, company=self.tenant_context.company, public_id=service_request_id, message="Service request not found.")
        if not data.get("currency_code"):
            data.pop("currency_code", None)
        try:
            item = create_work_order(
                company=self.tenant_context.company,
                asset=asset,
                plan=plan,
                service_request=service_request,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "work_order_number": item.work_order_number}, status=201)


class WorkOrderTransitionView(FacilityAPIView):
    required_permission = "facility.approve"

    def post(self, request: Request, work_order_id: uuid.UUID) -> Response:
        item = find(FacilityWorkOrder, company=self.tenant_context.company, public_id=work_order_id, message="Facility work order not found.")
        serializer = WorkOrderTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_work_order(work_order=item, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.status_code, "version": item.version})


class WarrantyClaimCreateView(FacilityAPIView):
    required_permission = "facility.warranty"

    def post(self, request: Request) -> Response:
        serializer = WarrantyClaimCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        asset = find(OperationalAsset, company=self.tenant_context.company, public_id=data.pop("asset_public_id"), message="Operational asset not found.")
        work_order = None
        work_order_id = data.pop("work_order_public_id", None)
        if work_order_id:
            work_order = find(FacilityWorkOrder, company=self.tenant_context.company, public_id=work_order_id, message="Facility work order not found.")
        if not data.get("currency_code"):
            data.pop("currency_code", None)
        try:
            item = create_warranty_claim(
                company=self.tenant_context.company,
                asset=asset,
                work_order=work_order,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "claim_number": item.claim_number}, status=201)


class WarrantyClaimTransitionView(FacilityAPIView):
    required_permission = "facility.approve"

    def post(self, request: Request, claim_id: uuid.UUID) -> Response:
        item = find(WarrantyClaim, company=self.tenant_context.company, public_id=claim_id, message="Warranty claim not found.")
        serializer = WarrantyTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_warranty_claim(claim=item, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.status_code, "version": item.version})


class InspectionCreateView(FacilityAPIView):
    required_permission = "facility.inspect"

    def post(self, request: Request) -> Response:
        serializer = InspectionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        facility = find(Facility, company=self.tenant_context.company, public_id=data.pop("facility_public_id"), message="Facility not found.")
        space = None
        asset = None
        space_id = data.pop("space_public_id", None)
        asset_id = data.pop("asset_public_id", None)
        if space_id:
            space = find(FacilitySpace, company=self.tenant_context.company, public_id=space_id, message="Facility space not found.")
        if asset_id:
            asset = find(OperationalAsset, company=self.tenant_context.company, public_id=asset_id, message="Operational asset not found.")
        try:
            item = create_inspection(
                company=self.tenant_context.company,
                facility=facility,
                space=space,
                asset=asset,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "inspection_number": item.inspection_number}, status=201)


class InspectionTransitionView(FacilityAPIView):
    required_permission = "facility.approve"

    def post(self, request: Request, inspection_id: uuid.UUID) -> Response:
        item = find(ConditionInspection, company=self.tenant_context.company, public_id=inspection_id, message="Condition inspection not found.")
        serializer = LifecycleTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_inspection(inspection=item, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.status_code, "version": item.version})


class LifecycleEventCreateView(FacilityAPIView):
    required_permission = "facility.asset"

    def post(self, request: Request) -> Response:
        serializer = LifecycleEventCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        asset = find(OperationalAsset, company=self.tenant_context.company, public_id=data.pop("asset_public_id"), message="Operational asset not found.")
        try:
            item = record_lifecycle_event(
                company=self.tenant_context.company,
                asset=asset,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "event_type": item.event_type_code}, status=201)
