from rest_framework import serializers


class EmailDeliveryUpdateSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)
    delivery_mode = serializers.ChoiceField(choices=["PLATFORM", "TENANT_SMTP"])
    smtp_host = serializers.CharField(max_length=253, required=False, allow_blank=True)
    smtp_port = serializers.IntegerField(min_value=1, max_value=65535, default=587)
    smtp_username = serializers.CharField(max_length=320, required=False, allow_blank=True)
    smtp_password = serializers.CharField(
        max_length=1000,
        required=False,
        allow_blank=True,
        trim_whitespace=False,
        write_only=True,
    )
    clear_password = serializers.BooleanField(default=False)
    smtp_use_tls = serializers.BooleanField(default=True)
    smtp_use_ssl = serializers.BooleanField(default=False)
    from_email = serializers.EmailField(max_length=254, required=False, allow_blank=True)
    reply_to_email = serializers.EmailField(max_length=254, required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs.get("smtp_use_tls") and attrs.get("smtp_use_ssl"):
            raise serializers.ValidationError("SMTP TLS and SSL cannot both be enabled.")
        return attrs


class EmailDeliveryTestSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)
