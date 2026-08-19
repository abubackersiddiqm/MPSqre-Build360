from rest_framework import serializers

from modules.compliance.models import (
    AccessReviewCampaign,
    AccessReviewItem,
    ComplianceAssessment,
    ControlEvaluation,
    RiskRegisterItem,
    SecurityException,
)


class AssessmentCreateSerializer(serializers.Serializer):
    framework_public_id = serializers.UUIDField()
    assessment_code = serializers.CharField(max_length=100)
    assessment_type = serializers.ChoiceField(
        choices=ComplianceAssessment.AssessmentType.choices
    )
    scope = serializers.CharField(max_length=500)
    period_start = serializers.DateField()
    period_end = serializers.DateField()
    assessor_membership_public_id = serializers.UUIDField()


class EvaluationSerializer(serializers.Serializer):
    result = serializers.ChoiceField(choices=ControlEvaluation.Result.choices)
    evidence_summary = serializers.CharField(required=False, allow_blank=True)
    evidence_reference = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
    )
    remediation_due_at = serializers.DateTimeField(required=False, allow_null=True)
    expected_version = serializers.IntegerField(min_value=1)


class AssessmentTransitionSerializer(serializers.Serializer):
    target_status = serializers.ChoiceField(
        choices=ComplianceAssessment.Status.choices
    )
    expected_version = serializers.IntegerField(min_value=1)
    decision_reason = serializers.CharField(
        max_length=1000,
        required=False,
        allow_blank=True,
    )


class RiskCreateSerializer(serializers.Serializer):
    risk_code = serializers.CharField(max_length=100)
    title = serializers.CharField(max_length=220)
    description = serializers.CharField(required=False, allow_blank=True)
    category = serializers.ChoiceField(choices=RiskRegisterItem.Category.choices)
    likelihood = serializers.IntegerField(min_value=1, max_value=5)
    impact = serializers.IntegerField(min_value=1, max_value=5)
    treatment = serializers.ChoiceField(choices=RiskRegisterItem.Treatment.choices)
    treatment_plan = serializers.CharField(required=False, allow_blank=True)
    owner_membership_public_id = serializers.UUIDField()
    due_at = serializers.DateTimeField(required=False, allow_null=True)


class RiskTransitionSerializer(serializers.Serializer):
    target_status = serializers.ChoiceField(choices=RiskRegisterItem.Status.choices)
    treatment_plan = serializers.CharField(required=False, allow_blank=True)
    expected_version = serializers.IntegerField(min_value=1)


class ExceptionCreateSerializer(serializers.Serializer):
    exception_code = serializers.CharField(max_length=100)
    control_public_id = serializers.UUIDField(required=False, allow_null=True)
    title = serializers.CharField(max_length=220)
    justification = serializers.CharField()
    compensating_controls = serializers.CharField()
    risk_rating = serializers.ChoiceField(choices=SecurityException.RiskRating.choices)
    expires_at = serializers.DateTimeField()


class ExceptionDecisionSerializer(serializers.Serializer):
    target_status = serializers.ChoiceField(choices=SecurityException.Status.choices)
    decision_reason = serializers.CharField(max_length=1000)
    expected_version = serializers.IntegerField(min_value=1)


class AccessReviewCreateSerializer(serializers.Serializer):
    campaign_code = serializers.CharField(max_length=100)
    name = serializers.CharField(max_length=220)
    scope = serializers.ChoiceField(choices=AccessReviewCampaign.Scope.choices)
    owner_membership_public_id = serializers.UUIDField()
    due_at = serializers.DateTimeField()


class AccessReviewItemDecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=AccessReviewItem.Decision.choices)
    reason = serializers.CharField(max_length=1000)
    expected_version = serializers.IntegerField(min_value=1)


class AccessReviewTransitionSerializer(serializers.Serializer):
    target_status = serializers.ChoiceField(
        choices=AccessReviewCampaign.Status.choices
    )
    expected_version = serializers.IntegerField(min_value=1)
