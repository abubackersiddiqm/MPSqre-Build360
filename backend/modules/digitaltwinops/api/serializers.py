from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers


class ModelCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=80)
    name = serializers.CharField(max_length=240)
    project_public_id = serializers.UUIDField(required=False, allow_null=True)
    site_reference = serializers.CharField(max_length=160, required=False, allow_blank=True, default="")
    discipline_code = serializers.CharField(max_length=60)
    model_type_code = serializers.CharField(max_length=40, required=False, default="AUTHORING")
    file_format_code = serializers.CharField(max_length=30, required=False, default="IFC")
    authoring_tool = serializers.CharField(max_length=160, required=False, allow_blank=True, default="")
    coordinate_system_code = serializers.CharField(max_length=80, required=False, default="PROJECT_LOCAL")
    storage_reference = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    checksum_sha256 = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    model_metadata = serializers.JSONField(required=False, default=dict)


class RevisionCreateSerializer(serializers.Serializer):
    model_public_id = serializers.UUIDField()
    revision_code = serializers.CharField(max_length=40)
    issue_purpose_code = serializers.CharField(max_length=60, required=False, default="COORDINATION")
    file_reference = serializers.CharField(max_length=500)
    checksum_sha256 = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class LifecycleTransitionSerializer(serializers.Serializer):
    status_code = serializers.CharField(max_length=30)
    expected_version = serializers.IntegerField(min_value=1)


class ClashTransitionSerializer(LifecycleTransitionSerializer):
    resolution_note = serializers.CharField(required=False, allow_blank=True, default="")


class FederationCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=80)
    name = serializers.CharField(max_length=240)
    project_public_id = serializers.UUIDField(required=False, allow_null=True)
    model_public_ids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)
    coordination_date = serializers.DateField(required=False, allow_null=True)


class ClashCreateSerializer(serializers.Serializer):
    federation_public_id = serializers.UUIDField()
    clash_number = serializers.CharField(max_length=80)
    clash_type_code = serializers.CharField(max_length=60, required=False, default="HARD")
    severity_code = serializers.CharField(max_length=30, required=False, default="MEDIUM")
    discipline_a_code = serializers.CharField(max_length=60)
    discipline_b_code = serializers.CharField(max_length=60)
    element_a_reference = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    element_b_reference = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    location_reference = serializers.CharField(max_length=240, required=False, allow_blank=True, default="")
    coordinates = serializers.JSONField(required=False, default=dict)
    title = serializers.CharField(max_length=240)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    assigned_to_public_id = serializers.UUIDField(required=False, allow_null=True)
    due_date = serializers.DateField(required=False, allow_null=True)


class IssueCreateSerializer(serializers.Serializer):
    project_public_id = serializers.UUIDField(required=False, allow_null=True)
    site_reference = serializers.CharField(max_length=160, required=False, allow_blank=True, default="")
    model_public_id = serializers.UUIDField(required=False, allow_null=True)
    revision_public_id = serializers.UUIDField(required=False, allow_null=True)
    issue_code = serializers.CharField(max_length=80)
    category_code = serializers.CharField(max_length=60, required=False, default="COORDINATION")
    priority_code = serializers.CharField(max_length=30, required=False, default="NORMAL")
    title = serializers.CharField(max_length=240)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    assigned_to_public_id = serializers.UUIDField(required=False, allow_null=True)
    due_date = serializers.DateField(required=False, allow_null=True)
    evidence = serializers.JSONField(required=False, default=dict)


class DeviceCreateSerializer(serializers.Serializer):
    project_public_id = serializers.UUIDField(required=False, allow_null=True)
    site_reference = serializers.CharField(max_length=160, required=False, allow_blank=True, default="")
    code = serializers.CharField(max_length=80)
    name = serializers.CharField(max_length=240)
    device_type_code = serializers.CharField(max_length=60)
    external_device_reference = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    provider_code = serializers.CharField(max_length=80, required=False, default="GENERIC")
    protocol_code = serializers.CharField(max_length=40, required=False, default="HTTP")
    metric_code = serializers.CharField(max_length=80)
    unit_code = serializers.CharField(max_length=40)
    threshold_configuration = serializers.JSONField(required=False, default=dict)
    installed_at = serializers.DateTimeField(required=False, allow_null=True)
    firmware_version = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")


class TelemetryCreateSerializer(serializers.Serializer):
    device_public_id = serializers.UUIDField()
    observed_at = serializers.DateTimeField()
    metric_code = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    numeric_value = serializers.DecimalField(
        max_digits=20,
        decimal_places=6,
        required=False,
        allow_null=True,
        min_value=Decimal("-99999999999999.999999"),
    )
    text_value = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    unit_code = serializers.CharField(max_length=40, required=False, allow_blank=True, default="")
    quality_code = serializers.CharField(max_length=30, required=False, default="GOOD")
    source_reference = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")
    payload = serializers.JSONField(required=False, default=dict)

    def validate(self, attrs):
        if attrs.get("numeric_value") is None and not attrs.get("text_value"):
            raise serializers.ValidationError("Telemetry reading requires numeric_value or text_value.")
        return attrs


class AssetCreateSerializer(serializers.Serializer):
    project_public_id = serializers.UUIDField(required=False, allow_null=True)
    site_reference = serializers.CharField(max_length=160, required=False, allow_blank=True, default="")
    asset_tag = serializers.CharField(max_length=100)
    asset_name = serializers.CharField(max_length=240)
    classification_code = serializers.CharField(max_length=80)
    model_public_id = serializers.UUIDField(required=False, allow_null=True)
    model_element_reference = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    serial_number = serializers.CharField(max_length=160, required=False, allow_blank=True, default="")
    manufacturer = serializers.CharField(max_length=240, required=False, allow_blank=True, default="")
    location_reference = serializers.CharField(max_length=240, required=False, allow_blank=True, default="")
    commissioned_on = serializers.DateField(required=False, allow_null=True)
    warranty_end_on = serializers.DateField(required=False, allow_null=True)
    maintainable = serializers.BooleanField(required=False, default=True)
    document_references = serializers.ListField(child=serializers.CharField(max_length=500), required=False, default=list)
    attributes = serializers.JSONField(required=False, default=dict)
