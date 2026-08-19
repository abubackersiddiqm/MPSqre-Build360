from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count, Sum
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.estimation.api.serializers import (
    BoqItemCreateSerializer,
    BoqSectionCreateSerializer,
    EstimateBaselineSerializer,
    EstimateCreateSerializer,
    EstimateTransitionSerializer,
    EstimateVersionCreateSerializer,
)
from modules.estimation.application.services import (
    baseline_estimate_version,
    create_boq_item,
    create_estimate,
    create_estimate_version,
    create_section,
    transition_estimate_version,
)
from modules.estimation.models import (
    BoqItem,
    BoqSection,
    Estimate,
    EstimateBaseline,
    EstimateVersion,
)
from modules.platform.actors import request_actor
from modules.projects.application.services import available_transitions
from modules.projects.models import DeliveryStage
from modules.tenant.api.base import TenantScopedAPIView


def _validation(exc: DjangoValidationError) -> ValidationError:
    if hasattr(exc, "message_dict"):
        return ValidationError(exc.message_dict)
    return ValidationError(exc.messages)


def _limit(request: Request) -> int:
    try:
        return min(max(int(request.query_params.get("limit", "100")), 1), 200)
    except ValueError:
        return 100


def _stage(stage: DeliveryStage) -> dict[str, object]:
    return {
        "public_id": str(stage.public_id),
        "code": stage.code,
        "name": stage.name,
        "outcome": stage.outcome,
        "allowed_next_codes": stage.allowed_next_codes,
        "allows_baseline": stage.allows_baseline,
    }


def _estimate(estimate: Estimate) -> dict[str, object]:
    active = estimate.versions.select_related("stage").filter(
        version_number=estimate.active_version_number
    ).first()
    return {
        "public_id": str(estimate.public_id),
        "project_public_id": str(estimate.project.public_id),
        "project_code": estimate.project.code,
        "code": estimate.code,
        "name": estimate.name,
        "currency": estimate.currency,
        "active_version_number": estimate.active_version_number,
        "active_version": _version(active) if active else None,
        "version": estimate.version,
        "created_at": estimate.created_at,
    }


def _version(version: EstimateVersion) -> dict[str, object]:
    return {
        "public_id": str(version.public_id),
        "estimate_public_id": str(version.estimate.public_id),
        "version_number": version.version_number,
        "stage": _stage(version.stage),
        "available_transitions": [_stage(item) for item in available_transitions(version.stage)],
        "notes": version.notes,
        "subtotal": str(version.subtotal),
        "tax_total": str(version.tax_total),
        "grand_total": str(version.grand_total),
        "submitted_at": version.submitted_at,
        "approved_at": version.approved_at,
        "baselined_at": version.baselined_at,
        "superseded_at": version.superseded_at,
        "version": version.version,
        "created_at": version.created_at,
    }


def _section(section: BoqSection) -> dict[str, object]:
    return {
        "public_id": str(section.public_id),
        "estimate_version_public_id": str(section.estimate_version.public_id),
        "code": section.code,
        "name": section.name,
        "sort_order": section.sort_order,
    }


def _item(item: BoqItem) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "estimate_version_public_id": str(item.estimate_version.public_id),
        "section_public_id": str(item.section.public_id) if item.section else None,
        "item_code": item.item_code,
        "description": item.description,
        "unit_code": item.unit_code,
        "quantity": str(item.quantity),
        "rate": str(item.rate),
        "amount": str(item.amount),
        "tax_rate_percent": str(item.tax_rate_percent),
        "tax_amount": str(item.tax_amount),
        "total_amount": str(item.total_amount),
        "sort_order": item.sort_order,
        "version": item.version,
    }


