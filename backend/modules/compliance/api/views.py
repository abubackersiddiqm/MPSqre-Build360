from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.compliance.api.serializers import (
    AccessReviewCreateSerializer,
    AccessReviewItemDecisionSerializer,
    AccessReviewTransitionSerializer,
    AssessmentCreateSerializer,
    AssessmentTransitionSerializer,
    EvaluationSerializer,
    ExceptionCreateSerializer,
    ExceptionDecisionSerializer,
    RiskCreateSerializer,
    RiskTransitionSerializer,
)
from modules.compliance.application.services import (
    compliance_portfolio,
    compliance_summary,
    create_access_review,
    create_assessment,
    create_risk,
    decide_access_review_item,
    decide_exception,
    evaluate_control,
    request_exception,
    transition_access_review,
    transition_assessment,
    transition_risk,
)
from modules.compliance.models import (
    AccessReviewCampaign,
    AccessReviewItem,
    ComplianceAssessment,
    ComplianceControl,
    ComplianceFramework,
    ControlEvaluation,
    RiskRegisterItem,
    SecurityException,
)
from modules.platform.actors import request_actor
from modules.tenant.api.base import TenantScopedAPIView


def _validation(exc: DjangoValidationError) -> ValidationError:
    return ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)


def _membership(item) -> dict[str, object] | None:
    if item is None:
        return None
    return {
        "public_id": str(item.public_id),
        "display_name": item.user.display_name,
        "email": item.user.email,
    }


def _control(item: ComplianceControl) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "code": item.code,
        "title": item.title,
        "description": item.description,
        "domain": item.domain,
        "severity": item.severity,
        "evidence_frequency_days": item.evidence_frequency_days,
        "status": item.status,
        "owner": _membership(item.owner_membership),
        "version": item.version,
    }


def _framework(item: ComplianceFramework) -> dict[str, object]:
    controls = list(item.controls.all())
    return {
        "public_id": str(item.public_id),
        "code": item.code,
        "name": item.name,
        "framework_type": item.framework_type,
        "jurisdiction": item.jurisdiction,
        "version_label": item.version_label,
        "description": item.description,
        "status": item.status,
        "effective_from": item.effective_from,
        "effective_to": item.effective_to,
        "control_count": len(controls),
        "controls": [_control(control) for control in controls],
        "version": item.version,
    }


def _evaluation(item: ControlEvaluation) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "control": _control(item.control),
        "result": item.result,
        "evidence_summary": item.evidence_summary,
        "evidence_reference": item.evidence_reference,
        "remediation_due_at": item.remediation_due_at,
        "assessed_by": _membership(item.assessed_by_membership),
        "assessed_at": item.assessed_at,
        "version": item.version,
    }


def _assessment(item: ComplianceAssessment) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "assessment_code": item.assessment_code,
        "assessment_type": item.assessment_type,
        "scope": item.scope,
        "period_start": item.period_start,
        "period_end": item.period_end,
        "status": item.status,
        "framework": {
            "public_id": str(item.framework.public_id),
            "code": item.framework.code,
            "name": item.framework.name,
            "version_label": item.framework.version_label,
        },
        "assessor": _membership(item.assessor_membership),
        "reviewer": _membership(item.reviewer_membership),
        "score_percent": str(item.score_percent),
        "evidence_sha256": item.evidence_sha256,
        "submitted_at": item.submitted_at,
        "decided_at": item.decided_at,
        "decision_reason": item.decision_reason,
        "evaluations": [_evaluation(value) for value in item.evaluations.all()],
        "version": item.version,
    }


def _risk(item: RiskRegisterItem) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "risk_code": item.risk_code,
        "title": item.title,
        "description": item.description,
        "category": item.category,
        "likelihood": item.likelihood,
        "impact": item.impact,
        "score": item.score,
        "treatment": item.treatment,
        "treatment_plan": item.treatment_plan,
        "status": item.status,
        "owner": _membership(item.owner_membership),
        "due_at": item.due_at,
        "accepted_at": item.accepted_at,
        "closed_at": item.closed_at,
        "version": item.version,
    }


def _exception(item: SecurityException) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "exception_code": item.exception_code,
        "control": (
            {"public_id": str(item.control.public_id), "code": item.control.code}
            if item.control
            else None
        ),
        "title": item.title,
        "justification": item.justification,
        "compensating_controls": item.compensating_controls,
        "risk_rating": item.risk_rating,
        "status": item.status,
        "requester": _membership(item.requested_by_membership),
        "reviewer": _membership(item.reviewer_membership),
        "expires_at": item.expires_at,
        "decision_reason": item.decision_reason,
        "decided_at": item.decided_at,
        "version": item.version,
    }


def _access_item(item: AccessReviewItem) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "membership": _membership(item.membership),
        "role_public_id": str(item.role_public_id),
        "role_code": item.role_code,
        "role_name": item.role_name,
        "permission_count": item.permission_count,
        "decision": item.decision,
        "reason": item.reason,
        "reviewer": _membership(item.reviewed_by_membership),
        "reviewed_at": item.reviewed_at,
        "version": item.version,
    }


def _campaign(item: AccessReviewCampaign) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "campaign_code": item.campaign_code,
        "name": item.name,
        "scope": item.scope,
        "status": item.status,
        "owner": _membership(item.owner_membership),
        "reviewer": _membership(item.reviewer_membership),
        "due_at": item.due_at,
        "submitted_at": item.submitted_at,
        "approved_at": item.approved_at,
        "items": [_access_item(value) for value in item.items.all()],
        "version": item.version,
    }


class ComplianceSummaryView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("compliance.dashboard.read")
        return Response(compliance_summary(self.tenant_context.company))


