from rest_framework import serializers

from modules.adminops.models import (
    HealthSnapshot,
    Incident,
    MaintenanceWindow,
    ReleaseCheck,
    ReleaseRecord,
    RuntimeEnvironment,
    ServiceObjective,
)


class EnvironmentCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=60)
    name = serializers.CharField(max_length=160)
    environment_type = serializers.ChoiceField(choices=RuntimeEnvironment.EnvironmentType.choices)
    base_url = serializers.URLField(required=False, allow_blank=True)
    region = serializers.CharField(max_length=100, required=False, allow_blank=True)
    data_residency = serializers.CharField(max_length=100, required=False, allow_blank=True)
    production_data_allowed = serializers.BooleanField(default=False)
    requires_change_approval = serializers.BooleanField(default=True)


class ReleaseCreateSerializer(serializers.Serializer):
    environment_public_id = serializers.UUIDField()
    version_label = serializers.CharField(max_length=80)
    release_name = serializers.CharField(max_length=180)
    source_revision = serializers.CharField(max_length=160)
    artifact_sha256 = serializers.RegexField(r"^[0-9a-fA-F]{64}$")
    migration_plan_sha256 = serializers.RegexField(
        r"^[0-9a-fA-F]{64}$",
        required=False,
        allow_blank=True,
    )
    change_summary = serializers.CharField(required=False, allow_blank=True)


class ReleaseTransitionSerializer(serializers.Serializer):
    target_status = serializers.ChoiceField(choices=ReleaseRecord.Status.choices)
    expected_version = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)
    rollback_reference = serializers.CharField(max_length=240, required=False, allow_blank=True)


class ReleaseCheckSerializer(serializers.Serializer):
    release_public_id = serializers.UUIDField()
    code = serializers.CharField(max_length=100)
    name = serializers.CharField(max_length=180)
    category = serializers.ChoiceField(choices=ReleaseCheck.Category.choices)
    status = serializers.ChoiceField(choices=ReleaseCheck.Status.choices)
    is_critical = serializers.BooleanField(default=True)
    target_value = serializers.CharField(max_length=160, required=False, allow_blank=True)
    measured_value = serializers.CharField(max_length=160, required=False, allow_blank=True)
    evidence = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    waiver_reason = serializers.CharField(max_length=500, required=False, allow_blank=True)


class ServiceObjectiveSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=100)
    name = serializers.CharField(max_length=180)
    service_code = serializers.CharField(max_length=100)
    indicator_type = serializers.ChoiceField(choices=ServiceObjective.IndicatorType.choices)
    target_value = serializers.DecimalField(max_digits=12, decimal_places=4)
    warning_threshold = serializers.DecimalField(max_digits=12, decimal_places=4)
    critical_threshold = serializers.DecimalField(max_digits=12, decimal_places=4)
    window_days = serializers.IntegerField(min_value=1, max_value=365, default=30)
    unit_code = serializers.CharField(max_length=40, default="percent")


class HealthSnapshotSerializer(serializers.Serializer):
    environment_public_id = serializers.UUIDField()
    service_code = serializers.CharField(max_length=100)
    status = serializers.ChoiceField(choices=HealthSnapshot.Status.choices)
    latency_ms = serializers.IntegerField(min_value=0, required=False, allow_null=True)
    observed_value = serializers.DecimalField(
        max_digits=14,
        decimal_places=4,
        required=False,
        allow_null=True,
    )
    source = serializers.CharField(max_length=120, default="manual")
    details = serializers.DictField(required=False, default=dict)


class IncidentCreateSerializer(serializers.Serializer):
    environment_public_id = serializers.UUIDField()
    number = serializers.CharField(max_length=60)
    severity = serializers.ChoiceField(choices=Incident.Severity.choices)
    title = serializers.CharField(max_length=220)
    summary = serializers.CharField(required=False, allow_blank=True)
    customer_impact = serializers.CharField(required=False, allow_blank=True)
    postmortem_required = serializers.BooleanField(default=False)


class IncidentTransitionSerializer(serializers.Serializer):
    target_status = serializers.ChoiceField(choices=Incident.Status.choices)
    expected_version = serializers.IntegerField(min_value=1)
    root_cause = serializers.CharField(required=False, allow_blank=True)
    corrective_actions = serializers.ListField(
        child=serializers.DictField(),
        required=False,
    )
    postmortem_reference = serializers.CharField(max_length=240, required=False, allow_blank=True)


class RunbookCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=100)
    title = serializers.CharField(max_length=220)
    category = serializers.CharField(max_length=100)
    purpose = serializers.CharField(required=False, allow_blank=True)
    steps = serializers.ListField(child=serializers.DictField(), min_length=1, max_length=100)
    review_due_at = serializers.DateTimeField(required=False, allow_null=True)


class FeatureFlagCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=100)
    name = serializers.CharField(max_length=180)
    description = serializers.CharField(required=False, allow_blank=True)
    scope = serializers.DictField(required=False, default=dict)
    requires_approval = serializers.BooleanField(default=True)


class FeatureFlagUpdateSerializer(serializers.Serializer):
    is_enabled = serializers.BooleanField()
    rollout_percent = serializers.IntegerField(min_value=0, max_value=100)
    expected_version = serializers.IntegerField(min_value=1)


class MaintenanceCreateSerializer(serializers.Serializer):
    environment_public_id = serializers.UUIDField()
    reference = serializers.CharField(max_length=80)
    title = serializers.CharField(max_length=220)
    reason = serializers.CharField(required=False, allow_blank=True)
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    affected_services = serializers.ListField(
        child=serializers.CharField(max_length=100),
        min_length=1,
        max_length=100,
    )


class MaintenanceTransitionSerializer(serializers.Serializer):
    target_status = serializers.ChoiceField(choices=MaintenanceWindow.Status.choices)
    expected_version = serializers.IntegerField(min_value=1)
