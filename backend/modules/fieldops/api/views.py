from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.fieldops.api.serializers import FieldStageCreateSerializer, OfflineOperationSerializer
from modules.fieldops.application.sync import receive_operation
from modules.fieldops.models import FieldStage, OfflineOperation, SyncConflict
from modules.platform.actors import request_actor
from modules.tenant.api.base import TenantScopedAPIView


def _validation(exc: DjangoValidationError) -> ValidationError:
    if hasattr(exc, "message_dict"):
        return ValidationError(exc.message_dict)
    return ValidationError(exc.messages)


def stage_payload(stage: FieldStage) -> dict[str, object]:
    return {
        "public_id": str(stage.public_id),
        "entity_type": stage.entity_type,
        "code": stage.code,
        "name": stage.name,
        "outcome": stage.outcome,
        "sort_order": stage.sort_order,
        "allowed_next_codes": stage.allowed_next_codes,
        "is_initial": stage.is_initial,
    }


class FieldStageListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("field.stage.read")
        queryset = FieldStage.objects.filter(
            company=self.tenant_context.company,
            is_active=True,
            effective_from__lte=timezone.now(),
        ).filter(Q(effective_to__isnull=True) | Q(effective_to__gt=timezone.now()))
        entity_type = request.query_params.get("entity_type", "").strip()
        if entity_type:
            queryset = queryset.filter(entity_type=entity_type)
        return Response({"items": [stage_payload(item) for item in queryset]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("field.stage.manage")
        serializer = FieldStageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            with transaction.atomic():
                if data.get("is_initial"):
                    FieldStage.objects.filter(
                        company=self.tenant_context.company,
                        entity_type=data["entity_type"],
                        is_initial=True,
                    ).update(is_initial=False)
                stage = FieldStage(
                    company=self.tenant_context.company,
                    effective_from=timezone.now(),
                    **data,
                )
                stage.full_clean()
                stage.save()
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(stage_payload(stage), status=201)


class OfflineOperationListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("field.offline.read")
        operations = OfflineOperation.objects.filter(
            company=self.tenant_context.company
        ).order_by("-received_at")[:100]
        return Response({
            "items": [
                {
                    "public_id": str(item.public_id),
                    "operation_id": str(item.operation_id),
                    "device_id": str(item.device_id),
                    "operation_type": item.operation_type,
                    "status": item.status,
                    "received_at": item.received_at,
                    "processed_at": item.processed_at,
                }
                for item in operations
            ]
        })

    def post(self, request: Request) -> Response:
        self.tenant_context.require("field.offline.submit")
        serializer = OfflineOperationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            operation, created = receive_operation(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                membership_public_id=self.tenant_context.membership.public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(
            {
                "public_id": str(operation.public_id),
                "operation_id": str(operation.operation_id),
                "status": operation.status,
                "created": created,
            },
            status=201 if created else 200,
        )


class FieldSyncSummaryView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("field.dashboard.read")
        operations = OfflineOperation.objects.filter(company=self.tenant_context.company)
        conflicts = SyncConflict.objects.filter(
            company=self.tenant_context.company,
            resolved_at__isnull=True,
        )
        return Response({
            "offline_operations": operations.count(),
            "pending_operations": operations.filter(status="received").count(),
            "open_conflicts": conflicts.count(),
            "approved_operation_types": [
                "labour.attendance.create",
                "equipment.meter_reading.create",
                "quality.inspection.submit",
                "safety.incident.report",
            ],
        })
