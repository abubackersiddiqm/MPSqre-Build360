from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.cloudops.api.serializers import (
    BackupExecutionSerializer,
    BackupPolicyCreateSerializer,
    CloudTargetCreateSerializer,
    CloudTargetTransitionSerializer,
    DeploymentCreateSerializer,
    DeploymentTransitionSerializer,
    PipelineCreateSerializer,
    RestoreExerciseCreateSerializer,
    RestoreExerciseTransitionSerializer,
    SecretPolicyCreateSerializer,
    SecretRotationSerializer,
)
from modules.cloudops.application.services import (
    cloudops_portfolio,
    cloudops_summary,
    create_backup_policy,
    create_deployment,
    create_pipeline,
    create_restore_exercise,
    create_secret_policy,
    create_target,
    deployment_readiness,
    record_backup_execution,
    record_secret_rotation,
    transition_deployment,
    transition_restore_exercise,
    transition_target,
)
from modules.cloudops.models import (
    BackupExecution,
    BackupPolicy,
    CloudTarget,
    DeploymentExecution,
    DeploymentPipeline,
    RestoreExercise,
    SecretRotationPolicy,
)
from modules.platform.actors import request_actor
from modules.tenant.api.base import TenantScopedAPIView


def _validation(exc: DjangoValidationError) -> ValidationError:
    return ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)


def _environment(item) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "code": item.code,
        "name": item.name,
        "environment_type": item.environment_type,
        "base_url": item.base_url,
        "region": item.region,
        "data_residency": item.data_residency,
        "is_active": item.is_active,
    }


def _target(item: CloudTarget) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "environment": _environment(item.environment),
        "code": item.code,
        "name": item.name,
        "provider": item.provider,
        "region": item.region,
        "data_residency": item.data_residency,
        "backend_service": item.backend_service,
        "frontend_service": item.frontend_service,
        "database_service": item.database_service,
        "cache_service": item.cache_service,
        "object_storage_service": item.object_storage_service,
        "worker_service": item.worker_service,
        "secret_manager_service": item.secret_manager_service,
        "status": item.status,
        "production_approved": item.production_approved,
        "version": item.version,
    }


def _pipeline(item: DeploymentPipeline) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "target": {
            "public_id": str(item.target.public_id),
            "code": item.target.code,
            "name": item.target.name,
        },
        "code": item.code,
        "name": item.name,
        "source_branch": item.source_branch,
        "trigger_mode": item.trigger_mode,
        "quality_gates": item.quality_gates,
        "requires_approval": item.requires_approval,
        "is_active": item.is_active,
        "version": item.version,
    }


def _release(item) -> dict[str, object] | None:
    if item is None:
        return None
    return {
        "public_id": str(item.public_id),
        "version_label": item.version_label,
        "release_name": item.release_name,
        "status": item.status,
    }


def _deployment(item: DeploymentExecution) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "pipeline": _pipeline(item.pipeline),
        "release": _release(item.release),
        "status": item.status,
        "source_revision": item.source_revision,
        "artifact_sha256": item.artifact_sha256,
        "migration_plan_sha256": item.migration_plan_sha256,
        "deployment_url": item.deployment_url,
        "requested_by_public_id": str(item.requested_by_public_id),
        "approved_by_public_id": (
            str(item.approved_by_public_id) if item.approved_by_public_id else None
        ),
        "executed_by_public_id": (
            str(item.executed_by_public_id) if item.executed_by_public_id else None
        ),
        "started_at": item.started_at,
        "finished_at": item.finished_at,
        "logs_sha256": item.logs_sha256,
        "error_summary": item.error_summary,
        "rollback_reference": item.rollback_reference,
        "readiness": deployment_readiness(item),
        "version": item.version,
    }


def _backup_policy(item: BackupPolicy) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "target": {
            "public_id": str(item.target.public_id),
            "code": item.target.code,
            "name": item.target.name,
        },
        "code": item.code,
        "name": item.name,
        "resource_type": item.resource_type,
        "schedule_cron": item.schedule_cron,
        "retention_days": item.retention_days,
        "encryption_required": item.encryption_required,
        "point_in_time_recovery": item.point_in_time_recovery,
        "is_active": item.is_active,
        "version": item.version,
    }


def _backup_execution(item: BackupExecution) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "policy": {
            "public_id": str(item.policy.public_id),
            "code": item.policy.code,
            "name": item.policy.name,
        },
        "status": item.status,
        "backup_reference": item.backup_reference,
        "backup_sha256": item.backup_sha256,
        "size_bytes": item.size_bytes,
        "recovery_point_at": item.recovery_point_at,
        "started_at": item.started_at,
        "finished_at": item.finished_at,
        "evidence_sha256": item.evidence_sha256,
        "error_summary": item.error_summary,
    }


def _restore(item: RestoreExercise) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "target": {
            "public_id": str(item.target.public_id),
            "code": item.target.code,
            "name": item.target.name,
        },
        "backup_execution": {
            "public_id": str(item.backup_execution.public_id),
            "policy_code": item.backup_execution.policy.code,
        },
        "status": item.status,
        "requested_by_public_id": str(item.requested_by_public_id),
        "reviewed_by_public_id": (
            str(item.reviewed_by_public_id) if item.reviewed_by_public_id else None
        ),
        "started_at": item.started_at,
        "finished_at": item.finished_at,
        "measured_rpo_minutes": item.measured_rpo_minutes,
        "measured_rto_minutes": item.measured_rto_minutes,
        "evidence_sha256": item.evidence_sha256,
        "notes": item.notes,
        "version": item.version,
    }


