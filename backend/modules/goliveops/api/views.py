from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.goliveops.application.selectors import go_live_overview
from modules.goliveops.application.services import (
    create_cutover_plan,
    create_cutover_task,
    create_go_live_wave,
    create_hypercare_issue,
    create_migration_batch,
    create_migration_issue,
    create_training_cohort,
    create_training_enrollment,
    decide_gate,
    resolve_migration_issue,
    seed_defaults,
    transition_cutover_task,
    transition_go_live_wave,
    transition_hypercare_issue,
    transition_migration_batch,
    transition_training_enrollment,
)
from modules.goliveops.models import (
    CutoverPlan,
    CutoverTask,
    GoLiveGate,
    GoLiveWave,
    HypercareIssue,
    MigrationBatch,
    MigrationIssue,
    TrainingCohort,
    TrainingEnrollment,
)
from modules.tenant.api.base import TenantScopedAPIView

from .serializers import (
    CutoverPlanCreateSerializer,
    CutoverTaskCreateSerializer,
    CutoverTaskTransitionSerializer,
    GateDecisionSerializer,
    GoLiveWaveCreateSerializer,
    GoLiveWaveTransitionSerializer,
    HypercareIssueCreateSerializer,
    HypercareIssueTransitionSerializer,
    MigrationBatchCreateSerializer,
    MigrationBatchTransitionSerializer,
    MigrationIssueCreateSerializer,
    MigrationIssueResolveSerializer,
    TrainingCohortCreateSerializer,
    TrainingEnrollmentCreateSerializer,
    TrainingEnrollmentTransitionSerializer,
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


class GoLiveAPIView(TenantScopedAPIView):
    required_permission = "golive.view"

    def initial(self, request: Request, *args: object, **kwargs: object) -> None:
        super().initial(request, *args, **kwargs)
        self.tenant_context.require(self.required_permission)

    @property
    def actor(self) -> uuid.UUID:
        return self.tenant_context.principal.user.public_id


class OverviewView(GoLiveAPIView):
    def get(self, request: Request) -> Response:
        seed_defaults(self.tenant_context.company)
        payload = go_live_overview(self.tenant_context.company)
        payload["capabilities"] = {
            "can_manage": self.tenant_context.can("golive.manage"),
            "can_migrate": self.tenant_context.can("golive.migration"),
            "can_train": self.tenant_context.can("golive.training"),
            "can_cutover": self.tenant_context.can("golive.cutover"),
            "can_approve": self.tenant_context.can("golive.approve"),
            "can_hypercare": self.tenant_context.can("golive.hypercare"),
            "can_configure": self.tenant_context.can("golive.configure"),
            "can_export": self.tenant_context.can("golive.export"),
        }
        return Response(payload)


class MigrationBatchCreateView(GoLiveAPIView):
    required_permission = "golive.migration"

    def post(self, request: Request) -> Response:
        serializer = MigrationBatchCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            batch = create_migration_batch(
                company=self.tenant_context.company,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(batch.public_id), "code": batch.code, "status": batch.status_code, "version": batch.version}, status=201)


class MigrationBatchTransitionView(GoLiveAPIView):
    required_permission = "golive.migration"

    def post(self, request: Request, batch_id: uuid.UUID) -> Response:
        batch = find(MigrationBatch, company=self.tenant_context.company, public_id=batch_id, message="Migration batch not found")
        serializer = MigrationBatchTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        status_code = data.pop("status_code")
        expected_version = data.pop("expected_version")
        if status_code == "APPROVED" and not self.tenant_context.can("golive.approve"):
            raise ValidationError("golive.approve permission is required for migration approval.")
        try:
            batch = transition_migration_batch(
                batch=batch,
                status_code=status_code,
                expected_version=expected_version,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(batch.public_id), "status": batch.status_code, "version": batch.version})


class MigrationIssueCreateView(GoLiveAPIView):
    required_permission = "golive.migration"

    def post(self, request: Request) -> Response:
        serializer = MigrationIssueCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        batch_id = data.pop("batch_public_id")
        batch = find(MigrationBatch, company=self.tenant_context.company, public_id=batch_id, message="Migration batch not found")
        try:
            issue = create_migration_issue(
                company=self.tenant_context.company,
                batch=batch,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(issue.public_id), "issue_code": issue.issue_code, "version": issue.version}, status=201)


class MigrationIssueResolveView(GoLiveAPIView):
    required_permission = "golive.migration"

    def post(self, request: Request, issue_id: uuid.UUID) -> Response:
        issue = find(MigrationIssue, company=self.tenant_context.company, public_id=issue_id, message="Migration issue not found")
        serializer = MigrationIssueResolveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            issue = resolve_migration_issue(
                issue=issue,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(issue.public_id), "resolved": issue.resolved, "version": issue.version})


class TrainingCohortCreateView(GoLiveAPIView):
    required_permission = "golive.training"

    def post(self, request: Request) -> Response:
        serializer = TrainingCohortCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            cohort = create_training_cohort(
                company=self.tenant_context.company,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(cohort.public_id), "code": cohort.code, "version": cohort.version}, status=201)


