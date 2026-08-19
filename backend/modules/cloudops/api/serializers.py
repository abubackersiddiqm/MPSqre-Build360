from rest_framework import serializers

from modules.cloudops.models import (
    BackupExecution,
    BackupPolicy,
    CloudTarget,
    DeploymentExecution,
    DeploymentPipeline,
    RestoreExercise,
)


class CloudTargetCreateSerializer(serializers.Serializer):
    environment_public_id = serializers.UUIDField()
    code = serializers.CharField(max_length=80)
    name = serializers.CharField(max_length=180)
    provider = serializers.ChoiceField(choices=CloudTarget.Provider.choices)
    region = serializers.CharField(max_length=100)
    data_residency = serializers.CharField(max_length=100)
    backend_service = serializers.CharField(max_length=160, required=False, allow_blank=True)
    frontend_service = serializers.CharField(max_length=160, required=False, allow_blank=True)
    database_service = serializers.CharField(max_length=160, required=False, allow_blank=True)
    cache_service = serializers.CharField(max_length=160, required=False, allow_blank=True)
    object_storage_service = serializers.CharField(
        max_length=160,
        required=False,
        allow_blank=True,
    )
    worker_service = serializers.CharField(max_length=160, required=False, allow_blank=True)
    secret_manager_service = serializers.CharField(
        max_length=160,
        required=False,
        allow_blank=True,
    )


class CloudTargetTransitionSerializer(serializers.Serializer):
    target_status = serializers.ChoiceField(choices=CloudTarget.Status.choices)
    expected_version = serializers.IntegerField(min_value=1)
    production_approved = serializers.BooleanField(required=False, default=False)
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)


class PipelineCreateSerializer(serializers.Serializer):
    target_public_id = serializers.UUIDField()
    code = serializers.CharField(max_length=100)
    name = serializers.CharField(max_length=180)
    source_branch = serializers.CharField(max_length=160, default="main")
    trigger_mode = serializers.ChoiceField(choices=DeploymentPipeline.TriggerMode.choices)
    quality_gates = serializers.ListField(
        child=serializers.CharField(max_length=120),
        allow_empty=False,
    )
    requires_approval = serializers.BooleanField(default=True)


class DeploymentCreateSerializer(serializers.Serializer):
    pipeline_public_id = serializers.UUIDField()
    source_revision = serializers.CharField(max_length=160)
    artifact_sha256 = serializers.RegexField(regex=r"^[0-9a-fA-F]{64}$")
    migration_plan_sha256 = serializers.RegexField(
        regex=r"^[0-9a-fA-F]{64}$",
        required=False,
        allow_blank=True,
    )
    release_public_id = serializers.UUIDField(required=False, allow_null=True)


class DeploymentTransitionSerializer(serializers.Serializer):
    target_status = serializers.ChoiceField(choices=DeploymentExecution.Status.choices)
    expected_version = serializers.IntegerField(min_value=1)
    deployment_url = serializers.URLField(required=False, allow_blank=True)
    logs_sha256 = serializers.RegexField(
        regex=r"^[0-9a-fA-F]{64}$",
        required=False,
        allow_blank=True,
    )
    error_summary = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    rollback_reference = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
    )
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)


class BackupPolicyCreateSerializer(serializers.Serializer):
    target_public_id = serializers.UUIDField()
    code = serializers.CharField(max_length=100)
    name = serializers.CharField(max_length=180)
    resource_type = serializers.ChoiceField(choices=BackupPolicy.ResourceType.choices)
    schedule_cron = serializers.CharField(max_length=100)
    retention_days = serializers.IntegerField(min_value=1, max_value=3650)
    encryption_required = serializers.BooleanField(default=True)
    point_in_time_recovery = serializers.BooleanField(default=False)


class BackupExecutionSerializer(serializers.Serializer):
    policy_public_id = serializers.UUIDField()
    status = serializers.ChoiceField(choices=BackupExecution.Status.choices)
    backup_reference = serializers.CharField(max_length=500, required=False, allow_blank=True)
    backup_sha256 = serializers.RegexField(
        regex=r"^[0-9a-fA-F]{64}$",
        required=False,
        allow_blank=True,
    )
    size_bytes = serializers.IntegerField(min_value=0, default=0)
    recovery_point_at = serializers.DateTimeField(required=False, allow_null=True)
    started_at = serializers.DateTimeField(required=False, allow_null=True)
    finished_at = serializers.DateTimeField(required=False, allow_null=True)
    error_summary = serializers.CharField(max_length=1000, required=False, allow_blank=True)


class RestoreExerciseCreateSerializer(serializers.Serializer):
    target_public_id = serializers.UUIDField()
    backup_execution_public_id = serializers.UUIDField()
    notes = serializers.CharField(max_length=1000, required=False, allow_blank=True)


class RestoreExerciseTransitionSerializer(serializers.Serializer):
    target_status = serializers.ChoiceField(choices=RestoreExercise.Status.choices)
    expected_version = serializers.IntegerField(min_value=1)
    measured_rpo_minutes = serializers.IntegerField(min_value=0, required=False, allow_null=True)
    measured_rto_minutes = serializers.IntegerField(min_value=0, required=False, allow_null=True)
    evidence_sha256 = serializers.RegexField(
        regex=r"^[0-9a-fA-F]{64}$",
        required=False,
        allow_blank=True,
    )
    notes = serializers.CharField(max_length=1000, required=False, allow_blank=True)


class SecretPolicyCreateSerializer(serializers.Serializer):
    target_public_id = serializers.UUIDField()
    code = serializers.CharField(max_length=100)
    name = serializers.CharField(max_length=180)
    secret_provider = serializers.CharField(max_length=100)
    secret_reference = serializers.CharField(max_length=500)
    rotation_interval_days = serializers.IntegerField(min_value=1, max_value=730)


class SecretRotationSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)
    rotated_at = serializers.DateTimeField(required=False, allow_null=True)
    evidence_reference = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
    )
