from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.adminops.api.serializers import (
    EnvironmentCreateSerializer,
    FeatureFlagCreateSerializer,
    FeatureFlagUpdateSerializer,
    HealthSnapshotSerializer,
    IncidentCreateSerializer,
    IncidentTransitionSerializer,
    MaintenanceCreateSerializer,
    MaintenanceTransitionSerializer,
    ReleaseCheckSerializer,
    ReleaseCreateSerializer,
    ReleaseTransitionSerializer,
    RunbookCreateSerializer,
    ServiceObjectiveSerializer,
)
from modules.adminops.application.services import (
    adminops_summary,
    create_environment,
    create_feature_flag,
    create_incident,
    create_maintenance_window,
    create_release,
    create_runbook,
    create_service_objective,
    record_health_snapshot,
    record_release_check,
    release_readiness,
    transition_incident,
    transition_maintenance_window,
    transition_release,
    update_feature_flag,
)
from modules.adminops.models import (
    FeatureFlag,
    HealthSnapshot,
    Incident,
    MaintenanceWindow,
    ReleaseCheck,
    ReleaseRecord,
    Runbook,
    RuntimeEnvironment,
    ServiceObjective,
)
from modules.platform.actors import request_actor
from modules.tenant.api.base import TenantScopedAPIView


def _validation(exc: DjangoValidationError) -> ValidationError:
    return ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)


def _environment(item: RuntimeEnvironment) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "code": item.code,
        "name": item.name,
        "environment_type": item.environment_type,
        "base_url": item.base_url,
        "region": item.region,
        "data_residency": item.data_residency,
        "production_data_allowed": item.production_data_allowed,
        "requires_change_approval": item.requires_change_approval,
        "is_active": item.is_active,
        "version": item.version,
    }


def _check(item: ReleaseCheck) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "release_public_id": str(item.release.public_id),
        "code": item.code,
        "name": item.name,
        "category": item.category,
        "status": item.status,
        "is_critical": item.is_critical,
        "target_value": item.target_value,
        "measured_value": item.measured_value,
        "evidence": item.evidence,
        "waiver_reason": item.waiver_reason,
        "checked_at": item.checked_at,
    }


def _release(item: ReleaseRecord) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "environment": _environment(item.environment),
        "version_label": item.version_label,
        "release_name": item.release_name,
        "source_revision": item.source_revision,
        "artifact_sha256": item.artifact_sha256,
        "migration_plan_sha256": item.migration_plan_sha256,
        "change_summary": item.change_summary,
        "status": item.status,
        "requested_by_public_id": str(item.requested_by_public_id),
        "validated_at": item.validated_at,
        "approved_at": item.approved_at,
        "deployed_at": item.deployed_at,
        "rollback_reference": item.rollback_reference,
        "readiness": release_readiness(item),
        "checks": [_check(check) for check in item.checks.all()],
        "created_at": item.created_at,
        "version": item.version,
    }


def _objective(item: ServiceObjective) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "code": item.code,
        "name": item.name,
        "service_code": item.service_code,
        "indicator_type": item.indicator_type,
        "target_value": str(item.target_value),
        "warning_threshold": str(item.warning_threshold),
        "critical_threshold": str(item.critical_threshold),
        "window_days": item.window_days,
        "unit_code": item.unit_code,
        "is_active": item.is_active,
        "version": item.version,
    }


def _health(item: HealthSnapshot) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "environment": {
            "public_id": str(item.environment.public_id),
            "code": item.environment.code,
        },
        "service_code": item.service_code,
        "status": item.status,
        "latency_ms": item.latency_ms,
        "observed_value": str(item.observed_value) if item.observed_value is not None else None,
        "source": item.source,
        "details": item.details,
        "checked_at": item.checked_at,
    }


def _incident(item: Incident) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "environment": {
            "public_id": str(item.environment.public_id),
            "code": item.environment.code,
        },
        "number": item.number,
        "severity": item.severity,
        "title": item.title,
        "summary": item.summary,
        "status": item.status,
        "detected_at": item.detected_at,
        "acknowledged_at": item.acknowledged_at,
        "mitigated_at": item.mitigated_at,
        "resolved_at": item.resolved_at,
        "closed_at": item.closed_at,
        "customer_impact": item.customer_impact,
        "root_cause": item.root_cause,
        "corrective_actions": item.corrective_actions,
        "postmortem_required": item.postmortem_required,
        "postmortem_reference": item.postmortem_reference,
        "version": item.version,
    }


def _runbook(item: Runbook) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "code": item.code,
        "title": item.title,
        "category": item.category,
        "purpose": item.purpose,
        "steps": item.steps,
        "review_due_at": item.review_due_at,
        "is_active": item.is_active,
        "version": item.version,
    }


def _flag(item: FeatureFlag) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "code": item.code,
        "name": item.name,
        "description": item.description,
        "is_enabled": item.is_enabled,
        "rollout_percent": item.rollout_percent,
        "scope": item.scope,
        "requires_approval": item.requires_approval,
        "approved_at": item.approved_at,
        "version": item.version,
    }


def _maintenance(item: MaintenanceWindow) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "environment": {
            "public_id": str(item.environment.public_id),
            "code": item.environment.code,
        },
        "reference": item.reference,
        "title": item.title,
        "reason": item.reason,
        "starts_at": item.starts_at,
        "ends_at": item.ends_at,
        "status": item.status,
        "affected_services": item.affected_services,
        "approved_at": item.approved_at,
        "version": item.version,
    }


