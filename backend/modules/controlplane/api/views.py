from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.controlplane.api.serializers import (
    PlanCreateSerializer,
    SubscriptionAssignSerializer,
    SupportDecisionSerializer,
    SupportRequestCreateSerializer,
    TenantLifecycleSerializer,
)
from modules.controlplane.application.context import (
    PlatformScopedAPIView,
    platform_actor,
)
from modules.controlplane.application.services import (
    assign_subscription,
    collect_usage_snapshot,
    controlplane_summary,
    create_plan,
    create_support_access_request,
    current_subscription,
    decide_support_access_request,
    publish_plan,
    transition_tenant_lifecycle,
)
from modules.controlplane.models import (
    PlatformOperatorAssignment,
    SupportAccessRequest,
    TenantAccount,
    TenantUsageSnapshot,
)
from modules.platform.actors import request_actor
from modules.subscription.models import CompanySubscription, PlanVersion
from modules.tenant.api.base import TenantScopedAPIView


def _validation(exc: DjangoValidationError) -> ValidationError:
    return ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)


def _plan(item: PlanVersion) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "code": item.code,
        "version": item.version,
        "name": item.name,
        "status": item.status,
        "entitlements": item.entitlements,
        "limits": item.limits,
        "effective_from": item.effective_from,
        "effective_to": item.effective_to,
        "published_at": item.published_at,
    }


def _subscription(item: CompanySubscription | None) -> dict[str, object] | None:
    if item is None:
        return None
    return {
        "public_id": str(item.public_id),
        "company_public_id": str(item.company.public_id),
        "plan": _plan(item.plan_version),
        "status": item.status,
        "starts_at": item.starts_at,
        "ends_at": item.ends_at,
        "grace_until": item.grace_until,
    }


def _tenant(item: TenantAccount) -> dict[str, object]:
    subscription = current_subscription(item.company)
    latest_usage = item.usage_snapshots.order_by("-period_end").first()
    return {
        "public_id": str(item.public_id),
        "company": {
            "public_id": str(item.company.public_id),
            "code": item.company.code,
            "legal_name": item.company.legal_name,
            "display_name": item.company.display_name,
            "locale": item.company.locale,
            "timezone": item.company.timezone,
            "currency": item.company.currency,
            "is_active": item.company.is_active,
        },
        "lifecycle_status": item.lifecycle_status,
        "onboarding_status": item.onboarding_status,
        "segment_code": item.segment_code,
        "deployment_region": item.deployment_region,
        "data_residency": item.data_residency,
        "pilot_started_at": item.pilot_started_at,
        "activated_at": item.activated_at,
        "grace_until": item.grace_until,
        "suspended_at": item.suspended_at,
        "closed_at": item.closed_at,
        "lifecycle_reason": item.lifecycle_reason,
        "subscription": _subscription(subscription),
        "latest_usage": _usage(latest_usage) if latest_usage else None,
        "version": item.version,
    }


def _usage(item: TenantUsageSnapshot) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "tenant_public_id": str(item.tenant_account.public_id),
        "company": {
            "code": item.tenant_account.company.code,
            "display_name": item.tenant_account.company.display_name,
        },
        "period_start": item.period_start,
        "period_end": item.period_end,
        "metrics": item.metrics,
        "quota_status": item.quota_status,
        "checksum_sha256": item.checksum_sha256,
        "collected_at": item.collected_at,
    }


def _support(item: SupportAccessRequest) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "tenant": {
            "public_id": str(item.tenant_account.public_id),
            "company_code": item.tenant_account.company.code,
            "company_name": item.tenant_account.company.display_name,
        },
        "operator": {
            "assignment_public_id": str(item.operator_assignment.public_id),
            "email": item.operator_assignment.user.email,
            "display_name": item.operator_assignment.user.display_name,
        },
        "reason": item.reason,
        "scope_codes": item.scope_codes,
        "status": item.status,
        "requested_at": item.requested_at,
        "expires_at": item.expires_at,
        "decided_at": item.decided_at,
        "decision_reason": item.decision_reason,
        "version": item.version,
        "access_token_issued": False,
    }


class PlatformMeView(PlatformScopedAPIView):
    def get(self, request: Request) -> Response:
        roles = [assignment.role for assignment in self.platform_context.assignments]
        return Response(
            {
                "is_operator": True,
                "user": {
                    "public_id": str(self.platform_context.principal.user.public_id),
                    "email": self.platform_context.principal.user.email,
                    "display_name": self.platform_context.principal.user.display_name,
                },
                "roles": [
                    {"public_id": str(role.public_id), "code": role.code, "name": role.name}
                    for role in roles
                ],
                "permissions": sorted(self.platform_context.permission_codes),
            }
        )


