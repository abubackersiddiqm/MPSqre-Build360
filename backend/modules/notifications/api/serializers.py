from rest_framework import serializers

from modules.communication.models import CommunicationChannel
from modules.notifications.models import Notification, NotificationPreference


class NotificationCreateSerializer(serializers.Serializer):
    user_public_id = serializers.UUIDField(required=False)
    event_code = serializers.CharField(max_length=120)
    title = serializers.CharField(max_length=250)
    body = serializers.CharField()
    severity = serializers.ChoiceField(
        choices=Notification.Severity.values,
        required=False,
        default=Notification.Severity.INFO,
    )
    action_path = serializers.CharField(max_length=300, required=False, allow_blank=True)
    source_type = serializers.CharField(max_length=100, required=False, allow_blank=True)
    source_public_id = serializers.UUIDField(required=False, allow_null=True)
    route_external = serializers.BooleanField(required=False, default=False)


class PreferenceSerializer(serializers.Serializer):
    event_code = serializers.CharField(max_length=120)
    channel = serializers.ChoiceField(choices=CommunicationChannel.values)
    enabled = serializers.BooleanField(required=False, default=True)
    digest_mode = serializers.ChoiceField(
        choices=NotificationPreference.DigestMode.values,
        required=False,
        default=NotificationPreference.DigestMode.IMMEDIATE,
    )
    quiet_hours_start = serializers.TimeField(required=False, allow_null=True)
    quiet_hours_end = serializers.TimeField(required=False, allow_null=True)
    expected_version = serializers.IntegerField(min_value=1, required=False)


class RuleSerializer(serializers.Serializer):
    event_code = serializers.CharField(max_length=120)
    name = serializers.CharField(max_length=200)
    default_title_template = serializers.CharField(max_length=250)
    default_body_template = serializers.CharField()
    severity = serializers.ChoiceField(choices=Notification.Severity.values)
    channels = serializers.ListField(
        child=serializers.ChoiceField(choices=CommunicationChannel.values),
        allow_empty=False,
    )
