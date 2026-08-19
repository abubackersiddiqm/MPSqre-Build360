from decimal import Decimal

from rest_framework import serializers

from modules.pilotops.models import (
    GoLivePlan,
    GoLiveSignoff,
    PilotChecklistItem,
    TrainingCompletion,
)


class ChecklistTransitionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=PilotChecklistItem.Status.choices)
    expected_version = serializers.IntegerField(min_value=1)
    evidence = serializers.DictField(required=False, default=dict)
    waiver_reason = serializers.CharField(max_length=500, required=False, allow_blank=True)


class TrainingCompletionSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)
    status = serializers.ChoiceField(choices=TrainingCompletion.Status.choices)
    score_percent = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        required=False,
        allow_null=True,
    )
    evidence = serializers.DictField(required=False, default=dict)


class SignoffDecisionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=GoLiveSignoff.Status.choices)
    expected_version = serializers.IntegerField(min_value=1)
    evidence = serializers.DictField(required=False, default=dict)
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)


class GoLiveTransitionSerializer(serializers.Serializer):
    target_status = serializers.ChoiceField(choices=GoLivePlan.Status.choices)
    expected_version = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)


class AdoptionCollectSerializer(serializers.Serializer):
    period_end = serializers.DateField(required=False)
