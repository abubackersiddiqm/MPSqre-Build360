from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from modules.qualityops.models import (
    InspectionTestPlan,
    NonConformanceReport,
    QualityApproval,
    QualityCorrectiveAction,
    QualityInspection,
    QualityInspectionRequest,
    QualityPolicyVersion,
    QualityRisk,
    QualityTestResult,
)


class QualityPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = QualityPolicyVersion
        fields = (
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
            "created_by_membership_public_id",
            "published_by_membership_public_id",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "public_id",
            "created_by_membership_public_id",
            "published_by_membership_public_id",
            "created_at",
            "updated_at",
        )


class PolicyBoundCreateSerializer(serializers.Serializer):
    policy_public_id = serializers.UUIDField()


class InspectionTestPlanSerializer(serializers.ModelSerializer):
    policy_code = serializers.CharField(source="policy.code", read_only=True)
    policy_version = serializers.IntegerField(source="policy.version", read_only=True)

    class Meta:
        model = InspectionTestPlan
        fields = (
            "public_id",
            "itp_code",
            "project_public_id",
            "discipline_code",
            "work_package_code",
            "revision",
            "status_code",
            "title",
            "description",
            "hold_points",
            "witness_points",
            "acceptance_criteria",
            "approved_at",
            "approved_by_membership_public_id",
            "policy_code",
            "policy_version",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class InspectionTestPlanCreateSerializer(PolicyBoundCreateSerializer):
    itp_code = serializers.CharField(max_length=80)
    project_public_id = serializers.UUIDField(required=False, allow_null=True)
    discipline_code = serializers.CharField(max_length=100)
    work_package_code = serializers.CharField(max_length=120)
    revision = serializers.IntegerField(required=False, min_value=1)
    title = serializers.CharField(max_length=240)
    description = serializers.CharField(required=False, allow_blank=True)
    hold_points = serializers.ListField(child=serializers.JSONField(), required=False)
    witness_points = serializers.ListField(child=serializers.JSONField(), required=False)
    acceptance_criteria = serializers.JSONField(required=False)


class QualityInspectionRequestSerializer(serializers.ModelSerializer):
    policy_code = serializers.CharField(source="policy.code", read_only=True)
    itp_code = serializers.CharField(source="itp.itp_code", read_only=True, allow_null=True)

    class Meta:
        model = QualityInspectionRequest
        fields = (
            "public_id",
            "request_code",
            "request_type_code",
            "project_public_id",
            "location_public_id",
            "activity_code",
            "lot_or_batch_code",
            "supplier_public_id",
            "status_code",
            "requested_for",
            "requested_by_membership_public_id",
            "assigned_inspector_membership_public_id",
            "notes",
            "closed_at",
            "policy_code",
            "itp_code",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class QualityInspectionRequestCreateSerializer(PolicyBoundCreateSerializer):
    itp_public_id = serializers.UUIDField(required=False, allow_null=True)
    request_code = serializers.CharField(max_length=80)
    request_type_code = serializers.CharField(max_length=80)
    project_public_id = serializers.UUIDField(required=False, allow_null=True)
    location_public_id = serializers.UUIDField(required=False, allow_null=True)
    activity_code = serializers.CharField(max_length=120)
    lot_or_batch_code = serializers.CharField(required=False, allow_blank=True, max_length=120)
    supplier_public_id = serializers.UUIDField(required=False, allow_null=True)
    requested_for = serializers.DateTimeField()
    assigned_inspector_membership_public_id = serializers.UUIDField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class QualityInspectionSerializer(serializers.ModelSerializer):
    policy_code = serializers.CharField(source="policy.code", read_only=True)
    request_code = serializers.CharField(
        source="request.request_code", read_only=True, allow_null=True
    )

    class Meta:
        model = QualityInspection
        fields = (
            "public_id",
            "inspection_code",
            "project_public_id",
            "location_public_id",
            "inspection_type_code",
            "status_code",
            "result_code",
            "scheduled_at",
            "completed_at",
            "inspector_membership_public_id",
            "score_percent",
            "sample_size",
            "accepted_quantity",
            "rejected_quantity",
            "checklist_result",
            "policy_code",
            "request_code",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class QualityInspectionCreateSerializer(PolicyBoundCreateSerializer):
    request_public_id = serializers.UUIDField(required=False, allow_null=True)
    inspection_code = serializers.CharField(max_length=80)
    project_public_id = serializers.UUIDField(required=False, allow_null=True)
    location_public_id = serializers.UUIDField(required=False, allow_null=True)
    inspection_type_code = serializers.CharField(max_length=100)
    result_code = serializers.CharField(required=False, allow_blank=True, max_length=80)
    scheduled_at = serializers.DateTimeField()
    completed_at = serializers.DateTimeField(required=False, allow_null=True)
    inspector_membership_public_id = serializers.UUIDField(required=False, allow_null=True)
    score_percent = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        allow_null=True,
        min_value=Decimal("0.00"),
        max_value=Decimal("100.00"),
    )
    sample_size = serializers.IntegerField(required=False, min_value=0)
    accepted_quantity = serializers.IntegerField(required=False, min_value=0)
    rejected_quantity = serializers.IntegerField(required=False, min_value=0)
    checklist_result = serializers.JSONField(required=False)
    evidence_reference = serializers.CharField(required=False, allow_blank=True, max_length=500)


class QualityTestResultSerializer(serializers.ModelSerializer):
    policy_code = serializers.CharField(source="policy.code", read_only=True)
    inspection_code = serializers.CharField(
        source="inspection.inspection_code", read_only=True, allow_null=True
    )

    class Meta:
        model = QualityTestResult
        fields = (
            "public_id",
            "test_code",
            "test_type_code",
            "specimen_code",
            "laboratory_reference",
            "result_code",
            "measured_value",
            "unit_code",
            "specification_min",
            "specification_max",
            "tested_at",
            "tested_by_membership_public_id",
            "remarks",
            "policy_code",
            "inspection_code",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class QualityTestResultCreateSerializer(PolicyBoundCreateSerializer):
    inspection_public_id = serializers.UUIDField(required=False, allow_null=True)
    test_code = serializers.CharField(max_length=80)
    test_type_code = serializers.CharField(max_length=100)
    specimen_code = serializers.CharField(required=False, allow_blank=True, max_length=120)
    laboratory_reference = serializers.CharField(required=False, allow_blank=True, max_length=160)
    result_code = serializers.CharField(max_length=80)
    measured_value = serializers.DecimalField(
        max_digits=18, decimal_places=6, required=False, allow_null=True
    )
    unit_code = serializers.CharField(required=False, allow_blank=True, max_length=40)
    specification_min = serializers.DecimalField(
        max_digits=18, decimal_places=6, required=False, allow_null=True
    )
    specification_max = serializers.DecimalField(
        max_digits=18, decimal_places=6, required=False, allow_null=True
    )
    tested_at = serializers.DateTimeField()
    tested_by_membership_public_id = serializers.UUIDField(required=False, allow_null=True)
    certificate_reference = serializers.CharField(required=False, allow_blank=True, max_length=500)
    remarks = serializers.CharField(required=False, allow_blank=True)


class NonConformanceReportSerializer(serializers.ModelSerializer):
    policy_code = serializers.CharField(source="policy.code", read_only=True)

    class Meta:
        model = NonConformanceReport
        fields = (
            "public_id",
            "ncr_code",
            "project_public_id",
            "location_public_id",
            "source_type_code",
            "source_public_id",
            "category_code",
            "severity_code",
            "status_code",
            "title",
            "description",
            "detected_at",
            "detected_by_membership_public_id",
            "responsible_membership_public_id",
            "root_cause",
            "disposition_code",
            "due_at",
            "closed_at",
            "closure_note",
            "policy_code",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class NonConformanceReportCreateSerializer(PolicyBoundCreateSerializer):
    ncr_code = serializers.CharField(max_length=80)
    project_public_id = serializers.UUIDField(required=False, allow_null=True)
    location_public_id = serializers.UUIDField(required=False, allow_null=True)
    source_type_code = serializers.CharField(max_length=80)
    source_public_id = serializers.UUIDField(required=False, allow_null=True)
    category_code = serializers.CharField(max_length=100)
    severity_code = serializers.CharField(max_length=80)
    title = serializers.CharField(max_length=240)
    description = serializers.CharField()
    detected_at = serializers.DateTimeField()
    responsible_membership_public_id = serializers.UUIDField(required=False, allow_null=True)
    due_at = serializers.DateTimeField(required=False, allow_null=True)
    evidence_reference = serializers.CharField(required=False, allow_blank=True, max_length=500)


class QualityCorrectiveActionSerializer(serializers.ModelSerializer):
    policy_code = serializers.CharField(source="policy.code", read_only=True)

    class Meta:
        model = QualityCorrectiveAction
        fields = (
            "public_id",
            "action_code",
            "source_type_code",
            "source_public_id",
            "project_public_id",
            "category_code",
            "priority_code",
            "status_code",
            "title",
            "description",
            "owner_membership_public_id",
            "due_at",
            "completed_at",
            "verified_at",
            "verified_by_membership_public_id",
            "closure_note",
            "policy_code",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class QualityCorrectiveActionCreateSerializer(PolicyBoundCreateSerializer):
    action_code = serializers.CharField(max_length=80)
    source_type_code = serializers.CharField(max_length=80)
    source_public_id = serializers.UUIDField(required=False, allow_null=True)
    project_public_id = serializers.UUIDField(required=False, allow_null=True)
    category_code = serializers.CharField(max_length=100)
    priority_code = serializers.CharField(max_length=80)
    title = serializers.CharField(max_length=240)
    description = serializers.CharField(required=False, allow_blank=True)
    owner_membership_public_id = serializers.UUIDField(required=False, allow_null=True)
    due_at = serializers.DateTimeField(required=False, allow_null=True)


class QualityApprovalSerializer(serializers.ModelSerializer):
    policy_code = serializers.CharField(source="policy.code", read_only=True)

    class Meta:
        model = QualityApproval
        fields = (
            "public_id",
            "entity_type_code",
            "entity_public_id",
            "step_code",
            "status_code",
            "requested_by_membership_public_id",
            "requested_from_membership_public_id",
            "requested_at",
            "due_at",
            "decided_by_membership_public_id",
            "decided_at",
            "decision_note",
            "policy_code",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class QualityApprovalRequestSerializer(PolicyBoundCreateSerializer):
    entity_type_code = serializers.CharField(max_length=80)
    entity_public_id = serializers.UUIDField()
    step_code = serializers.CharField(max_length=100)
    requested_from_membership_public_id = serializers.UUIDField()
    due_at = serializers.DateTimeField(required=False, allow_null=True)


class QualityApprovalDecisionSerializer(serializers.Serializer):
    decision_code = serializers.CharField(max_length=80)
    decision_note = serializers.CharField(required=False, allow_blank=True)
    expected_version = serializers.IntegerField(required=False, min_value=1)


class QualityRiskSerializer(serializers.ModelSerializer):
    policy_code = serializers.CharField(source="policy.code", read_only=True)

    class Meta:
        model = QualityRisk
        fields = (
            "public_id",
            "linked_entity_type_code",
            "linked_entity_public_id",
            "risk_code",
            "severity_code",
            "status_code",
            "message",
            "due_at",
            "resolved_at",
            "resolved_by_membership_public_id",
            "resolution_note",
            "policy_code",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class QualityRiskCreateSerializer(PolicyBoundCreateSerializer):
    linked_entity_type_code = serializers.CharField(max_length=80)
    linked_entity_public_id = serializers.UUIDField(required=False, allow_null=True)
    risk_code = serializers.CharField(max_length=100)
    severity_code = serializers.CharField(max_length=80)
    message = serializers.CharField(max_length=500)
    due_at = serializers.DateTimeField(required=False, allow_null=True)


class QualityRiskResolutionSerializer(serializers.Serializer):
    resolution_note = serializers.CharField()
    expected_version = serializers.IntegerField(required=False, min_value=1)


class TransitionSerializer(serializers.Serializer):
    target_status_code = serializers.CharField(max_length=80)
    expected_version = serializers.IntegerField(required=False, min_value=1)
    closure_note = serializers.CharField(required=False, allow_blank=True)
    root_cause = serializers.CharField(required=False, allow_blank=True)
    disposition_code = serializers.CharField(required=False, allow_blank=True, max_length=100)
