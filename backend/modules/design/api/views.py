from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count, Q
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.design.api.serializers import (
    DesignDocumentCreateSerializer,
    DesignIssueCloseSerializer,
    DesignIssueCreateSerializer,
    DesignTransitionSerializer,
    DesignVersionCreateSerializer,
    ReviewDecisionSerializer,
    ReviewRequestSerializer,
    TransmittalCreateSerializer,
)
from modules.design.application.services import (
    close_issue,
    create_document,
    create_issue,
    create_transmittal,
    create_version,
    decide_review,
    request_review,
    transition_version,
)
from modules.design.models import (
    DesignDocument,
    DesignIssue,
    DesignReview,
    DesignTransmittal,
    DesignVersion,
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


def _document(document: DesignDocument) -> dict[str, object]:
    latest = document.versions.select_related("stage").order_by("-version_number").first()
    return {
        "public_id": str(document.public_id),
        "project_public_id": str(document.project.public_id),
        "project_code": document.project.code,
        "document_number": document.document_number,
        "title": document.title,
        "discipline_code": document.discipline_code,
        "document_type_code": document.document_type_code,
        "description": document.description,
        "latest_version": _version(latest) if latest else None,
        "version": document.version,
        "created_at": document.created_at,
    }


def _version(version: DesignVersion) -> dict[str, object]:
    return {
        "public_id": str(version.public_id),
        "document_public_id": str(version.document.public_id),
        "version_number": version.version_number,
        "revision_code": version.revision_code,
        "stage": _stage(version.stage),
        "available_transitions": [_stage(item) for item in available_transitions(version.stage)],
        "description": version.description,
        "file_object_public_id": (
            str(version.file_object_public_id) if version.file_object_public_id else None
        ),
        "checksum_sha256": version.checksum_sha256,
        "submitted_at": version.submitted_at,
        "approved_at": version.approved_at,
        "issued_at": version.issued_at,
        "superseded_at": version.superseded_at,
        "version": version.version,
        "created_at": version.created_at,
    }


def _review(review: DesignReview) -> dict[str, object]:
    return {
        "public_id": str(review.public_id),
        "design_version_public_id": str(review.design_version.public_id),
        "reviewer_membership_public_id": str(review.reviewer_membership_public_id),
        "decision": review.decision,
        "comments": review.comments,
        "requested_at": review.requested_at,
        "decided_at": review.decided_at,
        "version": review.version,
    }


def _issue(issue: DesignIssue) -> dict[str, object]:
    return {
        "public_id": str(issue.public_id),
        "project_public_id": str(issue.project.public_id),
        "design_version_public_id": (
            str(issue.design_version.public_id) if issue.design_version else None
        ),
        "title": issue.title,
        "description": issue.description,
        "severity": issue.severity,
        "assigned_membership_public_id": (
            str(issue.assigned_membership_public_id)
            if issue.assigned_membership_public_id
            else None
        ),
        "due_at": issue.due_at,
        "closed_at": issue.closed_at,
        "resolution": issue.resolution,
        "version": issue.version,
        "created_at": issue.created_at,
    }


def _transmittal(item: DesignTransmittal) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "project_public_id": str(item.project.public_id),
        "reference": item.reference,
        "purpose_code": item.purpose_code,
        "recipient": item.recipient,
        "notes": item.notes,
        "issued_at": item.issued_at,
        "versions": [
            {
                "public_id": str(link.design_version.public_id),
                "document_number": link.design_version.document.document_number,
                "revision_code": link.design_version.revision_code,
            }
            for link in item.items.select_related("design_version__document")
        ],
    }


