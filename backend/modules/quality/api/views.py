from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.fieldops.api.views import stage_payload
from modules.platform.actors import request_actor
from modules.quality.api.serializers import (
    InspectionCreateSerializer,
    InspectionSubmitSerializer,
    NcrCreateSerializer,
    TemplateCreateSerializer,
)
from modules.quality.application.services import (
    create_inspection,
    create_ncr,
    create_template,
    submit_inspection,
)
from modules.quality.models import Inspection, InspectionTemplate, NonConformanceReport
from modules.tenant.api.base import TenantScopedAPIView


def _validation(exc: DjangoValidationError) -> ValidationError:
    return ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)


def template_payload(item: InspectionTemplate) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "code": item.code,
        "name": item.name,
        "discipline_code": item.discipline_code,
        "version_number": item.version_number,
        "checklist": item.checklist,
        "is_published": item.is_published,
    }


def inspection_payload(item: Inspection) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "inspection_number": item.inspection_number,
        "title": item.title,
        "project": {
            "public_id": str(item.project.public_id),
            "code": item.project.code,
            "name": item.project.name,
        },
        "template": template_payload(item.template),
        "stage": stage_payload(item.stage),
        "overall_result": item.overall_result,
        "scheduled_at": item.scheduled_at,
        "inspected_at": item.inspected_at,
        "version": item.version,
    }


class QualitySummaryView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("quality.dashboard.read")
        inspections = Inspection.objects.filter(company=self.tenant_context.company)
        ncrs = NonConformanceReport.objects.filter(company=self.tenant_context.company)
        return Response(
            {
                "templates": InspectionTemplate.objects.filter(
                    company=self.tenant_context.company, retired_at__isnull=True
                ).count(),
                "inspections": inspections.count(),
                "pending_inspections": inspections.exclude(
                    stage__outcome__in=["approved", "complete", "rejected", "cancelled"]
                ).count(),
                "open_ncrs": ncrs.exclude(stage__outcome__in=["complete", "cancelled"]).count(),
                "overdue_ncrs": ncrs.filter(due_date__lt=timezone.localdate())
                .exclude(stage__outcome__in=["complete", "cancelled"])
                .count(),
            }
        )


class TemplateListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("quality.template.read")
        return Response(
            {
                "items": [
                    template_payload(i)
                    for i in InspectionTemplate.objects.filter(
                        company=self.tenant_context.company, retired_at__isnull=True
                    ).order_by("code")[:200]
                ]
            }
        )

    def post(self, request: Request) -> Response:
        self.tenant_context.require("quality.template.manage")
        s = TemplateCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            i = create_template(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **s.validated_data,
            )
        except DjangoValidationError as e:
            raise _validation(e) from e
        return Response(template_payload(i), status=201)


class InspectionListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("quality.inspection.read")
        items = (
            Inspection.objects.select_related("project", "template", "stage")
            .filter(company=self.tenant_context.company)
            .order_by("-created_at")[:200]
        )
        return Response({"items": [inspection_payload(i) for i in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("quality.inspection.manage")
        s = InspectionCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            i = create_inspection(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **s.validated_data,
            )
        except DjangoValidationError as e:
            raise _validation(e) from e
        return Response(inspection_payload(i), status=201)


class InspectionSubmitView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("quality.inspection.submit")
        s = InspectionSubmitSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            i = submit_inspection(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                inspection_public_id=public_id,
                **s.validated_data,
            )
        except DjangoValidationError as e:
            raise _validation(e) from e
        return Response(inspection_payload(i))


class NcrListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("quality.ncr.read")
        items = (
            NonConformanceReport.objects.select_related("project", "stage")
            .filter(company=self.tenant_context.company)
            .order_by("-created_at")[:200]
        )
        return Response(
            {
                "items": [
                    {
                        "public_id": str(i.public_id),
                        "ncr_number": i.ncr_number,
                        "title": i.title,
                        "severity": i.severity,
                        "project": {
                            "public_id": str(i.project.public_id),
                            "code": i.project.code,
                            "name": i.project.name,
                        },
                        "stage": stage_payload(i.stage),
                        "due_date": i.due_date,
                        "version": i.version,
                    }
                    for i in items
                ]
            }
        )

    def post(self, request: Request) -> Response:
        self.tenant_context.require("quality.ncr.manage")
        s = NcrCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            i = create_ncr(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **s.validated_data,
            )
        except DjangoValidationError as e:
            raise _validation(e) from e
        return Response(
            {
                "public_id": str(i.public_id),
                "ncr_number": i.ncr_number,
                "stage": stage_payload(i.stage),
                "version": i.version,
            },
            status=201,
        )
