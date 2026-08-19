from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.myworkops.application.selectors import my_work_overview
from modules.myworkops.application.services import (
    complete_own_checklist,
    create_own_timesheet,
    current_employee,
    decide_own_approval,
    decide_team_timesheet,
    discard_offline_draft,
    record_own_progress,
    submit_own_timesheet,
    sync_offline_draft,
    transition_own_work_item,
    update_notification_state,
    upsert_offline_draft,
)
from modules.tenant.api.base import TenantScopedAPIView
from modules.workops.models import Project, WorkItem

from .serializers import (
    ChecklistCompletionSerializer,
    DecisionSerializer,
    NotificationStateSerializer,
    OfflineDraftSerializer,
    ProgressSerializer,
    StatusTransitionSerializer,
    TeamTimesheetDecisionSerializer,
    TimesheetSerializer,
    VersionSerializer,
)


def correlation_id(request: Request) -> uuid.UUID:
    return getattr(request, "request_id", uuid.uuid4())


def translate(error: DjangoValidationError) -> ValidationError:
    if hasattr(error, "message_dict"):
        return ValidationError(error.message_dict)
    return ValidationError(getattr(error, "messages", [str(error)]))


def find(model, *, company, public_id, message):
    item = model.objects.filter(company=company, public_id=public_id).first()
    if item is None:
        raise NotFound(message)
    return item


class MyWorkAPIView(TenantScopedAPIView):
    required_permission = "mywork.view"

    def initial(self, request: Request, *args: object, **kwargs: object) -> None:
        super().initial(request, *args, **kwargs)
        self.tenant_context.require(self.required_permission)

    @property
    def actor(self) -> uuid.UUID:
        return self.tenant_context.principal.user.public_id

    @property
    def employee(self):
        try:
            return current_employee(self.tenant_context.company, self.tenant_context.membership)
        except DjangoValidationError as error:
            raise translate(error) from error


class OverviewView(MyWorkAPIView):
    def get(self, request: Request) -> Response:
        payload = my_work_overview(self.tenant_context.company, self.tenant_context.membership)
        payload["capabilities"] = {
            "can_execute": self.tenant_context.can("mywork.execute"),
            "can_log_time": self.tenant_context.can("mywork.time"),
            "can_approve": self.tenant_context.can("mywork.approve"),
            "can_use_offline": self.tenant_context.can("mywork.offline"),
            "can_export": self.tenant_context.can("mywork.export"),
        }
        return Response(payload)


class WorkTransitionView(MyWorkAPIView):
    required_permission = "mywork.execute"

    def post(self, request: Request, work_item_id: uuid.UUID) -> Response:
        serializer = StatusTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_own_work_item(
                company=self.tenant_context.company,
                employee=self.employee,
                work_item_public_id=work_item_id,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status_code": item.status_code, "version": item.version})


class ChecklistCompletionView(MyWorkAPIView):
    required_permission = "mywork.execute"

    def post(self, request: Request, checklist_id: uuid.UUID) -> Response:
        serializer = ChecklistCompletionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = complete_own_checklist(
                company=self.tenant_context.company,
                employee=self.employee,
                checklist_public_id=checklist_id,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "is_completed": item.is_completed, "version": item.version})


class ProgressView(MyWorkAPIView):
    required_permission = "mywork.execute"

    def post(self, request: Request) -> Response:
        serializer = ProgressSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        work_item = find(
            WorkItem,
            company=self.tenant_context.company,
            public_id=data.pop("work_item_public_id"),
            message="Work item not found",
        )
        try:
            item = record_own_progress(
                company=self.tenant_context.company,
                employee=self.employee,
                work_item=work_item,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "version": item.version}, status=201)


class TimesheetView(MyWorkAPIView):
    required_permission = "mywork.time"

    def post(self, request: Request) -> Response:
        serializer = TimesheetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        project = find(
            Project,
            company=self.tenant_context.company,
            public_id=data.pop("project_public_id"),
            message="Project not found",
        )
        work_item_public_id = data.pop("work_item_public_id", None)
        work_item = (
            find(
                WorkItem,
                company=self.tenant_context.company,
                public_id=work_item_public_id,
                message="Work item not found",
            )
            if work_item_public_id
            else None
        )
        try:
            item = create_own_timesheet(
                company=self.tenant_context.company,
                employee=self.employee,
                project=project,
                work_item=work_item,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response(
            {"public_id": str(item.public_id), "status_code": item.status_code, "version": item.version},
            status=201,
        )


class TimesheetSubmitView(MyWorkAPIView):
    required_permission = "mywork.time"

    def post(self, request: Request, timesheet_id: uuid.UUID) -> Response:
        serializer = VersionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = submit_own_timesheet(
                company=self.tenant_context.company,
                employee=self.employee,
                timesheet_public_id=timesheet_id,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status_code": item.status_code, "version": item.version})


class ApprovalDecisionView(MyWorkAPIView):
    required_permission = "mywork.approve"

    def post(self, request: Request, approval_id: uuid.UUID) -> Response:
        serializer = DecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = decide_own_approval(
                company=self.tenant_context.company,
                employee=self.employee,
                approval_public_id=approval_id,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status_code": item.status_code, "version": item.version})


class TeamTimesheetDecisionView(MyWorkAPIView):
    required_permission = "mywork.approve"

    def post(self, request: Request, timesheet_id: uuid.UUID) -> Response:
        serializer = TeamTimesheetDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = decide_team_timesheet(
                company=self.tenant_context.company,
                manager=self.employee,
                timesheet_public_id=timesheet_id,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status_code": item.status_code, "version": item.version})


class OfflineDraftView(MyWorkAPIView):
    required_permission = "mywork.offline"

    def post(self, request: Request) -> Response:
        serializer = OfflineDraftSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        work_item_public_id = data.pop("work_item_public_id", None)
        work_item = (
            find(
                WorkItem,
                company=self.tenant_context.company,
                public_id=work_item_public_id,
                message="Work item not found",
            )
            if work_item_public_id
            else None
        )
        try:
            item = upsert_offline_draft(
                company=self.tenant_context.company,
                employee=self.employee,
                work_item=work_item,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response(
            {"public_id": str(item.public_id), "status_code": item.status_code, "version": item.version},
            status=201,
        )


class OfflineDraftSyncView(MyWorkAPIView):
    required_permission = "mywork.offline"

    def post(self, request: Request, draft_id: uuid.UUID) -> Response:
        serializer = VersionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = sync_offline_draft(
                company=self.tenant_context.company,
                employee=self.employee,
                draft_public_id=draft_id,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response(
            {
                "public_id": str(item.public_id),
                "status_code": item.status_code,
                "conflict_reason": item.conflict_reason,
                "version": item.version,
            }
        )


class OfflineDraftDiscardView(MyWorkAPIView):
    required_permission = "mywork.offline"

    def post(self, request: Request, draft_id: uuid.UUID) -> Response:
        serializer = VersionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = discard_offline_draft(
                company=self.tenant_context.company,
                employee=self.employee,
                draft_public_id=draft_id,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status_code": item.status_code, "version": item.version})


class NotificationStateView(MyWorkAPIView):
    def post(self, request: Request, notification_id: uuid.UUID) -> Response:
        serializer = NotificationStateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = update_notification_state(
                company=self.tenant_context.company,
                employee=self.employee,
                notification_public_id=notification_id,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response(
            {
                "public_id": str(item.public_id),
                "read_at": item.read_at.isoformat() if item.read_at else None,
                "dismissed_at": item.dismissed_at.isoformat() if item.dismissed_at else None,
                "version": item.version,
            }
        )
