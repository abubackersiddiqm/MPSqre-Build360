from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.platform.actors import request_actor
from modules.tenant.api.base import TenantScopedAPIView
from modules.vendor.api.serializers import (
    SupplyStageCreateSerializer,
    VendorCreateSerializer,
    VendorQualifySerializer,
    VendorTransitionSerializer,
)
from modules.vendor.application.services import (
    available_transitions,
    create_vendor,
    qualify_vendor,
    transition_vendor,
)
from modules.vendor.models import SupplyStage, VendorProfile


def _validation(exc: DjangoValidationError) -> ValidationError:
    if hasattr(exc, "message_dict"):
        return ValidationError(exc.message_dict)
    return ValidationError(exc.messages)


def _stage(stage: SupplyStage) -> dict[str, object]:
    return {
        "public_id": str(stage.public_id),
        "entity_type": stage.entity_type,
        "code": stage.code,
        "name": stage.name,
        "outcome": stage.outcome,
        "sort_order": stage.sort_order,
        "allowed_next_codes": stage.allowed_next_codes,
        "is_initial": stage.is_initial,
        "is_active": stage.is_active,
    }


def _mask_email(value: str) -> str:
    if not value or "@" not in value:
        return ""
    local, domain = value.split("@", 1)
    visible = local[:2]
    return f"{visible}{'*' * max(len(local) - 2, 2)}@{domain}"


def _mask_phone(value: str) -> str:
    digits = "".join(character for character in value if character.isdigit())
    if not digits:
        return ""
    return f"{'*' * max(len(digits) - 4, 4)}{digits[-4:]}"


def _vendor(vendor: VendorProfile) -> dict[str, object]:
    return {
        "public_id": str(vendor.public_id),
        "code": vendor.code,
        "legal_name": vendor.legal_name,
        "display_name": vendor.display_name,
        "stage": _stage(vendor.stage),
        "available_transitions": [
            _stage(item) for item in available_transitions(vendor.stage)
        ],
        "categories": vendor.categories,
        "service_regions": vendor.service_regions,
        "tax_reference_masked": vendor.tax_reference_masked,
        "primary_contact_name": vendor.primary_contact_name,
        "primary_contact_email_masked": _mask_email(vendor.primary_contact_email),
        "primary_contact_phone_masked": _mask_phone(vendor.primary_contact_phone),
        "version": vendor.version,
        "qualified_at": vendor.qualified_at,
        "created_at": vendor.created_at,
    }


class SupplyStageListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("vendor.stage.read")
        queryset = SupplyStage.objects.filter(
            company=self.tenant_context.company,
            is_active=True,
            effective_from__lte=timezone.now(),
        ).filter(
            Q(effective_to__isnull=True) | Q(effective_to__gt=timezone.now())
        )
        entity_type = request.query_params.get("entity_type", "").strip()
        if entity_type:
            queryset = queryset.filter(entity_type=entity_type)
        return Response({"items": [_stage(item) for item in queryset]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("vendor.stage.manage")
        serializer = SupplyStageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        data.setdefault("effective_from", timezone.now())
        try:
            with transaction.atomic():
                if data.get("is_initial"):
                    SupplyStage.objects.filter(
                        company=self.tenant_context.company,
                        entity_type=data["entity_type"],
                        is_initial=True,
                    ).update(is_initial=False)
                stage = SupplyStage(
                    company=self.tenant_context.company,
                    **data,
                )
                stage.full_clean()
                stage.save()
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_stage(stage), status=201)


class VendorSummaryView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("vendor.dashboard.read")
        queryset = VendorProfile.objects.filter(
            company=self.tenant_context.company,
            retired_at__isnull=True,
        )
        return Response(
            {
                "vendors": queryset.count(),
                "qualified": queryset.filter(stage__code="qualified").count(),
                "pending": queryset.filter(
                    stage__code__in=["registered", "under_review"]
                ).count(),
                "suspended": queryset.filter(stage__code="suspended").count(),
                "by_stage": list(
                    queryset.values("stage__code", "stage__name").annotate(
                        count=Count("id")
                    )
                ),
            }
        )


class VendorListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("vendor.vendor.read")
        queryset = VendorProfile.objects.select_related("stage").filter(
            company=self.tenant_context.company,
            retired_at__isnull=True,
        )
        search = request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(code__icontains=search)
                | Q(display_name__icontains=search)
                | Q(legal_name__icontains=search)
            )
        items = queryset.order_by("display_name")[:200]
        return Response({"items": [_vendor(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("vendor.vendor.manage")
        serializer = VendorCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            vendor = create_vendor(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_vendor(vendor), status=201)


class VendorQualifyView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("vendor.qualification.decide")
        serializer = VendorQualifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            vendor = qualify_vendor(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                vendor_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_vendor(vendor))


class VendorTransitionView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("vendor.vendor.manage")
        serializer = VendorTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            vendor = transition_vendor(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                vendor_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_vendor(vendor))
