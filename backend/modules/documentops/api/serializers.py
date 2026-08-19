from __future__ import annotations

from rest_framework import serializers

from modules.documentops.models import (
    ControlledDocument,
    DocumentApproval,
    DocumentControlPolicyVersion,
    DocumentDistribution,
    DocumentRevision,
    DocumentRisk,
    DocumentTransmittal,
    RequestForInformation,
    TechnicalSubmittal,
)


class DocumentControlPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentControlPolicyVersion
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


class ControlledDocumentSerializer(serializers.ModelSerializer):
    policy_code = serializers.CharField(source="policy.code", read_only=True)
    policy_version = serializers.IntegerField(source="policy.version", read_only=True)

    class Meta:
        model = ControlledDocument
        fields = (
            "public_id",
            "document_number",
            "project_public_id",
            "discipline_code",
            "document_type_code",
            "title",
            "description",
            "status_code",
            "current_revision_code",
            "confidentiality_code",
            "originator_membership_public_id",
            "owner_membership_public_id",
            "attributes",
            "policy_code",
            "policy_version",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class ControlledDocumentCreateSerializer(PolicyBoundCreateSerializer):
    document_number = serializers.CharField(max_length=120)
    project_public_id = serializers.UUIDField(required=False, allow_null=True)
    discipline_code = serializers.CharField(max_length=100)
    document_type_code = serializers.CharField(max_length=100)
    title = serializers.CharField(max_length=300)
    description = serializers.CharField(required=False, allow_blank=True)
    confidentiality_code = serializers.CharField(required=False, allow_blank=True, max_length=80)
    originator_membership_public_id = serializers.UUIDField(required=False, allow_null=True)
    owner_membership_public_id = serializers.UUIDField(required=False, allow_null=True)
    attributes = serializers.JSONField(required=False)


class DocumentRevisionSerializer(serializers.ModelSerializer):
    policy_code = serializers.CharField(source="policy.code", read_only=True)
    document_number = serializers.CharField(source="document.document_number", read_only=True)

    class Meta:
        model = DocumentRevision
        fields = (
            "public_id",
            "document_number",
            "revision_code",
            "sequence_number",
            "status_code",
            "purpose_code",
            "description",
            "file_size_bytes",
            "created_by_membership_public_id",
            "reviewed_by_membership_public_id",
            "approved_by_membership_public_id",
            "submitted_at",
            "issued_at",
            "superseded_at",
            "policy_code",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class DocumentRevisionCreateSerializer(PolicyBoundCreateSerializer):
    document_public_id = serializers.UUIDField()
    revision_code = serializers.CharField(max_length=40)
    sequence_number = serializers.IntegerField(required=False, min_value=1)
    purpose_code = serializers.CharField(max_length=100)
    description = serializers.CharField(required=False, allow_blank=True)
    file_reference = serializers.CharField(required=False, allow_blank=True, max_length=500)
    checksum_sha256 = serializers.CharField(required=False, allow_blank=True, max_length=64)
    file_size_bytes = serializers.IntegerField(required=False, allow_null=True, min_value=0)


class DocumentTransmittalSerializer(serializers.ModelSerializer):
    policy_code = serializers.CharField(source="policy.code", read_only=True)

    class Meta:
        model = DocumentTransmittal
        fields = (
            "public_id",
            "transmittal_number",
            "project_public_id",
            "direction_code",
            "status_code",
            "subject",
            "sender_party_public_id",
            "recipient_party_public_id",
            "issued_at",
            "due_at",
            "acknowledged_at",
            "closed_at",
            "document_manifest",
            "notes",
            "created_by_membership_public_id",
            "policy_code",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class DocumentTransmittalCreateSerializer(PolicyBoundCreateSerializer):
    transmittal_number = serializers.CharField(max_length=120)
    project_public_id = serializers.UUIDField(required=False, allow_null=True)
    direction_code = serializers.CharField(max_length=40)
    subject = serializers.CharField(max_length=300)
    sender_party_public_id = serializers.UUIDField(required=False, allow_null=True)
    recipient_party_public_id = serializers.UUIDField(required=False, allow_null=True)
    due_at = serializers.DateTimeField(required=False, allow_null=True)
    document_manifest = serializers.ListField(child=serializers.JSONField(), required=False)
    notes = serializers.CharField(required=False, allow_blank=True)


class RequestForInformationSerializer(serializers.ModelSerializer):
    policy_code = serializers.CharField(source="policy.code", read_only=True)

    class Meta:
        model = RequestForInformation
        fields = (
            "public_id",
            "rfi_number",
            "project_public_id",
            "discipline_code",
            "priority_code",
            "status_code",
            "subject",
            "question",
            "raised_at",
            "raised_by_membership_public_id",
            "assigned_to_membership_public_id",
            "response_due_at",
            "responded_at",
            "responded_by_membership_public_id",
            "response_text",
            "closed_at",
            "linked_document_public_ids",
            "policy_code",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class RequestForInformationCreateSerializer(PolicyBoundCreateSerializer):
    rfi_number = serializers.CharField(max_length=120)
    project_public_id = serializers.UUIDField(required=False, allow_null=True)
    discipline_code = serializers.CharField(max_length=100)
    priority_code = serializers.CharField(max_length=80)
    subject = serializers.CharField(max_length=300)
    question = serializers.CharField()
    raised_at = serializers.DateTimeField()
    assigned_to_membership_public_id = serializers.UUIDField(required=False, allow_null=True)
    response_due_at = serializers.DateTimeField(required=False, allow_null=True)
    linked_document_public_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False
    )


class TechnicalSubmittalSerializer(serializers.ModelSerializer):
    policy_code = serializers.CharField(source="policy.code", read_only=True)

    class Meta:
        model = TechnicalSubmittal
        fields = (
            "public_id",
            "submittal_number",
            "revision_number",
            "project_public_id",
            "category_code",
            "package_code",
            "status_code",
            "title",
            "description",
            "submitted_at",
            "review_due_at",
            "reviewed_at",
            "submitted_by_membership_public_id",
            "reviewer_membership_public_id",
            "decision_code",
            "decision_note",
            "linked_document_public_ids",
            "policy_code",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class TechnicalSubmittalCreateSerializer(PolicyBoundCreateSerializer):
    submittal_number = serializers.CharField(max_length=120)
    revision_number = serializers.IntegerField(required=False, min_value=1)
    project_public_id = serializers.UUIDField(required=False, allow_null=True)
    category_code = serializers.CharField(max_length=100)
    package_code = serializers.CharField(required=False, allow_blank=True, max_length=120)
    title = serializers.CharField(max_length=300)
    description = serializers.CharField(required=False, allow_blank=True)
    submitted_at = serializers.DateTimeField(required=False, allow_null=True)
    review_due_at = serializers.DateTimeField(required=False, allow_null=True)
    reviewer_membership_public_id = serializers.UUIDField(required=False, allow_null=True)
    linked_document_public_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False
    )


class DocumentApprovalSerializer(serializers.ModelSerializer):
    policy_code = serializers.CharField(source="policy.code", read_only=True)

    class Meta:
        model = DocumentApproval
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


class DocumentApprovalCreateSerializer(PolicyBoundCreateSerializer):
    entity_type_code = serializers.CharField(max_length=80)
    entity_public_id = serializers.UUIDField()
    step_code = serializers.CharField(max_length=100)
    requested_from_membership_public_id = serializers.UUIDField()
    due_at = serializers.DateTimeField(required=False, allow_null=True)


class DocumentDistributionSerializer(serializers.ModelSerializer):
    policy_code = serializers.CharField(source="policy.code", read_only=True)
    document_number = serializers.CharField(
        source="revision.document.document_number", read_only=True
    )
    revision_code = serializers.CharField(source="revision.revision_code", read_only=True)

    class Meta:
        model = DocumentDistribution
        fields = (
            "public_id",
            "document_number",
            "revision_code",
            "recipient_type_code",
            "recipient_public_id",
            "purpose_code",
            "status_code",
            "distributed_at",
            "distributed_by_membership_public_id",
            "acknowledged_at",
            "revoked_at",
            "note",
            "policy_code",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class DocumentDistributionCreateSerializer(PolicyBoundCreateSerializer):
    revision_public_id = serializers.UUIDField()
    recipient_type_code = serializers.CharField(max_length=80)
    recipient_public_id = serializers.UUIDField()
    purpose_code = serializers.CharField(max_length=100)
    note = serializers.CharField(required=False, allow_blank=True)


class DocumentRiskSerializer(serializers.ModelSerializer):
    policy_code = serializers.CharField(source="policy.code", read_only=True)

    class Meta:
        model = DocumentRisk
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


class DocumentRiskCreateSerializer(PolicyBoundCreateSerializer):
    linked_entity_type_code = serializers.CharField(max_length=80)
    linked_entity_public_id = serializers.UUIDField(required=False, allow_null=True)
    risk_code = serializers.CharField(max_length=100)
    severity_code = serializers.CharField(max_length=80)
    message = serializers.CharField(max_length=500)
    due_at = serializers.DateTimeField(required=False, allow_null=True)


class TransitionSerializer(serializers.Serializer):
    target_status_code = serializers.CharField(max_length=80)
    expected_version = serializers.IntegerField(required=False, min_value=1)
    response_text = serializers.CharField(required=False, allow_blank=True)
    decision_code = serializers.CharField(required=False, allow_blank=True, max_length=80)
    decision_note = serializers.CharField(required=False, allow_blank=True)


class ApprovalDecisionSerializer(serializers.Serializer):
    decision_code = serializers.CharField(max_length=80)
    decision_note = serializers.CharField(required=False, allow_blank=True)
    expected_version = serializers.IntegerField(required=False, min_value=1)


class ResolveRiskSerializer(serializers.Serializer):
    resolution_note = serializers.CharField()
    expected_version = serializers.IntegerField(required=False, min_value=1)


class AcknowledgeDistributionSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(required=False, min_value=1)
