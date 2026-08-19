from rest_framework import serializers

from modules.fieldops.models import FieldStage


class FieldStageCreateSerializer(serializers.Serializer):
    entity_type = serializers.ChoiceField(choices=FieldStage.EntityType.choices)
    code = serializers.CharField(max_length=80)
    name = serializers.CharField(max_length=160)
    outcome = serializers.ChoiceField(choices=FieldStage.Outcome.choices)
    sort_order = serializers.IntegerField(min_value=1, default=100)
    allowed_next_codes = serializers.ListField(
        child=serializers.CharField(max_length=80),
        default=list,
    )
    is_initial = serializers.BooleanField(default=False)


class OfflineOperationSerializer(serializers.Serializer):
    operation_id = serializers.UUIDField()
    device_id = serializers.UUIDField()
    operation_type = serializers.CharField(max_length=100)
    aggregate_type = serializers.CharField(max_length=80)
    aggregate_public_id = serializers.UUIDField(required=False, allow_null=True)
    expected_version = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    payload = serializers.JSONField()
