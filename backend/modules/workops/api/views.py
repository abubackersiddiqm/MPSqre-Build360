from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.employee.models import Employee
from modules.tenant.api.base import TenantScopedAPIView
from modules.tenant.models import Location
from modules.workops.application.selectors import project_work_overview
from modules.workops.application.services import (
    add_dependency,
    assign_work_item,
    create_checklist_item,
    create_milestone,
    create_project,
    create_site,
    create_timesheet,
    create_wbs_node,
    create_work_item,
    create_work_package,
    record_daily_progress,
    request_work_approval,
    review_timesheet,
    review_work_approval,
    set_checklist_completion,
    submit_timesheet,
    transition_project,
    transition_work_item,
)
from modules.workops.models import (
    Project,
    ProjectSite,
    WBSNode,
    WorkItem,
    WorkPackage,
)

from .serializers import (
    ApprovalRequestSerializer,
    ApprovalReviewSerializer,
    AssignmentCreateSerializer,
    ChecklistCompletionSerializer,
    ChecklistCreateSerializer,
    DependencyCreateSerializer,
    MilestoneCreateSerializer,
    ProgressCreateSerializer,
    ProjectCreateSerializer,
    SiteCreateSerializer,
    StatusTransitionSerializer,
    TimesheetCreateSerializer,
    TimesheetReviewSerializer,
    VersionSerializer,
    WBSCreateSerializer,
    WorkItemCreateSerializer,
    WorkPackageCreateSerializer,
)


def correlation_id(request: Request) -> uuid.UUID:
    return getattr(request, "request_id", uuid.uuid4())


def translate(error: DjangoValidationError) -> ValidationError:
    if hasattr(error, "message_dict"):
        return ValidationError(error.message_dict)
    return ValidationError(getattr(error, "messages", [str(error)]))


def find(model, *, company, public_id, message):
    item = model.objects.filter(company=company, public_id=public_id).first()
    if not item:
        raise NotFound(message)
    return item


class WorkAPIView(TenantScopedAPIView):
    required_permission = "work.view"

    def initial(self, request: Request, *args: object, **kwargs: object) -> None:
        super().initial(request, *args, **kwargs)
        self.tenant_context.require(self.required_permission)

    @property
    def actor(self) -> uuid.UUID:
        return self.tenant_context.principal.user.public_id


class OverviewView(WorkAPIView):
    def get(self, request: Request) -> Response:
        return Response(project_work_overview(self.tenant_context.company))


class ProjectView(WorkAPIView):
    required_permission = "work.project.manage"

    def post(self, request: Request) -> Response:
        serializer = ProjectCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        manager = find(Employee, company=self.tenant_context.company, public_id=data["manager_public_id"], message="Project manager not found") if data.get("manager_public_id") else None
        location = find(Location, company=self.tenant_context.company, public_id=data["location_public_id"], message="Location not found") if data.get("location_public_id") else None
        try:
            project = create_project(
                company=self.tenant_context.company,
                code=data["code"],
                name=data["name"],
                description=data.get("description", ""),
                project_type_code=data.get("project_type_code", "CONSTRUCTION"),
                priority_code=data.get("priority_code", "NORMAL"),
                manager=manager,
                location=location,
                start_date=data["start_date"],
                target_end_date=data["target_end_date"],
                currency=data.get("currency") or self.tenant_context.company.currency,
                budget=data.get("budget"),
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(project.public_id), "code": project.code, "version": project.version}, status=201)


class ProjectTransitionView(WorkAPIView):
    required_permission = "work.project.manage"

    def post(self, request: Request, project_id: uuid.UUID) -> Response:
        serializer = StatusTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            project = transition_project(
                company=self.tenant_context.company,
                project_public_id=project_id,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(project.public_id), "status_code": project.status_code, "version": project.version})


class SiteView(WorkAPIView):
    required_permission = "work.project.manage"

    def post(self, request: Request) -> Response:
        serializer = SiteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        project = find(Project, company=self.tenant_context.company, public_id=data["project_public_id"], message="Project not found")
        location = find(Location, company=self.tenant_context.company, public_id=data["location_public_id"], message="Location not found") if data.get("location_public_id") else None
        try:
            site = create_site(
                company=self.tenant_context.company,
                project=project,
                code=data["code"],
                name=data["name"],
                location=location,
                address=data.get("address", {}),
                start_date=data.get("start_date"),
                target_end_date=data.get("target_end_date"),
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(site.public_id), "code": site.code, "version": site.version}, status=201)


class WBSView(WorkAPIView):
    required_permission = "work.plan.manage"

    def post(self, request: Request) -> Response:
        serializer = WBSCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        project = find(Project, company=self.tenant_context.company, public_id=data["project_public_id"], message="Project not found")
        parent = find(WBSNode, company=self.tenant_context.company, public_id=data["parent_public_id"], message="WBS parent not found") if data.get("parent_public_id") else None
        try:
            item = create_wbs_node(
                company=self.tenant_context.company,
                project=project,
                code=data["code"],
                name=data["name"],
                parent=parent,
                sequence=data.get("sequence", 1),
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "code": item.code, "version": item.version}, status=201)


