
from rest_framework import serializers

from modules.dataops.models import PrivacyRequest, RecoveryVerification


class ImportJobCreateSerializer(serializers.Serializer):
    template_public_id = serializers.UUIDField()
    source_name = serializers.CharField(max_length=240)
    idempotency_key = serializers.CharField(max_length=120)
    rows = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        max_length=500,
    )


class ImportCommitSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)
    allow_partial = serializers.BooleanField(required=False, default=False)


class PrivacyCreateSerializer(serializers.Serializer):
    request_number = serializers.CharField(max_length=80)
    request_type = serializers.ChoiceField(choices=PrivacyRequest.RequestType.choices)
    subject_type = serializers.CharField(max_length=80)
    subject_public_id = serializers.UUIDField()
    due_in_days = serializers.IntegerField(min_value=1, max_value=90, default=30)


class PrivacyResolveSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)
    status = serializers.ChoiceField(
        choices=[
            PrivacyRequest.Status.COMPLETED,
            PrivacyRequest.Status.REJECTED,
            PrivacyRequest.Status.CANCELLED,
        ]
    )
    resolution_summary = serializers.CharField()
    reason_code = serializers.CharField(max_length=100, required=False, allow_blank=True)


class RetentionCreateSerializer(serializers.Serializer):
    record_type = serializers.CharField(max_length=120)
    retention_days = serializers.IntegerField(min_value=1, max_value=36500)
    legal_hold_default = serializers.BooleanField(required=False, default=False)


class RecoveryCreateSerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=120)
    scope = serializers.ChoiceField(choices=RecoveryVerification.Scope.choices)
    target_rpo_minutes = serializers.IntegerField(min_value=0, max_value=10080)
    target_rto_minutes = serializers.IntegerField(min_value=0, max_value=10080)


class RecoveryCompleteSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)
    measured_rpo_minutes = serializers.IntegerField(min_value=0, max_value=10080)
    measured_rto_minutes = serializers.IntegerField(min_value=0, max_value=10080)
    evidence_summary = serializers.CharField()