def _secret(item: SecretRotationPolicy) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "target": {
            "public_id": str(item.target.public_id),
            "code": item.target.code,
            "name": item.target.name,
        },
        "code": item.code,
        "name": item.name,
        "secret_provider": item.secret_provider,
        "secret_reference": item.secret_reference,
        "rotation_interval_days": item.rotation_interval_days,
        "last_rotated_at": item.last_rotated_at,
        "next_rotation_at": item.next_rotation_at,
        "status": item.status,
        "version": item.version,
    }


class CloudopsSummaryView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("cloudops.dashboard.read")
        return Response(cloudops_summary(self.tenant_context.company))


class CloudopsPortfolioView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("cloudops.dashboard.read")
        portfolio = cloudops_portfolio(self.tenant_context.company)
        return Response(
            {
                "summary": portfolio["summary"],
                "current_user_public_id": str(self.tenant_context.principal.user.public_id),
                "environments": [_environment(item) for item in portfolio["environments"]],
                "targets": [_target(item) for item in portfolio["targets"]],
                "pipelines": [_pipeline(item) for item in portfolio["pipelines"]],
                "deployments": [
                    _deployment(item) for item in portfolio["deployments"]
                ],
                "backup_policies": [
                    _backup_policy(item) for item in portfolio["backup_policies"]
                ],
                "backup_executions": [
                    _backup_execution(item)
                    for item in portfolio["backup_executions"]
                ],
                "restore_exercises": [
                    _restore(item) for item in portfolio["restore_exercises"]
                ],
                "secret_policies": [
                    _secret(item) for item in portfolio["secret_policies"]
                ],
            }
        )


class CloudTargetListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("cloudops.target.read")
        values = CloudTarget.objects.filter(company=self.tenant_context.company).select_related(
            "environment"
        )
        return Response([_target(item) for item in values])

    def post(self, request: Request) -> Response:
        self.tenant_context.require("cloudops.target.manage")
        serializer = CloudTargetCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_target(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_target(item), status=201)


class CloudTargetTransitionView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("cloudops.target.activate")
        serializer = CloudTargetTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_target(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                target_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_target(item))


class PipelineListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("cloudops.pipeline.read")
        values = DeploymentPipeline.objects.filter(
            company=self.tenant_context.company
        ).select_related("target", "target__environment")
        return Response([_pipeline(item) for item in values])

    def post(self, request: Request) -> Response:
        self.tenant_context.require("cloudops.pipeline.manage")
        serializer = PipelineCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_pipeline(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_pipeline(item), status=201)


class DeploymentListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("cloudops.deployment.read")
        values = DeploymentExecution.objects.filter(
            company=self.tenant_context.company
        ).select_related("pipeline", "pipeline__target", "release")[:100]
        return Response([_deployment(item) for item in values])

    def post(self, request: Request) -> Response:
        self.tenant_context.require("cloudops.deployment.create")
        serializer = DeploymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_deployment(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_deployment(item), status=201)


class DeploymentTransitionView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        serializer = DeploymentTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target_status = serializer.validated_data["target_status"]
        permission = {
            DeploymentExecution.Status.VALIDATED: "cloudops.deployment.validate",
            DeploymentExecution.Status.APPROVED: "cloudops.deployment.approve",
            DeploymentExecution.Status.RUNNING: "cloudops.deployment.execute",
            DeploymentExecution.Status.SUCCEEDED: "cloudops.deployment.execute",
            DeploymentExecution.Status.FAILED: "cloudops.deployment.execute",
            DeploymentExecution.Status.ROLLED_BACK: "cloudops.deployment.rollback",
            DeploymentExecution.Status.REQUESTED: "cloudops.deployment.create",
        }[target_status]
        self.tenant_context.require(permission)
        try:
            item = transition_deployment(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                deployment_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_deployment(item))


class BackupPolicyListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("cloudops.backup.read")
        values = BackupPolicy.objects.filter(company=self.tenant_context.company).select_related(
            "target"
        )
        return Response([_backup_policy(item) for item in values])

    def post(self, request: Request) -> Response:
        self.tenant_context.require("cloudops.backup.manage")
        serializer = BackupPolicyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_backup_policy(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_backup_policy(item), status=201)


class BackupExecutionListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("cloudops.backup.read")
        values = BackupExecution.objects.filter(
            company=self.tenant_context.company
        ).select_related("policy", "policy__target")[:100]
        return Response([_backup_execution(item) for item in values])

    def post(self, request: Request) -> Response:
        self.tenant_context.require("cloudops.backup.execute")
        serializer = BackupExecutionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = record_backup_execution(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_backup_execution(item), status=201)


class RestoreExerciseListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("cloudops.restore.read")
        values = RestoreExercise.objects.filter(
            company=self.tenant_context.company
        ).select_related("target", "backup_execution", "backup_execution__policy")[:100]
        return Response([_restore(item) for item in values])

    def post(self, request: Request) -> Response:
        self.tenant_context.require("cloudops.restore.create")
        serializer = RestoreExerciseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_restore_exercise(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_restore(item), status=201)


class RestoreExerciseTransitionView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        serializer = RestoreExerciseTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        permission = (
            "cloudops.restore.approve"
            if serializer.validated_data["target_status"] == RestoreExercise.Status.APPROVED
            else "cloudops.restore.execute"
        )
        self.tenant_context.require(permission)
        try:
            item = transition_restore_exercise(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                exercise_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_restore(item))


class SecretPolicyListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("cloudops.secret.read")
        values = SecretRotationPolicy.objects.filter(
            company=self.tenant_context.company
        ).select_related("target")
        return Response([_secret(item) for item in values])

    def post(self, request: Request) -> Response:
        self.tenant_context.require("cloudops.secret.manage")
        serializer = SecretPolicyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_secret_policy(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_secret(item), status=201)


class SecretRotationView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("cloudops.secret.rotate")
        serializer = SecretRotationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = record_secret_rotation(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                policy_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_secret(item))
