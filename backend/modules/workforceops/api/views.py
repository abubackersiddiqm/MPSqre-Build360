from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework import status
from rest_framework.exceptions import ValidationError as ApiValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.platform.audit import request_metadata
from modules.tenant.api.base import TenantScopedAPIView
from modules.workforceops.api.serializers import (
    ApprovalDecisionSerializer,
    ApprovalRequestSerializer,
    CredentialSerializer,
    CredentialUpsertSerializer,
    RiskCreateSerializer,
    RiskResolutionSerializer,
    SkillDefinitionSerializer,
    WorkforceAssignmentCreateSerializer,
    WorkforceDemandCreateSerializer,
    WorkforceDemandSerializer,
    WorkforcePlanCreateSerializer,
    WorkforcePlanSerializer,
    WorkforcePlanTransitionSerializer,
    WorkforcePolicySerializer,
)
from modules.workforceops.application.selectors import workforce_overview
from modules.workforceops.application.services import (
    RequestEvidence,
    assign_worker,
    create_demand,
    create_plan,
    create_policy,
    create_risk,
    create_skill,
    decide_approval,
    request_approval,
    resolve_risk,
    transition_plan,
    upsert_credential,
)
from modules.workforceops.models import (
    EmployeeSkillCredential,
    SkillDefinition,
    WorkforceApproval,
    WorkforceDemand,
    WorkforcePlan,
    WorkforcePolicyVersion,
    WorkforceRisk,
)


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


class WorkforceOverviewView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("workforce.view")
        return Response(workforce_overview(self.tenant_context.company))


class WorkforcePolicyListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("workforce.view")
        items = WorkforcePolicyVersion.objects.filter(
            company=self.tenant_context.company
        ).order_by("code", "-version")[:200]
        return Response(WorkforcePolicySerializer(items, many=True).data)

    def post(self, request: Request) -> Response:
        serializer = WorkforcePolicySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            policy = create_policy(
                context=self.tenant_context,
                evidence=_evidence(request),
                attributes=dict(serializer.validated_data),
            )
        except IntegrityError as exc:
            raise ApiValidationError(
                {"code": "A workforce policy with this code and version already exists"}
            ) from exc
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(
            WorkforcePolicySerializer(policy).data,
            status=status.HTTP_201_CREATED,
        )


class SkillDefinitionListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("workforce.view")
        items = SkillDefinition.objects.filter(
            company=self.tenant_context.company
        ).order_by("category_code", "code", "-version")[:500]
        return Response(SkillDefinitionSerializer(items, many=True).data)

    def post(self, request: Request) -> Response:
        serializer = SkillDefinitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            skill = create_skill(
                context=self.tenant_context,
                evidence=_evidence(request),
                attributes=dict(serializer.validated_data),
            )
        except IntegrityError as exc:
            raise ApiValidationError(
                {"code": "A skill with this code and version already exists"}
            ) from exc
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(
            SkillDefinitionSerializer(skill).data,
            status=status.HTTP_201_CREATED,
        )


class WorkforcePlanListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("workforce.view")
        items = (
            WorkforcePlan.objects.filter(company=self.tenant_context.company)
            .select_related("policy")
            .order_by("-created_at")[:200]
        )
        return Response(WorkforcePlanSerializer(items, many=True).data)

    def post(self, request: Request) -> Response:
        serializer = WorkforcePlanCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            plan = create_plan(
                context=self.tenant_context,
                evidence=_evidence(request),
                **serializer.validated_data,
            )
        except IntegrityError as exc:
            raise ApiValidationError(
                {"code": "A workforce plan with this code already exists"}
            ) from exc
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(
            WorkforcePlanSerializer(plan).data,
            status=status.HTTP_201_CREATED,
        )


class WorkforceDemandListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("workforce.view")
        items = WorkforceDemand.objects.filter(company=self.tenant_context.company)
        plan_public_id = request.query_params.get("plan_public_id")
        if plan_public_id:
            try:
                parsed_plan_id = uuid.UUID(plan_public_id)
            except ValueError as exc:
                raise ApiValidationError(
                    {"plan_public_id": "Enter a valid UUID"}
                ) from exc
            items = items.filter(plan__public_id=parsed_plan_id)
        items = items.select_related("plan").order_by("starts_on", "priority_code")[:500]
        return Response(WorkforceDemandSerializer(items, many=True).data)

    def post(self, request: Request) -> Response:
        serializer = WorkforceDemandCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attributes = dict(serializer.validated_data)
        plan_public_id = attributes.pop("plan_public_id")
        try:
            demand = create_demand(
                context=self.tenant_context,
                evidence=_evidence(request),
                plan_public_id=plan_public_id,
                attributes=attributes,
            )
        except IntegrityError as exc:
            raise ApiValidationError(
                {"demand_code": "This demand code already exists in the plan"}
            ) from exc
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(
            WorkforceDemandSerializer(demand).data,
            status=status.HTTP_201_CREATED,
        )


