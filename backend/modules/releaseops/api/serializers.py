from rest_framework import serializers


class DeploymentTargetSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=60)
    name = serializers.CharField(max_length=160)
    environment_code = serializers.ChoiceField(choices=["LOCAL", "DEVELOPMENT", "STAGING", "PRODUCTION"], default="PRODUCTION")
    frontend_url = serializers.URLField(max_length=500)
    backend_url = serializers.URLField(max_length=500)
    health_url = serializers.URLField(max_length=500, required=False, allow_blank=True)
    region_code = serializers.CharField(max_length=80, required=False, allow_blank=True)
    hosting_provider_code = serializers.CharField(max_length=80, required=False, allow_blank=True)
    configuration = serializers.JSONField(required=False, default=dict)


class ReleaseCandidateSerializer(serializers.Serializer):
    target_public_id = serializers.UUIDField()
    release_code = serializers.CharField(max_length=80)
    version_label = serializers.CharField(max_length=80, default="v1.0.0")
    title = serializers.CharField(max_length=220)
    summary = serializers.CharField(required=False, allow_blank=True)
    source_reference = serializers.CharField(max_length=250, required=False, allow_blank=True)
    artifact_reference = serializers.CharField(max_length=500, required=False, allow_blank=True)
    artifact_sha256 = serializers.RegexField(r"^[0-9a-fA-F]{64}$", required=False, allow_blank=True)
    planned_at = serializers.DateTimeField(required=False, allow_null=True)


class GateDecisionSerializer(serializers.Serializer):
    status_code = serializers.ChoiceField(choices=["PASSED", "FAILED", "WAIVED", "PENDING"])
    notes = serializers.CharField(required=False, allow_blank=True)
    evidence = serializers.JSONField(required=False, default=dict)
    expected_version = serializers.IntegerField(min_value=1)


class UATExecutionSerializer(serializers.Serializer):
    status_code = serializers.ChoiceField(choices=["NOT_RUN", "IN_PROGRESS", "PASSED", "FAILED", "BLOCKED"])
    notes = serializers.CharField(required=False, allow_blank=True)
    evidence = serializers.JSONField(required=False, default=dict)
    defect_reference = serializers.CharField(max_length=250, required=False, allow_blank=True)
    expected_version = serializers.IntegerField(min_value=1)


class BackupSerializer(serializers.Serializer):
    release_public_id = serializers.UUIDField(required=False, allow_null=True)
    target_public_id = serializers.UUIDField()
    reference = serializers.CharField(max_length=160)
    backup_type_code = serializers.ChoiceField(choices=["FULL", "DATABASE", "MEDIA", "CONFIGURATION"], default="FULL")
    status_code = serializers.ChoiceField(choices=["CREATING", "AVAILABLE", "FAILED", "EXPIRED"], default="AVAILABLE")
    storage_reference = serializers.CharField(max_length=500)
    checksum_sha256 = serializers.RegexField(r"^[0-9a-fA-F]{64}$", required=False, allow_blank=True)
    database_included = serializers.BooleanField(default=True)
    media_included = serializers.BooleanField(default=True)
    configuration_included = serializers.BooleanField(default=True)
    restore_tested = serializers.BooleanField(default=False)
    restore_tested_at = serializers.DateTimeField(required=False, allow_null=True)
    captured_at = serializers.DateTimeField()
    retention_until = serializers.DateTimeField(required=False, allow_null=True)


class ReadinessRunSerializer(serializers.Serializer):
    release_public_id = serializers.UUIDField(required=False, allow_null=True)


class VersionActionSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)



class EvidenceAttachmentSerializer(serializers.Serializer):
    file_public_id = serializers.UUIDField()
    note = serializers.CharField(max_length=500, required=False, allow_blank=True)
    expected_version = serializers.IntegerField(min_value=1)