class DesignSummaryView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("design.dashboard.read")
        company = self.tenant_context.company
        documents = DesignDocument.objects.filter(company=company, archived_at__isnull=True)
        versions = DesignVersion.objects.filter(company=company)
        issues = DesignIssue.objects.filter(company=company)
        return Response(
            {
                "documents": documents.count(),
                "versions": versions.count(),
                "issued_versions": versions.filter(
                    stage__outcome=DeliveryStage.Outcome.ISSUED,
                    superseded_at__isnull=True,
                ).count(),
                "open_issues": issues.filter(closed_at__isnull=True).count(),
                "pending_reviews": DesignReview.objects.filter(
                    company=company,
                    decision=DesignReview.Decision.PENDING,
                ).count(),
                "disciplines": list(
                    documents.values("discipline_code").annotate(count=Count("id"))
                ),
            }
        )


class DesignDocumentListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("design.document.read")
        queryset = DesignDocument.objects.select_related("project").filter(
            company=self.tenant_context.company,
            archived_at__isnull=True,
        )
        project_id = request.query_params.get("project_public_id", "").strip()
        if project_id:
            queryset = queryset.filter(project__public_id=project_id)
        search = request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(document_number__icontains=search)
            )
        items = queryset.order_by("document_number")[: _limit(request)]
        return Response({"items": [_document(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("design.document.manage")
        serializer = DesignDocumentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            document = create_document(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_document(document), status=201)


class DesignVersionListCreateView(TenantScopedAPIView):
    def get(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("design.version.read")
        versions = DesignVersion.objects.select_related("document", "stage").filter(
            company=self.tenant_context.company,
            document__public_id=public_id,
        ).order_by("-version_number")
        return Response({"items": [_version(item) for item in versions]})

    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("design.version.manage")
        serializer = DesignVersionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            version = create_version(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                document_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_version(version), status=201)


class DesignVersionTransitionView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("design.version.transition")
        serializer = DesignTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            version = transition_version(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                version_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_version(version))


class DesignReviewListCreateView(TenantScopedAPIView):
    def get(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("design.review.read")
        reviews = DesignReview.objects.select_related("design_version").filter(
            company=self.tenant_context.company,
            design_version__public_id=public_id,
        )
        return Response({"items": [_review(item) for item in reviews]})

    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("design.review.manage")
        serializer = ReviewRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            review = request_review(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                version_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_review(review), status=201)


class DesignReviewDecisionView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("design.review.decide")
        serializer = ReviewDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            review = decide_review(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                review_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_review(review))


class DesignIssueListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("design.issue.read")
        queryset = DesignIssue.objects.select_related("project", "design_version").filter(
            company=self.tenant_context.company
        )
        project_id = request.query_params.get("project_public_id", "").strip()
        if project_id:
            queryset = queryset.filter(project__public_id=project_id)
        state = request.query_params.get("state", "open")
        if state == "open":
            queryset = queryset.filter(closed_at__isnull=True)
        elif state == "closed":
            queryset = queryset.filter(closed_at__isnull=False)
        items = queryset.order_by("-created_at")[: _limit(request)]
        return Response({"items": [_issue(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("design.issue.manage")
        serializer = DesignIssueCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            issue = create_issue(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_issue(issue), status=201)


class DesignIssueCloseView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("design.issue.manage")
        serializer = DesignIssueCloseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            issue = close_issue(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                issue_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_issue(issue))


class DesignTransmittalListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("design.transmittal.read")
        queryset = DesignTransmittal.objects.select_related("project").filter(
            company=self.tenant_context.company
        )
        project_id = request.query_params.get("project_public_id", "").strip()
        if project_id:
            queryset = queryset.filter(project__public_id=project_id)
        items = queryset.order_by("-issued_at")[: _limit(request)]
        return Response({"items": [_transmittal(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("design.transmittal.manage")
        serializer = TransmittalCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            transmittal = create_transmittal(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_transmittal(transmittal), status=201)


class DesignVersionDetailView(TenantScopedAPIView):
    def get(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("design.version.read")
        version = DesignVersion.objects.select_related("document", "stage").filter(
            company=self.tenant_context.company,
            public_id=public_id,
        ).first()
        if version is None:
            raise NotFound("Resource not found")
        return Response(_version(version))
