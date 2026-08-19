from decimal import Decimal

from rest_framework import serializers


class EndpointSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=80)
    name = serializers.CharField(max_length=180)
    route_pattern = serializers.CharField(max_length=300)
    method_code = serializers.ChoiceField(choices=["GET", "POST", "PUT", "PATCH", "DELETE"], default="GET")
    service_code = serializers.CharField(max_length=50, default="BACKEND")
    critical = serializers.BooleanField(default=True)
    target_p95_ms = serializers.IntegerField(min_value=1, max_value=86_400_000, default=750)
    target_availability_percent = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0.00"),
        max_value=Decimal("100.00"),
        default=Decimal("99.90"),
    )
    active = serializers.BooleanField(default=True)


class PerformanceSampleSerializer(serializers.Serializer):
    endpoint_public_id = serializers.UUIDField(required=False, allow_null=True)
    source_code = serializers.ChoiceField(choices=["BROWSER", "SERVER", "PROBE", "SYNTHETIC"], default="BROWSER")
    route_label = serializers.CharField(max_length=300)
    method_code = serializers.CharField(max_length=12, default="GET")
    http_status = serializers.IntegerField(min_value=100, max_value=599, required=False, allow_null=True)
    duration_ms = serializers.IntegerField(min_value=0, max_value=86_400_000)
    observed_at = serializers.DateTimeField()
    request_id = serializers.UUIDField(required=False, allow_null=True)
    session_fingerprint = serializers.RegexField(regex=r"^[0-9a-fA-F]{0,64}$", max_length=64, required=False, allow_blank=True)
    metadata = serializers.JSONField(required=False, default=dict)


class IncidentCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=80)
    title = serializers.CharField(max_length=240)
    severity_code = serializers.ChoiceField(choices=["P0", "P1", "P2", "P3"], default="P2")
    source_code = serializers.CharField(max_length=50, default="MANUAL")
    affected_service_code = serializers.CharField(max_length=80, required=False, allow_blank=True)
    impact_summary = serializers.CharField(required=False, allow_blank=True)
    detected_at = serializers.DateTimeField()
    owner_public_id = serializers.UUIDField(required=False, allow_null=True)


class IncidentTransitionSerializer(serializers.Serializer):
    status_code = serializers.ChoiceField(choices=["OPEN", "ACKNOWLEDGED", "MITIGATING", "RESOLVED", "CLOSED"])
    expected_version = serializers.IntegerField(min_value=1)
    owner_public_id = serializers.UUIDField(required=False, allow_null=True)
    root_cause = serializers.CharField(required=False, allow_blank=True)
    resolution_summary = serializers.CharField(required=False, allow_blank=True)


class RegressionCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=80)
    title = serializers.CharField(max_length=240)
    area_code = serializers.CharField(max_length=80, default="GENERAL")
    severity_code = serializers.ChoiceField(choices=["LOW", "MEDIUM", "HIGH", "CRITICAL"], default="MEDIUM")
    baseline_value = serializers.DecimalField(max_digits=16, decimal_places=3, required=False, allow_null=True)
    current_value = serializers.DecimalField(max_digits=16, decimal_places=3, required=False, allow_null=True)
    threshold_value = serializers.DecimalField(max_digits=16, decimal_places=3, required=False, allow_null=True)
    unit_code = serializers.CharField(max_length=30, required=False, allow_blank=True)
    detected_at = serializers.DateTimeField()
    incident_public_id = serializers.UUIDField(required=False, allow_null=True)
    evidence = serializers.JSONField(required=False, default=dict)
    notes = serializers.CharField(required=False, allow_blank=True)


class RegressionTransitionSerializer(serializers.Serializer):
    status_code = serializers.ChoiceField(choices=["OPEN", "ACCEPTED", "FIXED", "WONT_FIX"])
    notes = serializers.CharField(required=False, allow_blank=True)
    expected_version = serializers.IntegerField(min_value=1)


class GateDecisionSerializer(serializers.Serializer):
    status_code = serializers.ChoiceField(choices=["PENDING", "PASSED", "FAILED", "WAIVED"])
    notes = serializers.CharField(required=False, allow_blank=True)
    evidence = serializers.JSONField(required=False, default=dict)
    expected_version = serializers.IntegerField(min_value=1)
