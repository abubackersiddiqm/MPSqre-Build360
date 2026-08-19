from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework import status
from rest_framework.exceptions import ValidationError as ApiValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.platform.audit import request_metadata
from modules.qualityops.api.serializers import (
    InspectionTestPlanCreateSerializer,
    InspectionTestPlanSerializer,
    NonConformanceReportCreateSerializer,
    NonConformanceReportSerializer,
    QualityApprovalDecisionSerializer,
    QualityApprovalRequestSerializer,
    QualityApprovalSerializer,
    QualityCorrectiveActionCreateSerializer,
    QualityCorrectiveActionSerializer,
    QualityInspectionCreateSerializer,
    QualityInspectionRequestCreateSerializer,
    QualityInspectionRequestSerializer,
    QualityInspectionSerializer,
    QualityPolicySerializer,
    QualityRiskCreateSerializer,
    QualityRiskResolutionSerializer,
    QualityRiskSerializer,
    QualityTestResultCreateSerializer,
    QualityTestResultSerializer,
    TransitionSerializer,
)
from modules.qualityops.application.selectors import quality_overview
from modules.qualityops.application.services import (
    RequestEvidence,
    create_action,
    create_inspection_request,
    create_itp,
    create_ncr,
    create_policy,
    create_risk,
    decide_approval,
    record_inspection,
    record_test_result,
    request_approval,
    resolve_risk,
    transition_action,
    transition_inspection_request,
    transition_itp,
    transition_ncr,
)
from modules.qualityops.models import (
    InspectionTestPlan,
    NonConformanceReport,
    QualityApproval,
    QualityCorrectiveAction,
    QualityInspection,
    QualityInspectionRequest,
    QualityPolicyVersion,
    QualityRisk,
    QualityTestResult,
)
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


def _raise_domain(exc: Exception) -> None:
    if isinstance(exc, DjangoValidationError):
        raise _api_validation(exc) from exc
    if isinstance(exc, IntegrityError):
        raise ApiValidationError(
            {"code": "A quality record with this tenant code already exists"}
        ) from exc
    raise exc


class QualityOverviewView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("quality.view")
        return Response(quality_overview(self.tenant_context.company))


class QualityPolicyListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("quality.view")
        items = QualityPolicyVersion.objects.filter(
            company=self.tenant_context.company
        ).order_by("code", "-version")[:200]
        return Response(QualityPolicySerializer(items, many=True).data)

    def post(self, request: Request) -> Response:
        serializer = QualityPolicySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_policy(
                context=self.tenant_context,
                evidence=_evidence(request),
                attributes=dict(serializer.validated_data),
            )
        except (DjangoValidationError, IntegrityError) as exc:
            _raise_domain(exc)
        return Response(QualityPolicySerializer(item).data, status=status.HTTP_201_CREATED)


class InspectionTestPlanListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("quality.view")
        items = InspectionTestPlan.objects.filter(
            company=self.tenant_context.company
        ).select_related("policy")
        if value := request.query_params.get("status_code"):
            items = items.filter(status_code=value.upper())
        if value := request.query_params.get("discipline_code"):
            items = items.filter(discipline_code=value.upper())
        return Response(
            InspectionTestPlanSerializer(
                items.order_by("discipline_code", "itp_code", "-revision")[:200],
                many=True,
            ).data
        )

    def post(self, request: Request) -> Response:
        serializer = InspectionTestPlanCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        policy_id = data.pop("policy_public_id")
        try:
            item = create_itp(
                context=self.tenant_context,
                evidence=_evidence(request),
                policy_public_id=policy_id,
                attributes=data,
            )
        except (DjangoValidationError, IntegrityError) as exc:
            _raise_domain(exc)
        return Response(InspectionTestPlanSerializer(item).data, status=status.HTTP_201_CREATED)


class InspectionTestPlanTransitionView(TenantScopedAPIView):
    def post(self, request: Request, itp_id) -> Response:
        serializer = TransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_itp(
                context=self.tenant_context,
                evidence=_evidence(request),
                itp_public_id=itp_id,
                target_status_code=serializer.validated_data["target_status_code"],
                expected_version=serializer.validated_data.get("expected_version"),
            )
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(InspectionTestPlanSerializer(item).data)


class QualityInspectionRequestListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("quality.view")
        items = QualityInspectionRequest.objects.filter(
            company=self.tenant_context.company
        ).select_related("policy", "itp")
        if value := request.query_params.get("status_code"):
            items = items.filter(status_code=value.upper())
        if value := request.query_params.get("request_type_code"):
            items = items.filter(request_type_code=value.upper())
        return Response(
            QualityInspectionRequestSerializer(
                items.order_by("requested_for")[:200], many=True
            ).data
        )

    def post(self, request: Request) -> Response:
        serializer = QualityInspectionRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        policy_id = data.pop("policy_public_id")
        itp_id = data.pop("itp_public_id", None)
        try:
            item = create_inspection_request(
                context=self.tenant_context,
                evidence=_evidence(request),
                policy_public_id=policy_id,
                itp_public_id=itp_id,
                attributes=data,
            )
        except (DjangoValidationError, IntegrityError) as exc:
            _raise_domain(exc)
        return Response(
            QualityInspectionRequestSerializer(item).data,
            status=status.HTTP_201_CREATED,
        )


class QualityInspectionRequestTransitionView(TenantScopedAPIView):
    def post(self, request: Request, inspection_request_id) -> Response:
        serializer = TransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_inspection_request(
                context=self.tenant_context,
                evidence=_evidence(request),
                request_public_id=inspection_request_id,
                target_status_code=serializer.validated_data["target_status_code"],
                expected_version=serializer.validated_data.get("expected_version"),
                closure_note=serializer.validated_data.get("closure_note", ""),
            )
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(QualityInspectionRequestSerializer(item).data)


class QualityInspectionListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("quality.view")
        items = QualityInspection.objects.filter(
            company=self.tenant_context.company
        ).select_related("policy", "request")
        if value := request.query_params.get("status_code"):
            items = items.filter(status_code=value.upper())
        if value := request.query_params.get("result_code"):
            items = items.filter(result_code=value.upper())
        return Response(
            QualityInspectionSerializer(
                items.order_by("-scheduled_at")[:200], many=True
            ).data
        )

    def post(self, request: Request) -> Response:
        serializer = QualityInspectionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        policy_id = data.pop("policy_public_id")
        request_id = data.pop("request_public_id", None)
        try:
            item = record_inspection(
                context=self.tenant_context,
                evidence=_evidence(request),
                policy_public_id=policy_id,
                request_public_id=request_id,
                attributes=data,
            )
        except (DjangoValidationError, IntegrityError) as exc:
            _raise_domain(exc)
        return Response(QualityInspectionSerializer(item).data, status=status.HTTP_201_CREATED)


class QualityTestResultListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("quality.view")
        items = QualityTestResult.objects.filter(
            company=self.tenant_context.company
        ).select_related("policy", "inspection")
        if value := request.query_params.get("result_code"):
            items = items.filter(result_code=value.upper())
        if value := request.query_params.get("test_type_code"):
            items = items.filter(test_type_code=value.upper())
        return Response(
            QualityTestResultSerializer(items.order_by("-tested_at")[:200], many=True).data
        )

    def post(self, request: Request) -> Response:
        serializer = QualityTestResultCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        policy_id = data.pop("policy_public_id")
        inspection_id = data.pop("inspection_public_id", None)
        try:
            item = record_test_result(
                context=self.tenant_context,
                evidence=_evidence(request),
                policy_public_id=policy_id,
                inspection_public_id=inspection_id,
                attributes=data,
            )
        except (DjangoValidationError, IntegrityError) as exc:
            _raise_domain(exc)
        return Response(QualityTestResultSerializer(item).data, status=status.HTTP_201_CREATED)


class NonConformanceReportListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("quality.view")
        items = NonConformanceReport.objects.filter(
            company=self.tenant_context.company
        ).select_related("policy")
        if value := request.query_params.get("status_code"):
            items = items.filter(status_code=value.upper())
        if value := request.query_params.get("severity_code"):
            items = items.filter(severity_code=value.upper())
        return Response(
            NonConformanceReportSerializer(
                items.order_by("due_at", "-detected_at")[:200], many=True
            ).data
        )

    def post(self, request: Request) -> Response:
        serializer = NonConformanceReportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        policy_id = data.pop("policy_public_id")
        try:
            item = create_ncr(
                context=self.tenant_context,
                evidence=_evidence(request),
                policy_public_id=policy_id,
                attributes=data,
            )
        except (DjangoValidationError, IntegrityError) as exc:
            _raise_domain(exc)
        return Response(
            NonConformanceReportSerializer(item).data, status=status.HTTP_201_CREATED
        )


