from rest_framework import serializers


class UploadInitiateSerializer(serializers.Serializer):
    purpose_code = serializers.RegexField(r"^[a-z0-9][a-z0-9._-]{1,99}$")
    data_class = serializers.RegexField(r"^[a-z0-9][a-z0-9._-]{1,99}$")
    original_name = serializers.CharField(max_length=255)
    content_type = serializers.CharField(max_length=150)
    size_bytes = serializers.IntegerField(min_value=1)
    sha256 = serializers.RegexField(r"^[0-9a-fA-F]{64}$")
