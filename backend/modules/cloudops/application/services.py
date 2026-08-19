from __future__ import annotations

import hashlib
import json
import uuid
from datetime import timedelta
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from modules.adminops.application.services import release_readiness
from modules.adminops.models import ReleaseRecord, RuntimeEnvironment
from modules.cloudops.models import (
    BackupExecution,
    BackupPolicy,
    CloudTarget,
    DeploymentExecution,
    DeploymentPipeline,
    RestoreExercise,
    SecretRotationPolicy,
)
from modules.platform.actors import RequestActor
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.tenant.models import Company


def _audit(
    *,
    actor: RequestActor,
    company: Company,
    action: str,
    entity_type: str,
    entity_public_id: uuid.UUID,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason_code: str = "",
) -> None:
    append_audit(
        AuditRecord(
            action=action,
            entity_type=entity_type,
            entity_public_id=entity_public_id,
            actor_public_id=actor.user_public_id,
            company_public_id=company.public_id,
            request_id=actor.request_id,
            correlation_id=actor.request_id,
            ip_address=actor.ip_address,
            user_agent=actor.user_agent,
            reason_code=reason_code[:100],
            before=before or {},
            after=after or {},
        )
    )


def _event(
    *,
    actor: RequestActor,
    company: Company,
    event_type: str,
    aggregate_type: str,
    aggregate_public_id: uuid.UUID,
    aggregate_version: int,
    payload: dict[str, Any],
) -> None:
    append_event(
        EventRecord(
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_public_id=aggregate_public_id,
            aggregate_version=aggregate_version,
            correlation_id=actor.request_id,
            company_public_id=company.public_id,
            payload=payload,
        )
    )


