from rest_framework import serializers

from modules.design.models import DesignIssue, DesignReview


class DesignDocumentCreateSerializer(serializers.Serializer):
    project_public_id = serializers.UUIDField()
    document_number = serializers.CharField(max_length=120)
    title = serializers.CharField(max_length=250)
    discipline_code = serializers.SlugField(max_length=80)
    document_type_code = serializers.SlugField(max_length=80)
    description = serializers.CharField(required=False, allow_blank=True)


class DesignVersionCreateSerializer(serializers.Serializer):
    revision_code = serializers.CharField(max_length=80)
    description = serializers.CharField(required=False, allow_blank=True)
    file_object_public_id = serializers.UUIDField(required=False, allow_null=True)
    checksum_sha256 = serializers.RegexField(
        r"^[0-9a-fA-F]{64}$",
        required=False,
        allow_blank=True,
    )


class DesignTransitionSerializer(serializers.Serializer):
    target_stage_public_id = serializers.UUIDField()
    expected_version = serializers.IntegerField(min_value=1)
    reason_code = serializers.CharField(max_length=100, required=False, allow_blank=True)


class ReviewRequestSerializer(serializers.Serializer):
    reviewer_membership_public_id = serializers.UUIDField()


class ReviewDecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(
        choices=[
            DesignReview.Decision.APPROVED,
            DesignReview.Decision.APPROVED_WITH_COMMENTS,
            DesignReview.Decision.REJECTED,
        ]
    )
    comments = serializers.CharField(required=False, allow_blank=True)
    expected_version = serializers.IntegerField(min_value=1)


class DesignIssueCreateSerializer(serializers.Serializer):
    project_public_id = serializers.UUIDField()
    design_version_public_id = serializers.UUIDField(required=False, allow_null=True)
    title = serializers.CharField(max_length=250)
    description = serializers.CharField(required=False, allow_blank=True)
    severity = serializers.ChoiceField(choices=DesignIssue.Severity.choices)
    assigned_membership_public_id = serializers.UUIDField(required=False, allow_null=True)
    due_at = serializers.DateTimeField(required=False, allow_null=True)


class DesignIssueCloseSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)
    resolution = serializers.CharField()


class TransmittalCreateSerializer(serializers.Serializer):
    project_public_id = serializers.UUIDField()
    reference = serializers.CharField(max_length=120)
    purpose_code = serializers.SlugField(max_length=80)
    recipient = serializers.CharField(max_length=250)
    design_version_public_ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=False,
    )
    notes = serializers.CharField(required=False, allow_blank=True)
