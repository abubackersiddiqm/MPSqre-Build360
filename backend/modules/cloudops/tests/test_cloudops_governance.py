import hashlib
import uuid

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from modules.adminops.models import RuntimeEnvironment
from modules.cloudops.application.services import (
    create_backup_policy,
    create_deployment,
    create_pipeline,
    create_restore_exercise,
    create_secret_policy,
    record_backup_execution,
    record_secret_rotation,
    transition_deployment,
    transition_restore_exercise,
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
from modules.platform.actors import RequestActor


def actor(user, membership):
    return RequestActor(
        user.public_id,
        membership.public_id,
        uuid.uuid4(),
        "127.0.0.1",
        "pytest",
    )


def environment(company, code="LOCAL", environment_type="local"):
    return RuntimeEnvironment.objects.create(
        company=company,
        code=code,
        name=f"{code} environment",
        environment_type=environment_type,
        base_url="http://localhost:3000",
        region="local",
        data_residency="local",
        production_data_allowed=environment_type == "production",
        requires_change_approval=environment_type == "production",
        is_active=True,
    )


def active_target(company, env):
    return CloudTarget.objects.create(
        company=company,
        environment=env,
        code="LOCAL_NATIVE",
        name="Local target",
        provider=CloudTarget.Provider.GENERIC,
        region="local",
        data_residency="local",
        backend_service="Django",
        status=CloudTarget.Status.ACTIVE,
    )


@pytest.mark.django_db
def test_deployment_requires_independent_approval(
    company_factory,
    user_factory,
    membership_factory,
):
    company = company_factory()
    requester_user = user_factory()
    reviewer_user = user_factory()
    requester = membership_factory(requester_user, company)
    reviewer = membership_factory(reviewer_user, company)
    target = active_target(company, environment(company))
    pipeline = create_pipeline(
        company=company,
        actor=actor(requester_user, requester),
        target_public_id=target.public_id,
        code="LOCAL_VALIDATION",
        name="Local validation",
        source_branch="main",
        trigger_mode=DeploymentPipeline.TriggerMode.MANUAL,
        quality_gates=["backend.pytest", "frontend.build"],
        requires_approval=True,
    )
    digest = hashlib.sha256(b"artifact").hexdigest()
    deployment = create_deployment(
        company=company,
        actor=actor(requester_user, requester),
        pipeline_public_id=pipeline.public_id,
        source_revision="abc123",
        artifact_sha256=digest,
    )
    validated = transition_deployment(
        company=company,
        actor=actor(requester_user, requester),
        deployment_public_id=deployment.public_id,
        target_status=DeploymentExecution.Status.VALIDATED,
        expected_version=1,
    )
    with pytest.raises(ValidationError, match="requester cannot approve"):
        transition_deployment(
            company=company,
            actor=actor(requester_user, requester),
            deployment_public_id=deployment.public_id,
            target_status=DeploymentExecution.Status.APPROVED,
            expected_version=validated.version,
        )
    approved = transition_deployment(
        company=company,
        actor=actor(reviewer_user, reviewer),
        deployment_public_id=deployment.public_id,
        target_status=DeploymentExecution.Status.APPROVED,
        expected_version=validated.version,
    )
    running = transition_deployment(
        company=company,
        actor=actor(requester_user, requester),
        deployment_public_id=deployment.public_id,
        target_status=DeploymentExecution.Status.RUNNING,
        expected_version=approved.version,
    )
    succeeded = transition_deployment(
        company=company,
        actor=actor(requester_user, requester),
        deployment_public_id=deployment.public_id,
        target_status=DeploymentExecution.Status.SUCCEEDED,
        expected_version=running.version,
        deployment_url="http://localhost:3000",
        logs_sha256=hashlib.sha256(b"logs").hexdigest(),
    )
    assert succeeded.status == DeploymentExecution.Status.SUCCEEDED


@pytest.mark.django_db
def test_restore_exercise_requires_independent_approval(
    company_factory,
    user_factory,
    membership_factory,
):
    company = company_factory()
    requester_user = user_factory()
    reviewer_user = user_factory()
    requester = membership_factory(requester_user, company)
    reviewer = membership_factory(reviewer_user, company)
    target = active_target(company, environment(company))
    policy = create_backup_policy(
        company=company,
        actor=actor(requester_user, requester),
        target_public_id=target.public_id,
        code="DB_DAILY",
        name="Daily database backup",
        resource_type=BackupPolicy.ResourceType.DATABASE,
        schedule_cron="0 1 * * *",
        retention_days=30,
        encryption_required=True,
        point_in_time_recovery=False,
    )
    backup_digest = hashlib.sha256(b"backup").hexdigest()
    backup = record_backup_execution(
        company=company,
        actor=actor(requester_user, requester),
        policy_public_id=policy.public_id,
        status=BackupExecution.Status.VERIFIED,
        backup_reference="s3://private/backups/test",
        backup_sha256=backup_digest,
        size_bytes=1024,
        recovery_point_at=timezone.now(),
    )
    exercise = create_restore_exercise(
        company=company,
        actor=actor(requester_user, requester),
        target_public_id=target.public_id,
        backup_execution_public_id=backup.public_id,
    )
    running = transition_restore_exercise(
        company=company,
        actor=actor(requester_user, requester),
        exercise_public_id=exercise.public_id,
        target_status=RestoreExercise.Status.RUNNING,
        expected_version=1,
    )
    evidence = hashlib.sha256(b"restore-evidence").hexdigest()
    passed = transition_restore_exercise(
        company=company,
        actor=actor(requester_user, requester),
        exercise_public_id=exercise.public_id,
        target_status=RestoreExercise.Status.PASSED,
        expected_version=running.version,
        measured_rpo_minutes=5,
        measured_rto_minutes=18,
        evidence_sha256=evidence,
    )
    with pytest.raises(ValidationError, match="requester cannot approve"):
        transition_restore_exercise(
            company=company,
            actor=actor(requester_user, requester),
            exercise_public_id=exercise.public_id,
            target_status=RestoreExercise.Status.APPROVED,
            expected_version=passed.version,
        )
    approved = transition_restore_exercise(
        company=company,
        actor=actor(reviewer_user, reviewer),
        exercise_public_id=exercise.public_id,
        target_status=RestoreExercise.Status.APPROVED,
        expected_version=passed.version,
    )
    assert approved.reviewed_by_public_id == reviewer_user.public_id


@pytest.mark.django_db
def test_secret_policy_rejects_raw_secret_and_tracks_rotation(
    company_factory,
    user_factory,
    membership_factory,
):
    company = company_factory()
    user = user_factory()
    membership = membership_factory(user, company)
    target = active_target(company, environment(company))
    with pytest.raises(ValidationError, match="never a raw secret"):
        create_secret_policy(
            company=company,
            actor=actor(user, membership),
            target_public_id=target.public_id,
            code="BAD_SECRET",
            name="Unsafe secret",
            secret_provider="local",
            secret_reference="password=plain-text",
            rotation_interval_days=90,
        )
    policy = create_secret_policy(
        company=company,
        actor=actor(user, membership),
        target_public_id=target.public_id,
        code="JWT_SIGNING_KEY",
        name="JWT signing key",
        secret_provider="managed-vault",
        secret_reference="vault://build360/jwt-signing-key",
        rotation_interval_days=90,
    )
    rotated = record_secret_rotation(
        company=company,
        actor=actor(user, membership),
        policy_public_id=policy.public_id,
        expected_version=1,
        evidence_reference="rotation-ticket-001",
    )
    assert rotated.status == SecretRotationPolicy.Status.CURRENT
    assert rotated.next_rotation_at is not None


def test_cloud_launch_security_checks_allow_local_demo(settings):
    from modules.cloudops.checks import cloud_launch_security_checks

    settings.BUILD360_ENVIRONMENT = "demo"
    settings.APP_ENV = "demo"
    settings.LOCAL_NO_DOCKER = True

    assert cloud_launch_security_checks(None) == []


def test_cloud_launch_security_checks_keep_hosted_demo_production_grade(settings):
    from modules.cloudops.checks import cloud_launch_security_checks

    settings.BUILD360_ENVIRONMENT = "demo"
    settings.APP_ENV = "demo"
    settings.LOCAL_NO_DOCKER = False
    settings.ALLOWED_HOSTS = ["demo.build360.local"]
    settings.CSRF_TRUSTED_ORIGINS = ["https://demo.build360.local"]
    settings.CORS_ALLOWED_ORIGINS = ["https://demo.build360.local"]
    settings.OBJECT_STORAGE_ENDPOINT = "http://localhost:9000"
    settings.DATABASES = {
        "default": {
            "OPTIONS": {
                "sslmode": "prefer",
            }
        }
    }

    issue_ids = {issue.id for issue in cloud_launch_security_checks(None)}

    assert "cloudops.E001" not in issue_ids
    assert "cloudops.E004" in issue_ids
    assert "cloudops.E005" in issue_ids