class AdminopsSummaryView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("adminops.dashboard.read")
        return Response(adminops_summary(self.tenant_context.company))


class EnvironmentListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("adminops.environment.read")
        items = RuntimeEnvironment.objects.filter(company=self.tenant_context.company)[:100]
        return Response({"items": [_environment(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("adminops.environment.manage")
        serializer = EnvironmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_environment(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_environment(item), status=201)


class ReleaseListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("adminops.release.read")
        items = (
            ReleaseRecord.objects.select_related("environment")
            .prefetch_related("checks")
            .filter(company=self.tenant_context.company)[:200]
        )
        return Response({"items": [_release(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("adminops.release.create")
        serializer = ReleaseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_release(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_release(item), status=201)


class ReleaseDetailView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        serializer = ReleaseTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target = serializer.validated_data["target_status"]
        permission = {
            ReleaseRecord.Status.VALIDATED: "adminops.release.validate",
            ReleaseRecord.Status.APPROVED: "adminops.release.approve",
            ReleaseRecord.Status.DEPLOYED: "adminops.release.deploy",
            ReleaseRecord.Status.ROLLED_BACK: "adminops.release.rollback",
            ReleaseRecord.Status.FAILED: "adminops.release.validate",
            ReleaseRecord.Status.DRAFT: "adminops.release.create",
        }[target]
        self.tenant_context.require(permission)
        try:
            item = transition_release(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                release_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        item = (
            ReleaseRecord.objects.select_related("environment")
            .prefetch_related("checks")
            .get(pk=item.pk)
        )
        return Response(_release(item))


class ReleaseCheckListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("adminops.check.read")
        items = ReleaseCheck.objects.select_related("release").filter(
            company=self.tenant_context.company
        )[:500]
        return Response({"items": [_check(item) for item in items]})

    def post(self, request: Request) -> Response:
        serializer = ReleaseCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data["status"] == ReleaseCheck.Status.WAIVED:
            self.tenant_context.require("adminops.check.waive")
        else:
            self.tenant_context.require("adminops.check.manage")
        try:
            item = record_release_check(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_check(item), status=201)


class ServiceObjectiveListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("adminops.slo.read")
        items = ServiceObjective.objects.filter(company=self.tenant_context.company)[:200]
        return Response({"items": [_objective(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("adminops.slo.manage")
        serializer = ServiceObjectiveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_service_objective(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_objective(item), status=201)


class HealthSnapshotListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("adminops.health.read")
        items = HealthSnapshot.objects.select_related("environment").filter(
            company=self.tenant_context.company
        )[:300]
        return Response({"items": [_health(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("adminops.health.record")
        serializer = HealthSnapshotSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = record_health_snapshot(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_health(item), status=201)


class IncidentListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("adminops.incident.read")
        items = Incident.objects.select_related("environment").filter(
            company=self.tenant_context.company
        )[:300]
        return Response({"items": [_incident(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("adminops.incident.create")
        serializer = IncidentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_incident(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_incident(item), status=201)


class IncidentDetailView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        serializer = IncidentTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target = serializer.validated_data["target_status"]
        permission = (
            "adminops.incident.close"
            if target == Incident.Status.CLOSED
            else "adminops.incident.manage"
        )
        self.tenant_context.require(permission)
        try:
            item = transition_incident(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                incident_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        item = Incident.objects.select_related("environment").get(pk=item.pk)
        return Response(_incident(item))


class RunbookListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("adminops.runbook.read")
        items = Runbook.objects.filter(company=self.tenant_context.company)[:300]
        return Response({"items": [_runbook(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("adminops.runbook.manage")
        serializer = RunbookCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_runbook(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_runbook(item), status=201)


class FeatureFlagListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("adminops.feature_flag.read")
        items = FeatureFlag.objects.filter(company=self.tenant_context.company)[:300]
        return Response({"items": [_flag(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("adminops.feature_flag.manage")
        serializer = FeatureFlagCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_feature_flag(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_flag(item), status=201)


class FeatureFlagDetailView(TenantScopedAPIView):
    def patch(self, request: Request, public_id: uuid.UUID) -> Response:
        serializer = FeatureFlagUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        permission = (
            "adminops.feature_flag.approve"
            if serializer.validated_data["is_enabled"]
            else "adminops.feature_flag.manage"
        )
        self.tenant_context.require(permission)
        try:
            item = update_feature_flag(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                flag_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_flag(item))


class MaintenanceListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("adminops.maintenance.read")
        items = MaintenanceWindow.objects.select_related("environment").filter(
            company=self.tenant_context.company
        )[:300]
        return Response({"items": [_maintenance(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("adminops.maintenance.manage")
        serializer = MaintenanceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_maintenance_window(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_maintenance(item), status=201)


class MaintenanceDetailView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        serializer = MaintenanceTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target = serializer.validated_data["target_status"]
        self.tenant_context.require(
            "adminops.maintenance.approve"
            if target == MaintenanceWindow.Status.APPROVED
            else "adminops.maintenance.manage"
        )
        try:
            item = transition_maintenance_window(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                window_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        item = MaintenanceWindow.objects.select_related("environment").get(pk=item.pk)
        return Response(_maintenance(item))
