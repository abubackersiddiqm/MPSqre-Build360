from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.fieldops.api.views import stage_payload
from modules.platform.actors import request_actor
from modules.safety.api.serializers import IncidentCreateSerializer, ObservationCreateSerializer
from modules.safety.application.services import create_observation, report_incident
from modules.safety.models import SafetyIncident, SafetyObservation
from modules.tenant.api.base import TenantScopedAPIView


def _validation(exc: DjangoValidationError) -> ValidationError:
    return ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)


def incident_payload(i: SafetyIncident) -> dict[str, object]:
    return {
        "public_id": str(i.public_id),
        "incident_number": i.incident_number,
        "title": i.title,
        "severity": i.severity,
        "project": {
            "public_id": str(i.project.public_id),
            "code": i.project.code,
            "name": i.project.name,
        },
        "stage": stage_payload(i.stage),
        "occurred_at": i.occurred_at,
        "version": i.version,
    }


class SafetySummaryView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("safety.dashboard.read")
        inc = SafetyIncident.objects.filter(company=self.tenant_context.company)
        obs = SafetyObservation.objects.filter(company=self.tenant_context.company)
        return Response(
            {
                "incidents": inc.count(),
                "open_incidents": inc.exclude(stage__outcome__in=["complete", "cancelled"]).count(),
                "critical_incidents": inc.filter(severity__in=["critical", "fatal"]).count(),
                "observations": obs.count(),
                "open_actions": obs.filter(action_required=True, closed_at__isnull=True).count(),
            }
        )


class IncidentListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("safety.incident.read")
        items = (
            SafetyIncident.objects.select_related("project", "stage")
            .filter(company=self.tenant_context.company)
            .order_by("-occurred_at")[:200]
        )
        return Response({"items": [incident_payload(i) for i in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("safety.incident.report")
        s = IncidentCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        values = dict(s.validated_data)
        values["reported_by_membership_public_id"] = self.tenant_context.membership.public_id
        try:
            i = report_incident(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **values,
            )
        except DjangoValidationError as e:
            raise _validation(e) from e
        return Response(incident_payload(i), status=201)


class ObservationListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("safety.observation.read")
        items = (
            SafetyObservation.objects.select_related("project")
            .filter(company=self.tenant_context.company)
            .order_by("-observed_at")[:200]
        )
        return Response(
            {
                "items": [
                    {
                        "public_id": str(i.public_id),
                        "observation_number": i.observation_number,
                        "observation_type": i.observation_type,
                        "description": i.description,
                        "project": {
                            "public_id": str(i.project.public_id),
                            "code": i.project.code,
                            "name": i.project.name,
                        },
                        "is_positive": i.is_positive,
                        "action_required": i.action_required,
                        "observed_at": i.observed_at,
                        "version": i.version,
                    }
                    for i in items
                ]
            }
        )

    def post(self, request: Request) -> Response:
        self.tenant_context.require("safety.observation.manage")
        s = ObservationCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            i = create_observation(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **s.validated_data,
            )
        except DjangoValidationError as e:
            raise _validation(e) from e
        return Response(
            {
                "public_id": str(i.public_id),
                "observation_number": i.observation_number,
                "version": i.version,
            },
            status=201,
        )