class TrainingEnrollmentCreateView(GoLiveAPIView):
    required_permission = "golive.training"

    def post(self, request: Request) -> Response:
        serializer = TrainingEnrollmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        cohort_id = data.pop("cohort_public_id")
        cohort = find(TrainingCohort, company=self.tenant_context.company, public_id=cohort_id, message="Training cohort not found")
        try:
            enrollment = create_training_enrollment(
                company=self.tenant_context.company,
                cohort=cohort,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(enrollment.public_id), "status": enrollment.status_code, "version": enrollment.version}, status=201)


class TrainingEnrollmentTransitionView(GoLiveAPIView):
    required_permission = "golive.training"

    def post(self, request: Request, enrollment_id: uuid.UUID) -> Response:
        enrollment = find(TrainingEnrollment, company=self.tenant_context.company, public_id=enrollment_id, message="Training enrollment not found")
        serializer = TrainingEnrollmentTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            enrollment = transition_training_enrollment(
                enrollment=enrollment,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(enrollment.public_id), "status": enrollment.status_code, "version": enrollment.version})


class CutoverPlanCreateView(GoLiveAPIView):
    required_permission = "golive.cutover"

    def post(self, request: Request) -> Response:
        serializer = CutoverPlanCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            plan = create_cutover_plan(
                company=self.tenant_context.company,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(plan.public_id), "code": plan.code, "version": plan.version}, status=201)


class CutoverTaskCreateView(GoLiveAPIView):
    required_permission = "golive.cutover"

    def post(self, request: Request) -> Response:
        serializer = CutoverTaskCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        plan_id = data.pop("plan_public_id")
        plan = find(CutoverPlan, company=self.tenant_context.company, public_id=plan_id, message="Cutover plan not found")
        try:
            task = create_cutover_task(
                company=self.tenant_context.company,
                plan=plan,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(task.public_id), "code": task.code, "version": task.version}, status=201)


class CutoverTaskTransitionView(GoLiveAPIView):
    required_permission = "golive.cutover"

    def post(self, request: Request, task_id: uuid.UUID) -> Response:
        task = find(CutoverTask, company=self.tenant_context.company, public_id=task_id, message="Cutover task not found")
        serializer = CutoverTaskTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            task = transition_cutover_task(
                task=task,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(task.public_id), "status": task.status_code, "version": task.version})


class GoLiveWaveCreateView(GoLiveAPIView):
    required_permission = "golive.cutover"

    def post(self, request: Request) -> Response:
        serializer = GoLiveWaveCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        plan_id = data.pop("plan_public_id", None)
        plan = find(CutoverPlan, company=self.tenant_context.company, public_id=plan_id, message="Cutover plan not found") if plan_id else None
        try:
            wave = create_go_live_wave(
                company=self.tenant_context.company,
                plan=plan,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(wave.public_id), "code": wave.code, "status": wave.status_code, "version": wave.version}, status=201)


class GoLiveWaveTransitionView(GoLiveAPIView):
    required_permission = "golive.cutover"

    def post(self, request: Request, wave_id: uuid.UUID) -> Response:
        wave = find(GoLiveWave, company=self.tenant_context.company, public_id=wave_id, message="Go-live wave not found")
        serializer = GoLiveWaveTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data["status_code"] == "APPROVED" and not self.tenant_context.can("golive.approve"):
            raise ValidationError("golive.approve permission is required for go-live approval.")
        try:
            wave = transition_go_live_wave(
                wave=wave,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(wave.public_id), "status": wave.status_code, "version": wave.version})


class HypercareIssueCreateView(GoLiveAPIView):
    required_permission = "golive.hypercare"

    def post(self, request: Request) -> Response:
        serializer = HypercareIssueCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        wave_id = data.pop("wave_public_id", None)
        wave = find(GoLiveWave, company=self.tenant_context.company, public_id=wave_id, message="Go-live wave not found") if wave_id else None
        try:
            issue = create_hypercare_issue(
                company=self.tenant_context.company,
                wave=wave,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(issue.public_id), "code": issue.code, "status": issue.status_code, "version": issue.version}, status=201)


class HypercareIssueTransitionView(GoLiveAPIView):
    required_permission = "golive.hypercare"

    def post(self, request: Request, issue_id: uuid.UUID) -> Response:
        issue = find(HypercareIssue, company=self.tenant_context.company, public_id=issue_id, message="Hypercare issue not found")
        serializer = HypercareIssueTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            issue = transition_hypercare_issue(
                issue=issue,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(issue.public_id), "status": issue.status_code, "version": issue.version})


class GateDecisionView(GoLiveAPIView):
    required_permission = "golive.approve"

    def post(self, request: Request, gate_id: uuid.UUID) -> Response:
        gate = find(GoLiveGate, company=self.tenant_context.company, public_id=gate_id, message="Go-live gate not found")
        serializer = GateDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            gate = decide_gate(
                gate=gate,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(gate.public_id), "status": gate.status_code, "version": gate.version})
