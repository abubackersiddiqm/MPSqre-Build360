
from rest_framework import serializers

from modules.portal.models import PortalScopeType, PortalShare, PortalType


class InvitationCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    portal_type = serializers.ChoiceField(choices=PortalType.choices)
    scope_type = serializers.ChoiceField(choices=PortalScopeType.choices)
    scope_public_id = serializers.UUIDField(required=False, allow_null=True)
    permission_codes = serializers.ListField(
        child=serializers.CharField(max_length=120),
        min_length=1,
        max_length=50,
    )
    expires_in_days = serializers.IntegerField(min_value=1, max_value=30, default=7)


class InvitationAcceptSerializer(serializers.Serializer):
    token = serializers.CharField(min_length=20, max_length=200, required=False, allow_blank=True)
    invitation_public_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs):
        token = (attrs.get("token") or "").strip()
        invitation_public_id = attrs.get("invitation_public_id")
        if bool(token) == bool(invitation_public_id):
            raise serializers.ValidationError("Provide either token or invitation_public_id.")
        return attrs


class InvitationDeliverySerializer(serializers.Serializer):
    dispatch_now = serializers.BooleanField(default=False)


class DirectGrantSerializer(serializers.Serializer):
    user_public_id = serializers.UUIDField()
    portal_type = serializers.ChoiceField(choices=PortalType.choices)
    scope_type = serializers.ChoiceField(choices=PortalScopeType.choices)
    scope_public_id = serializers.UUIDField(required=False, allow_null=True)
    permission_codes = serializers.ListField(
        child=serializers.CharField(max_length=120),
        min_length=1,
        max_length=50,
    )
    effective_to = serializers.DateTimeField(required=False, allow_null=True)


class GrantRevokeSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=500)


class ShareCreateSerializer(serializers.Serializer):
    grant_public_id = serializers.UUIDField()
    entity_type = serializers.CharField(max_length=100)
    entity_public_id = serializers.UUIDField()
    access_level = serializers.ChoiceField(choices=PortalShare.AccessLevel.choices)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)
