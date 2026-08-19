from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.equipment.api.serializers import (
    EquipmentAllocationSerializer,
    EquipmentCreateSerializer,
    MaintenanceCreateSerializer,
    MeterReadingSerializer,
)
from modules.equipment.application.services import (
    allocate_equipment,
    create_equipment,
    create_maintenance,
    record_meter,
)
from modules.equipment.models import EquipmentAllocation, EquipmentAsset, MaintenanceWorkOrder
from modules.fieldops.api.views import stage_payload
from modules.platform.actors import request_actor
from modules.tenant.api.base import TenantScopedAPIView


def _validation(exc: DjangoValidationError) -> ValidationError:
    return ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)


def asset_payload(item: EquipmentAsset) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "code": item.code,
        "name": item.name,
        "category_code": item.category_code,
        "ownership_type": item.ownership_type,
        "stage": stage_payload(item.stage),
        "current_meter": item.current_meter,
        "meter_unit": item.meter_unit,
        "hourly_cost": item.hourly_cost,
        "currency": item.currency,
        "version": item.version,
    }


class EquipmentSummaryView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("equipment.dashboard.read")
        assets = EquipmentAsset.objects.filter(
            company=self.tenant_context.company, retired_at__isnull=True
        )
        return Response(
            {
                "assets": assets.count(),
                "allocated": EquipmentAllocation.objects.filter(company=self.tenant_context.company)
                .exclude(stage__outcome__in=["complete", "cancelled"])
                .count(),
                "open_maintenance": MaintenanceWorkOrder.objects.filter(
                    company=self.tenant_context.company
                )
                .exclude(stage__outcome__in=["complete", "cancelled"])
                .count(),
                "by_stage": list(
                    assets.values("stage__code", "stage__name").annotate(count=Count("id"))
                ),
            }
        )


class EquipmentListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("equipment.asset.read")
        items = (
            EquipmentAsset.objects.select_related("stage")
            .filter(company=self.tenant_context.company, retired_at__isnull=True)
            .order_by("code")[:200]
        )
        return Response({"items": [asset_payload(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("equipment.asset.manage")
        serializer = EquipmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_equipment(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(asset_payload(item), status=201)


class EquipmentAllocationListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("equipment.allocation.read")
        items = (
            EquipmentAllocation.objects.select_related("equipment", "project", "stage")
            .filter(company=self.tenant_context.company)
            .order_by("-allocated_from")[:200]
        )
        return Response(
            {
                "items": [
                    {
                        "public_id": str(item.public_id),
                        "equipment": asset_payload(item.equipment),
                        "project": {
                            "public_id": str(item.project.public_id),
                            "code": item.project.code,
                            "name": item.project.name,
                        },
                        "stage": stage_payload(item.stage),
                        "allocated_from": item.allocated_from,
                        "allocated_to": item.allocated_to,
                        "version": item.version,
                    }
                    for item in items
                ]
            }
        )

    def post(self, request: Request) -> Response:
        self.tenant_context.require("equipment.allocation.manage")
        serializer = EquipmentAllocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = allocate_equipment(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(
            {
                "public_id": str(item.public_id),
                "stage": stage_payload(item.stage),
                "version": item.version,
            },
            status=201,
        )


class MeterReadingCreateView(TenantScopedAPIView):
    def post(self, request: Request) -> Response:
        self.tenant_context.require("equipment.meter.manage")
        serializer = MeterReadingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = record_meter(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(
            {
                "public_id": str(item.public_id),
                "reading": item.reading,
                "reading_at": item.reading_at,
            },
            status=201,
        )


class MaintenanceListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("equipment.maintenance.read")
        items = (
            MaintenanceWorkOrder.objects.select_related("equipment", "stage")
            .filter(company=self.tenant_context.company)
            .order_by("-opened_at")[:200]
        )
        return Response(
            {
                "items": [
                    {
                        "public_id": str(item.public_id),
                        "work_order_number": item.work_order_number,
                        "equipment": asset_payload(item.equipment),
                        "stage": stage_payload(item.stage),
                        "summary": item.summary,
                        "due_date": item.due_date,
                        "version": item.version,
                    }
                    for item in items
                ]
            }
        )

    def post(self, request: Request) -> Response:
        self.tenant_context.require("equipment.maintenance.manage")
        serializer = MaintenanceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_maintenance(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(
            {
                "public_id": str(item.public_id),
                "work_order_number": item.work_order_number,
                "stage": stage_payload(item.stage),
            },
            status=201,
        )