class WorkPackageView(WorkAPIView):
    required_permission = "work.plan.manage"

    def post(self, request: Request) -> Response:
        serializer = WorkPackageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        project = find(Project, company=self.tenant_context.company, public_id=data["project_public_id"], message="Project not found")
        wbs_node = find(WBSNode, company=self.tenant_context.company, public_id=data["wbs_node_public_id"], message="WBS node not found")
        owner = find(Employee, company=self.tenant_context.company, public_id=data["owner_public_id"], message="Owner not found") if data.get("owner_public_id") else None
        try:
            item = create_work_package(
                company=self.tenant_context.company,
                project=project,
                wbs_node=wbs_node,
                code=data["code"],
                name=data["name"],
                description=data.get("description", ""),
                owner=owner,
                planned_start=data["planned_start"],
                planned_end=data["planned_end"],
                progress_weight=data.get("progress_weight"),
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "code": item.code, "version": item.version}, status=201)


class MilestoneView(WorkAPIView):
    required_permission = "work.project.manage"

    def post(self, request: Request) -> Response:
        serializer = MilestoneCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        project = find(Project, company=self.tenant_context.company, public_id=data["project_public_id"], message="Project not found")
        owner = find(Employee, company=self.tenant_context.company, public_id=data["owner_public_id"], message="Owner not found") if data.get("owner_public_id") else None
        try:
            item = create_milestone(
                company=self.tenant_context.company,
                project=project,
                code=data["code"],
                name=data["name"],
                target_date=data["target_date"],
                owner=owner,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "code": item.code, "version": item.version}, status=201)


class WorkItemView(WorkAPIView):
    required_permission = "work.assign"

    def post(self, request: Request) -> Response:
        serializer = WorkItemCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        project = find(Project, company=self.tenant_context.company, public_id=data["project_public_id"], message="Project not found")
        site = find(ProjectSite, company=self.tenant_context.company, public_id=data["site_public_id"], message="Project site not found") if data.get("site_public_id") else None
        package = find(WorkPackage, company=self.tenant_context.company, public_id=data["work_package_public_id"], message="Work package not found") if data.get("work_package_public_id") else None
        assignee = find(Employee, company=self.tenant_context.company, public_id=data["primary_assignee_public_id"], message="Assignee not found") if data.get("primary_assignee_public_id") else None
        reviewer = find(Employee, company=self.tenant_context.company, public_id=data["reviewer_public_id"], message="Reviewer not found") if data.get("reviewer_public_id") else None
        try:
            item = create_work_item(
                company=self.tenant_context.company,
                project=project,
                site=site,
                work_package=package,
                code=data["code"],
                title=data["title"],
                description=data.get("description", ""),
                work_type_code=data.get("work_type_code", "TASK"),
                priority_code=data.get("priority_code", "NORMAL"),
                planned_start=data.get("planned_start"),
                due_date=data.get("due_date"),
                estimated_hours=data.get("estimated_hours"),
                primary_assignee=assignee,
                reviewer=reviewer,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "code": item.code, "status_code": item.status_code, "version": item.version}, status=201)


class WorkItemTransitionView(WorkAPIView):
    required_permission = "work.progress"

    def post(self, request: Request, work_item_id: uuid.UUID) -> Response:
        serializer = StatusTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_work_item(
                company=self.tenant_context.company,
                work_item_public_id=work_item_id,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status_code": item.status_code, "version": item.version})


class AssignmentView(WorkAPIView):
    required_permission = "work.assign"

    def post(self, request: Request) -> Response:
        serializer = AssignmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        employee = find(Employee, company=self.tenant_context.company, public_id=data["employee_public_id"], message="Employee not found")
        try:
            item = assign_work_item(
                company=self.tenant_context.company,
                work_item_public_id=data["work_item_public_id"],
                employee=employee,
                assignment_role_code=data.get("assignment_role_code", "ASSIGNEE"),
                allocation_percent=data.get("allocation_percent"),
                effective_from=data["effective_from"],
                effective_to=data.get("effective_to"),
                make_primary=data.get("make_primary", False),
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "version": item.version}, status=201)


class DependencyView(WorkAPIView):
    required_permission = "work.plan.manage"

    def post(self, request: Request) -> Response:
        serializer = DependencyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        predecessor = find(WorkItem, company=self.tenant_context.company, public_id=data["predecessor_public_id"], message="Predecessor not found")
        successor = find(WorkItem, company=self.tenant_context.company, public_id=data["successor_public_id"], message="Successor not found")
        try:
            item = add_dependency(
                company=self.tenant_context.company,
                predecessor=predecessor,
                successor=successor,
                dependency_type_code=data.get("dependency_type_code", "FINISH_TO_START"),
                lag_days=data.get("lag_days", 0),
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "version": item.version}, status=201)


