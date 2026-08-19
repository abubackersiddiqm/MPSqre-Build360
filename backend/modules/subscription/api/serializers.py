from rest_framework import serializers


class EntitlementOverrideSerializer(serializers.Serializer):
    entitlement_code = serializers.RegexField(r"^[a-z0-9][a-z0-9._-]{1,149}$")
    enabled = serializers.BooleanField()
    limit_value = serializers.IntegerField(min_value=0, required=False, allow_null=True)
    effective_from = serializers.DateTimeField()
    effective_to = serializers.DateTimeField(required=False, allow_null=True)
    reason_code = serializers.RegexField(r"^[a-z0-9][a-z0-9._-]{1,99}$")
