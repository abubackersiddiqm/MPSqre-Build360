from decimal import Decimal

from rest_framework import serializers


class LocalizationPackCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=80)
    name = serializers.CharField(max_length=200)
    country_code = serializers.CharField(min_length=2, max_length=2)
    locale = serializers.CharField(max_length=35)
    currency = serializers.CharField(min_length=3, max_length=3)
    timezone_code = serializers.CharField(max_length=64)
    unit_system_code = serializers.CharField(max_length=50)
    date_format = serializers.CharField(max_length=50, default="DD/MM/YYYY")
    time_format = serializers.CharField(max_length=20, default="24h")
    number_format = serializers.JSONField(default=dict)
    address_schema = serializers.JSONField(default=dict)
    tax_schema = serializers.JSONField(default=dict)
    terminology = serializers.JSONField(default=dict)
    effective_from = serializers.DateTimeField()
    effective_to = serializers.DateTimeField(required=False, allow_null=True)
    is_default = serializers.BooleanField(default=False)


class PublishSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)


class ExchangeRateCreateSerializer(serializers.Serializer):
    base_currency = serializers.CharField(min_length=3, max_length=3)
    quote_currency = serializers.CharField(min_length=3, max_length=3)
    rate = serializers.DecimalField(max_digits=20, decimal_places=8, min_value=Decimal("0.00000001"))
    effective_at = serializers.DateTimeField()
    source_code = serializers.CharField(max_length=100)


class ConnectorCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=100)
    name = serializers.CharField(max_length=200)
    connector_type = serializers.ChoiceField(
        choices=["ACCOUNTING", "IDENTITY", "STORAGE", "COMMUNICATION", "ANALYTICS", "CUSTOM"]
    )
    provider_code = serializers.CharField(max_length=100)
    direction = serializers.ChoiceField(choices=["INBOUND", "OUTBOUND", "BIDIRECTIONAL"])
    base_url = serializers.URLField(max_length=500, required=False, allow_blank=True)
    public_config = serializers.JSONField(default=dict)
    secret_ref = serializers.CharField(max_length=500, required=False, allow_blank=True)
    allowed_data_classes = serializers.ListField(
        child=serializers.CharField(max_length=100),
        required=False,
        default=list,
    )


class ApiClientCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    scopes = serializers.ListField(child=serializers.CharField(max_length=200), min_length=1)
    allowed_ip_ranges = serializers.ListField(
        child=serializers.CharField(max_length=100),
        required=False,
        default=list,
    )
    expires_at = serializers.DateTimeField(required=False, allow_null=True)


class ApiClientActionSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)


class WebhookCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=100)
    event_code = serializers.CharField(max_length=200)
    target_url = serializers.URLField(max_length=500)
    secret_ref = serializers.CharField(max_length=500)
    headers_public = serializers.JSONField(default=dict)
    allowed_data_classes = serializers.ListField(
        child=serializers.CharField(max_length=100),
        required=False,
        default=list,
    )


class StatusActionSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)
    target_status = serializers.CharField(max_length=20)
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)


class WebhookSimulationSerializer(serializers.Serializer):
    event_type = serializers.CharField(max_length=200)
    payload = serializers.JSONField(default=dict)


class MappingCreateSerializer(serializers.Serializer):
    connector_public_id = serializers.UUIDField()
    code = serializers.CharField(max_length=100)
    name = serializers.CharField(max_length=200)
    source_schema_code = serializers.CharField(max_length=150)
    target_schema_code = serializers.CharField(max_length=150)
    mappings = serializers.ListField(child=serializers.DictField(), min_length=1)
    transformations = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        default=list,
    )


class SyncStartSerializer(serializers.Serializer):
    connector_public_id = serializers.UUIDField()
    direction = serializers.ChoiceField(choices=["INBOUND", "OUTBOUND", "BIDIRECTIONAL"])
    idempotency_key = serializers.CharField(max_length=150)
    mapping_public_id = serializers.UUIDField(required=False, allow_null=True)


class SyncCompleteSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)
    status = serializers.ChoiceField(choices=["COMPLETED", "PARTIAL", "FAILED", "CANCELLED"])
    records_read = serializers.IntegerField(min_value=0)
    records_written = serializers.IntegerField(min_value=0)
    records_rejected = serializers.IntegerField(min_value=0)
    error_summary = serializers.CharField(max_length=500, required=False, allow_blank=True)



class MetaLeadConnectorCreateSerializer(serializers.Serializer):
    code = serializers.RegexField(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,99}$")
    name = serializers.CharField(max_length=200)
    page_id = serializers.CharField(max_length=160)
    page_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    lead_form_ids = serializers.ListField(
        child=serializers.CharField(max_length=160),
        required=False,
        default=list,
    )
    graph_api_version = serializers.RegexField(r"^v\d{1,2}\.\d{1,2}$")
    default_owner_membership_public_id = serializers.UUIDField()
    secret_ref = serializers.CharField(max_length=500)


class MetaLeadStatusSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)
    target_status = serializers.ChoiceField(choices=["ACTIVE", "SUSPENDED"])


class MetaLeadRotateVerifyTokenSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)


class MetaLeadTestSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)
