from rest_framework import serializers

from modules.ai.models import AIModelPolicy


class InteractionCreateSerializer(serializers.Serializer):
    policy_code = serializers.CharField(max_length=100, default="BUILD360_ASSISTANT")
    prompt = serializers.CharField(max_length=8000)
    metric_codes = serializers.ListField(
        child=serializers.CharField(max_length=100),
        min_length=1,
        max_length=100,
    )
    idempotency_key = serializers.CharField(max_length=120)


class InteractionReviewSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["approve", "reject", "correct"])
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)
    corrected_response = serializers.CharField(required=False, allow_blank=True)


class ExtractionCreateSerializer(serializers.Serializer):
    policy_code = serializers.CharField(max_length=100, default="BUILD360_EXTRACTION")
    source_type = serializers.CharField(max_length=100)
    source_public_id = serializers.UUIDField(required=False, allow_null=True)
    source_text = serializers.CharField(max_length=50000, write_only=True)
    schema_code = serializers.CharField(max_length=100)
    requested_fields = serializers.ListField(
        child=serializers.CharField(max_length=100),
        min_length=1,
        max_length=100,
    )
    idempotency_key = serializers.CharField(max_length=120)


class ExtractionReviewSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["approve", "reject", "correct"])
    corrections = serializers.DictField(required=False, default=dict)
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)


class RiskScanSerializer(serializers.Serializer):
    policy_code = serializers.CharField(max_length=100, default="BUILD360_RISK")


class RiskDecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["acknowledged", "resolved", "dismissed"])
    reason = serializers.CharField(max_length=500)


class ToolActionCreateSerializer(serializers.Serializer):
    interaction_public_id = serializers.UUIDField()
    action_code = serializers.CharField(max_length=120)
    target_type = serializers.CharField(max_length=100)
    target_public_id = serializers.UUIDField(required=False, allow_null=True)
    proposed_payload = serializers.DictField(required=False, default=dict)
    idempotency_key = serializers.CharField(max_length=120)


class ToolActionDecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["confirm", "reject"])
    reason = serializers.CharField(max_length=500)


class EvaluationRunSerializer(serializers.Serializer):
    policy_code = serializers.CharField(max_length=100)
    suite_code = serializers.CharField(max_length=100, default="FOUNDATION_GUARDRAILS")


class PolicyCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=100)
    name = serializers.CharField(max_length=180)
    provider_public_id = serializers.UUIDField()
    model_name = serializers.CharField(max_length=160)
    purpose = serializers.ChoiceField(choices=AIModelPolicy.Purpose.choices)
    system_instruction = serializers.CharField(required=False, allow_blank=True)
    allowed_source_types = serializers.ListField(
        child=serializers.CharField(max_length=120),
        required=False,
        default=list,
    )
    allowed_data_classifications = serializers.ListField(
        child=serializers.CharField(max_length=30),
        required=False,
        default=list,
    )
    allowed_tool_codes = serializers.ListField(
        child=serializers.CharField(max_length=120),
        required=False,
        default=list,
    )
    max_context_records = serializers.IntegerField(min_value=1, max_value=100, default=20)
    max_output_characters = serializers.IntegerField(min_value=500, max_value=20000, default=6000)
    human_review_required = serializers.BooleanField(default=True)
    citations_required = serializers.BooleanField(default=True)
    retention_days = serializers.IntegerField(min_value=1, max_value=3650, default=30)
