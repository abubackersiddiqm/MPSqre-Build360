from __future__ import annotations

from rest_framework import serializers

from modules.equipmentops.models import (
    EquipmentApproval,
    EquipmentAsset,
    EquipmentDeployment,
    EquipmentInspection,
    EquipmentMeterReading,
    EquipmentPolicyVersion,
    EquipmentRisk,
    MaintenanceWorkOrder,
)


class EquipmentPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = EquipmentPolicyVersion
        fields = [
            "public_id",
            "code",
            "name",
            "version",
            "status_code",
            "effective_from",
            "effective_to",
            "published_at",
            "retired_at",
            "configuration",
            "change_note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["public_id", "created_at", "updated_at"]


class EquipmentAssetSerializer(serializers.ModelSerializer):
    policy_code = serializers.CharField(source="policy.code", read_only=True)
    policy_version = serializers.IntegerField(source="policy.version", read_only=True)

    class Meta:
        model = EquipmentAsset
        fields = [
            "public_id",
            "policy_code",
            "policy_version",
            "asset_code",
            "name",
            "category_code",
            "asset_type_code",
            "ownership_code",
            "status_code",
            "manufacturer",
            "model_reference",
            "serial_number",
            "registration_number",
            "commissioned_on",
            "decommissioned_on",
            "home_location_public_id",
            "responsible_membership_public_id",
            "capacity_value",
            "capacity_unit_code",
            "meter_type_code",
            "current_meter_value",
            "acquisition_cost",
            "currency",
            "next_service_on",
            "next_service_meter",
            "compliance_due_on",
            "metadata",
            "version",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "public_id",
            "status_code",
            "version",
            "created_at",
            "updated_at",
        ]


class EquipmentAssetCreateSerializer(serializers.Serializer):
    policy_public_id = serializers.UUIDField()
    asset_code = serializers.CharField(max_length=80)
    name = serializers.CharField(max_length=200)
    category_code = serializers.CharField(max_length=80)
    asset_type_code = serializers.CharField(max_length=80)
    ownership_code = serializers.CharField(max_length=80)
    manufacturer = serializers.CharField(max_length=150, allow_blank=True, required=False)
    model_reference = serializers.CharField(max_length=150, allow_blank=True, required=False)
    serial_number = serializers.CharField(max_length=150, allow_blank=True, required=False)
    registration_number = serializers.CharField(max_length=150, allow_blank=True, required=False)
    commissioned_on = serializers.DateField(required=False, allow_null=True)
    home_location_public_id = serializers.UUIDField(required=False, allow_null=True)
    responsible_membership_public_id = serializers.UUIDField(required=False, allow_null=True)
    capacity_value = serializers.DecimalField(
        max_digits=18,
        decimal_places=4,
        required=False,
        allow_null=True,
    )
    capacity_unit_code = serializers.CharField(max_length=50, allow_blank=True, required=False)
    meter_type_code = serializers.CharField(max_length=50, allow_blank=True, required=False)
    current_meter_value = serializers.DecimalField(max_digits=18, decimal_places=2, required=False)
    acquisition_cost = serializers.DecimalField(max_digits=18, decimal_places=2, required=False)
    currency = serializers.CharField(max_length=3, required=False)
    next_service_on = serializers.DateField(required=False, allow_null=True)
    next_service_meter = serializers.DecimalField(
        max_digits=18,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    compliance_due_on = serializers.DateField(required=False, allow_null=True)
    metadata = serializers.JSONField(required=False)


class EquipmentDeploymentSerializer(serializers.ModelSerializer):
    asset_public_id = serializers.UUIDField(source="asset.public_id", read_only=True)
    asset_code = serializers.CharField(source="asset.asset_code", read_only=True)

    class Meta:
        model = EquipmentDeployment
        fields = [
            "public_id",
            "asset_public_id",
            "asset_code",
            "deployment_code",
            "project_public_id",
            "location_public_id",
            "operator_employee_public_id",
            "status_code",
            "starts_at",
            "ends_at",
            "planned_meter_start",
            "planned_meter_end",
            "approved_at",
            "approved_by_public_id",
            "source_reference",
            "metadata",
            "version",
            "created_at",
            "updated_at",
        ]


class EquipmentDeploymentCreateSerializer(serializers.Serializer):
    asset_public_id = serializers.UUIDField()
    deployment_code = serializers.CharField(max_length=100)
    project_public_id = serializers.UUIDField(required=False, allow_null=True)
    location_public_id = serializers.UUIDField(required=False, allow_null=True)
    operator_employee_public_id = serializers.UUIDField(required=False, allow_null=True)
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField(required=False, allow_null=True)
    planned_meter_start = serializers.DecimalField(
        max_digits=18,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    planned_meter_end = serializers.DecimalField(
        max_digits=18,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    source_reference = serializers.CharField(max_length=150, allow_blank=True, required=False)
    metadata = serializers.JSONField(required=False)


class EquipmentMeterReadingSerializer(serializers.ModelSerializer):
    asset_public_id = serializers.UUIDField(source="asset.public_id", read_only=True)
    deployment_public_id = serializers.UUIDField(
        source="deployment.public_id",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = EquipmentMeterReading
        fields = [
            "public_id",
            "asset_public_id",
            "deployment_public_id",
            "reading_at",
            "meter_type_code",
            "reading_value",
            "source_code",
            "recorded_by_public_id",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class EquipmentMeterReadingCreateSerializer(serializers.Serializer):
    asset_public_id = serializers.UUIDField()
    deployment_public_id = serializers.UUIDField(required=False, allow_null=True)
    reading_at = serializers.DateTimeField()
    meter_type_code = serializers.CharField(max_length=50)
    reading_value = serializers.DecimalField(max_digits=18, decimal_places=2)
    source_code = serializers.CharField(max_length=80)
    evidence_object_key = serializers.CharField(
        max_length=500,
        allow_blank=True,
        required=False,
        write_only=True,
    )
    metadata = serializers.JSONField(required=False)
    expected_asset_version = serializers.IntegerField(min_value=1, required=False)


class MaintenanceWorkOrderSerializer(serializers.ModelSerializer):
    asset_public_id = serializers.UUIDField(source="asset.public_id", read_only=True)
    asset_code = serializers.CharField(source="asset.asset_code", read_only=True)

    class Meta:
        model = MaintenanceWorkOrder
        fields = [
            "public_id",
            "asset_public_id",
            "asset_code",
            "code",
            "maintenance_type_code",
            "priority_code",
            "status_code",
            "reported_at",
            "scheduled_start",
            "scheduled_end",
            "completed_at",
            "meter_at_open",
            "summary",
            "details",
            "vendor_public_id",
            "estimated_cost",
            "actual_cost",
            "currency",
            "requires_approval",
            "approved_at",
            "approved_by_public_id",
            "closed_at",
            "metadata",
            "version",
            "created_at",
            "updated_at",
        ]


class MaintenanceWorkOrderCreateSerializer(serializers.Serializer):
    asset_public_id = serializers.UUIDField()
    code = serializers.CharField(max_length=100)
    maintenance_type_code = serializers.CharField(max_length=80)
    priority_code = serializers.CharField(max_length=80)
    reported_at = serializers.DateTimeField(required=False)
    scheduled_start = serializers.DateTimeField(required=False, allow_null=True)
    scheduled_end = serializers.DateTimeField(required=False, allow_null=True)
    meter_at_open = serializers.DecimalField(
        max_digits=18,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    summary = serializers.CharField(max_length=300)
    details = serializers.CharField(allow_blank=True, required=False)
    vendor_public_id = serializers.UUIDField(required=False, allow_null=True)
    estimated_cost = serializers.DecimalField(max_digits=18, decimal_places=2, required=False)
    actual_cost = serializers.DecimalField(max_digits=18, decimal_places=2, required=False)
    currency = serializers.CharField(max_length=3, required=False)
    requires_approval = serializers.BooleanField(required=False)
    metadata = serializers.JSONField(required=False)


class MaintenanceTransitionSerializer(serializers.Serializer):
    target_status_code = serializers.CharField(max_length=80)
    expected_version = serializers.IntegerField(min_value=1)
    reason_code = serializers.CharField(max_length=100, allow_blank=True, required=False)


class EquipmentInspectionSerializer(serializers.ModelSerializer):
    asset_public_id = serializers.UUIDField(source="asset.public_id", read_only=True)
    asset_code = serializers.CharField(source="asset.asset_code", read_only=True)

    class Meta:
        model = EquipmentInspection
        fields = [
            "public_id",
            "asset_public_id",
            "asset_code",
            "inspection_code",
            "inspection_type_code",
            "status_code",
            "result_code",
            "inspected_at",
            "valid_until",
            "inspector_public_id",
            "score",
            "findings_count",
            "certificate_reference",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class EquipmentInspectionCreateSerializer(serializers.Serializer):
    asset_public_id = serializers.UUIDField()
    inspection_code = serializers.CharField(max_length=100)
    inspection_type_code = serializers.CharField(max_length=80)
    status_code = serializers.CharField(max_length=80)
    result_code = serializers.CharField(max_length=80)
    inspected_at = serializers.DateTimeField()
    valid_until = serializers.DateField(required=False, allow_null=True)
    inspector_public_id = serializers.UUIDField()
    score = serializers.DecimalField(
        max_digits=7,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    findings_count = serializers.IntegerField(min_value=0, required=False)
    certificate_reference = serializers.CharField(max_length=150, allow_blank=True, required=False)
    evidence_object_key = serializers.CharField(
        max_length=500,
        allow_blank=True,
        required=False,
        write_only=True,
    )
    metadata = serializers.JSONField(required=False)


class EquipmentApprovalSerializer(serializers.ModelSerializer):
    work_order_public_id = serializers.UUIDField(
        source="work_order.public_id",
        read_only=True,
    )
    work_order_code = serializers.CharField(source="work_order.code", read_only=True)

    class Meta:
        model = EquipmentApproval
        fields = [
            "public_id",
            "work_order_public_id",
            "work_order_code",
            "step_code",
            "status_code",
            "requested_from_membership_public_id",
            "requested_by_public_id",
            "requested_at",
            "due_at",
            "decided_by_public_id",
            "decided_at",
            "decision_code",
            "decision_reason",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class EquipmentApprovalRequestSerializer(serializers.Serializer):
    work_order_public_id = serializers.UUIDField()
    step_code = serializers.CharField(max_length=100)
    requested_from_membership_public_id = serializers.UUIDField()
    status_code = serializers.CharField(max_length=80)
    due_at = serializers.DateTimeField(required=False, allow_null=True)
    metadata = serializers.JSONField(required=False)


class EquipmentApprovalDecisionSerializer(serializers.Serializer):
    decision_code = serializers.CharField(max_length=80)
    decision_reason = serializers.CharField(max_length=500, allow_blank=True, required=False)


class EquipmentRiskSerializer(serializers.ModelSerializer):
    asset_public_id = serializers.UUIDField(source="asset.public_id", read_only=True)
    asset_code = serializers.CharField(source="asset.asset_code", read_only=True)
    work_order_public_id = serializers.UUIDField(
        source="work_order.public_id",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = EquipmentRisk
        fields = [
            "public_id",
            "asset_public_id",
            "asset_code",
            "work_order_public_id",
            "risk_code",
            "severity_code",
            "status_code",
            "message",
            "due_at",
            "assigned_to_membership_public_id",
            "resolved_at",
            "resolved_by_public_id",
            "resolution_code",
            "resolution_note",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class EquipmentRiskCreateSerializer(serializers.Serializer):
    asset_public_id = serializers.UUIDField()
    work_order_public_id = serializers.UUIDField(required=False, allow_null=True)
    risk_code = serializers.CharField(max_length=100)
    severity_code = serializers.CharField(max_length=80)
    status_code = serializers.CharField(max_length=80)
    message = serializers.CharField(max_length=1000)
    due_at = serializers.DateTimeField(required=False, allow_null=True)
    assigned_to_membership_public_id = serializers.UUIDField(required=False, allow_null=True)
    metadata = serializers.JSONField(required=False)


class EquipmentRiskResolutionSerializer(serializers.Serializer):
    resolution_code = serializers.CharField(max_length=80)
    resolution_note = serializers.CharField(max_length=1000, allow_blank=True, required=False)
    resolved_status_code = serializers.CharField(max_length=80, required=False)