class WorkforcePlanTransitionView(TenantScopedAPIView):
    def post(self, request: Request, plan_id: uuid.UUID) -> Response:
        serializer = WorkforcePlanTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            plan = transition_plan(
                context=self.tenant_context,
                evidence=_evidence(request),
                plan_public_id=plan_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(WorkforcePlanSerializer(plan).data)


class WorkforceDemandAssignmentView(TenantScopedAPIView):
    def post(self, request: Request, demand_id: uuid.UUID) -> Response:
        serializer = WorkforceAssignmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            assignment = assign_worker(
                context=self.tenant_context,
                evidence=_evidence(request),
                demand_public_id=demand_id,
                **serializer.validated_data,
            )
        except IntegrityError as exc:
            raise ApiValidationError(
                {"employee_public_id": "This assignment already exists"}
            ) from exc
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(
            {
                "public_id": str(assignment.public_id),
                "demand_public_id": str(assignment.demand.public_id),
                "employee_public_id": str(assignment.employee_public_id),
                "assignment_status_code": assignment.assignment_status_code,
                "allocation_percent": str(assignment.allocation_percent),
                "starts_on": assignment.starts_on.isoformat(),
                "ends_on": (
                    assignment.ends_on.isoformat() if assignment.ends_on else None
                ),
            },
            status=status.HTTP_201_CREATED,
        )


class CredentialListUpsertView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("workforce.view")
        items = EmployeeSkillCredential.objects.filter(
            company=self.tenant_context.company
        ).select_related("skill")
        employee_public_id = request.query_params.get("employee_public_id")
        if employee_public_id:
            try:
                parsed_employee_id = uuid.UUID(employee_public_id)
            except ValueError as exc:
                raise ApiValidationError(
                    {"employee_public_id": "Enter a valid UUID"}
                ) from exc
            items = items.filter(employee_public_id=parsed_employee_id)
        items = items.order_by("expires_on", "skill__code")[:500]
        return Response(CredentialSerializer(items, many=True).data)

    def post(self, request: Request) -> Response:
        serializer = CredentialUpsertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attributes = dict(serializer.validated_data)
        employee_public_id = attributes.pop("employee_public_id")
        skill_public_id = attributes.pop("skill_public_id")
        try:
            credential = upsert_credential(
                context=self.tenant_context,
                evidence=_evidence(request),
                employee_public_id=employee_public_id,
                skill_public_id=skill_public_id,
                attributes=attributes,
            )
        except IntegrityError as exc:
            raise ApiValidationError(
                {"credential": "Credential could not be persisted"}
            ) from exc
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(CredentialSerializer(credential).data)


class WorkforceApprovalListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("workforce.view")
        items = (
            WorkforceApproval.objects.filter(
                company=self.tenant_context.company,
                decided_at__isnull=True,
            )
            .select_related("plan")
            .order_by("due_at", "requested_at")[:100]
        )
        return Response(
            [
                {
                    "public_id": str(item.public_id),
                    "plan_public_id": str(item.plan.public_id),
                    "plan_code": item.plan.code,
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
                {"step_code": "This approval step already exists for the plan"}
            ) from exc
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(
            {"public_id": str(approval.public_id), "status_code": approval.status_code},
            status=status.HTTP_201_CREATED,
        )


class WorkforceApprovalDecisionView(TenantScopedAPIView):
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


class WorkforceRiskListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("workforce.view")
        items = (
            WorkforceRisk.objects.filter(
                company=self.tenant_context.company,
                resolved_at__isnull=True,
            )
            .select_related("plan", "demand")
            .order_by("due_at", "-created_at")[:200]
        )
        return Response(
            [
                {
                    "public_id": str(item.public_id),
                    "plan_public_id": str(item.plan.public_id) if item.plan else None,
                    "demand_public_id": (
                        str(item.demand.public_id) if item.demand else None
                    ),
                    "employee_public_id": (
                        str(item.employee_public_id) if item.employee_public_id else None
                    ),
                    "risk_code": item.risk_code,
                    "severity_code": item.severity_code,
                    "status_code": item.status_code,
                    "message": item.message,
                    "due_at": item.due_at.isoformat() if item.due_at else None,
                    "created_at": item.created_at.isoformat(),
                }
                for item in items
            ]
        )

    def post(self, request: Request) -> Response:
        serializer = RiskCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            risk = create_risk(
                context=self.tenant_context,
                evidence=_evidence(request),
                attributes=dict(serializer.validated_data),
            )
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(
            {"public_id": str(risk.public_id), "status_code": risk.status_code},
            status=status.HTTP_201_CREATED,
        )


class WorkforceRiskResolveView(TenantScopedAPIView):
    def post(self, request: Request, risk_id: uuid.UUID) -> Response:
        serializer = RiskResolutionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            risk = resolve_risk(
                context=self.tenant_context,
                evidence=_evidence(request),
                risk_public_id=risk_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _api_validation(exc) from exc
        return Response(
            {
                "public_id": str(risk.public_id),
                "status_code": risk.status_code,
                "resolved_at": risk.resolved_at.isoformat() if risk.resolved_at else None,
            }
        )
