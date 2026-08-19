from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework import status
from rest_framework.exceptions import ValidationError as ApiValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.documentops.api.serializers import (
    AcknowledgeDistributionSerializer,
    ApprovalDecisionSerializer,
    ControlledDocumentCreateSerializer,
    ControlledDocumentSerializer,
    DocumentApprovalCreateSerializer,
    DocumentApprovalSerializer,
    DocumentControlPolicySerializer,
    DocumentDistributionCreateSerializer,
    DocumentDistributionSerializer,
    DocumentRevisionCreateSerializer,
    DocumentRevisionSerializer,
    DocumentRiskCreateSerializer,
    DocumentRiskSerializer,
    DocumentTransmittalCreateSerializer,
    DocumentTransmittalSerializer,
    RequestForInformationCreateSerializer,
    RequestForInformationSerializer,
    ResolveRiskSerializer,
    TechnicalSubmittalCreateSerializer,
    TechnicalSubmittalSerializer,
    TransitionSerializer,
)
from modules.documentops.application.selectors import document_control_overview
from modules.documentops.application.services import (
    RequestEvidence,
    acknowledge_distribution,
    create_document,
    create_policy,
    create_revision,
    create_rfi,
    create_risk,
    create_submittal,
    create_transmittal,
    decide_approval,
    record_distribution,
    request_approval,
    resolve_risk,
    transition_document,
    transition_revision,
    transition_rfi,
    transition_submittal,
    transition_transmittal,
)
from modules.documentops.models import (
    ControlledDocument,
    DocumentApproval,
    DocumentControlPolicyVersion,
    DocumentDistribution,
    DocumentRevision,
    DocumentRisk,
    DocumentTransmittal,
    RequestForInformation,
    TechnicalSubmittal,
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


def _raise_domain(exc: Exception) -> None:
    if isinstance(exc, DjangoValidationError):
        raise _api_validation(exc) from exc
    if isinstance(exc, IntegrityError):
        raise ApiValidationError(
            {"code": "A document-control record with this tenant code already exists"}
        ) from exc
    raise exc


class DocumentControlOverviewView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("document.view")
        return Response(document_control_overview(self.tenant_context.company))


class DocumentControlPolicyListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("document.view")
        items = DocumentControlPolicyVersion.objects.filter(
            company=self.tenant_context.company
        ).order_by("code", "-version")[:200]
        return Response(DocumentControlPolicySerializer(items, many=True).data)

    def post(self, request: Request) -> Response:
        serializer = DocumentControlPolicySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_policy(
                context=self.tenant_context,
                evidence=_evidence(request),
                attributes=dict(serializer.validated_data),
            )
        except (DjangoValidationError, IntegrityError) as exc:
            _raise_domain(exc)
        return Response(
            DocumentControlPolicySerializer(item).data,
            status=status.HTTP_201_CREATED,
        )


class ControlledDocumentListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("document.view")
        items = ControlledDocument.objects.filter(
            company=self.tenant_context.company
        ).select_related("policy")
        if value := request.query_params.get("status_code"):
            items = items.filter(status_code=value.upper())
        if value := request.query_params.get("discipline_code"):
            items = items.filter(discipline_code=value.upper())
        if value := request.query_params.get("document_type_code"):
            items = items.filter(document_type_code=value.upper())
        return Response(
            ControlledDocumentSerializer(
                items.order_by("discipline_code", "document_number")[:200], many=True
            ).data
        )

    def post(self, request: Request) -> Response:
        serializer = ControlledDocumentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        policy_id = data.pop("policy_public_id")
        try:
            item = create_document(
                context=self.tenant_context,
                evidence=_evidence(request),
                policy_public_id=policy_id,
                attributes=data,
            )
        except (DjangoValidationError, IntegrityError) as exc:
            _raise_domain(exc)
        return Response(
            ControlledDocumentSerializer(item).data, status=status.HTTP_201_CREATED
        )


class ControlledDocumentTransitionView(TenantScopedAPIView):
    def post(self, request: Request, document_id) -> Response:
        serializer = TransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_document(
                context=self.tenant_context,
                evidence=_evidence(request),
                document_public_id=document_id,
                target_status_code=serializer.validated_data["target_status_code"],
                expected_version=serializer.validated_data.get("expected_version"),
            )
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(ControlledDocumentSerializer(item).data)


class DocumentRevisionListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("document.view")
        items = DocumentRevision.objects.filter(
            company=self.tenant_context.company
        ).select_related("policy", "document")
        if value := request.query_params.get("status_code"):
            items = items.filter(status_code=value.upper())
        if value := request.query_params.get("document_public_id"):
            items = items.filter(document__public_id=value)
        return Response(
            DocumentRevisionSerializer(
                items.order_by("document__document_number", "-sequence_number")[:200],
                many=True,
            ).data
        )

    def post(self, request: Request) -> Response:
        serializer = DocumentRevisionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        policy_id = data.pop("policy_public_id")
        document_id = data.pop("document_public_id")
        try:
            item = create_revision(
                context=self.tenant_context,
                evidence=_evidence(request),
                policy_public_id=policy_id,
                document_public_id=document_id,
                attributes=data,
            )
        except (DjangoValidationError, IntegrityError) as exc:
            _raise_domain(exc)
        return Response(
            DocumentRevisionSerializer(item).data, status=status.HTTP_201_CREATED
        )


class DocumentRevisionTransitionView(TenantScopedAPIView):
    def post(self, request: Request, revision_id) -> Response:
        serializer = TransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_revision(
                context=self.tenant_context,
                evidence=_evidence(request),
                revision_public_id=revision_id,
                target_status_code=serializer.validated_data["target_status_code"],
                expected_version=serializer.validated_data.get("expected_version"),
            )
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(DocumentRevisionSerializer(item).data)


class DocumentTransmittalListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("document.view")
        items = DocumentTransmittal.objects.filter(
            company=self.tenant_context.company
        ).select_related("policy")
        if value := request.query_params.get("status_code"):
            items = items.filter(status_code=value.upper())
        if value := request.query_params.get("direction_code"):
            items = items.filter(direction_code=value.upper())
        return Response(
            DocumentTransmittalSerializer(
                items.order_by("due_at", "-created_at")[:200], many=True
            ).data
        )

    def post(self, request: Request) -> Response:
        serializer = DocumentTransmittalCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        policy_id = data.pop("policy_public_id")
        try:
            item = create_transmittal(
                context=self.tenant_context,
                evidence=_evidence(request),
                policy_public_id=policy_id,
                attributes=data,
            )
        except (DjangoValidationError, IntegrityError) as exc:
            _raise_domain(exc)
        return Response(
            DocumentTransmittalSerializer(item).data,
            status=status.HTTP_201_CREATED,
        )


class DocumentTransmittalTransitionView(TenantScopedAPIView):
    def post(self, request: Request, transmittal_id) -> Response:
        serializer = TransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_transmittal(
                context=self.tenant_context,
                evidence=_evidence(request),
                transmittal_public_id=transmittal_id,
                target_status_code=serializer.validated_data["target_status_code"],
                expected_version=serializer.validated_data.get("expected_version"),
            )
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(DocumentTransmittalSerializer(item).data)


class RequestForInformationListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("document.view")
        items = RequestForInformation.objects.filter(
            company=self.tenant_context.company
        ).select_related("policy")
        if value := request.query_params.get("status_code"):
            items = items.filter(status_code=value.upper())
        if value := request.query_params.get("priority_code"):
            items = items.filter(priority_code=value.upper())
        if value := request.query_params.get("discipline_code"):
            items = items.filter(discipline_code=value.upper())
        return Response(
            RequestForInformationSerializer(
                items.order_by("response_due_at", "-raised_at")[:200], many=True
            ).data
        )

    def post(self, request: Request) -> Response:
        serializer = RequestForInformationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        policy_id = data.pop("policy_public_id")
        try:
            item = create_rfi(
                context=self.tenant_context,
                evidence=_evidence(request),
                policy_public_id=policy_id,
                attributes=data,
            )
        except (DjangoValidationError, IntegrityError) as exc:
            _raise_domain(exc)
        return Response(
            RequestForInformationSerializer(item).data,
            status=status.HTTP_201_CREATED,
        )


class RequestForInformationTransitionView(TenantScopedAPIView):
    def post(self, request: Request, rfi_id) -> Response:
        serializer = TransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_rfi(
                context=self.tenant_context,
                evidence=_evidence(request),
                rfi_public_id=rfi_id,
                target_status_code=serializer.validated_data["target_status_code"],
                expected_version=serializer.validated_data.get("expected_version"),
                response_text=serializer.validated_data.get("response_text", ""),
            )
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(RequestForInformationSerializer(item).data)


class TechnicalSubmittalListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("document.view")
        items = TechnicalSubmittal.objects.filter(
            company=self.tenant_context.company
        ).select_related("policy")
        if value := request.query_params.get("status_code"):
            items = items.filter(status_code=value.upper())
        if value := request.query_params.get("category_code"):
            items = items.filter(category_code=value.upper())
        return Response(
            TechnicalSubmittalSerializer(
                items.order_by("review_due_at", "-submitted_at")[:200], many=True
            ).data
        )

    def post(self, request: Request) -> Response:
        serializer = TechnicalSubmittalCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        policy_id = data.pop("policy_public_id")
        try:
            item = create_submittal(
                context=self.tenant_context,
                evidence=_evidence(request),
                policy_public_id=policy_id,
                attributes=data,
            )
        except (DjangoValidationError, IntegrityError) as exc:
            _raise_domain(exc)
        return Response(
            TechnicalSubmittalSerializer(item).data,
            status=status.HTTP_201_CREATED,
        )


class TechnicalSubmittalTransitionView(TenantScopedAPIView):
    def post(self, request: Request, submittal_id) -> Response:
        serializer = TransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_submittal(
                context=self.tenant_context,
                evidence=_evidence(request),
                submittal_public_id=submittal_id,
                target_status_code=serializer.validated_data["target_status_code"],
                expected_version=serializer.validated_data.get("expected_version"),
                decision_code=serializer.validated_data.get("decision_code", ""),
                decision_note=serializer.validated_data.get("decision_note", ""),
            )
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(TechnicalSubmittalSerializer(item).data)


class DocumentApprovalListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("document.view")
        items = DocumentApproval.objects.filter(
            company=self.tenant_context.company
        ).select_related("policy")
        if value := request.query_params.get("status_code"):
            items = items.filter(status_code=value.upper())
        if value := request.query_params.get("entity_type_code"):
            items = items.filter(entity_type_code=value.upper())
        return Response(
            DocumentApprovalSerializer(
                items.order_by("due_at", "-requested_at")[:200], many=True
            ).data
        )

    def post(self, request: Request) -> Response:
        serializer = DocumentApprovalCreateSerializer(data=request.data)
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
        return Response(
            DocumentApprovalSerializer(item).data,
            status=status.HTTP_201_CREATED,
        )


class DocumentApprovalDecisionView(TenantScopedAPIView):
    def post(self, request: Request, approval_id) -> Response:
        serializer = ApprovalDecisionSerializer(data=request.data)
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
        return Response(DocumentApprovalSerializer(item).data)


class DocumentDistributionListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("document.view")
        items = DocumentDistribution.objects.filter(
            company=self.tenant_context.company
        ).select_related("policy", "revision", "revision__document")
        if value := request.query_params.get("status_code"):
            items = items.filter(status_code=value.upper())
        if value := request.query_params.get("recipient_type_code"):
            items = items.filter(recipient_type_code=value.upper())
        return Response(
            DocumentDistributionSerializer(
                items.order_by("-distributed_at")[:200], many=True
            ).data
        )

    def post(self, request: Request) -> Response:
        serializer = DocumentDistributionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        policy_id = data.pop("policy_public_id")
        revision_id = data.pop("revision_public_id")
        try:
            item = record_distribution(
                context=self.tenant_context,
                evidence=_evidence(request),
                policy_public_id=policy_id,
                revision_public_id=revision_id,
                attributes=data,
            )
        except (DjangoValidationError, IntegrityError) as exc:
            _raise_domain(exc)
        return Response(
            DocumentDistributionSerializer(item).data,
            status=status.HTTP_201_CREATED,
        )


class DocumentDistributionAcknowledgeView(TenantScopedAPIView):
    def post(self, request: Request, distribution_id) -> Response:
        serializer = AcknowledgeDistributionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = acknowledge_distribution(
                context=self.tenant_context,
                evidence=_evidence(request),
                distribution_public_id=distribution_id,
                expected_version=serializer.validated_data.get("expected_version"),
            )
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(DocumentDistributionSerializer(item).data)


class DocumentRiskListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("document.view")
        items = DocumentRisk.objects.filter(
            company=self.tenant_context.company
        ).select_related("policy")
        if value := request.query_params.get("status_code"):
            items = items.filter(status_code=value.upper())
        if value := request.query_params.get("severity_code"):
            items = items.filter(severity_code=value.upper())
        return Response(
            DocumentRiskSerializer(items.order_by("due_at", "-created_at")[:200], many=True).data
        )

    def post(self, request: Request) -> Response:
        serializer = DocumentRiskCreateSerializer(data=request.data)
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
        return Response(DocumentRiskSerializer(item).data, status=status.HTTP_201_CREATED)


class DocumentRiskResolveView(TenantScopedAPIView):
    def post(self, request: Request, risk_id) -> Response:
        serializer = ResolveRiskSerializer(data=request.data)
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
        return Response(DocumentRiskSerializer(item).data)
