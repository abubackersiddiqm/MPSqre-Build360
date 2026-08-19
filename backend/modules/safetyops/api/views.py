from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework import status
from rest_framework.exceptions import ValidationError as ApiValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.platform.audit import request_metadata
from modules.safetyops.api.serializers import (
    CorrectiveActionCreateSerializer,
    CorrectiveActionSerializer,
    PermitToWorkCreateSerializer,
    PermitToWorkSerializer,
    SafetyApprovalDecisionSerializer,
    SafetyApprovalRequestSerializer,
    SafetyApprovalSerializer,
    SafetyIncidentCreateSerializer,
    SafetyIncidentSerializer,
    SafetyInspectionCreateSerializer,
    SafetyInspectionSerializer,
    SafetyObservationCreateSerializer,
    SafetyObservationSerializer,
    SafetyPolicySerializer,
    SafetyRiskCreateSerializer,
    SafetyRiskResolutionSerializer,
    SafetyRiskSerializer,
    ToolboxTalkCreateSerializer,
    ToolboxTalkSerializer,
    TransitionSerializer,
)
from modules.safetyops.application.selectors import safety_overview
from modules.safetyops.application.services import (
    RequestEvidence,
    create_action,
    create_observation,
    create_permit,
    create_policy,
    create_risk,
    decide_approval,
    record_inspection,
    record_toolbox_talk,
    report_incident,
    request_approval,
    resolve_risk,
    transition_action,
    transition_incident,
    transition_observation,
    transition_permit,
)
from modules.safetyops.models import (
    CorrectiveAction,
    PermitToWork,
    SafetyApproval,
    SafetyIncident,
    SafetyInspection,
    SafetyObservation,
    SafetyPolicyVersion,
    SafetyRisk,
    ToolboxTalk,
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
        raise ApiValidationError({"code": "A record with this tenant code already exists"}) from exc
    raise exc


class SafetyOverviewView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("safety.view")
        return Response(safety_overview(self.tenant_context.company))


class SafetyPolicyListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("safety.view")
        items = SafetyPolicyVersion.objects.filter(
            company=self.tenant_context.company
        ).order_by("code", "-version")[:200]
        return Response(SafetyPolicySerializer(items, many=True).data)

    def post(self, request: Request) -> Response:
        serializer = SafetyPolicySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_policy(
                context=self.tenant_context,
                evidence=_evidence(request),
                attributes=dict(serializer.validated_data),
            )
        except (DjangoValidationError, IntegrityError) as exc:
            _raise_domain(exc)
        return Response(SafetyPolicySerializer(item).data, status=status.HTTP_201_CREATED)


class SafetyObservationListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("safety.view")
        items = SafetyObservation.objects.filter(
            company=self.tenant_context.company
        ).select_related("policy")
        if value := request.query_params.get("status_code"):
            items = items.filter(status_code=value.upper())
        if value := request.query_params.get("severity_code"):
            items = items.filter(severity_code=value.upper())
        return Response(
            SafetyObservationSerializer(items.order_by("-observed_at")[:200], many=True).data
        )

    def post(self, request: Request) -> Response:
        serializer = SafetyObservationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        policy_id = data.pop("policy_public_id")
        try:
            item = create_observation(
                context=self.tenant_context,
                evidence=_evidence(request),
                policy_public_id=policy_id,
                attributes=data,
            )
        except (DjangoValidationError, IntegrityError) as exc:
            _raise_domain(exc)
        return Response(SafetyObservationSerializer(item).data, status=status.HTTP_201_CREATED)


class SafetyObservationTransitionView(TenantScopedAPIView):
    def post(self, request: Request, observation_id) -> Response:
        serializer = TransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_observation(
                context=self.tenant_context,
                evidence=_evidence(request),
                observation_public_id=observation_id,
                target_status_code=serializer.validated_data["target_status_code"],
                expected_version=serializer.validated_data.get("expected_version"),
                closure_note=serializer.validated_data.get("closure_note", ""),
            )
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(SafetyObservationSerializer(item).data)


class SafetyIncidentListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("safety.view")
        items = SafetyIncident.objects.filter(
            company=self.tenant_context.company
        ).select_related("policy")
        if value := request.query_params.get("status_code"):
            items = items.filter(status_code=value.upper())
        if value := request.query_params.get("severity_code"):
            items = items.filter(severity_code=value.upper())
        return Response(
            SafetyIncidentSerializer(items.order_by("-reported_at")[:200], many=True).data
        )

    def post(self, request: Request) -> Response:
        serializer = SafetyIncidentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        policy_id = data.pop("policy_public_id")
        try:
            item = report_incident(
                context=self.tenant_context,
                evidence=_evidence(request),
                policy_public_id=policy_id,
                attributes=data,
            )
        except (DjangoValidationError, IntegrityError) as exc:
            _raise_domain(exc)
        return Response(SafetyIncidentSerializer(item).data, status=status.HTTP_201_CREATED)


class SafetyIncidentTransitionView(TenantScopedAPIView):
    def post(self, request: Request, incident_id) -> Response:
        serializer = TransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_incident(
                context=self.tenant_context,
                evidence=_evidence(request),
                incident_public_id=incident_id,
                target_status_code=serializer.validated_data["target_status_code"],
                expected_version=serializer.validated_data.get("expected_version"),
                root_cause=serializer.validated_data.get("root_cause", ""),
            )
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(SafetyIncidentSerializer(item).data)


class PermitToWorkListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("safety.view")
        items = PermitToWork.objects.filter(
            company=self.tenant_context.company
        ).select_related("policy")
        if value := request.query_params.get("status_code"):
            items = items.filter(status_code=value.upper())
        if value := request.query_params.get("permit_type_code"):
            items = items.filter(permit_type_code=value.upper())
        return Response(
            PermitToWorkSerializer(items.order_by("valid_until")[:200], many=True).data
        )

    def post(self, request: Request) -> Response:
        serializer = PermitToWorkCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        policy_id = data.pop("policy_public_id")
        try:
            item = create_permit(
                context=self.tenant_context,
                evidence=_evidence(request),
                policy_public_id=policy_id,
                attributes=data,
            )
        except (DjangoValidationError, IntegrityError) as exc:
            _raise_domain(exc)
        return Response(PermitToWorkSerializer(item).data, status=status.HTTP_201_CREATED)


class PermitToWorkTransitionView(TenantScopedAPIView):
    def post(self, request: Request, permit_id) -> Response:
        serializer = TransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_permit(
                context=self.tenant_context,
                evidence=_evidence(request),
                permit_public_id=permit_id,
                target_status_code=serializer.validated_data["target_status_code"],
                expected_version=serializer.validated_data.get("expected_version"),
            )
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(PermitToWorkSerializer(item).data)


class SafetyInspectionListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("safety.view")
        items = SafetyInspection.objects.filter(
            company=self.tenant_context.company
        ).select_related("policy")
        if value := request.query_params.get("status_code"):
            items = items.filter(status_code=value.upper())
        if value := request.query_params.get("result_code"):
            items = items.filter(result_code=value.upper())
        return Response(
            SafetyInspectionSerializer(items.order_by("-scheduled_at")[:200], many=True).data
        )

    def post(self, request: Request) -> Response:
        serializer = SafetyInspectionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        policy_id = data.pop("policy_public_id")
        try:
            item = record_inspection(
                context=self.tenant_context,
                evidence=_evidence(request),
                policy_public_id=policy_id,
                attributes=data,
            )
        except (DjangoValidationError, IntegrityError) as exc:
            _raise_domain(exc)
        return Response(SafetyInspectionSerializer(item).data, status=status.HTTP_201_CREATED)


class ToolboxTalkListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("safety.view")
        items = ToolboxTalk.objects.filter(
            company=self.tenant_context.company
        ).select_related("policy")
        if value := request.query_params.get("topic_code"):
            items = items.filter(topic_code=value.upper())
        return Response(
            ToolboxTalkSerializer(items.order_by("-delivered_at")[:200], many=True).data
        )

    def post(self, request: Request) -> Response:
        serializer = ToolboxTalkCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        policy_id = data.pop("policy_public_id")
        try:
            item = record_toolbox_talk(
                context=self.tenant_context,
                evidence=_evidence(request),
                policy_public_id=policy_id,
                attributes=data,
            )
        except (DjangoValidationError, IntegrityError) as exc:
            _raise_domain(exc)
        return Response(ToolboxTalkSerializer(item).data, status=status.HTTP_201_CREATED)


class CorrectiveActionListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("safety.view")
        items = CorrectiveAction.objects.filter(
            company=self.tenant_context.company
        ).select_related("policy")
        if value := request.query_params.get("status_code"):
            items = items.filter(status_code=value.upper())
        if value := request.query_params.get("priority_code"):
            items = items.filter(priority_code=value.upper())
        return Response(
            CorrectiveActionSerializer(items.order_by("due_at", "-created_at")[:200], many=True).data
        )

    def post(self, request: Request) -> Response:
        serializer = CorrectiveActionCreateSerializer(data=request.data)
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
        return Response(CorrectiveActionSerializer(item).data, status=status.HTTP_201_CREATED)


class CorrectiveActionTransitionView(TenantScopedAPIView):
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
        return Response(CorrectiveActionSerializer(item).data)


class SafetyApprovalListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("safety.view")
        items = SafetyApproval.objects.filter(
            company=self.tenant_context.company
        ).select_related("policy")
        if request.query_params.get("pending") == "true":
            items = items.filter(decided_at__isnull=True)
        return Response(
            SafetyApprovalSerializer(items.order_by("due_at", "-requested_at")[:200], many=True).data
        )

    def post(self, request: Request) -> Response:
        serializer = SafetyApprovalRequestSerializer(data=request.data)
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
        return Response(SafetyApprovalSerializer(item).data, status=status.HTTP_201_CREATED)


class SafetyApprovalDecisionView(TenantScopedAPIView):
    def post(self, request: Request, approval_id) -> Response:
        serializer = SafetyApprovalDecisionSerializer(data=request.data)
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
        return Response(SafetyApprovalSerializer(item).data)


class SafetyRiskListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("safety.view")
        items = SafetyRisk.objects.filter(
            company=self.tenant_context.company
        ).select_related("policy")
        if request.query_params.get("open") == "true":
            items = items.filter(resolved_at__isnull=True)
        return Response(
            SafetyRiskSerializer(items.order_by("due_at", "-created_at")[:200], many=True).data
        )

    def post(self, request: Request) -> Response:
        serializer = SafetyRiskCreateSerializer(data=request.data)
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
        return Response(SafetyRiskSerializer(item).data, status=status.HTTP_201_CREATED)


class SafetyRiskResolveView(TenantScopedAPIView):
    def post(self, request: Request, risk_id) -> Response:
        serializer = SafetyRiskResolutionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = resolve_risk(
                context=self.tenant_context,
                evidence=_evidence(request),
                risk_public_id=risk_id,
                resolution_note=serializer.validated_data["resolution_note"],
            )
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(SafetyRiskSerializer(item).data)
