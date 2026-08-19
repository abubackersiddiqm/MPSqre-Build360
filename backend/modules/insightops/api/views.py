from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.insightops.application.selectors import insight_overview
from modules.insightops.application.services import (
    create_action,
    create_benefit,
    create_board_report,
    create_kpi,
    create_objective,
    create_snapshot,
    record_benefit_measurement,
    record_observation,
    seed_defaults,
    transition_action,
    transition_board_report,
    transition_snapshot,
)
from modules.insightops.models import (
    BenefitPlan,
    BoardReport,
    ExecutiveAction,
    KPIDefinition,
    PortfolioSnapshot,
    StrategicObjective,
)
from modules.tenant.api.base import TenantScopedAPIView

from .serializers import (
    ActionCreateSerializer,
    ActionTransitionSerializer,
    BenefitCreateSerializer,
    BenefitMeasurementCreateSerializer,
    BoardReportCreateSerializer,
    KPICreateSerializer,
    ObjectiveCreateSerializer,
    ObservationCreateSerializer,
    SnapshotCreateSerializer,
    TransitionSerializer,
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


class InsightAPIView(TenantScopedAPIView):
    required_permission = "insights.view"

    def initial(self, request: Request, *args: object, **kwargs: object) -> None:
        super().initial(request, *args, **kwargs)
        self.tenant_context.require(self.required_permission)

    @property
    def actor(self) -> uuid.UUID:
        return self.tenant_context.principal.user.public_id


class OverviewView(InsightAPIView):
    def get(self, request: Request) -> Response:
        seed_defaults(self.tenant_context.company)
        return Response(insight_overview(self.tenant_context.company))


class ObjectiveCreateView(InsightAPIView):
    required_permission = "insights.objective"

    def post(self, request: Request) -> Response:
        serializer = ObjectiveCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_objective(company=self.tenant_context.company, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "code": item.code}, status=201)


class KPICreateView(InsightAPIView):
    required_permission = "insights.kpi"

    def post(self, request: Request) -> Response:
        serializer = KPICreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        objective_id = data.pop("objective_public_id", None)
        objective = find(StrategicObjective, company=self.tenant_context.company, public_id=objective_id, message="Objective not found") if objective_id else None
        try:
            item = create_kpi(company=self.tenant_context.company, objective=objective, actor_public_id=self.actor, correlation_id=correlation_id(request), **data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "code": item.code}, status=201)


class ObservationCreateView(InsightAPIView):
    required_permission = "insights.kpi"

    def post(self, request: Request) -> Response:
        serializer = ObservationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        kpi = find(KPIDefinition, company=self.tenant_context.company, public_id=data.pop("kpi_public_id"), message="KPI not found")
        try:
            item = record_observation(company=self.tenant_context.company, kpi=kpi, actor_public_id=self.actor, correlation_id=correlation_id(request), **data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id)}, status=201)


class SnapshotCreateView(InsightAPIView):
    required_permission = "insights.portfolio"

    def post(self, request: Request) -> Response:
        serializer = SnapshotCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_snapshot(company=self.tenant_context.company, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "code": item.code}, status=201)


class SnapshotTransitionView(InsightAPIView):
    required_permission = "insights.approve"

    def post(self, request: Request, snapshot_id: uuid.UUID) -> Response:
        snapshot = find(PortfolioSnapshot, company=self.tenant_context.company, public_id=snapshot_id, message="Portfolio snapshot not found")
        serializer = TransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            snapshot = transition_snapshot(snapshot=snapshot, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(snapshot.public_id), "status": snapshot.status_code, "version": snapshot.version})


class BenefitCreateView(InsightAPIView):
    required_permission = "insights.benefit"

    def post(self, request: Request) -> Response:
        serializer = BenefitCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        objective_id = data.pop("objective_public_id", None)
        objective = find(StrategicObjective, company=self.tenant_context.company, public_id=objective_id, message="Objective not found") if objective_id else None
        try:
            item = create_benefit(company=self.tenant_context.company, objective=objective, actor_public_id=self.actor, correlation_id=correlation_id(request), **data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "code": item.code}, status=201)


class BenefitMeasurementCreateView(InsightAPIView):
    required_permission = "insights.benefit"

    def post(self, request: Request) -> Response:
        serializer = BenefitMeasurementCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        benefit = find(BenefitPlan, company=self.tenant_context.company, public_id=data.pop("benefit_public_id"), message="Benefit plan not found")
        data.setdefault("currency", benefit.currency)
        try:
            item = record_benefit_measurement(company=self.tenant_context.company, benefit=benefit, actor_public_id=self.actor, correlation_id=correlation_id(request), **data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id)}, status=201)


class ActionCreateView(InsightAPIView):
    required_permission = "insights.action"

    def post(self, request: Request) -> Response:
        serializer = ActionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_action(company=self.tenant_context.company, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "code": item.code}, status=201)


class ActionTransitionView(InsightAPIView):
    required_permission = "insights.action"

    def post(self, request: Request, action_id: uuid.UUID) -> Response:
        action = find(ExecutiveAction, company=self.tenant_context.company, public_id=action_id, message="Executive action not found")
        serializer = ActionTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            action = transition_action(action=action, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(action.public_id), "status": action.status_code, "version": action.version})


class BoardReportCreateView(InsightAPIView):
    required_permission = "insights.board"

    def post(self, request: Request) -> Response:
        serializer = BoardReportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_board_report(company=self.tenant_context.company, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "code": item.code}, status=201)


class BoardReportTransitionView(InsightAPIView):
    required_permission = "insights.approve"

    def post(self, request: Request, report_id: uuid.UUID) -> Response:
        report = find(BoardReport, company=self.tenant_context.company, public_id=report_id, message="Board report not found")
        serializer = TransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            report = transition_board_report(report=report, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(report.public_id), "status": report.status_code, "version": report.version})
