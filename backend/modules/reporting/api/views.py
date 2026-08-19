
from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpResponse
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.platform.actors import request_actor
from modules.reporting.api.serializers import (
    MetricCreateSerializer,
    ReportRunCreateSerializer,
    SavedReportCreateSerializer,
)
from modules.reporting.application.services import (
    create_and_execute_run,
    create_metric,
    create_saved_report,
    mark_artifact_downloaded,
    reporting_summary,
)
from modules.reporting.models import ExportArtifact, MetricDefinition, ReportRun, SavedReport
from modules.tenant.api.base import TenantScopedAPIView


def _validation(exc: DjangoValidationError) -> ValidationError:
    return ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)


def _metric(item: MetricDefinition) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "code": item.code,
        "name": item.name,
        "description": item.description,
        "domain_code": item.domain_code,
        "calculation_code": item.calculation_code,
        "unit_code": item.unit_code,
        "data_classification": item.data_classification,
        "is_active": item.is_active,
        "version": item.version,
    }


def _saved(item: SavedReport) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "code": item.code,
        "name": item.name,
        "description": item.description,
        "report_type": item.report_type,
        "metric_codes": item.metric_codes,
        "filters": item.filters,
        "columns": item.columns,
        "visibility": item.visibility,
        "default_export_format": item.default_export_format,
        "schedule_expression": item.schedule_expression,
        "next_run_at": item.next_run_at,
        "is_active": item.is_active,
        "version": item.version,
    }


def _run(item: ReportRun) -> dict[str, object]:
    artifact: ExportArtifact | None = None
    try:
        artifact = item.artifact
    except ExportArtifact.DoesNotExist:
        pass
    return {
        "public_id": str(item.public_id),
        "saved_report_public_id": str(item.saved_report.public_id) if item.saved_report_id else None,
        "report_code": item.report_code,
        "status": item.status,
        "export_format": item.export_format,
        "parameters": item.parameters,
        "metric_snapshot": item.metric_snapshot,
        "row_count": item.row_count,
        "started_at": item.started_at,
        "completed_at": item.completed_at,
        "expires_at": item.expires_at,
        "error_message": item.error_message,
        "version": item.version,
        "artifact": {
            "file_name": artifact.file_name,
            "content_type": artifact.content_type,
            "byte_size": artifact.byte_size,
            "sha256": artifact.sha256,
            "download_count": artifact.download_count,
        } if artifact else None,
    }


class ReportingSummaryView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("reporting.dashboard.read")
        return Response(reporting_summary(self.tenant_context.company))


class MetricListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("reporting.metric.read")
        items = MetricDefinition.objects.filter(
            company=self.tenant_context.company,
        ).order_by("domain_code", "name")[:300]
        return Response({"items": [_metric(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("reporting.metric.manage")
        serializer = MetricCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_metric(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_metric(item), status=201)


class SavedReportListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("reporting.report.read")
        items = SavedReport.objects.filter(
            company=self.tenant_context.company,
            is_active=True,
        ).order_by("name")[:300]
        return Response({"items": [_saved(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("reporting.report.manage")
        serializer = SavedReportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_saved_report(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_saved(item), status=201)


class ReportRunListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("reporting.run.read")
        items = (
            ReportRun.objects.select_related("saved_report")
            .filter(company=self.tenant_context.company)
            .order_by("-created_at")[:300]
        )
        return Response({"items": [_run(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("reporting.run.execute")
        serializer = ReportRunCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_and_execute_run(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_run(item), status=201)


class ReportDownloadView(TenantScopedAPIView):
    def get(self, request: Request, public_id: uuid.UUID) -> HttpResponse:
        self.tenant_context.require("reporting.export.download")
        try:
            run, content, content_type, extension = mark_artifact_downloaded(
                company=self.tenant_context.company,
                run_public_id=public_id,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        response = HttpResponse(content, content_type=content_type)
        response["Content-Disposition"] = (
            f'attachment; filename="{run.report_code.lower()}-{run.public_id}.{extension}"'
        )
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"
        return response
