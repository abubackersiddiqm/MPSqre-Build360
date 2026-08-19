from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework import status
from rest_framework.exceptions import ValidationError as ApiValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.commercialops.api.serializers import (
    ApprovalDecisionSerializer,
    CommercialApprovalCreateSerializer,
    CommercialApprovalSerializer,
    CommercialClaimCreateSerializer,
    CommercialClaimSerializer,
    CommercialContractCreateSerializer,
    CommercialContractSerializer,
    CommercialPolicySerializer,
    CommercialRiskCreateSerializer,
    CommercialRiskSerializer,
    ContractMilestoneCreateSerializer,
    ContractMilestoneSerializer,
    ExtensionOfTimeCreateSerializer,
    ExtensionOfTimeSerializer,
    PaymentApplicationCreateSerializer,
    PaymentApplicationSerializer,
    ResolveRiskSerializer,
    TransitionSerializer,
    VariationOrderCreateSerializer,
    VariationOrderSerializer,
)
from modules.commercialops.application.selectors import commercial_overview
from modules.commercialops.application.services import (
    RequestEvidence,
    create_claim,
    create_contract,
    create_eot,
    create_milestone,
    create_payment,
    create_policy,
    create_risk,
    create_variation,
    decide_approval,
    request_approval,
    resolve_risk,
    transition_record,
)
from modules.commercialops.models import (
    CommercialApproval,
    CommercialClaim,
    CommercialContract,
    CommercialPolicyVersion,
    CommercialRisk,
    ContractMilestone,
    ExtensionOfTime,
    PaymentApplication,
    VariationOrder,
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
            {"code": "A commercial record with this tenant code already exists"}
        ) from exc
    raise exc


def _filters(queryset, request: Request, *fields: str):
    for field in fields:
        if value := request.query_params.get(field):
            queryset = queryset.filter(**{field: value.upper()})
    if contract_id := request.query_params.get("contract_public_id"):
        if any(field.name == "contract" for field in queryset.model._meta.fields):
            queryset = queryset.filter(contract__public_id=contract_id)
    return queryset


class CommercialOverviewView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("commercial.view")
        return Response(commercial_overview(self.tenant_context.company))


class CommercialPolicyListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("commercial.view")
        items = CommercialPolicyVersion.objects.filter(
            company=self.tenant_context.company
        ).order_by("code", "-version")[:200]
        return Response(CommercialPolicySerializer(items, many=True).data)

    def post(self, request: Request) -> Response:
        serializer = CommercialPolicySerializer(data=request.data)
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
            CommercialPolicySerializer(item).data,
            status=status.HTTP_201_CREATED,
        )


class CommercialContractListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("commercial.view")
        items = CommercialContract.objects.filter(
            company=self.tenant_context.company
        ).select_related("policy")
        items = _filters(items, request, "status_code", "contract_type_code")
        return Response(
            CommercialContractSerializer(
                items.order_by("planned_completion_date", "contract_number")[:200],
                many=True,
            ).data
        )

    def post(self, request: Request) -> Response:
        serializer = CommercialContractCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        policy_id = data.pop("policy_public_id")
        try:
            item = create_contract(
                context=self.tenant_context,
                evidence=_evidence(request),
                policy_public_id=policy_id,
                attributes=data,
            )
        except (DjangoValidationError, IntegrityError) as exc:
            _raise_domain(exc)
        return Response(
            CommercialContractSerializer(item).data,
            status=status.HTTP_201_CREATED,
        )


class ContractMilestoneListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("commercial.view")
        items = ContractMilestone.objects.filter(
            company=self.tenant_context.company
        ).select_related("policy", "contract")
        items = _filters(items, request, "status_code")
        return Response(
            ContractMilestoneSerializer(
                items.order_by("due_date", "milestone_number")[:200], many=True
            ).data
        )

    def post(self, request: Request) -> Response:
        serializer = ContractMilestoneCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        policy_id = data.pop("policy_public_id")
        contract_id = data.pop("contract_public_id")
        try:
            item = create_milestone(
                context=self.tenant_context,
                evidence=_evidence(request),
                policy_public_id=policy_id,
                contract_public_id=contract_id,
                attributes=data,
            )
        except (DjangoValidationError, IntegrityError) as exc:
            _raise_domain(exc)
        return Response(
            ContractMilestoneSerializer(item).data,
            status=status.HTTP_201_CREATED,
        )


class VariationOrderListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("commercial.view")
        items = VariationOrder.objects.filter(
            company=self.tenant_context.company
        ).select_related("policy", "contract")
        items = _filters(items, request, "status_code", "reason_code")
        return Response(
            VariationOrderSerializer(
                items.order_by("decision_due_at", "variation_number")[:200], many=True
            ).data
        )

    def post(self, request: Request) -> Response:
        serializer = VariationOrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        policy_id = data.pop("policy_public_id")
        contract_id = data.pop("contract_public_id")
        try:
            item = create_variation(
                context=self.tenant_context,
                evidence=_evidence(request),
                policy_public_id=policy_id,
                contract_public_id=contract_id,
                attributes=data,
            )
        except (DjangoValidationError, IntegrityError) as exc:
            _raise_domain(exc)
        return Response(
            VariationOrderSerializer(item).data,
            status=status.HTTP_201_CREATED,
        )


class PaymentApplicationListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("commercial.view")
        items = PaymentApplication.objects.filter(
            company=self.tenant_context.company
        ).select_related("policy", "contract")
        items = _filters(items, request, "status_code")
        return Response(
            PaymentApplicationSerializer(
                items.order_by("certification_due_at", "application_number")[:200],
                many=True,
            ).data
        )

    def post(self, request: Request) -> Response:
        serializer = PaymentApplicationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        policy_id = data.pop("policy_public_id")
        contract_id = data.pop("contract_public_id")
        try:
            item = create_payment(
                context=self.tenant_context,
                evidence=_evidence(request),
                policy_public_id=policy_id,
                contract_public_id=contract_id,
                attributes=data,
            )
        except (DjangoValidationError, IntegrityError) as exc:
            _raise_domain(exc)
        return Response(
            PaymentApplicationSerializer(item).data,
            status=status.HTTP_201_CREATED,
        )


class CommercialClaimListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("commercial.view")
        items = CommercialClaim.objects.filter(
            company=self.tenant_context.company
        ).select_related("policy", "contract")
        items = _filters(
            items, request, "status_code", "priority_code", "claim_type_code"
        )
        return Response(
            CommercialClaimSerializer(
                items.order_by("response_due_at", "claim_number")[:200], many=True
            ).data
        )

    def post(self, request: Request) -> Response:
        serializer = CommercialClaimCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        policy_id = data.pop("policy_public_id")
        contract_id = data.pop("contract_public_id")
        try:
            item = create_claim(
                context=self.tenant_context,
                evidence=_evidence(request),
                policy_public_id=policy_id,
                contract_public_id=contract_id,
                attributes=data,
            )
        except (DjangoValidationError, IntegrityError) as exc:
            _raise_domain(exc)
        return Response(
            CommercialClaimSerializer(item).data,
            status=status.HTTP_201_CREATED,
        )


class ExtensionOfTimeListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("commercial.view")
        items = ExtensionOfTime.objects.filter(
            company=self.tenant_context.company
        ).select_related("policy", "contract", "claim")
        items = _filters(items, request, "status_code", "reason_code")
        return Response(
            ExtensionOfTimeSerializer(
                items.order_by("decision_due_at", "eot_number")[:200], many=True
            ).data
        )

    def post(self, request: Request) -> Response:
        serializer = ExtensionOfTimeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        policy_id = data.pop("policy_public_id")
        contract_id = data.pop("contract_public_id")
        claim_id = data.pop("claim_public_id", None)
        try:
            item = create_eot(
                context=self.tenant_context,
                evidence=_evidence(request),
                policy_public_id=policy_id,
                contract_public_id=contract_id,
                claim_public_id=claim_id,
                attributes=data,
            )
        except (DjangoValidationError, IntegrityError) as exc:
            _raise_domain(exc)
        return Response(
            ExtensionOfTimeSerializer(item).data,
            status=status.HTTP_201_CREATED,
        )


class CommercialTransitionView(TenantScopedAPIView):
    serializers = {
        "CONTRACT": CommercialContractSerializer,
        "MILESTONE": ContractMilestoneSerializer,
        "VARIATION": VariationOrderSerializer,
        "PAYMENT": PaymentApplicationSerializer,
        "CLAIM": CommercialClaimSerializer,
        "EOT": ExtensionOfTimeSerializer,
    }

    def post(self, request: Request, entity_type: str, record_id) -> Response:
        serializer = TransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        normalized = entity_type.upper()
        output = self.serializers.get(normalized)
        if output is None:
            raise ApiValidationError(
                {"entity_type": "Unsupported commercial entity type"}
            )
        try:
            item = transition_record(
                context=self.tenant_context,
                evidence=_evidence(request),
                entity_type_code=normalized,
                record_public_id=record_id,
                target_status_code=serializer.validated_data["target_status_code"],
                expected_version=serializer.validated_data.get("expected_version"),
            )
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(output(item).data)


class CommercialApprovalListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("commercial.view")
        items = CommercialApproval.objects.filter(
            company=self.tenant_context.company
        ).select_related("policy")
        items = _filters(items, request, "status_code", "entity_type_code")
        return Response(
            CommercialApprovalSerializer(
                items.order_by("due_at", "requested_at")[:200], many=True
            ).data
        )

    def post(self, request: Request) -> Response:
        serializer = CommercialApprovalCreateSerializer(data=request.data)
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
            CommercialApprovalSerializer(item).data,
            status=status.HTTP_201_CREATED,
        )


class CommercialApprovalDecisionView(TenantScopedAPIView):
    def post(self, request: Request, approval_id) -> Response:
        serializer = ApprovalDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = decide_approval(
                context=self.tenant_context,
                evidence=_evidence(request),
                approval_public_id=approval_id,
                decision_code=serializer.validated_data["decision_code"],
                reason=serializer.validated_data.get("reason", ""),
                expected_version=serializer.validated_data.get("expected_version"),
            )
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(CommercialApprovalSerializer(item).data)


class CommercialRiskListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("commercial.view")
        items = CommercialRisk.objects.filter(
            company=self.tenant_context.company
        ).select_related("policy", "contract")
        items = _filters(items, request, "status_code", "severity_code")
        return Response(
            CommercialRiskSerializer(
                items.order_by("due_at", "-created_at")[:200], many=True
            ).data
        )

    def post(self, request: Request) -> Response:
        serializer = CommercialRiskCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        policy_id = data.pop("policy_public_id")
        contract_id = data.pop("contract_public_id", None)
        try:
            item = create_risk(
                context=self.tenant_context,
                evidence=_evidence(request),
                policy_public_id=policy_id,
                contract_public_id=contract_id,
                attributes=data,
            )
        except (DjangoValidationError, IntegrityError) as exc:
            _raise_domain(exc)
        return Response(
            CommercialRiskSerializer(item).data,
            status=status.HTTP_201_CREATED,
        )


class CommercialRiskResolveView(TenantScopedAPIView):
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
        return Response(CommercialRiskSerializer(item).data)
