from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework import status
from rest_framework.exceptions import ValidationError as ApiValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.payrollops.api.serializers import (
    ApprovalDecisionSerializer,
    ApprovalRequestSerializer,
    ExceptionResolutionSerializer,
    PayrollLinesUpsertSerializer,
    PayrollPeriodCreateSerializer,
    PayrollPeriodSerializer,
    PayrollPolicySerializer,
    PayrollRunCreateSerializer,
    PayrollRunSerializer,
    PayrollRunTransitionSerializer,
)
from modules.payrollops.application.selectors import payroll_overview
from modules.payrollops.application.services import (
    RequestEvidence,
    create_period,
    create_policy,
    create_run,
    decide_approval,
    request_approval,
    resolve_exception,
    transition_run,
    upsert_run_lines,
)
from modules.payrollops.models import (
    PayrollApproval,
    PayrollException,
    PayrollPeriod,
    PayrollPolicyVersion,
    PayrollRun,
)
from modules.platform.audit import request_metadata
from modules.tenant.api.base import TenantScopedAPIView


def _evidence(request: Request) -> RequestEvidence:
    request_id, ip_address, user_agent = request_metadata(request._request)
    return RequestEvidence(
        request_id=request_id,
        correlation_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )


def _api_validation(exc: DjangoValidationError) -> ApiValidationError:
    if hasattr(exc, "message_dict"):
        return ApiValidationError(exc.message_dict)
    return ApiValidationError({"non_field_errors": list(exc.messages)})


class PayrollOverviewView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("payroll.view")
        return Response(payroll_overview(self.tenant_context.company))


class PayrollPolicyListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("payroll.view")
        items = PayrollPolicyVersion.objects.filter(
            company=self.tenant_context.company
        ).order_by("code", "-version")[:200]
        return Response(PayrollPolicySerializer(items, many=True).data)

    def post(self, request: Request) -> Response:
        self.tenant_context.require("payroll.configure")
        serializer = PayrollPolicySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            policy = create_policy(
                context=self.tenant_context,
                evidence=_evidence(request),
                attributes=dict(serializer.validated_data),
            )
        except IntegrityError as exc:
            raise ApiValidationError(
                {"code": "A policy with this company, code and version already exists"}
            ) from exc
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(PayrollPolicySerializer(policy).data, status=status.HTTP_201_CREATED)


class PayrollPeriodListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("payroll.view")
        items = PayrollPeriod.objects.filter(
            company=self.tenant_context.company
        ).order_by("-ends_on", "-created_at")[:100]
        return Response(PayrollPeriodSerializer(items, many=True).data)

    def post(self, request: Request) -> Response:
        serializer = PayrollPeriodCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            period = create_period(
                context=self.tenant_context,
                evidence=_evidence(request),
                **serializer.validated_data,
            )
        except IntegrityError as exc:
            raise ApiValidationError(
                {"code": "A payroll period with this code already exists"}
            ) from exc
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(PayrollPeriodSerializer(period).data, status=status.HTTP_201_CREATED)


class PayrollRunListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("payroll.view")
        items = (
            PayrollRun.objects.filter(company=self.tenant_context.company)
            .select_related("period", "policy")
            .order_by("-created_at")[:100]
        )
        return Response(PayrollRunSerializer(items, many=True).data)

    def post(self, request: Request) -> Response:
        serializer = PayrollRunCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            run = create_run(
                context=self.tenant_context,
                evidence=_evidence(request),
                **serializer.validated_data,
            )
        except IntegrityError as exc:
            raise ApiValidationError(
                {"run_number": "This run number already exists for the payroll period"}
            ) from exc
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(PayrollRunSerializer(run).data, status=status.HTTP_201_CREATED)


class PayrollRunTransitionView(TenantScopedAPIView):
    def post(self, request: Request, run_id: uuid.UUID) -> Response:
        serializer = PayrollRunTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            run = transition_run(
                context=self.tenant_context,
                evidence=_evidence(request),
                run_public_id=run_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(PayrollRunSerializer(run).data)


class PayrollRunLinesView(TenantScopedAPIView):
    def post(self, request: Request, run_id: uuid.UUID) -> Response:
        serializer = PayrollLinesUpsertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            run = upsert_run_lines(
                context=self.tenant_context,
                evidence=_evidence(request),
                run_public_id=run_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(PayrollRunSerializer(run).data)


class PayrollApprovalListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("payroll.view")
        items = (
            PayrollApproval.objects.filter(
                company=self.tenant_context.company,
                decided_at__isnull=True,
            )
            .select_related("run", "run__period")
            .order_by("due_at", "requested_at")[:100]
        )
        return Response(
            [
                {
                    "public_id": str(item.public_id),
                    "run_public_id": str(item.run.public_id),
                    "period_code": item.run.period.code,
                    "step_code": item.step_code,
                    "status_code": item.status_code,
                    "requested_from_membership_public_id": str(
                        item.requested_from_membership_public_id
                    ),
                    "requested_at": item.requested_at.isoformat(),
                    "due_at": item.due_at.isoformat() if item.due_at else None,
                }
                for item in items
            ]
        )

    def post(self, request: Request) -> Response:
        serializer = ApprovalRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            approval = request_approval(
                context=self.tenant_context,
                evidence=_evidence(request),
                **serializer.validated_data,
            )
        except IntegrityError as exc:
            raise ApiValidationError(
                {"step_code": "This approval step already exists for the run"}
            ) from exc
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(
            {"public_id": str(approval.public_id), "status_code": approval.status_code},
            status=status.HTTP_201_CREATED,
        )


class PayrollApprovalDecisionView(TenantScopedAPIView):
    def post(self, request: Request, approval_id: uuid.UUID) -> Response:
        serializer = ApprovalDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            approval = decide_approval(
                context=self.tenant_context,
                evidence=_evidence(request),
                approval_public_id=approval_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(
            {
                "public_id": str(approval.public_id),
                "status_code": approval.status_code,
                "decision_code": approval.decision_code,
                "decided_at": (
                    approval.decided_at.isoformat() if approval.decided_at else None
                ),
            }
        )


class PayrollExceptionListView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("payroll.view")
        items = (
            PayrollException.objects.filter(
                company=self.tenant_context.company,
                resolved_at__isnull=True,
            )
            .select_related("run", "run__period")
            .order_by("due_at", "-created_at")[:100]
        )
        return Response(
            [
                {
                    "public_id": str(item.public_id),
                    "run_public_id": str(item.run.public_id),
                    "period_code": item.run.period.code,
                    "employee_public_id": (
                        str(item.employee_public_id) if item.employee_public_id else None
                    ),
                    "exception_code": item.exception_code,
                    "severity_code": item.severity_code,
                    "status_code": item.status_code,
                    "message": item.message,
                    "due_at": item.due_at.isoformat() if item.due_at else None,
                    "created_at": item.created_at.isoformat(),
                }
                for item in items
            ]
        )


class PayrollExceptionResolveView(TenantScopedAPIView):
    def post(self, request: Request, exception_id: uuid.UUID) -> Response:
        serializer = ExceptionResolutionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            exception = resolve_exception(
                context=self.tenant_context,
                evidence=_evidence(request),
                exception_public_id=exception_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(
            {
                "public_id": str(exception.public_id),
                "status_code": exception.status_code,
                "resolved_at": (
                    exception.resolved_at.isoformat() if exception.resolved_at else None
                ),
            }
        )
