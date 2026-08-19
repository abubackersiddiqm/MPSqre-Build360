from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.stabilityops.application.selectors import stability_overview
from modules.stabilityops.application.services import (
    create_endpoint,
    create_incident,
    create_regression,
    decide_gate,
    record_performance_sample,
    run_stability_scan,
    seed_defaults,
    transition_incident,
    transition_regression,
)
from modules.stabilityops.models import (
    ProductionIncident,
    RegressionRecord,
    ServiceEndpoint,
    StabilizationGate,
)
from modules.tenant.api.base import TenantScopedAPIView

from .serializers import (
    EndpointSerializer,
    GateDecisionSerializer,
    IncidentCreateSerializer,
    IncidentTransitionSerializer,
    PerformanceSampleSerializer,
    RegressionCreateSerializer,
    RegressionTransitionSerializer,
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


class StabilityAPIView(TenantScopedAPIView):
    required_permission = "stability.view"

    def initial(self, request: Request, *args: object, **kwargs: object) -> None:
        super().initial(request, *args, **kwargs)
        self.tenant_context.require(self.required_permission)

    @property
    def actor(self) -> uuid.UUID:
        return self.tenant_context.principal.user.public_id


class OverviewView(StabilityAPIView):
    def get(self, request: Request) -> Response:
        seed_defaults(self.tenant_context.company)
        payload = stability_overview(self.tenant_context.company)
        payload["capabilities"] = {
            "can_manage": self.tenant_context.can("stability.manage"),
            "can_scan": self.tenant_context.can("stability.scan"),
            "can_record_telemetry": self.tenant_context.can("stability.telemetry"),
            "can_manage_incidents": self.tenant_context.can("stability.incident"),
            "can_manage_regressions": self.tenant_context.can("stability.regression"),
            "can_decide_gates": self.tenant_context.can("stability.gate"),
            "can_configure": self.tenant_context.can("stability.configure"),
            "can_export": self.tenant_context.can("stability.export"),
        }
        return Response(payload)


class EndpointCreateView(StabilityAPIView):
    required_permission = "stability.configure"

    def post(self, request: Request) -> Response:
        serializer = EndpointSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            endpoint = create_endpoint(
                company=self.tenant_context.company,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(endpoint.public_id), "code": endpoint.code, "version": endpoint.version}, status=201)


class SampleCreateView(StabilityAPIView):
    required_permission = "stability.telemetry"

    def post(self, request: Request) -> Response:
        serializer = PerformanceSampleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        endpoint_id = data.pop("endpoint_public_id", None)
        endpoint = (
            find(ServiceEndpoint, company=self.tenant_context.company, public_id=endpoint_id, message="Monitored endpoint not found")
            if endpoint_id
            else None
        )
        try:
            sample = record_performance_sample(
                company=self.tenant_context.company,
                endpoint=endpoint,
                **data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(sample.public_id), "duration_ms": sample.duration_ms}, status=201)


class ScanRunView(StabilityAPIView):
    required_permission = "stability.scan"

    def post(self, request: Request) -> Response:
        scan = run_stability_scan(
            company=self.tenant_context.company,
            actor_public_id=self.actor,
            correlation_id=correlation_id(request),
        )
        return Response(
            {
                "public_id": str(scan.public_id),
                "status": scan.status_code,
                "checks_total": scan.checks_total,
                "checks_passed": scan.checks_passed,
                "checks_failed": scan.checks_failed,
                "api_p95_ms": scan.api_p95_ms,
                "error_rate_percent": str(scan.error_rate_percent),
                "results": scan.results,
            },
            status=201,
        )


class IncidentCreateView(StabilityAPIView):
    required_permission = "stability.incident"

    def post(self, request: Request) -> Response:
        serializer = IncidentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            incident = create_incident(
                company=self.tenant_context.company,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(incident.public_id), "code": incident.code, "status": incident.status_code}, status=201)


class IncidentTransitionView(StabilityAPIView):
    required_permission = "stability.incident"

    def post(self, request: Request, incident_id: uuid.UUID) -> Response:
        incident = find(ProductionIncident, company=self.tenant_context.company, public_id=incident_id, message="Production incident not found")
        serializer = IncidentTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            incident = transition_incident(
                incident=incident,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(incident.public_id), "status": incident.status_code, "version": incident.version})


class RegressionCreateView(StabilityAPIView):
    required_permission = "stability.regression"

    def post(self, request: Request) -> Response:
        serializer = RegressionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        incident_id = data.pop("incident_public_id", None)
        incident = (
            find(ProductionIncident, company=self.tenant_context.company, public_id=incident_id, message="Production incident not found")
            if incident_id
            else None
        )
        try:
            regression = create_regression(
                company=self.tenant_context.company,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                incident=incident,
                **data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(regression.public_id), "code": regression.code, "status": regression.status_code}, status=201)


class RegressionTransitionView(StabilityAPIView):
    required_permission = "stability.regression"

    def post(self, request: Request, regression_id: uuid.UUID) -> Response:
        regression = find(RegressionRecord, company=self.tenant_context.company, public_id=regression_id, message="Regression not found")
        serializer = RegressionTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            regression = transition_regression(
                regression=regression,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(regression.public_id), "status": regression.status_code, "version": regression.version})


class GateDecisionView(StabilityAPIView):
    required_permission = "stability.gate"

    def post(self, request: Request, gate_id: uuid.UUID) -> Response:
        gate = find(StabilizationGate, company=self.tenant_context.company, public_id=gate_id, message="Stabilization gate not found")
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
