from rest_framework import serializers

from modules.safety.models import SafetyIncident


class IncidentCreateSerializer(serializers.Serializer):
    project_public_id = serializers.UUIDField()
    incident_number = serializers.CharField(max_length=80)
    title = serializers.CharField(max_length=250)
    description = serializers.CharField()
    severity = serializers.ChoiceField(choices=SafetyIncident.Severity.choices)
    occurred_at = serializers.DateTimeField()
    reported_by_membership_public_id = serializers.UUIDField(required=False, allow_null=True)
    location = serializers.JSONField(required=False, default=dict)
    immediate_actions = serializers.CharField(required=False, allow_blank=True, default="")
    operation_id = serializers.UUIDField(required=False, allow_null=True)


class ObservationCreateSerializer(serializers.Serializer):
    project_public_id = serializers.UUIDField()
    observation_number = serializers.CharField(max_length=80)
    observation_type = serializers.CharField(max_length=40)
    description = serializers.CharField()
    observed_at = serializers.DateTimeField()
    observed_by_membership_public_id = serializers.UUIDField()
    is_positive = serializers.BooleanField(default=False)
    action_required = serializers.BooleanField(default=False)