class EstimationSummaryView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("estimation.dashboard.read")
        company = self.tenant_context.company
        estimates = Estimate.objects.filter(company=company, archived_at__isnull=True)
        versions = EstimateVersion.objects.filter(company=company)
        totals = versions.filter(baselined_at__isnull=False).aggregate(total=Sum("grand_total"))
        return Response(
            {
                "estimates": estimates.count(),
                "versions": versions.count(),
                "baselined_versions": versions.filter(baselined_at__isnull=False).count(),
                "baselined_value": str(totals["total"] or 0),
                "currency": company.currency,
                "stages": list(
                    versions.values("stage__code", "stage__name").annotate(count=Count("id"))
                ),
            }
        )


class EstimateListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("estimation.estimate.read")
        queryset = Estimate.objects.select_related("project").filter(
            company=self.tenant_context.company,
            archived_at__isnull=True,
        )
        project_id = request.query_params.get("project_public_id", "").strip()
        if project_id:
            queryset = queryset.filter(project__public_id=project_id)
        items = queryset.order_by("-created_at")[: _limit(request)]
        return Response({"items": [_estimate(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("estimation.estimate.manage")
        serializer = EstimateCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            estimate, version = create_estimate(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        response = _estimate(estimate)
        response["active_version"] = _version(version)
        return Response(response, status=201)


class EstimateDetailView(TenantScopedAPIView):
    def get(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("estimation.estimate.read")
        estimate = Estimate.objects.select_related("project").filter(
            company=self.tenant_context.company,
            public_id=public_id,
        ).first()
        if estimate is None:
            raise NotFound("Resource not found")
        return Response(_estimate(estimate))


class EstimateVersionListCreateView(TenantScopedAPIView):
    def get(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("estimation.version.read")
        versions = EstimateVersion.objects.select_related("estimate", "stage").filter(
            company=self.tenant_context.company,
            estimate__public_id=public_id,
        ).order_by("-version_number")
        return Response({"items": [_version(item) for item in versions]})

    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("estimation.version.manage")
        serializer = EstimateVersionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            version = create_estimate_version(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                estimate_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_version(version), status=201)


class EstimateVersionTransitionView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("estimation.version.transition")
        serializer = EstimateTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            version = transition_estimate_version(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                version_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_version(version))


class EstimateVersionBaselineView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("estimation.version.baseline")
        serializer = EstimateBaselineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            baseline = baseline_estimate_version(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                version_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(
            {
                "public_id": str(baseline.public_id),
                "estimate_public_id": str(baseline.estimate.public_id),
                "estimate_version_public_id": str(baseline.estimate_version.public_id),
                "created_at": baseline.created_at,
            },
            status=201,
        )


class BoqSectionListCreateView(TenantScopedAPIView):
    def get(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("estimation.boq.read")
        sections = BoqSection.objects.select_related("estimate_version").filter(
            company=self.tenant_context.company,
            estimate_version__public_id=public_id,
        ).order_by("sort_order", "code")
        return Response({"items": [_section(item) for item in sections]})

    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("estimation.boq.manage")
        serializer = BoqSectionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            section = create_section(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                version_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_section(section), status=201)


class BoqItemListCreateView(TenantScopedAPIView):
    def get(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("estimation.boq.read")
        items = BoqItem.objects.select_related("estimate_version", "section").filter(
            company=self.tenant_context.company,
            estimate_version__public_id=public_id,
        ).order_by("sort_order", "item_code")
        return Response({"items": [_item(item) for item in items]})

    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("estimation.boq.manage")
        serializer = BoqItemCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_boq_item(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                version_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_item(item), status=201)


class EstimateBaselineListView(TenantScopedAPIView):
    def get(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("estimation.estimate.read")
        items = EstimateBaseline.objects.select_related("estimate_version").filter(
            company=self.tenant_context.company,
            estimate__public_id=public_id,
        ).order_by("-created_at")
        return Response(
            {
                "items": [
                    {
                        "public_id": str(item.public_id),
                        "estimate_version_public_id": str(item.estimate_version.public_id),
                        "version_number": item.estimate_version.version_number,
                        "created_at": item.created_at,
                    }
                    for item in items
                ]
            }
        )
