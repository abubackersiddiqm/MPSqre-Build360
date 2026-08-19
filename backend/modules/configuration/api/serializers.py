from rest_framework import serializers


class ConfigurationDraftSerializer(serializers.Serializer):
    definition_code = serializers.CharField(max_length=150)
    payload = serializers.JSONField()
    effective_from = serializers.DateTimeField()
    effective_to = serializers.DateTimeField(required=False, allow_null=True)