class ChecklistView(WorkAPIView):
    required_permission = "work.plan.manage"

    def post(self, request: Request) -> Response:
        serializer = ChecklistCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        work_item = find(WorkItem, company=self.tenant_context.company, public_id=data["work_item_public_id"], message="Work item not found")
        try:
            item = create_checklist_item(
                company=self.tenant_context.company,
                work_item=work_item,
                sequence=data["sequence"],
                title=data["title"],
                is_required=data.get("is_required", True),
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "version": item.version}, status=201)


class ChecklistCompletionView(WorkAPIView):
    required_permission = "work.progress"

    def post(self, request: Request, checklist_id: uuid.UUID) -> Response:
        serializer = ChecklistCompletionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = set_checklist_completion(
                company=self.tenant_context.company,
                checklist_public_id=checklist_id,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "is_completed": item.is_completed, "version": item.version})


class ProgressView(WorkAPIView):
    required_permission = "work.progress"

    def post(self, request: Request) -> Response:
        serializer = ProgressCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        project = find(Project, company=self.tenant_context.company, public_id=data["project_public_id"], message="Project not found")
        site = find(ProjectSite, company=self.tenant_context.company, public_id=data["site_public_id"], message="Project site not found") if data.get("site_public_id") else None
        work_item = find(WorkItem, company=self.tenant_context.company, public_id=data["work_item_public_id"], message="Work item not found") if data.get("work_item_public_id") else None
        recorded_by = find(Employee, company=self.tenant_context.company, public_id=data["recorded_by_public_id"], message="Recorder not found") if data.get("recorded_by_public_id") else None
        try:
            item = record_daily_progress(
                company=self.tenant_context.company,
                project=project,
                site=site,
                work_item=work_item,
                recorded_by=recorded_by,
                progress_date=data["progress_date"],
                quantity_completed=data.get("quantity_completed"),
                unit_code=data.get("unit_code", ""),
                progress_percent=data.get("progress_percent"),
                hours_worked=data.get("hours_worked"),
                note=data.get("note", ""),
                blockers=data.get("blockers", ""),
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "version": item.version}, status=201)


class TimesheetView(WorkAPIView):
    required_permission = "work.time.manage"

    def post(self, request: Request) -> Response:
        serializer = TimesheetCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        employee = find(Employee, company=self.tenant_context.company, public_id=data["employee_public_id"], message="Employee not found")
        project = find(Project, company=self.tenant_context.company, public_id=data["project_public_id"], message="Project not found")
        work_item = find(WorkItem, company=self.tenant_context.company, public_id=data["work_item_public_id"], message="Work item not found") if data.get("work_item_public_id") else None
        try:
            item = create_timesheet(
                company=self.tenant_context.company,
                employee=employee,
                project=project,
                work_item=work_item,
                work_date=data["work_date"],
                hours=data["hours"],
                description=data.get("description", ""),
                submit_now=data.get("submit_now", False),
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status_code": item.status_code, "version": item.version}, status=201)


class TimesheetSubmitView(WorkAPIView):
    required_permission = "work.time.manage"

    def post(self, request: Request, timesheet_id: uuid.UUID) -> Response:
        serializer = VersionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = submit_timesheet(
                company=self.tenant_context.company,
                timesheet_public_id=timesheet_id,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status_code": item.status_code, "version": item.version})


class TimesheetReviewView(WorkAPIView):
    required_permission = "work.approve"

    def post(self, request: Request, timesheet_id: uuid.UUID) -> Response:
        serializer = TimesheetReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = review_timesheet(
                company=self.tenant_context.company,
                timesheet_public_id=timesheet_id,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status_code": item.status_code, "version": item.version})


class ApprovalView(WorkAPIView):
    required_permission = "work.progress"

    def post(self, request: Request) -> Response:
        serializer = ApprovalRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        work_item = find(WorkItem, company=self.tenant_context.company, public_id=data["work_item_public_id"], message="Work item not found")
        reviewer = find(Employee, company=self.tenant_context.company, public_id=data["reviewer_public_id"], message="Reviewer not found")
        try:
            item = request_work_approval(
                company=self.tenant_context.company,
                work_item=work_item,
                reviewer=reviewer,
                approval_type_code=data.get("approval_type_code", "WORK_COMPLETION"),
                request_note=data.get("request_note", ""),
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status_code": item.status_code, "version": item.version}, status=201)


class ApprovalReviewView(WorkAPIView):
    required_permission = "work.approve"

    def post(self, request: Request, approval_id: uuid.UUID) -> Response:
        serializer = ApprovalReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = review_work_approval(
                company=self.tenant_context.company,
                approval_public_id=approval_id,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status_code": item.status_code, "version": item.version})