class CompliancePortfolioView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("compliance.dashboard.read")
        portfolio = compliance_portfolio(self.tenant_context.company)
        return Response(
            {
                "summary": portfolio["summary"],
                "current_membership_public_id": str(
                    self.tenant_context.membership.public_id
                ),
                "frameworks": [_framework(item) for item in portfolio["frameworks"]],
                "assessments": [
                    _assessment(item) for item in portfolio["assessments"]
                ],
                "risks": [_risk(item) for item in portfolio["risks"]],
                "exceptions": [
                    _exception(item) for item in portfolio["exceptions"]
                ],
                "access_reviews": [
                    _campaign(item) for item in portfolio["access_reviews"]
                ],
            }
        )


class AssessmentListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("compliance.assessment.read")
        items = (
            ComplianceAssessment.objects.select_related(
                "framework",
                "assessor_membership__user",
                "reviewer_membership__user",
            )
            .prefetch_related(
                "evaluations__control__owner_membership__user",
                "evaluations__assessed_by_membership__user",
            )
            .filter(company=self.tenant_context.company)[:100]
        )
        return Response({"items": [_assessment(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("compliance.assessment.create")
        serializer = AssessmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_assessment(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        item = (
            ComplianceAssessment.objects.select_related(
                "framework",
                "assessor_membership__user",
                "reviewer_membership__user",
            )
            .prefetch_related("evaluations__control")
            .get(pk=item.pk)
        )
        return Response(_assessment(item), status=201)


class EvaluationUpdateView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("compliance.assessment.evaluate")
        serializer = EvaluationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = evaluate_control(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                evaluation_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        item = ControlEvaluation.objects.select_related(
            "assessment", "control", "assessed_by_membership__user"
        ).get(pk=item.pk)
        return Response(_evaluation(item))


class AssessmentTransitionView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        serializer = AssessmentTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target = serializer.validated_data["target_status"]
        permission = (
            "compliance.assessment.approve"
            if target
            in {
                ComplianceAssessment.Status.APPROVED,
                ComplianceAssessment.Status.REJECTED,
            }
            else "compliance.assessment.submit"
        )
        self.tenant_context.require(permission)
        try:
            item = transition_assessment(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                assessment_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        item = (
            ComplianceAssessment.objects.select_related(
                "framework",
                "assessor_membership__user",
                "reviewer_membership__user",
            )
            .prefetch_related("evaluations__control")
            .get(pk=item.pk)
        )
        return Response(_assessment(item))


class RiskListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("compliance.risk.read")
        items = RiskRegisterItem.objects.select_related("owner_membership__user").filter(
            company=self.tenant_context.company
        )[:200]
        return Response({"items": [_risk(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("compliance.risk.manage")
        serializer = RiskCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_risk(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        item = RiskRegisterItem.objects.select_related("owner_membership__user").get(
            pk=item.pk
        )
        return Response(_risk(item), status=201)


class RiskTransitionView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        serializer = RiskTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        permission = (
            "compliance.risk.accept"
            if serializer.validated_data["target_status"]
            == RiskRegisterItem.Status.ACCEPTED
            else "compliance.risk.manage"
        )
        self.tenant_context.require(permission)
        try:
            item = transition_risk(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                risk_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        item = RiskRegisterItem.objects.select_related("owner_membership__user").get(
            pk=item.pk
        )
        return Response(_risk(item))


class ExceptionListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("compliance.exception.read")
        items = SecurityException.objects.select_related(
            "control",
            "requested_by_membership__user",
            "reviewer_membership__user",
        ).filter(company=self.tenant_context.company)[:200]
        return Response({"items": [_exception(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("compliance.exception.request")
        serializer = ExceptionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = request_exception(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        item = SecurityException.objects.select_related(
            "control", "requested_by_membership__user", "reviewer_membership__user"
        ).get(pk=item.pk)
        return Response(_exception(item), status=201)


class ExceptionDecisionView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("compliance.exception.approve")
        serializer = ExceptionDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = decide_exception(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                exception_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        item = SecurityException.objects.select_related(
            "control", "requested_by_membership__user", "reviewer_membership__user"
        ).get(pk=item.pk)
        return Response(_exception(item))


class AccessReviewListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("compliance.access_review.read")
        items = (
            AccessReviewCampaign.objects.select_related(
                "owner_membership__user", "reviewer_membership__user"
            )
            .prefetch_related(
                "items__membership__user", "items__reviewed_by_membership__user"
            )
            .filter(company=self.tenant_context.company)[:100]
        )
        return Response({"items": [_campaign(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("compliance.access_review.manage")
        serializer = AccessReviewCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_access_review(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        item = (
            AccessReviewCampaign.objects.select_related(
                "owner_membership__user", "reviewer_membership__user"
            )
            .prefetch_related("items__membership__user")
            .get(pk=item.pk)
        )
        return Response(_campaign(item), status=201)


class AccessReviewItemDecisionView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("compliance.access_review.decide")
        serializer = AccessReviewItemDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = decide_access_review_item(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                item_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        item = AccessReviewItem.objects.select_related(
            "membership__user", "reviewed_by_membership__user", "campaign"
        ).get(pk=item.pk)
        return Response(_access_item(item))


class AccessReviewTransitionView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        serializer = AccessReviewTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        permission = (
            "compliance.access_review.approve"
            if serializer.validated_data["target_status"]
            == AccessReviewCampaign.Status.APPROVED
            else "compliance.access_review.manage"
        )
        self.tenant_context.require(permission)
        try:
            item = transition_access_review(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                campaign_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        item = (
            AccessReviewCampaign.objects.select_related(
                "owner_membership__user", "reviewer_membership__user"
            )
            .prefetch_related("items__membership__user")
            .get(pk=item.pk)
        )
        return Response(_campaign(item))
