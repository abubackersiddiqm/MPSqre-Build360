from __future__ import annotations

from rest_framework import serializers

from modules.safetyops.models import (
    CorrectiveAction,
    PermitToWork,
    SafetyApproval,
    SafetyIncident,
    SafetyInspection,
    SafetyObservation,
    SafetyPolicyVersion,
    SafetyRisk,
    ToolboxTalk,
)


class SafetyPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = SafetyPolicyVersion
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


class SafetyObservationSerializer(serializers.ModelSerializer):
    policy_code = serializers.CharField(source="policy.code", read_only=True)
    policy_version = serializers.IntegerField(source="policy.version", read_only=True)

    class Meta:
        model = SafetyObservation
        fields = (
            "public_id",
            "observation_code",
            "project_public_id",
            "location_public_id",
            "category_code",
            "severity_code",
            "status_code",
            "title",
            "description",
            "observed_at",
            "observed_by_membership_public_id",
            "responsible_membership_public_id",
            "due_at",
            "closed_at",
            "closure_note",
            "policy_code",
            "policy_version",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class SafetyObservationCreateSerializer(PolicyBoundCreateSerializer):
    observation_code = serializers.CharField(max_length=80)
    project_public_id = serializers.UUIDField(required=False, allow_null=True)
    location_public_id = serializers.UUIDField(required=False, allow_null=True)
    category_code = serializers.CharField(max_length=100)
    severity_code = serializers.CharField(max_length=80)
    title = serializers.CharField(max_length=240)
    description = serializers.CharField(required=False, allow_blank=True)
    observed_at = serializers.DateTimeField()
    responsible_membership_public_id = serializers.UUIDField(required=False, allow_null=True)
    due_at = serializers.DateTimeField(required=False, allow_null=True)
    evidence_reference = serializers.CharField(required=False, allow_blank=True, max_length=500)


class TransitionSerializer(serializers.Serializer):
    target_status_code = serializers.CharField(max_length=80)
    expected_version = serializers.IntegerField(required=False, min_value=1)
    closure_note = serializers.CharField(required=False, allow_blank=True)
    root_cause = serializers.CharField(required=False, allow_blank=True)


class SafetyIncidentSerializer(serializers.ModelSerializer):
    policy_code = serializers.CharField(source="policy.code", read_only=True)
    policy_version = serializers.IntegerField(source="policy.version", read_only=True)

    class Meta:
        model = SafetyIncident
        fields = (
            "public_id",
            "incident_code",
            "project_public_id",
            "location_public_id",
            "incident_type_code",
            "severity_code",
            "status_code",
            "title",
            "description",
            "occurred_at",
            "reported_at",
            "reported_by_membership_public_id",
            "affected_people_count",
            "lost_time",
            "regulator_reportable",
            "immediate_action",
            "root_cause",
            "closed_at",
            "policy_code",
            "policy_version",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class SafetyIncidentCreateSerializer(PolicyBoundCreateSerializer):
    incident_code = serializers.CharField(max_length=80)
    project_public_id = serializers.UUIDField(required=False, allow_null=True)
    location_public_id = serializers.UUIDField(required=False, allow_null=True)
    incident_type_code = serializers.CharField(max_length=100)
    severity_code = serializers.CharField(max_length=80)
    title = serializers.CharField(max_length=240)
    description = serializers.CharField()
    occurred_at = serializers.DateTimeField()
    reported_at = serializers.DateTimeField()
    affected_people_count = serializers.IntegerField(required=False, min_value=0)
    lost_time = serializers.BooleanField(required=False)
    regulator_reportable = serializers.BooleanField(required=False)
    immediate_action = serializers.CharField(required=False, allow_blank=True)
    evidence_reference = serializers.CharField(required=False, allow_blank=True, max_length=500)


class PermitToWorkSerializer(serializers.ModelSerializer):
    policy_code = serializers.CharField(source="policy.code", read_only=True)
    policy_version = serializers.IntegerField(source="policy.version", read_only=True)

    class Meta:
        model = PermitToWork
        fields = (
            "public_id",
            "permit_code",
            "project_public_id",
            "location_public_id",
            "permit_type_code",
            "risk_level_code",
            "status_code",
            "work_summary",
            "valid_from",
            "valid_until",
            "issuer_membership_public_id",
            "receiver_membership_public_id",
            "approved_at",
            "suspended_at",
            "closed_at",
            "conditions",
            "isolation_points",
            "policy_code",
            "policy_version",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class PermitToWorkCreateSerializer(PolicyBoundCreateSerializer):
    permit_code = serializers.CharField(max_length=80)
    project_public_id = serializers.UUIDField(required=False, allow_null=True)
    location_public_id = serializers.UUIDField(required=False, allow_null=True)
    permit_type_code = serializers.CharField(max_length=100)
    risk_level_code = serializers.CharField(max_length=80)
    work_summary = serializers.CharField(max_length=300)
    valid_from = serializers.DateTimeField()
    valid_until = serializers.DateTimeField()
    receiver_membership_public_id = serializers.UUIDField()
    conditions = serializers.ListField(child=serializers.JSONField(), required=False)
    isolation_points = serializers.ListField(child=serializers.JSONField(), required=False)
    evidence_reference = serializers.CharField(required=False, allow_blank=True, max_length=500)


class SafetyInspectionSerializer(serializers.ModelSerializer):
    policy_code = serializers.CharField(source="policy.code", read_only=True)
    policy_version = serializers.IntegerField(source="policy.version", read_only=True)

    class Meta:
        model = SafetyInspection
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
            "checklist_result",
            "policy_code",
            "policy_version",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class SafetyInspectionCreateSerializer(PolicyBoundCreateSerializer):
    inspection_code = serializers.CharField(max_length=80)
    project_public_id = serializers.UUIDField(required=False, allow_null=True)
    location_public_id = serializers.UUIDField(required=False, allow_null=True)
    inspection_type_code = serializers.CharField(max_length=100)
    status_code = serializers.CharField(max_length=80)
    result_code = serializers.CharField(required=False, allow_blank=True, max_length=80)
    scheduled_at = serializers.DateTimeField()
    completed_at = serializers.DateTimeField(required=False, allow_null=True)
    inspector_membership_public_id = serializers.UUIDField(required=False, allow_null=True)
    score_percent = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, allow_null=True
    )
    checklist_result = serializers.JSONField(required=False)
    evidence_reference = serializers.CharField(required=False, allow_blank=True, max_length=500)


class ToolboxTalkSerializer(serializers.ModelSerializer):
    policy_code = serializers.CharField(source="policy.code", read_only=True)
    policy_version = serializers.IntegerField(source="policy.version", read_only=True)

    class Meta:
        model = ToolboxTalk
        fields = (
            "public_id",
            "talk_code",
            "project_public_id",
            "location_public_id",
            "topic_code",
            "status_code",
            "title",
            "delivered_at",
            "facilitator_membership_public_id",
            "attendee_count",
            "acknowledgement_count",
            "notes",
            "policy_code",
            "policy_version",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class ToolboxTalkCreateSerializer(PolicyBoundCreateSerializer):
    talk_code = serializers.CharField(max_length=80)
    project_public_id = serializers.UUIDField(required=False, allow_null=True)
    location_public_id = serializers.UUIDField(required=False, allow_null=True)
    topic_code = serializers.CharField(max_length=100)
    status_code = serializers.CharField(max_length=80)
    title = serializers.CharField(max_length=240)
    delivered_at = serializers.DateTimeField()
    attendee_count = serializers.IntegerField(required=False, min_value=0)
    acknowledgement_count = serializers.IntegerField(required=False, min_value=0)
    notes = serializers.CharField(required=False, allow_blank=True)
    evidence_reference = serializers.CharField(required=False, allow_blank=True, max_length=500)


class CorrectiveActionSerializer(serializers.ModelSerializer):
    policy_code = serializers.CharField(source="policy.code", read_only=True)
    policy_version = serializers.IntegerField(source="policy.version", read_only=True)

    class Meta:
        model = CorrectiveAction
        fields = (
            "public_id",
            "action_code",
            "source_type_code",
            "source_public_id",
            "project_public_id",
            "location_public_id",
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
            "policy_version",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class CorrectiveActionCreateSerializer(PolicyBoundCreateSerializer):
    action_code = serializers.CharField(max_length=80)
    source_type_code = serializers.CharField(max_length=80)
    source_public_id = serializers.UUIDField(required=False, allow_null=True)
    project_public_id = serializers.UUIDField(required=False, allow_null=True)
    location_public_id = serializers.UUIDField(required=False, allow_null=True)
    category_code = serializers.CharField(max_length=100)
    priority_code = serializers.CharField(max_length=80)
    title = serializers.CharField(max_length=240)
    description = serializers.CharField(required=False, allow_blank=True)
    owner_membership_public_id = serializers.UUIDField(required=False, allow_null=True)
    due_at = serializers.DateTimeField(required=False, allow_null=True)


class SafetyApprovalSerializer(serializers.ModelSerializer):
    policy_code = serializers.CharField(source="policy.code", read_only=True)
    policy_version = serializers.IntegerField(source="policy.version", read_only=True)

    class Meta:
        model = SafetyApproval
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
            "policy_version",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class SafetyApprovalRequestSerializer(PolicyBoundCreateSerializer):
    entity_type_code = serializers.CharField(max_length=80)
    entity_public_id = serializers.UUIDField()
    step_code = serializers.CharField(max_length=100)
    requested_from_membership_public_id = serializers.UUIDField()
    due_at = serializers.DateTimeField(required=False, allow_null=True)


class SafetyApprovalDecisionSerializer(serializers.Serializer):
    decision_code = serializers.CharField(max_length=80)
    decision_note = serializers.CharField(required=False, allow_blank=True)
    expected_version = serializers.IntegerField(required=False, min_value=1)


class SafetyRiskSerializer(serializers.ModelSerializer):
    policy_code = serializers.CharField(source="policy.code", read_only=True)
    policy_version = serializers.IntegerField(source="policy.version", read_only=True)

    class Meta:
        model = SafetyRisk
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
            "policy_version",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class SafetyRiskCreateSerializer(PolicyBoundCreateSerializer):
    linked_entity_type_code = serializers.CharField(max_length=80)
    linked_entity_public_id = serializers.UUIDField(required=False, allow_null=True)
    risk_code = serializers.CharField(max_length=100)
    severity_code = serializers.CharField(max_length=80)
    message = serializers.CharField(max_length=500)
    due_at = serializers.DateTimeField(required=False, allow_null=True)


class SafetyRiskResolutionSerializer(serializers.Serializer):
    resolution_note = serializers.CharField()
