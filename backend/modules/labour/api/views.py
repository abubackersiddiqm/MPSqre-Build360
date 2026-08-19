from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Sum
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.fieldops.api.views import stage_payload
from modules.labour.api.serializers import (
    AllocationCreateSerializer,
    AttendanceCreateSerializer,
    AttendanceTransitionSerializer,
    WorkerCreateSerializer,
)
from modules.labour.application.services import (
    allocate_worker,
    create_worker,
    record_attendance,
    transition_attendance,
)
from modules.labour.models import AttendanceRecord, WorkerProfile, WorkforceAllocation
from modules.platform.actors import request_actor
from modules.tenant.api.base import TenantScopedAPIView


def _validation(exc: DjangoValidationError) -> ValidationError:
    return ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)


def worker_payload(item: WorkerProfile) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "code": item.code,
        "display_name": item.display_name,
        "worker_type": item.worker_type,
        "trade_code": item.trade_code,
        "skill_codes": item.skill_codes,
        "daily_rate": item.daily_rate,
        "currency": item.currency,
        "is_active": item.is_active,
        "version": item.version,
    }


def attendance_payload(item: AttendanceRecord) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "worker": {
            "public_id": str(item.worker.public_id),
            "code": item.worker.code,
            "display_name": item.worker.display_name,
        },
        "project": {
            "public_id": str(item.project.public_id),
            "code": item.project.code,
            "name": item.project.name,
        },
        "work_date": item.work_date,
        "regular_hours": item.regular_hours,
        "overtime_hours": item.overtime_hours,
        "stage": stage_payload(item.stage),
        "source": item.source,
        "version": item.version,
    }


class LabourSummaryView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("labour.dashboard.read")
        workers = WorkerProfile.objects.filter(company=self.tenant_context.company, is_active=True)
        allocations = WorkforceAllocation.objects.filter(company=self.tenant_context.company)
        attendance = AttendanceRecord.objects.filter(company=self.tenant_context.company)
        totals = attendance.aggregate(regular=Sum("regular_hours"), overtime=Sum("overtime_hours"))
        return Response(
            {
                "active_workers": workers.count(),
                "active_allocations": allocations.exclude(
                    stage__outcome__in=["complete", "cancelled"]
                ).count(),
                "attendance_records": attendance.count(),
                "regular_hours": totals["regular"] or 0,
                "overtime_hours": totals["overtime"] or 0,
            }
        )


class WorkerListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("labour.worker.read")
        items = WorkerProfile.objects.filter(company=self.tenant_context.company).order_by(
            "display_name"
        )[:200]
        return Response({"items": [worker_payload(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("labour.worker.manage")
        serializer = WorkerCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_worker(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(worker_payload(item), status=201)


class AllocationListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("labour.allocation.read")
        items = (
            WorkforceAllocation.objects.select_related("worker", "project", "stage")
            .filter(company=self.tenant_context.company)
            .order_by("-allocated_from")[:200]
        )
        return Response(
            {
                "items": [
                    {
                        "public_id": str(item.public_id),
                        "worker": worker_payload(item.worker),
                        "project": {
                            "public_id": str(item.project.public_id),
                            "code": item.project.code,
                            "name": item.project.name,
                        },
                        "stage": stage_payload(item.stage),
                        "allocated_from": item.allocated_from,
                        "allocated_to": item.allocated_to,
                        "planned_hours": item.planned_hours,
                        "version": item.version,
                    }
                    for item in items
                ]
            }
        )

    def post(self, request: Request) -> Response:
        self.tenant_context.require("labour.allocation.manage")
        serializer = AllocationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = allocate_worker(
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


class AttendanceListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("labour.attendance.read")
        items = (
            AttendanceRecord.objects.select_related("worker", "project", "stage")
            .filter(company=self.tenant_context.company)
            .order_by("-work_date")[:200]
        )
        return Response({"items": [attendance_payload(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("labour.attendance.manage")
        serializer = AttendanceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = record_attendance(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(attendance_payload(item), status=201)


class AttendanceTransitionView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("labour.attendance.approve")
        serializer = AttendanceTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_attendance(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                attendance_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(attendance_payload(item))