class NonConformanceReportTransitionView(TenantScopedAPIView):
    def post(self, request: Request, ncr_id) -> Response:
        serializer = TransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_ncr(
                context=self.tenant_context,
                evidence=_evidence(request),
                ncr_public_id=ncr_id,
                target_status_code=serializer.validated_data["target_status_code"],
                expected_version=serializer.validated_data.get("expected_version"),
                root_cause=serializer.validated_data.get("root_cause", ""),
                disposition_code=serializer.validated_data.get("disposition_code", ""),
                closure_note=serializer.validated_data.get("closure_note", ""),
            )
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(NonConformanceReportSerializer(item).data)


class QualityCorrectiveActionListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("quality.view")
        items = QualityCorrectiveAction.objects.filter(
            company=self.tenant_context.company
        ).select_related("policy")
        if value := request.query_params.get("status_code"):
            items = items.filter(status_code=value.upper())
        if value := request.query_params.get("priority_code"):
            items = items.filter(priority_code=value.upper())
        return Response(
            QualityCorrectiveActionSerializer(
                items.order_by("due_at", "-created_at")[:200], many=True
            ).data
        )

    def post(self, request: Request) -> Response:
        serializer = QualityCorrectiveActionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        policy_id = data.pop("policy_public_id")
        try:
            item = create_action(
                context=self.tenant_context,
                evidence=_evidence(request),
                policy_public_id=policy_id,
                attributes=data,
            )
        except (DjangoValidationError, IntegrityError) as exc:
            _raise_domain(exc)
        return Response(
            QualityCorrectiveActionSerializer(item).data,
            status=status.HTTP_201_CREATED,
        )


class QualityCorrectiveActionTransitionView(TenantScopedAPIView):
    def post(self, request: Request, action_id) -> Response:
        serializer = TransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_action(
                context=self.tenant_context,
                evidence=_evidence(request),
                action_public_id=action_id,
                target_status_code=serializer.validated_data["target_status_code"],
                expected_version=serializer.validated_data.get("expected_version"),
                closure_note=serializer.validated_data.get("closure_note", ""),
            )
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(QualityCorrectiveActionSerializer(item).data)


class QualityApprovalListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("quality.view")
        items = QualityApproval.objects.filter(
            company=self.tenant_context.company
        ).select_related("policy")
        if request.query_params.get("pending") == "true":
            items = items.filter(decided_at__isnull=True)
        return Response(
            QualityApprovalSerializer(
                items.order_by("due_at", "-requested_at")[:200], many=True
            ).data
        )

    def post(self, request: Request) -> Response:
        serializer = QualityApprovalRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        policy_id = data.pop("policy_public_id")
        try:
            item = request_approval(
                context=self.tenant_context,
                evidence=_evidence(request),
                policy_public_id=policy_id,
                attributes=data,
            )
        except (DjangoValidationError, IntegrityError) as exc:
            _raise_domain(exc)
        return Response(QualityApprovalSerializer(item).data, status=status.HTTP_201_CREATED)


class QualityApprovalDecisionView(TenantScopedAPIView):
    def post(self, request: Request, approval_id) -> Response:
        serializer = QualityApprovalDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = decide_approval(
                context=self.tenant_context,
                evidence=_evidence(request),
                approval_public_id=approval_id,
                decision_code=serializer.validated_data["decision_code"],
                decision_note=serializer.validated_data.get("decision_note", ""),
                expected_version=serializer.validated_data.get("expected_version"),
            )
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(QualityApprovalSerializer(item).data)


class QualityRiskListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("quality.view")
        items = QualityRisk.objects.filter(
            company=self.tenant_context.company
        ).select_related("policy")
        if request.query_params.get("open") == "true":
            items = items.filter(resolved_at__isnull=True)
        return Response(
            QualityRiskSerializer(items.order_by("due_at", "-created_at")[:200], many=True).data
        )

    def post(self, request: Request) -> Response:
        serializer = QualityRiskCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        policy_id = data.pop("policy_public_id")
        try:
            item = create_risk(
                context=self.tenant_context,
                evidence=_evidence(request),
                policy_public_id=policy_id,
                attributes=data,
            )
        except (DjangoValidationError, IntegrityError) as exc:
            _raise_domain(exc)
        return Response(QualityRiskSerializer(item).data, status=status.HTTP_201_CREATED)


class QualityRiskResolveView(TenantScopedAPIView):
    def post(self, request: Request, risk_id) -> Response:
        serializer = QualityRiskResolutionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = resolve_risk(
                context=self.tenant_context,
                evidence=_evidence(request),
                risk_public_id=risk_id,
                resolution_note=serializer.validated_data["resolution_note"],
                expected_version=serializer.validated_data.get("expected_version"),
            )
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(QualityRiskSerializer(item).data)
