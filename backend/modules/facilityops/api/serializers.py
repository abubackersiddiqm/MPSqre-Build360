from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers


class FacilityCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=80)
    name = serializers.CharField(max_length=240)
    facility_type_code = serializers.CharField(max_length=60, required=False, default="BUILDING")
    project_public_id = serializers.UUIDField(required=False, allow_null=True)
    site_reference = serializers.CharField(max_length=160, required=False, allow_blank=True, default="")
    external_reference = serializers.CharField(max_length=160, required=False, allow_blank=True, default="")
    address = serializers.JSONField(required=False, default=dict)
    timezone = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    gross_area = serializers.DecimalField(max_digits=18, decimal_places=3, required=False, allow_null=True, min_value=Decimal("0"))
    area_unit_code = serializers.CharField(max_length=30, required=False, default="SQ_M")
    occupancy_capacity = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    operational_from = serializers.DateField(required=False, allow_null=True)


class SpaceCreateSerializer(serializers.Serializer):
    facility_public_id = serializers.UUIDField()
    parent_public_id = serializers.UUIDField(required=False, allow_null=True)
    code = serializers.CharField(max_length=80)
    name = serializers.CharField(max_length=240)
    space_type_code = serializers.CharField(max_length=60, required=False, default="ROOM")
    floor_reference = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    area = serializers.DecimalField(max_digits=18, decimal_places=3, required=False, allow_null=True, min_value=Decimal("0"))
    area_unit_code = serializers.CharField(max_length=30, required=False, default="SQ_M")
    criticality_code = serializers.CharField(max_length=30, required=False, default="NORMAL")


class AssetCreateSerializer(serializers.Serializer):
    facility_public_id = serializers.UUIDField()
    space_public_id = serializers.UUIDField(required=False, allow_null=True)
    asset_tag = serializers.CharField(max_length=100)
    asset_name = serializers.CharField(max_length=240)
    classification_code = serializers.CharField(max_length=80)
    source_handover_public_id = serializers.UUIDField(required=False, allow_null=True)
    model_element_reference = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    manufacturer = serializers.CharField(max_length=240, required=False, allow_blank=True, default="")
    model_number = serializers.CharField(max_length=160, required=False, allow_blank=True, default="")
    serial_number = serializers.CharField(max_length=160, required=False, allow_blank=True, default="")
    commissioned_on = serializers.DateField(required=False, allow_null=True)
    warranty_start_on = serializers.DateField(required=False, allow_null=True)
    warranty_end_on = serializers.DateField(required=False, allow_null=True)
    criticality_code = serializers.CharField(max_length=30, required=False, default="NORMAL")
    condition_code = serializers.CharField(max_length=30, required=False, default="GOOD")
    maintainable = serializers.BooleanField(required=False, default=True)
    service_interval_days = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    next_service_on = serializers.DateField(required=False, allow_null=True)
    document_references = serializers.ListField(child=serializers.CharField(max_length=500), required=False, default=list)
    attributes = serializers.JSONField(required=False, default=dict)


class PlanCreateSerializer(serializers.Serializer):
    asset_public_id = serializers.UUIDField()
    code = serializers.CharField(max_length=80)
    name = serializers.CharField(max_length=240)
    plan_type_code = serializers.CharField(max_length=40, required=False, default="PREVENTIVE")
    frequency_days = serializers.IntegerField(min_value=1)
    lead_time_days = serializers.IntegerField(required=False, default=7, min_value=0)
    next_due_date = serializers.DateField()
    estimated_duration_minutes = serializers.IntegerField(required=False, default=60, min_value=1)
    checklist = serializers.ListField(child=serializers.CharField(max_length=300), required=False, default=list)


class ServiceRequestCreateSerializer(serializers.Serializer):
    facility_public_id = serializers.UUIDField()
    space_public_id = serializers.UUIDField(required=False, allow_null=True)
    asset_public_id = serializers.UUIDField(required=False, allow_null=True)
    request_number = serializers.CharField(max_length=80)
    category_code = serializers.CharField(max_length=60, required=False, default="GENERAL")
    priority_code = serializers.CharField(max_length=30, required=False, default="NORMAL")
    channel_code = serializers.CharField(max_length=30, required=False, default="PORTAL")
    requester_reference = serializers.CharField(max_length=160, required=False, allow_blank=True, default="")
    title = serializers.CharField(max_length=240)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    assigned_to_public_id = serializers.UUIDField(required=False, allow_null=True)


