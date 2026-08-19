from rest_framework import serializers

from modules.projects.models import DeliveryStage


class ProjectCreateSerializer(serializers.Serializer):
    code = serializers.SlugField(max_length=80)
    name = serializers.CharField(max_length=250)
    description = serializers.CharField(required=False, allow_blank=True)
    customer_public_id = serializers.UUIDField(required=False, allow_null=True)
    opportunity_public_id = serializers.UUIDField(required=False, allow_null=True)
    manager_membership_public_id = serializers.UUIDField(required=False, allow_null=True)
    location = serializers.JSONField(required=False)
    planned_start_date = serializers.DateField(required=False, allow_null=True)
    planned_end_date = serializers.DateField(required=False, allow_null=True)
    currency = serializers.CharField(max_length=3, required=False, allow_blank=True)
    approved_budget = serializers.DecimalField(
        max_digits=19,
        decimal_places=4,
        required=False,
    )


class ProjectFromCrmOpportunitySerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=["preconstruction", "award"])
    code = serializers.SlugField(max_length=80, required=False, allow_blank=True)
    name = serializers.CharField(max_length=250, required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    location = serializers.JSONField(required=False)
    planned_start_date = serializers.DateField(required=False, allow_null=True)
    planned_end_date = serializers.DateField(required=False, allow_null=True)


class StageTransitionSerializer(serializers.Serializer):
    target_stage_public_id = serializers.UUIDField()
    expected_version = serializers.IntegerField(min_value=1)
    reason_code = serializers.CharField(max_length=100, required=False, allow_blank=True)


class ProjectBaselineSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)


class WbsCreateSerializer(serializers.Serializer):
    code = serializers.SlugField(max_length=80)
    name = serializers.CharField(max_length=250)
    description = serializers.CharField(required=False, allow_blank=True)
    parent_public_id = serializers.UUIDField(required=False, allow_null=True)
    sort_order = serializers.IntegerField(min_value=0, required=False)


class TaskCreateSerializer(serializers.Serializer):
    code = serializers.SlugField(max_length=80)
    title = serializers.CharField(max_length=250)
    description = serializers.CharField(required=False, allow_blank=True)
    wbs_node_public_id = serializers.UUIDField(required=False, allow_null=True)
    assignee_membership_public_id = serializers.UUIDField(required=False, allow_null=True)
    planned_start_date = serializers.DateField(required=False, allow_null=True)
    planned_end_date = serializers.DateField(required=False, allow_null=True)


class TaskTransitionSerializer(serializers.Serializer):
    target_stage_public_id = serializers.UUIDField()
    expected_version = serializers.IntegerField(min_value=1)
    progress_percent = serializers.IntegerField(
        min_value=0,
        max_value=100,
        required=False,
        allow_null=True,
    )


class DeliveryStageCreateSerializer(serializers.Serializer):
    entity_type = serializers.ChoiceField(choices=DeliveryStage.EntityType.choices)
    code = serializers.SlugField(max_length=80)
    name = serializers.CharField(max_length=160)
    outcome = serializers.ChoiceField(choices=DeliveryStage.Outcome.choices)
    sort_order = serializers.IntegerField(min_value=0)
    allowed_next_codes = serializers.ListField(
        child=serializers.SlugField(max_length=80),
        required=False,
    )
    is_initial = serializers.BooleanField(required=False)
    allows_baseline = serializers.BooleanField(required=False)
    effective_from = serializers.DateTimeField()
    effective_to = serializers.DateTimeField(required=False, allow_null=True)
