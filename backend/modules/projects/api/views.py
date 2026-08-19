from __future__ import annotations

import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.platform.actors import request_actor
from modules.projects.api.serializers import (
    DeliveryStageCreateSerializer,
    ProjectBaselineSerializer,
    ProjectCreateSerializer,
    ProjectFromCrmOpportunitySerializer,
    StageTransitionSerializer,
    TaskCreateSerializer,
    TaskTransitionSerializer,
    WbsCreateSerializer,
)
from modules.projects.application.crm_handoff import create_or_reuse_project_from_crm_opportunity
from modules.projects.application.services import (
    available_transitions,
    baseline_project,
    create_project,
    create_task,
    create_wbs_node,
    transition_project,
    transition_task,
)
from modules.projects.models import DeliveryStage, Project, ProjectBaseline, ProjectTask, WbsNode
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
        "entity_type": stage.entity_type,
        "code": stage.code,
        "name": stage.name,
        "outcome": stage.outcome,
        "sort_order": stage.sort_order,
        "allowed_next_codes": stage.allowed_next_codes,
        "is_initial": stage.is_initial,
        "allows_baseline": stage.allows_baseline,
    }


def _project(project: Project) -> dict[str, object]:
    transitions = list(available_transitions(project.stage))
    return {
        "public_id": str(project.public_id),
        "code": project.code,
        "name": project.name,
        "description": project.description,
        "customer_public_id": (
            str(project.customer_public_id) if project.customer_public_id else None
        ),
        "opportunity_public_id": (
            str(project.opportunity_public_id) if project.opportunity_public_id else None
        ),
        "stage": _stage(project.stage),
        "available_transitions": [_stage(item) for item in transitions],
        "manager_membership_public_id": str(project.manager_membership_public_id),
        "location": project.location,
        "planned_start_date": project.planned_start_date,
        "planned_end_date": project.planned_end_date,
        "actual_start_date": project.actual_start_date,
        "actual_end_date": project.actual_end_date,
        "currency": project.currency,
        "approved_budget": str(project.approved_budget),
        "version": project.version,
        "baseline_version": project.baseline_version,
        "baselined_at": project.baselined_at,
        "created_at": project.created_at,
    }


def _wbs(node: WbsNode) -> dict[str, object]:
    return {
        "public_id": str(node.public_id),
        "project_public_id": str(node.project.public_id),
        "parent_public_id": str(node.parent.public_id) if node.parent else None,
        "code": node.code,
        "name": node.name,
        "description": node.description,
        "sort_order": node.sort_order,
        "version": node.version,
    }


def _task(task: ProjectTask) -> dict[str, object]:
    return {
        "public_id": str(task.public_id),
        "project_public_id": str(task.project.public_id),
        "wbs_node_public_id": str(task.wbs_node.public_id) if task.wbs_node else None,
        "code": task.code,
        "title": task.title,
        "description": task.description,
        "stage": _stage(task.stage),
        "available_transitions": [_stage(item) for item in available_transitions(task.stage)],
        "assignee_membership_public_id": (
            str(task.assignee_membership_public_id)
            if task.assignee_membership_public_id
            else None
        ),
        "planned_start_date": task.planned_start_date,
        "planned_end_date": task.planned_end_date,
        "progress_percent": task.progress_percent,
        "version": task.version,
    }


class ProjectSummaryView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("project.dashboard.read")
        company = self.tenant_context.company
        projects = Project.objects.filter(company=company, archived_at__isnull=True)
        tasks = ProjectTask.objects.filter(company=company)
        stage_counts = list(
            projects.values("stage__code", "stage__name").annotate(count=Count("id"))
        )
        overdue_tasks = tasks.filter(
            planned_end_date__lt=timezone.localdate(),
        ).exclude(
            stage__outcome__in=[
                DeliveryStage.Outcome.COMPLETE,
                DeliveryStage.Outcome.CANCELLED,
            ]
        )
        return Response(
            {
                "projects": projects.count(),
                "tasks": tasks.count(),
                "overdue_tasks": overdue_tasks.count(),
                "baselined_projects": projects.filter(baseline_version__gt=0).count(),
                "approved_budget": str(
                    projects.aggregate(total=Sum("approved_budget"))["total"]
                    or Decimal("0")
                ),
                "currency": company.currency,
                "project_stages": stage_counts,
            }
        )


class DeliveryStageListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("project.stage.read")
        queryset = DeliveryStage.objects.filter(
            company=self.tenant_context.company,
            is_active=True,
            effective_from__lte=timezone.now(),
        ).filter(Q(effective_to__isnull=True) | Q(effective_to__gt=timezone.now()))
        entity_type = request.query_params.get("entity_type", "").strip()
        if entity_type:
            queryset = queryset.filter(entity_type=entity_type)
        return Response({"items": [_stage(stage) for stage in queryset]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("project.stage.manage")
        serializer = DeliveryStageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            with transaction.atomic():
                if data.get("is_initial"):
                    DeliveryStage.objects.filter(
                        company=self.tenant_context.company,
                        entity_type=data["entity_type"],
                        is_initial=True,
                    ).update(is_initial=False)
                stage = DeliveryStage(company=self.tenant_context.company, **data)
                stage.full_clean()
                stage.save()
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_stage(stage), status=201)


class ProjectFromCrmOpportunityView(TenantScopedAPIView):
    def post(self, request: Request, opportunity_public_id: uuid.UUID) -> Response:
        self.tenant_context.require("crm.opportunity.manage")
        self.tenant_context.require("project.project.manage")
        serializer = ProjectFromCrmOpportunitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = create_or_reuse_project_from_crm_opportunity(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                opportunity_public_id=opportunity_public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc

        project = result.project
        message = (
            "Preconstruction workspace created. Architect and estimator can continue on the same project."
            if result.created and result.mode == "preconstruction"
            else "Awarded project created from the won CRM opportunity."
            if result.created
            else "Existing project workspace reused; no duplicate project was created."
        )
        return Response(
            {
                "public_id": str(project.public_id),
                "code": project.code,
                "name": project.name,
                "created": result.created,
                "mode": result.mode,
                "opportunity_outcome": result.opportunity_outcome,
                "message": message,
            },
            status=201 if result.created else 200,
        )


class ProjectListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("project.project.read")
        queryset = Project.objects.select_related("stage").filter(
            company=self.tenant_context.company,
            archived_at__isnull=True,
        )
        search = request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(code__icontains=search))
        items = queryset.order_by("-created_at")[: _limit(request)]
        return Response({"items": [_project(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("project.project.manage")
        serializer = ProjectCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            project = create_project(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_project(project), status=201)


class ProjectDetailView(TenantScopedAPIView):
    def get(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("project.project.read")
        project = Project.objects.select_related("stage").filter(
            company=self.tenant_context.company,
            public_id=public_id,
        ).first()
        if project is None:
            raise NotFound("Resource not found")
        return Response(_project(project))


class ProjectTransitionView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("project.project.transition")
        serializer = StageTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            project = transition_project(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                project_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_project(project))


class ProjectBaselineView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("project.project.baseline")
        serializer = ProjectBaselineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            baseline = baseline_project(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                project_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(
            {
                "public_id": str(baseline.public_id),
                "baseline_number": baseline.baseline_number,
                "source_project_version": baseline.source_project_version,
                "created_at": baseline.created_at,
            },
            status=201,
        )


class ProjectWbsListCreateView(TenantScopedAPIView):
    def get(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("project.wbs.read")
        items = WbsNode.objects.select_related("project", "parent").filter(
            company=self.tenant_context.company,
            project__public_id=public_id,
        ).order_by("sort_order", "code")
        return Response({"items": [_wbs(item) for item in items]})

    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("project.wbs.manage")
        serializer = WbsCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            node = create_wbs_node(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                project_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_wbs(node), status=201)


class ProjectTaskListCreateView(TenantScopedAPIView):
    def get(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("project.task.read")
        items = ProjectTask.objects.select_related("project", "wbs_node", "stage").filter(
            company=self.tenant_context.company,
            project__public_id=public_id,
        ).order_by("code")
        return Response({"items": [_task(item) for item in items]})

    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("project.task.manage")
        serializer = TaskCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            task = create_task(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                project_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_task(task), status=201)


class TaskTransitionView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("project.task.transition")
        serializer = TaskTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            task = transition_task(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                task_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_task(task))


class ProjectBaselineListView(TenantScopedAPIView):
    def get(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("project.project.read")
        items = ProjectBaseline.objects.filter(
            company=self.tenant_context.company,
            project__public_id=public_id,
        ).order_by("-baseline_number")
        return Response(
            {
                "items": [
                    {
                        "public_id": str(item.public_id),
                        "baseline_number": item.baseline_number,
                        "source_project_version": item.source_project_version,
                        "created_at": item.created_at,
                    }
                    for item in items
                ]
            }
        )


class ProjectExperienceView(TenantScopedAPIView):
    def get(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("project.dashboard.read")
        project = Project.objects.select_related("stage").filter(
            company=self.tenant_context.company,
            public_id=public_id,
            archived_at__isnull=True,
        ).first()
        if project is None:
            raise NotFound("Resource not found")
        from modules.projects.application.experience import project_experience

        return Response(
            project_experience(
                company=self.tenant_context.company,
                project=project,
                permission_codes=set(self.tenant_context.permission_codes()),
            )
        )


class ProjectDesignBoardView(TenantScopedAPIView):
    def get(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("project.dashboard.read")
        project = Project.objects.select_related("stage").filter(
            company=self.tenant_context.company,
            public_id=public_id,
            archived_at__isnull=True,
        ).first()
        if project is None:
            raise NotFound("Resource not found")
        from modules.projects.application.visual_operations import project_design_board

        return Response(
            project_design_board(
                company=self.tenant_context.company,
                project=project,
                permission_codes=set(self.tenant_context.permission_codes()),
            )
        )


class GuidedWorkbenchView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        permission_codes = set(self.tenant_context.permission_codes())
        supported = {
            "project.dashboard.read",
            "crm.dashboard.read",
            "workflow.approve",
            "design.review.decide",
            "finance.dashboard.read",
            "procurement.dashboard.read",
        }
        if not (permission_codes & supported):
            raise PermissionDenied("No guided-work permission is available.")
        from modules.projects.application.guided_operations import guided_workbench

        return Response(guided_workbench(tenant_context=self.tenant_context))


class UniversalSearchView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        permission_codes = set(self.tenant_context.permission_codes())
        supported = {
            "project.dashboard.read",
            "crm.dashboard.read",
            "design.document.read",
            "design.dashboard.read",
            "procurement.dashboard.read",
            "finance.dashboard.read",
            "digitaltwin.view",
            "digitaltwin.handover",
        }
        if not (permission_codes & supported):
            raise PermissionDenied("No searchable workspace is available.")
        from modules.projects.application.guided_operations import universal_search

        return Response(
            universal_search(
                company=self.tenant_context.company,
                query=request.query_params.get("q", ""),
                permission_codes=permission_codes,
            )
        )


class ProjectSiteTimelineView(TenantScopedAPIView):
    def get(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("project.dashboard.read")
        project = Project.objects.select_related("stage").filter(
            company=self.tenant_context.company,
            public_id=public_id,
            archived_at__isnull=True,
        ).first()
        if project is None:
            raise NotFound("Resource not found")
        from modules.projects.application.guided_operations import project_site_timeline

        return Response(
            project_site_timeline(
                company=self.tenant_context.company,
                project=project,
                permission_codes=set(self.tenant_context.permission_codes()),
            )
        )


class ProjectProcurementFlowView(TenantScopedAPIView):
    def get(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("project.dashboard.read")
        self.tenant_context.require("procurement.dashboard.read")
        project = Project.objects.select_related("stage").filter(
            company=self.tenant_context.company,
            public_id=public_id,
            archived_at__isnull=True,
        ).first()
        if project is None:
            raise NotFound("Resource not found")
        from modules.projects.application.guided_operations import project_procurement_flow

        return Response(
            project_procurement_flow(
                company=self.tenant_context.company,
                project=project,
            )
        )


class ProjectHandoverBoardView(TenantScopedAPIView):
    def get(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("project.dashboard.read")
        project = Project.objects.select_related("stage").filter(
            company=self.tenant_context.company,
            public_id=public_id,
            archived_at__isnull=True,
        ).first()
        if project is None:
            raise NotFound("Resource not found")
        from modules.projects.application.guided_operations import project_handover_board

        return Response(
            project_handover_board(
                company=self.tenant_context.company,
                project=project,
                permission_codes=set(self.tenant_context.permission_codes()),
            )
        )


class ExecutivePortfolioView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("project.dashboard.read")
        from modules.projects.application.guided_operations import executive_portfolio
        return Response(executive_portfolio(
            company=self.tenant_context.company,
            permission_codes=set(self.tenant_context.permission_codes()),
        ))


class ProjectEvidencePanelView(TenantScopedAPIView):
    def get(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("project.dashboard.read")
        project = Project.objects.select_related("stage").filter(
            company=self.tenant_context.company,
            public_id=public_id,
            archived_at__isnull=True,
        ).first()
        if project is None:
            raise NotFound("Resource not found")
        from modules.projects.application.guided_operations import project_evidence_panel
        return Response(project_evidence_panel(
            company=self.tenant_context.company,
            project=project,
            permission_codes=set(self.tenant_context.permission_codes()),
        ))