class WorkOrderCreateSerializer(serializers.Serializer):
    asset_public_id = serializers.UUIDField()
    plan_public_id = serializers.UUIDField(required=False, allow_null=True)
    service_request_public_id = serializers.UUIDField(required=False, allow_null=True)
    work_order_number = serializers.CharField(max_length=80)
    work_type_code = serializers.CharField(max_length=40, required=False, default="CORRECTIVE")
    priority_code = serializers.CharField(max_length=30, required=False, default="NORMAL")
    title = serializers.CharField(max_length=240)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    assigned_to_public_id = serializers.UUIDField(required=False, allow_null=True)
    vendor_reference = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    due_date = serializers.DateField(required=False, allow_null=True)
    scheduled_start_at = serializers.DateTimeField(required=False, allow_null=True)
    scheduled_end_at = serializers.DateTimeField(required=False, allow_null=True)
    estimated_cost = serializers.DecimalField(max_digits=18, decimal_places=2, required=False, allow_null=True, min_value=Decimal("0"))
    currency_code = serializers.CharField(max_length=3, required=False, allow_blank=True, default="")


class WarrantyClaimCreateSerializer(serializers.Serializer):
    asset_public_id = serializers.UUIDField()
    work_order_public_id = serializers.UUIDField(required=False, allow_null=True)
    claim_number = serializers.CharField(max_length=80)
    supplier_reference = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    warranty_reference = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    reported_on = serializers.DateField()
    failure_date = serializers.DateField(required=False, allow_null=True)
    issue_description = serializers.CharField()
    claimed_amount = serializers.DecimalField(max_digits=18, decimal_places=2, required=False, allow_null=True, min_value=Decimal("0"))
    currency_code = serializers.CharField(max_length=3, required=False, allow_blank=True, default="")


class InspectionCreateSerializer(serializers.Serializer):
    facility_public_id = serializers.UUIDField()
    space_public_id = serializers.UUIDField(required=False, allow_null=True)
    asset_public_id = serializers.UUIDField(required=False, allow_null=True)
    inspection_number = serializers.CharField(max_length=80)
    inspection_type_code = serializers.CharField(max_length=60, required=False, default="CONDITION")
    scheduled_on = serializers.DateField(required=False, allow_null=True)
    inspected_on = serializers.DateField(required=False, allow_null=True)
    condition_code = serializers.CharField(max_length=30, required=False, default="GOOD")
    score = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True, min_value=Decimal("0"), max_value=Decimal("100"))
    findings = serializers.CharField(required=False, allow_blank=True, default="")
    actions_required = serializers.CharField(required=False, allow_blank=True, default="")
    evidence = serializers.JSONField(required=False, default=dict)


class LifecycleEventCreateSerializer(serializers.Serializer):
    asset_public_id = serializers.UUIDField()
    event_type_code = serializers.CharField(max_length=60)
    summary = serializers.CharField(max_length=300)
    from_status_code = serializers.CharField(max_length=40, required=False, allow_blank=True, default="")
    to_status_code = serializers.CharField(max_length=40, required=False, allow_blank=True, default="")
    reference = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")
    event_metadata = serializers.JSONField(required=False, default=dict)


class LifecycleTransitionSerializer(serializers.Serializer):
    status_code = serializers.CharField(max_length=30)
    expected_version = serializers.IntegerField(min_value=1)
    note = serializers.CharField(required=False, allow_blank=True, default="")


class WorkOrderTransitionSerializer(LifecycleTransitionSerializer):
    completion_evidence = serializers.JSONField(required=False, default=dict)


class WarrantyTransitionSerializer(LifecycleTransitionSerializer):
    approved_amount = serializers.DecimalField(max_digits=18, decimal_places=2, required=False, allow_null=True, min_value=Decimal("0"))
