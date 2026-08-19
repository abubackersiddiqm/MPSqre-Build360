from rest_framework import serializers

from modules.communication.models import CommunicationChannel, ConsentRecord


class ChannelPolicySerializer(serializers.Serializer):
    channel = serializers.ChoiceField(choices=CommunicationChannel.values)
    is_enabled = serializers.BooleanField(required=False)
    consent_required = serializers.BooleanField(required=False)
    quiet_hours_start = serializers.TimeField(required=False, allow_null=True)
    quiet_hours_end = serializers.TimeField(required=False, allow_null=True)
    timezone = serializers.CharField(max_length=64, required=False)
    retry_limit = serializers.IntegerField(min_value=0, max_value=10, required=False)
    max_daily_per_subject = serializers.IntegerField(min_value=1, max_value=1000, required=False)
    expected_version = serializers.IntegerField(min_value=1, required=False)


class ProviderCreateSerializer(serializers.Serializer):
    channel = serializers.ChoiceField(choices=CommunicationChannel.values)
    code = serializers.CharField(max_length=80)
    display_name = serializers.CharField(max_length=160)
    adapter_code = serializers.CharField(max_length=80)
    secret_reference = serializers.CharField(max_length=250, required=False, allow_blank=True)
    callback_key_id = serializers.CharField(max_length=100, required=False, allow_blank=True)
    priority = serializers.IntegerField(min_value=1, max_value=1000, required=False, default=100)
    is_active = serializers.BooleanField(required=False, default=False)
    supports_inbound = serializers.BooleanField(required=False, default=False)
    supports_delivery_receipts = serializers.BooleanField(required=False, default=False)
    configuration = serializers.JSONField(required=False, default=dict)


class TemplateCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=100)
    name = serializers.CharField(max_length=200)
    channel = serializers.ChoiceField(choices=CommunicationChannel.values)
    locale = serializers.CharField(max_length=35, required=False, default="en")
    subject_template = serializers.CharField(max_length=300, required=False, allow_blank=True)
    body_template = serializers.CharField()
    variable_names = serializers.ListField(
        child=serializers.CharField(max_length=80),
        required=False,
        default=list,
    )
    purpose_code = serializers.CharField(max_length=100)


class ConsentCreateSerializer(serializers.Serializer):
    subject_type = serializers.CharField(max_length=80)
    subject_public_id = serializers.UUIDField()
    channel = serializers.ChoiceField(choices=CommunicationChannel.values)
    purpose_code = serializers.CharField(max_length=100)
    status = serializers.ChoiceField(choices=ConsentRecord.Status.values)
    source_code = serializers.CharField(max_length=100)
    proof_reference = serializers.CharField(max_length=250, required=False, allow_blank=True)
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)


class CommunicationRequestCreateSerializer(serializers.Serializer):
    template_public_id = serializers.UUIDField()
    subject_type = serializers.CharField(max_length=80, required=False, default="user")
    subject_public_id = serializers.UUIDField(required=False)
    recipient_reference_type = serializers.CharField(max_length=80, required=False, default="user")
    recipient_reference_public_id = serializers.UUIDField(required=False)
    template_variables = serializers.JSONField(required=False, default=dict)
    idempotency_key = serializers.CharField(max_length=120)
    scheduled_for = serializers.DateTimeField(required=False, allow_null=True)


class CommunicationCancelSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=250)