class ControlplaneSummaryView(PlatformScopedAPIView):
    def get(self, request: Request) -> Response:
        self.platform_context.require("controlplane.dashboard.read")
        return Response(controlplane_summary())


class TenantListView(PlatformScopedAPIView):
    def get(self, request: Request) -> Response:
        self.platform_context.require("controlplane.tenant.read")
        items = (
            TenantAccount.objects.select_related("company")
            .prefetch_related("usage_snapshots")
            .all()[:250]
        )
        return Response({"items": [_tenant(item) for item in items]})


class TenantLifecycleView(PlatformScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.platform_context.require("controlplane.tenant.manage")
        serializer = TenantLifecycleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_tenant_lifecycle(
                tenant_public_id=public_id,
                actor=platform_actor(request, self.platform_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_tenant(item))


class PlanListCreateView(PlatformScopedAPIView):
    def get(self, request: Request) -> Response:
        self.platform_context.require("controlplane.plan.read")
        items = PlanVersion.objects.all().order_by("code", "-version")[:250]
        return Response({"items": [_plan(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.platform_context.require("controlplane.plan.manage")
        serializer = PlanCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_plan(
                actor=platform_actor(request, self.platform_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_plan(item), status=201)


class PlanPublishView(PlatformScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.platform_context.require("controlplane.plan.publish")
        try:
            item = publish_plan(
                plan_public_id=public_id,
                actor=platform_actor(request, self.platform_context),
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_plan(item))


class SubscriptionListView(PlatformScopedAPIView):
    def get(self, request: Request) -> Response:
        self.platform_context.require("controlplane.subscription.read")
        items = (
            CompanySubscription.objects.select_related("company", "plan_version")
            .order_by("-starts_at")[:500]
        )
        return Response({"items": [_subscription(item) for item in items]})


class SubscriptionAssignView(PlatformScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.platform_context.require("controlplane.subscription.manage")
        serializer = SubscriptionAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = assign_subscription(
                tenant_public_id=public_id,
                actor=platform_actor(request, self.platform_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_subscription(item), status=201)


class UsageListView(PlatformScopedAPIView):
    def get(self, request: Request) -> Response:
        self.platform_context.require("controlplane.usage.read")
        items = (
            TenantUsageSnapshot.objects.select_related("tenant_account__company")
            .all()[:500]
        )
        return Response({"items": [_usage(item) for item in items]})


class UsageCollectView(PlatformScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.platform_context.require("controlplane.usage.collect")
        try:
            item = collect_usage_snapshot(
                tenant_public_id=public_id,
                actor=platform_actor(request, self.platform_context),
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_usage(item), status=201)


class SupportRequestListCreateView(PlatformScopedAPIView):
    def get(self, request: Request) -> Response:
        self.platform_context.require("controlplane.support.read")
        items = (
            SupportAccessRequest.objects.select_related(
                "tenant_account__company",
                "operator_assignment__user",
            )
            .all()[:500]
        )
        return Response({"items": [_support(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.platform_context.require("controlplane.support.request")
        serializer = SupportRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        actor = platform_actor(request, self.platform_context)
        try:
            item = create_support_access_request(
                actor=actor,
                operator_assignment=self.platform_context.primary_assignment,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_support(item), status=201)


class OperatorListView(PlatformScopedAPIView):
    def get(self, request: Request) -> Response:
        self.platform_context.require("controlplane.operator.read")
        assignments = (
            PlatformOperatorAssignment.objects.select_related("user", "role")
            .all()[:250]
        )
        return Response(
            {
                "items": [
                    {
                        "public_id": str(item.public_id),
                        "user": {
                            "public_id": str(item.user.public_id),
                            "email": item.user.email,
                            "display_name": item.user.display_name,
                        },
                        "role": {
                            "public_id": str(item.role.public_id),
                            "code": item.role.code,
                            "name": item.role.name,
                        },
                        "effective_from": item.effective_from,
                        "effective_to": item.effective_to,
                        "suspended_at": item.suspended_at,
                    }
                    for item in assignments
                ]
            }
        )


class TenantSupportRequestListView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("controlplane.support.approve")
        items = (
            SupportAccessRequest.objects.select_related(
                "tenant_account__company",
                "operator_assignment__user",
            )
            .filter(tenant_account__company=self.tenant_context.company)[:200]
        )
        return Response({"items": [_support(item) for item in items]})


class TenantSupportRequestDecisionView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("controlplane.support.approve")
        serializer = SupportDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = decide_support_access_request(
                company=self.tenant_context.company,
                request_public_id=public_id,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_support(item))
