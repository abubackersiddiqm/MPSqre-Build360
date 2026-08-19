from rest_framework import serializers


class ObjectiveCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=80)
    name = serializers.CharField(max_length=240)
    description = serializers.CharField(required=False, allow_blank=True)
    perspective_code = serializers.CharField(max_length=40, default="OPERATIONS")
    status_code = serializers.ChoiceField(choices=["DRAFT", "ACTIVE", "ON_TRACK", "AT_RISK", "ACHIEVED", "CANCELLED"], default="DRAFT")
    owner_public_id = serializers.UUIDField(required=False, allow_null=True)
    weight_percent = serializers.DecimalField(max_digits=5, decimal_places=2, default="0.00")
    start_date = serializers.DateField(required=False, allow_null=True)
    target_date = serializers.DateField(required=False, allow_null=True)
    target_outcome = serializers.CharField(required=False, allow_blank=True)


class KPICreateSerializer(serializers.Serializer):
    objective_public_id = serializers.UUIDField(required=False, allow_null=True)
    code = serializers.CharField(max_length=80)
    name = serializers.CharField(max_length=240)
    description = serializers.CharField(required=False, allow_blank=True)
    unit_code = serializers.CharField(max_length=40, default="PERCENT")
    direction_code = serializers.ChoiceField(choices=["HIGHER_BETTER", "LOWER_BETTER", "TARGET_RANGE"], default="HIGHER_BETTER")
    aggregation_code = serializers.ChoiceField(choices=["LATEST", "AVERAGE", "SUM", "MIN", "MAX"], default="LATEST")
    frequency_code = serializers.ChoiceField(choices=["DAILY", "WEEKLY", "MONTHLY", "QUARTERLY", "ANNUAL"], default="MONTHLY")
    target_value = serializers.DecimalField(max_digits=20, decimal_places=4, required=False, allow_null=True)
    warning_value = serializers.DecimalField(max_digits=20, decimal_places=4, required=False, allow_null=True)
    critical_value = serializers.DecimalField(max_digits=20, decimal_places=4, required=False, allow_null=True)
    target_low = serializers.DecimalField(max_digits=20, decimal_places=4, required=False, allow_null=True)
    target_high = serializers.DecimalField(max_digits=20, decimal_places=4, required=False, allow_null=True)
    owner_public_id = serializers.UUIDField(required=False, allow_null=True)
    active = serializers.BooleanField(default=True)
    configuration = serializers.JSONField(required=False, default=dict)


class ObservationCreateSerializer(serializers.Serializer):
    kpi_public_id = serializers.UUIDField()
    period_start = serializers.DateField()
    period_end = serializers.DateField()
    actual_value = serializers.DecimalField(max_digits=20, decimal_places=4)
    source_code = serializers.CharField(max_length=80, default="MANUAL")
    source_reference = serializers.CharField(max_length=240, required=False, allow_blank=True)
    data_quality_code = serializers.ChoiceField(choices=["DRAFT", "VERIFIED", "ESTIMATED", "REJECTED"], default="VERIFIED")
    captured_at = serializers.DateTimeField(required=False)
    evidence = serializers.JSONField(required=False, default=dict)


class SnapshotCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=80)
    as_of_date = serializers.DateField()
    projects_total = serializers.IntegerField(min_value=0, default=0)
    projects_healthy = serializers.IntegerField(min_value=0, default=0)
    projects_at_risk = serializers.IntegerField(min_value=0, default=0)
    projects_critical = serializers.IntegerField(min_value=0, default=0)
    schedule_performance_percent = serializers.DecimalField(max_digits=7, decimal_places=2, default="0.00")
    cost_performance_percent = serializers.DecimalField(max_digits=7, decimal_places=2, default="0.00")
    portfolio_value = serializers.DecimalField(max_digits=20, decimal_places=2, default="0.00")
    currency = serializers.CharField(max_length=3, required=False)
    narrative = serializers.CharField(required=False, allow_blank=True)


class TransitionSerializer(serializers.Serializer):
    status_code = serializers.CharField(max_length=30)
    expected_version = serializers.IntegerField(min_value=1)


class BenefitCreateSerializer(serializers.Serializer):
    objective_public_id = serializers.UUIDField(required=False, allow_null=True)
    code = serializers.CharField(max_length=80)
    name = serializers.CharField(max_length=240)
    description = serializers.CharField(required=False, allow_blank=True)
    category_code = serializers.CharField(max_length=80, default="EFFICIENCY")
    status_code = serializers.ChoiceField(choices=["PLANNED", "IN_PROGRESS", "REALIZING", "REALIZED", "AT_RISK", "CANCELLED"], default="PLANNED")
    unit_code = serializers.CharField(max_length=40, default="PERCENT")
    baseline_value = serializers.DecimalField(max_digits=20, decimal_places=4, default="0.0000")
    target_value = serializers.DecimalField(max_digits=20, decimal_places=4, default="0.0000")
    expected_financial_value = serializers.DecimalField(max_digits=20, decimal_places=2, default="0.00")
    currency = serializers.CharField(max_length=3, required=False)
    owner_public_id = serializers.UUIDField(required=False, allow_null=True)
    target_date = serializers.DateField(required=False, allow_null=True)


class BenefitMeasurementCreateSerializer(serializers.Serializer):
    benefit_public_id = serializers.UUIDField()
    measured_at = serializers.DateField()
    actual_value = serializers.DecimalField(max_digits=20, decimal_places=4)
    realized_financial_value = serializers.DecimalField(max_digits=20, decimal_places=2, default="0.00")
    currency = serializers.CharField(max_length=3, required=False)
    confidence_percent = serializers.DecimalField(max_digits=5, decimal_places=2, default="100.00")
    evidence = serializers.JSONField(required=False, default=dict)


class ActionCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=80)
    title = serializers.CharField(max_length=240)
    description = serializers.CharField(required=False, allow_blank=True)
    priority_code = serializers.ChoiceField(choices=["P0", "P1", "P2", "P3", "P4"], default="P2")
    source_type_code = serializers.CharField(max_length=80, default="EXECUTIVE_REVIEW")
    source_public_id = serializers.UUIDField(required=False, allow_null=True)
    owner_public_id = serializers.UUIDField(required=False, allow_null=True)
    due_at = serializers.DateTimeField(required=False, allow_null=True)


class ActionTransitionSerializer(serializers.Serializer):
    status_code = serializers.ChoiceField(choices=["IN_PROGRESS", "BLOCKED", "COMPLETED", "CANCELLED", "OPEN"])
    expected_version = serializers.IntegerField(min_value=1)
    resolution_summary = serializers.CharField(required=False, allow_blank=True)


class BoardReportCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=80)
    title = serializers.CharField(max_length=240)
    period_start = serializers.DateField()
    period_end = serializers.DateField()
    executive_summary = serializers.CharField(required=False, allow_blank=True)
    scorecard = serializers.JSONField(required=False, default=dict)
    decisions = serializers.ListField(child=serializers.DictField(), required=False, default=list)
