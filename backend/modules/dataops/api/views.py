
from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.dataops.api.serializers import (
    ImportCommitSerializer,
    ImportJobCreateSerializer,
    PrivacyCreateSerializer,
    PrivacyResolveSerializer,
    RecoveryCompleteSerializer,
    RecoveryCreateSerializer,
    RetentionCreateSerializer,
)
from modules.dataops.application.services import (
    commit_import_job,
    complete_recovery_verification,
    create_import_job,
    create_privacy_request,
    create_recovery_verification,
    create_retention_policy,
    dataops_summary,
    resolve_privacy_request,
)
from modules.dataops.models import (
    ImportJob,
    ImportTemplate,
    PrivacyRequest,
    RecoveryVerification,
    RetentionPolicy,
)
from modules.platform.actors import request_actor
from modules.tenant.api.base import TenantScopedAPIView


def _validation(exc: DjangoValidationError) -> ValidationError:
    return ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)


def _template(item: ImportTemplate) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "code": item.code,
        "name": item.name,
        "destination_code": item.destination_code,
        "version": item.version,
        "schema": item.schema,
        "is_active": item.is_active,
    }


def _job(item: ImportJob, include_rows: bool = False) -> dict[str, object]:
    result: dict[str, object] = {
        "public_id": str(item.public_id),
        "template": _template(item.template),
        "source_name": item.source_name,
        "source_sha256": item.source_sha256,
        "status": item.status,
        "total_rows": item.total_rows,
        "valid_rows": item.valid_rows,
        "error_rows": item.error_rows,
        "committed_rows": item.committed_rows,
        "result_summary": item.result_summary,
        "started_at": item.started_at,
        "completed_at": item.completed_at,
        "version": item.version,
    }
    if include_rows:
        result["rows"] = [
            {
                "public_id": str(row.public_id),
                "row_number": row.row_number,
                "status": row.status,
                "normalized_payload": row.normalized_payload,
                "target_public_id": str(row.target_public_id) if row.target_public_id else None,
                "errors": [
                    {
                        "field_name": error.field_name,
                        "error_code": error.error_code,
                        "message": error.message,
                        "masked_value": error.masked_value,
                    }
                    for error in row.errors.all()
                ],
            }
            for row in item.rows.prefetch_related("errors").all()[:500]
        ]
    return result


def _privacy(item: PrivacyRequest) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "request_number": item.request_number,
        "request_type": item.request_type,
        "subject_type": item.subject_type,
        "subject_public_id": str(item.subject_public_id),
        "status": item.status,
        "due_at": item.due_at,
        "completed_at": item.completed_at,
        "resolution_summary": item.resolution_summary,
        "version": item.version,
    }


def _retention(item: RetentionPolicy) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "record_type": item.record_type,
        "retention_days": item.retention_days,
        "legal_hold_default": item.legal_hold_default,
        "effective_from": item.effective_from,
        "effective_to": item.effective_to,
        "is_active": item.is_active,
        "version": item.version,
    }


def _recovery(item: RecoveryVerification) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "reference": item.reference,
        "scope": item.scope,
        "status": item.status,
        "target_rpo_minutes": item.target_rpo_minutes,
        "measured_rpo_minutes": item.measured_rpo_minutes,
        "target_rto_minutes": item.target_rto_minutes,
        "measured_rto_minutes": item.measured_rto_minutes,
        "evidence_summary": item.evidence_summary,
        "started_at": item.started_at,
        "completed_at": item.completed_at,
        "version": item.version,
    }


class DataopsSummaryView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("dataops.dashboard.read")
        return Response(dataops_summary(self.tenant_context.company))


class TemplateListView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("dataops.template.read")
        items = ImportTemplate.objects.filter(
            company=self.tenant_context.company,
            is_active=True,
        ).order_by("name")[:200]
        return Response({"items": [_template(item) for item in items]})


class ImportJobListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("dataops.import.read")
        items = ImportJob.objects.select_related("template").filter(
            company=self.tenant_context.company,
        ).order_by("-created_at")[:200]
        return Response({"items": [_job(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("dataops.import.create")
        serializer = ImportJobCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_import_job(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_job(item, include_rows=True), status=201)


class ImportJobDetailView(TenantScopedAPIView):
    def get(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("dataops.import.read")
        item = ImportJob.objects.select_related("template").filter(
            company=self.tenant_context.company,
            public_id=public_id,
        ).first()
        if item is None:
            return Response({"detail": "Not found"}, status=404)
        return Response(_job(item, include_rows=True))


class ImportCommitView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("dataops.import.commit")
        serializer = ImportCommitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = commit_import_job(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                job_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_job(item, include_rows=True))


class PrivacyListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("dataops.privacy.read")
        items = PrivacyRequest.objects.filter(
            company=self.tenant_context.company,
        ).order_by("-created_at")[:300]
        return Response({"items": [_privacy(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("dataops.privacy.manage")
        serializer = PrivacyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_privacy_request(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_privacy(item), status=201)


class PrivacyResolveView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("dataops.privacy.resolve")
        serializer = PrivacyResolveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = resolve_privacy_request(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                request_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_privacy(item))


class RetentionListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("dataops.retention.read")
        items = RetentionPolicy.objects.filter(
            company=self.tenant_context.company,
            is_active=True,
        ).order_by("record_type")[:300]
        return Response({"items": [_retention(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("dataops.retention.manage")
        serializer = RetentionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_retention_policy(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_retention(item), status=201)


class RecoveryListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("dataops.recovery.read")
        items = RecoveryVerification.objects.filter(
            company=self.tenant_context.company,
        ).order_by("-created_at")[:300]
        return Response({"items": [_recovery(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("dataops.recovery.manage")
        serializer = RecoveryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_recovery_verification(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_recovery(item), status=201)


class RecoveryCompleteView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("dataops.recovery.manage")
        serializer = RecoveryCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = complete_recovery_verification(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                verification_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_recovery(item))