def _sha256_payload(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def cloudops_summary(company: Company) -> dict[str, Any]:
    now = timezone.now()
    deployments = DeploymentExecution.objects.filter(company=company)
    backups = BackupExecution.objects.filter(company=company)
    restores = RestoreExercise.objects.filter(company=company)
    secrets = SecretRotationPolicy.objects.filter(company=company)
    latest_deployment = deployments.order_by("-created_at").first()
    latest_backup = backups.order_by("-started_at").first()
    return {
        "targets": CloudTarget.objects.filter(company=company).count(),
        "active_targets": CloudTarget.objects.filter(
            company=company,
            status=CloudTarget.Status.ACTIVE,
        ).count(),
        "production_targets": CloudTarget.objects.filter(
            company=company,
            environment__environment_type=RuntimeEnvironment.EnvironmentType.PRODUCTION,
        ).count(),
        "pipelines": DeploymentPipeline.objects.filter(
            company=company,
            is_active=True,
        ).count(),
        "deployments": deployments.count(),
        "failed_deployments": deployments.filter(
            status=DeploymentExecution.Status.FAILED,
        ).count(),
        "latest_deployment_status": latest_deployment.status if latest_deployment else None,
        "backup_policies": BackupPolicy.objects.filter(
            company=company,
            is_active=True,
        ).count(),
        "verified_backups": backups.filter(status=BackupExecution.Status.VERIFIED).count(),
        "latest_backup_status": latest_backup.status if latest_backup else None,
        "passed_restore_exercises": restores.filter(
            status__in=[RestoreExercise.Status.PASSED, RestoreExercise.Status.APPROVED]
        ).count(),
        "secrets_due": secrets.filter(
            Q(status__in=[SecretRotationPolicy.Status.DUE, SecretRotationPolicy.Status.OVERDUE])
            | Q(next_rotation_at__lte=now)
        ).count(),
    }


def cloudops_portfolio(company: Company) -> dict[str, Any]:
    return {
        "summary": cloudops_summary(company),
        "environments": RuntimeEnvironment.objects.filter(company=company).order_by(
            "environment_type", "code"
        ),
        "targets": CloudTarget.objects.filter(company=company).select_related("environment"),
        "pipelines": DeploymentPipeline.objects.filter(company=company).select_related(
            "target", "target__environment"
        ),
        "deployments": DeploymentExecution.objects.filter(company=company).select_related(
            "pipeline", "pipeline__target", "release"
        )[:50],
        "backup_policies": BackupPolicy.objects.filter(company=company).select_related(
            "target"
        ),
        "backup_executions": BackupExecution.objects.filter(company=company).select_related(
            "policy", "policy__target"
        )[:50],
        "restore_exercises": RestoreExercise.objects.filter(company=company).select_related(
            "target", "backup_execution", "backup_execution__policy"
        )[:50],
        "secret_policies": SecretRotationPolicy.objects.filter(company=company).select_related(
            "target"
        ),
    }


@transaction.atomic
def create_target(
    *,
    company: Company,
    actor: RequestActor,
    environment_public_id: uuid.UUID,
    code: str,
    name: str,
    provider: str,
    region: str,
    data_residency: str,
    backend_service: str = "",
    frontend_service: str = "",
    database_service: str = "",
    cache_service: str = "",
    object_storage_service: str = "",
    worker_service: str = "",
    secret_manager_service: str = "",
) -> CloudTarget:
    environment = RuntimeEnvironment.objects.filter(
        company=company,
        public_id=environment_public_id,
        is_active=True,
    ).first()
    if environment is None:
        raise ValidationError("Runtime environment was not found")
    target = CloudTarget(
        company=company,
        environment=environment,
        code=code.strip().upper(),
        name=name.strip(),
        provider=provider,
        region=region.strip(),
        data_residency=data_residency.strip(),
        backend_service=backend_service.strip(),
        frontend_service=frontend_service.strip(),
        database_service=database_service.strip(),
        cache_service=cache_service.strip(),
        object_storage_service=object_storage_service.strip(),
        worker_service=worker_service.strip(),
        secret_manager_service=secret_manager_service.strip(),
    )
    target.full_clean()
    target.save()
    _audit(
        actor=actor,
        company=company,
        action="cloudops.target.created",
        entity_type="cloud_target",
        entity_public_id=target.public_id,
        after={"code": target.code, "provider": target.provider},
    )
    _event(
        actor=actor,
        company=company,
        event_type="cloudops.target.created",
        aggregate_type="cloud_target",
        aggregate_public_id=target.public_id,
        aggregate_version=target.version,
        payload={"code": target.code, "provider": target.provider},
    )
    return target


@transaction.atomic
def transition_target(
    *,
    company: Company,
    actor: RequestActor,
    target_public_id: uuid.UUID,
    target_status: str,
    expected_version: int,
    production_approved: bool = False,
    reason: str = "",
) -> CloudTarget:
    target = (
        CloudTarget.objects.select_for_update()
        .select_related("environment")
        .filter(company=company, public_id=target_public_id)
        .first()
    )
    if target is None:
        raise ValidationError("Cloud target was not found")
    if target.version != expected_version:
        raise ValidationError("Cloud target version conflict")
    allowed = {
        CloudTarget.Status.DRAFT: {CloudTarget.Status.READY, CloudTarget.Status.RETIRED},
        CloudTarget.Status.READY: {
            CloudTarget.Status.ACTIVE,
            CloudTarget.Status.SUSPENDED,
            CloudTarget.Status.RETIRED,
        },
        CloudTarget.Status.ACTIVE: {
            CloudTarget.Status.SUSPENDED,
            CloudTarget.Status.RETIRED,
        },
        CloudTarget.Status.SUSPENDED: {
            CloudTarget.Status.READY,
            CloudTarget.Status.RETIRED,
        },
        CloudTarget.Status.RETIRED: set(),
    }
    if target_status not in allowed[target.status]:
        raise ValidationError("Cloud target status transition is not allowed")
    before = {"status": target.status, "version": target.version}
    target.status = target_status
    if production_approved:
        target.production_approved = True
    target.version += 1
    target.full_clean()
    target.save()
    _audit(
        actor=actor,
        company=company,
        action="cloudops.target.transitioned",
        entity_type="cloud_target",
        entity_public_id=target.public_id,
        before=before,
        after={
            "status": target.status,
            "production_approved": target.production_approved,
            "version": target.version,
        },
        reason_code=reason,
    )
    _event(
        actor=actor,
        company=company,
        event_type="cloudops.target.transitioned",
        aggregate_type="cloud_target",
        aggregate_public_id=target.public_id,
        aggregate_version=target.version,
        payload={"status": target.status},
    )
    return target


@transaction.atomic
def create_pipeline(
    *,
    company: Company,
    actor: RequestActor,
    target_public_id: uuid.UUID,
    code: str,
    name: str,
    source_branch: str,
    trigger_mode: str,
    quality_gates: list[str],
    requires_approval: bool,
) -> DeploymentPipeline:
    target = CloudTarget.objects.filter(company=company, public_id=target_public_id).first()
    if target is None:
        raise ValidationError("Cloud target was not found")
    pipeline = DeploymentPipeline(
        company=company,
        target=target,
        code=code.strip().upper(),
        name=name.strip(),
        source_branch=source_branch.strip(),
        trigger_mode=trigger_mode,
        quality_gates=quality_gates,
        requires_approval=requires_approval,
    )
    pipeline.full_clean()
    pipeline.save()
    _audit(
        actor=actor,
        company=company,
        action="cloudops.pipeline.created",
        entity_type="deployment_pipeline",
        entity_public_id=pipeline.public_id,
        after={"code": pipeline.code, "target": target.code},
    )
    return pipeline


@transaction.atomic
def create_deployment(
    *,
    company: Company,
    actor: RequestActor,
    pipeline_public_id: uuid.UUID,
    source_revision: str,
    artifact_sha256: str,
    migration_plan_sha256: str = "",
    release_public_id: uuid.UUID | None = None,
) -> DeploymentExecution:
    pipeline = (
        DeploymentPipeline.objects.select_related("target", "target__environment")
        .filter(company=company, public_id=pipeline_public_id, is_active=True)
        .first()
    )
    if pipeline is None:
        raise ValidationError("Active deployment pipeline was not found")
    release = None
    if release_public_id:
        release = ReleaseRecord.objects.filter(
            company=company,
            public_id=release_public_id,
        ).first()
        if release is None:
            raise ValidationError("Release record was not found")
    deployment = DeploymentExecution(
        company=company,
        pipeline=pipeline,
        release=release,
        source_revision=source_revision.strip(),
        artifact_sha256=artifact_sha256.strip().lower(),
        migration_plan_sha256=migration_plan_sha256.strip().lower(),
        requested_by_public_id=actor.user_public_id,
    )
    deployment.full_clean()
    deployment.save()
    _audit(
        actor=actor,
        company=company,
        action="cloudops.deployment.requested",
        entity_type="deployment_execution",
        entity_public_id=deployment.public_id,
        after={
            "pipeline": pipeline.code,
            "target": pipeline.target.code,
            "revision": deployment.source_revision,
        },
    )
    _event(
        actor=actor,
        company=company,
        event_type="cloudops.deployment.requested",
        aggregate_type="deployment_execution",
        aggregate_public_id=deployment.public_id,
        aggregate_version=deployment.version,
        payload={"pipeline": pipeline.code, "target": pipeline.target.code},
    )
    return deployment


def deployment_readiness(deployment: DeploymentExecution) -> dict[str, Any]:
    target = deployment.pipeline.target
    is_production = (
        target.environment.environment_type == RuntimeEnvironment.EnvironmentType.PRODUCTION
    )
    release_ready = True
    release_status = None
    if deployment.release_id:
        release_status = deployment.release.status
        release_ready = release_readiness(deployment.release)["ready"]
    if is_production:
        release_ready = bool(
            deployment.release_id
            and deployment.release.status
            in [ReleaseRecord.Status.APPROVED, ReleaseRecord.Status.DEPLOYED]
            and release_ready
        )
    return {
        "target_ready": target.status == CloudTarget.Status.ACTIVE,
        "production_approved": not is_production or target.production_approved,
        "release_ready": release_ready,
        "release_status": release_status,
        "quality_gates": deployment.pipeline.quality_gates,
        "ready": (
            target.status == CloudTarget.Status.ACTIVE
            and (not is_production or target.production_approved)
            and release_ready
        ),
    }


@transaction.atomic
def transition_deployment(
    *,
    company: Company,
    actor: RequestActor,
    deployment_public_id: uuid.UUID,
    target_status: str,
    expected_version: int,
    deployment_url: str = "",
    logs_sha256: str = "",
    error_summary: str = "",
    rollback_reference: str = "",
    reason: str = "",
) -> DeploymentExecution:
    deployment = (
        DeploymentExecution.objects.select_for_update(of=("self",))
        .select_related("pipeline", "pipeline__target", "pipeline__target__environment", "release")
        .filter(company=company, public_id=deployment_public_id)
        .first()
    )
    if deployment is None:
        raise ValidationError("Deployment execution was not found")
    if deployment.version != expected_version:
        raise ValidationError("Deployment execution version conflict")
    allowed = {
        DeploymentExecution.Status.REQUESTED: {
            DeploymentExecution.Status.VALIDATED,
            DeploymentExecution.Status.FAILED,
        },
        DeploymentExecution.Status.VALIDATED: {
            DeploymentExecution.Status.APPROVED,
            DeploymentExecution.Status.RUNNING,
            DeploymentExecution.Status.FAILED,
        },
        DeploymentExecution.Status.APPROVED: {
            DeploymentExecution.Status.RUNNING,
            DeploymentExecution.Status.FAILED,
        },
        DeploymentExecution.Status.RUNNING: {
            DeploymentExecution.Status.SUCCEEDED,
            DeploymentExecution.Status.FAILED,
        },
        DeploymentExecution.Status.SUCCEEDED: {
            DeploymentExecution.Status.ROLLED_BACK,
        },
        DeploymentExecution.Status.FAILED: {
            DeploymentExecution.Status.REQUESTED,
        },
        DeploymentExecution.Status.ROLLED_BACK: set(),
    }
    if target_status not in allowed[deployment.status]:
        raise ValidationError("Deployment status transition is not allowed")
    readiness = deployment_readiness(deployment)
    if target_status in {
        DeploymentExecution.Status.VALIDATED,
        DeploymentExecution.Status.APPROVED,
        DeploymentExecution.Status.RUNNING,
    } and not readiness["ready"]:
        raise ValidationError("Cloud target or governed release is not ready")
    if target_status == DeploymentExecution.Status.APPROVED:
        if deployment.requested_by_public_id == actor.user_public_id:
            raise ValidationError("The deployment requester cannot approve the deployment")
        deployment.approved_by_public_id = actor.user_public_id
    if target_status == DeploymentExecution.Status.RUNNING:
        if deployment.pipeline.requires_approval and not deployment.approved_by_public_id:
            raise ValidationError("This deployment pipeline requires approval")
        deployment.executed_by_public_id = actor.user_public_id
        deployment.started_at = timezone.now()
    if target_status in {
        DeploymentExecution.Status.SUCCEEDED,
        DeploymentExecution.Status.FAILED,
        DeploymentExecution.Status.ROLLED_BACK,
    }:
        deployment.finished_at = timezone.now()
    before = {"status": deployment.status, "version": deployment.version}
    deployment.status = target_status
    if deployment_url:
        deployment.deployment_url = deployment_url.strip()
    if logs_sha256:
        deployment.logs_sha256 = logs_sha256.strip().lower()
    if error_summary:
        deployment.error_summary = error_summary.strip()
    if rollback_reference:
        deployment.rollback_reference = rollback_reference.strip()
    deployment.version += 1
    deployment.full_clean()
    deployment.save()
    _audit(
        actor=actor,
        company=company,
        action="cloudops.deployment.transitioned",
        entity_type="deployment_execution",
        entity_public_id=deployment.public_id,
        before=before,
        after={"status": deployment.status, "version": deployment.version},
        reason_code=reason,
    )
    _event(
        actor=actor,
        company=company,
        event_type="cloudops.deployment.transitioned",
        aggregate_type="deployment_execution",
        aggregate_public_id=deployment.public_id,
        aggregate_version=deployment.version,
        payload={"status": deployment.status},
    )
    return deployment


@transaction.atomic
def create_backup_policy(
    *,
    company: Company,
    actor: RequestActor,
    target_public_id: uuid.UUID,
    code: str,
    name: str,
    resource_type: str,
    schedule_cron: str,
    retention_days: int,
    encryption_required: bool,
    point_in_time_recovery: bool,
) -> BackupPolicy:
    target = CloudTarget.objects.filter(company=company, public_id=target_public_id).first()
    if target is None:
        raise ValidationError("Cloud target was not found")
    policy = BackupPolicy(
        company=company,
        target=target,
        code=code.strip().upper(),
        name=name.strip(),
        resource_type=resource_type,
        schedule_cron=schedule_cron.strip(),
        retention_days=retention_days,
        encryption_required=encryption_required,
        point_in_time_recovery=point_in_time_recovery,
    )
    policy.full_clean()
    policy.save()
    _audit(
        actor=actor,
        company=company,
        action="cloudops.backup_policy.created",
        entity_type="backup_policy",
        entity_public_id=policy.public_id,
        after={"code": policy.code, "resource_type": policy.resource_type},
    )
    return policy


@transaction.atomic
def record_backup_execution(
    *,
    company: Company,
    actor: RequestActor,
    policy_public_id: uuid.UUID,
    status: str,
    backup_reference: str = "",
    backup_sha256: str = "",
    size_bytes: int = 0,
    recovery_point_at=None,
    started_at=None,
    finished_at=None,
    error_summary: str = "",
) -> BackupExecution:
    policy = BackupPolicy.objects.filter(
        company=company,
        public_id=policy_public_id,
        is_active=True,
    ).first()
    if policy is None:
        raise ValidationError("Active backup policy was not found")
    started = started_at or timezone.now()
    finished = finished_at
    evidence = ""
    if status in {BackupExecution.Status.SUCCEEDED, BackupExecution.Status.VERIFIED}:
        finished = finished or timezone.now()
        evidence = _sha256_payload(
            {
                "policy": str(policy.public_id),
                "reference": backup_reference,
                "backup_sha256": backup_sha256.lower(),
                "size_bytes": size_bytes,
                "recovery_point_at": recovery_point_at,
                "started_at": started,
                "finished_at": finished,
            }
        )
    execution = BackupExecution(
        company=company,
        policy=policy,
        status=status,
        backup_reference=backup_reference.strip(),
        backup_sha256=backup_sha256.strip().lower(),
        size_bytes=size_bytes,
        recovery_point_at=recovery_point_at,
        started_at=started,
        finished_at=finished,
        evidence_sha256=evidence,
        error_summary=error_summary.strip(),
    )
    execution.full_clean()
    execution.save()
    _audit(
        actor=actor,
        company=company,
        action="cloudops.backup.recorded",
        entity_type="backup_execution",
        entity_public_id=execution.public_id,
        after={"policy": policy.code, "status": execution.status},
    )
    _event(
        actor=actor,
        company=company,
        event_type="cloudops.backup.recorded",
        aggregate_type="backup_execution",
        aggregate_public_id=execution.public_id,
        aggregate_version=1,
        payload={"policy": policy.code, "status": execution.status},
    )
    return execution


@transaction.atomic
def create_restore_exercise(
    *,
    company: Company,
    actor: RequestActor,
    target_public_id: uuid.UUID,
    backup_execution_public_id: uuid.UUID,
    notes: str = "",
) -> RestoreExercise:
    target = CloudTarget.objects.filter(company=company, public_id=target_public_id).first()
    backup = BackupExecution.objects.filter(
        company=company,
        public_id=backup_execution_public_id,
        status__in=[BackupExecution.Status.SUCCEEDED, BackupExecution.Status.VERIFIED],
    ).first()
    if target is None or backup is None:
        raise ValidationError("Target or successful backup was not found")
    exercise = RestoreExercise(
        company=company,
        target=target,
        backup_execution=backup,
        requested_by_public_id=actor.user_public_id,
        notes=notes.strip(),
    )
    exercise.full_clean()
    exercise.save()
    _audit(
        actor=actor,
        company=company,
        action="cloudops.restore.planned",
        entity_type="restore_exercise",
        entity_public_id=exercise.public_id,
        after={"target": target.code, "backup": str(backup.public_id)},
    )
    return exercise


@transaction.atomic
def transition_restore_exercise(
    *,
    company: Company,
    actor: RequestActor,
    exercise_public_id: uuid.UUID,
    target_status: str,
    expected_version: int,
    measured_rpo_minutes: int | None = None,
    measured_rto_minutes: int | None = None,
    evidence_sha256: str = "",
    notes: str = "",
) -> RestoreExercise:
    exercise = (
        RestoreExercise.objects.select_for_update()
        .filter(company=company, public_id=exercise_public_id)
        .first()
    )
    if exercise is None:
        raise ValidationError("Restore exercise was not found")
    if exercise.version != expected_version:
        raise ValidationError("Restore exercise version conflict")
    allowed = {
        RestoreExercise.Status.PLANNED: {RestoreExercise.Status.RUNNING},
        RestoreExercise.Status.RUNNING: {
            RestoreExercise.Status.PASSED,
            RestoreExercise.Status.FAILED,
        },
        RestoreExercise.Status.PASSED: {RestoreExercise.Status.APPROVED},
        RestoreExercise.Status.FAILED: {RestoreExercise.Status.PLANNED},
        RestoreExercise.Status.APPROVED: set(),
    }
    if target_status not in allowed[exercise.status]:
        raise ValidationError("Restore exercise status transition is not allowed")
    if target_status == RestoreExercise.Status.APPROVED:
        if exercise.requested_by_public_id == actor.user_public_id:
            raise ValidationError("The restore requester cannot approve the exercise")
        exercise.reviewed_by_public_id = actor.user_public_id
    if target_status == RestoreExercise.Status.RUNNING:
        exercise.started_at = timezone.now()
    if target_status in {RestoreExercise.Status.PASSED, RestoreExercise.Status.FAILED}:
        exercise.finished_at = timezone.now()
    if measured_rpo_minutes is not None:
        exercise.measured_rpo_minutes = measured_rpo_minutes
    if measured_rto_minutes is not None:
        exercise.measured_rto_minutes = measured_rto_minutes
    if evidence_sha256:
        exercise.evidence_sha256 = evidence_sha256.strip().lower()
    if notes:
        exercise.notes = notes.strip()
    before = {"status": exercise.status, "version": exercise.version}
    exercise.status = target_status
    exercise.version += 1
    exercise.full_clean()
    exercise.save()
    _audit(
        actor=actor,
        company=company,
        action="cloudops.restore.transitioned",
        entity_type="restore_exercise",
        entity_public_id=exercise.public_id,
        before=before,
        after={"status": exercise.status, "version": exercise.version},
    )
    _event(
        actor=actor,
        company=company,
        event_type="cloudops.restore.transitioned",
        aggregate_type="restore_exercise",
        aggregate_public_id=exercise.public_id,
        aggregate_version=exercise.version,
        payload={"status": exercise.status},
    )
    return exercise


@transaction.atomic
def create_secret_policy(
    *,
    company: Company,
    actor: RequestActor,
    target_public_id: uuid.UUID,
    code: str,
    name: str,
    secret_provider: str,
    secret_reference: str,
    rotation_interval_days: int,
) -> SecretRotationPolicy:
    target = CloudTarget.objects.filter(company=company, public_id=target_public_id).first()
    if target is None:
        raise ValidationError("Cloud target was not found")
    policy = SecretRotationPolicy(
        company=company,
        target=target,
        code=code.strip().upper(),
        name=name.strip(),
        secret_provider=secret_provider.strip(),
        secret_reference=secret_reference.strip(),
        rotation_interval_days=rotation_interval_days,
    )
    policy.full_clean()
    policy.save()
    _audit(
        actor=actor,
        company=company,
        action="cloudops.secret_policy.created",
        entity_type="secret_rotation_policy",
        entity_public_id=policy.public_id,
        after={"code": policy.code, "provider": policy.secret_provider},
    )
    return policy


@transaction.atomic
def record_secret_rotation(
    *,
    company: Company,
    actor: RequestActor,
    policy_public_id: uuid.UUID,
    expected_version: int,
    rotated_at=None,
    evidence_reference: str = "",
) -> SecretRotationPolicy:
    policy = (
        SecretRotationPolicy.objects.select_for_update()
        .filter(company=company, public_id=policy_public_id)
        .first()
    )
    if policy is None:
        raise ValidationError("Secret rotation policy was not found")
    if policy.version != expected_version:
        raise ValidationError("Secret rotation policy version conflict")
    moment = rotated_at or timezone.now()
    before = {
        "status": policy.status,
        "last_rotated_at": policy.last_rotated_at,
        "version": policy.version,
    }
    policy.last_rotated_at = moment
    policy.next_rotation_at = moment + timedelta(days=policy.rotation_interval_days)
    policy.status = SecretRotationPolicy.Status.CURRENT
    policy.version += 1
    policy.full_clean()
    policy.save()
    _audit(
        actor=actor,
        company=company,
        action="cloudops.secret.rotated",
        entity_type="secret_rotation_policy",
        entity_public_id=policy.public_id,
        before=before,
        after={
            "status": policy.status,
            "last_rotated_at": policy.last_rotated_at,
            "next_rotation_at": policy.next_rotation_at,
            "version": policy.version,
        },
        reason_code=evidence_reference,
    )
    _event(
        actor=actor,
        company=company,
        event_type="cloudops.secret.rotated",
        aggregate_type="secret_rotation_policy",
        aggregate_public_id=policy.public_id,
        aggregate_version=policy.version,
        payload={"code": policy.code, "next_rotation_at": policy.next_rotation_at},
    )
    return policy
