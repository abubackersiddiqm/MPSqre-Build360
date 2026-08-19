from decimal import Decimal

from rest_framework import serializers


class MigrationBatchCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=80)
    entity_code = serializers.CharField(max_length=80)
    source_file_name = serializers.CharField(max_length=240)
    source_checksum = serializers.RegexField(regex=r"^[0-9a-fA-F]{64}$", required=False, allow_blank=True)
    dry_run = serializers.BooleanField(default=True)
    total_rows = serializers.IntegerField(min_value=0, default=0)
    valid_rows = serializers.IntegerField(min_value=0, default=0)
    invalid_rows = serializers.IntegerField(min_value=0, default=0)
    warning_rows = serializers.IntegerField(min_value=0, default=0)
    notes = serializers.CharField(required=False, allow_blank=True)


class MigrationBatchTransitionSerializer(serializers.Serializer):
    status_code = serializers.ChoiceField(choices=["DRAFT", "VALIDATING", "VALIDATED", "FAILED", "APPROVED", "IMPORTED", "CANCELLED"])
    expected_version = serializers.IntegerField(min_value=1)
    total_rows = serializers.IntegerField(min_value=0, required=False)
    valid_rows = serializers.IntegerField(min_value=0, required=False)
    invalid_rows = serializers.IntegerField(min_value=0, required=False)
    warning_rows = serializers.IntegerField(min_value=0, required=False)
    notes = serializers.CharField(required=False, allow_blank=True)


class MigrationIssueCreateSerializer(serializers.Serializer):
    batch_public_id = serializers.UUIDField()
    row_number = serializers.IntegerField(min_value=1)
    field_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    severity_code = serializers.ChoiceField(choices=["WARNING", "ERROR", "BLOCKER"], default="ERROR")
    issue_code = serializers.CharField(max_length=80)
    message = serializers.CharField()
    raw_value = serializers.CharField(required=False, allow_blank=True)


class MigrationIssueResolveSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)
    resolution_notes = serializers.CharField()


class TrainingCohortCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=80)
    title = serializers.CharField(max_length=220)
    audience_code = serializers.CharField(max_length=80, default="ALL_USERS")
    delivery_mode_code = serializers.ChoiceField(choices=["ONLINE", "CLASSROOM", "BLENDED", "SITE"], default="ONLINE")
    required = serializers.BooleanField(default=True)
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    minimum_score_percent = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal("0.00"), max_value=Decimal("100.00"), default=Decimal("80.00"))
    facilitator_name = serializers.CharField(max_length=160, required=False, allow_blank=True)


class TrainingEnrollmentCreateSerializer(serializers.Serializer):
    cohort_public_id = serializers.UUIDField()
    participant_public_id = serializers.UUIDField()
    participant_name = serializers.CharField(max_length=180)
    participant_email = serializers.EmailField(required=False, allow_blank=True)


class TrainingEnrollmentTransitionSerializer(serializers.Serializer):
    status_code = serializers.ChoiceField(choices=["NOT_STARTED", "IN_PROGRESS", "COMPLETED", "FAILED", "WAIVED"])
    expected_version = serializers.IntegerField(min_value=1)
    score_percent = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal("0.00"), max_value=Decimal("100.00"), required=False, allow_null=True)
    evidence = serializers.JSONField(required=False, default=dict)


class CutoverPlanCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=80)
    name = serializers.CharField(max_length=220)
    environment_code = serializers.CharField(max_length=40, default="PRODUCTION")
    planned_start_at = serializers.DateTimeField()
    planned_go_live_at = serializers.DateTimeField()
    rollback_deadline_at = serializers.DateTimeField(required=False, allow_null=True)
    owner_public_id = serializers.UUIDField(required=False, allow_null=True)


class CutoverTaskCreateSerializer(serializers.Serializer):
    plan_public_id = serializers.UUIDField()
    code = serializers.CharField(max_length=80)
    title = serializers.CharField(max_length=240)
    category_code = serializers.CharField(max_length=80, default="GENERAL")
    owner_public_id = serializers.UUIDField(required=False, allow_null=True)
    sequence = serializers.IntegerField(min_value=1, default=10)
    critical = serializers.BooleanField(default=True)
    due_at = serializers.DateTimeField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class CutoverTaskTransitionSerializer(serializers.Serializer):
    status_code = serializers.ChoiceField(choices=["PENDING", "IN_PROGRESS", "BLOCKED", "DONE", "SKIPPED"])
    expected_version = serializers.IntegerField(min_value=1)
    notes = serializers.CharField(required=False, allow_blank=True)
    evidence = serializers.JSONField(required=False, default=dict)


class GoLiveWaveCreateSerializer(serializers.Serializer):
    plan_public_id = serializers.UUIDField(required=False, allow_null=True)
    code = serializers.CharField(max_length=80)
    name = serializers.CharField(max_length=220)
    scope = serializers.JSONField(required=False, default=dict)
    planned_at = serializers.DateTimeField()


class GoLiveWaveTransitionSerializer(serializers.Serializer):
    status_code = serializers.ChoiceField(choices=["DRAFT", "READY", "APPROVED", "LIVE", "HYPERCARE", "CLOSED", "ROLLED_BACK"])
    expected_version = serializers.IntegerField(min_value=1)


class HypercareIssueCreateSerializer(serializers.Serializer):
    wave_public_id = serializers.UUIDField(required=False, allow_null=True)
    code = serializers.CharField(max_length=80)
    title = serializers.CharField(max_length=240)
    severity_code = serializers.ChoiceField(choices=["P0", "P1", "P2", "P3"], default="P2")
    area_code = serializers.CharField(max_length=80, default="GENERAL")
    impact_summary = serializers.CharField(required=False, allow_blank=True)
    owner_public_id = serializers.UUIDField(required=False, allow_null=True)
    reported_at = serializers.DateTimeField()


class HypercareIssueTransitionSerializer(serializers.Serializer):
    status_code = serializers.ChoiceField(choices=["OPEN", "ACKNOWLEDGED", "MITIGATING", "RESOLVED", "CLOSED"])
    expected_version = serializers.IntegerField(min_value=1)
    resolution_summary = serializers.CharField(required=False, allow_blank=True)


class GateDecisionSerializer(serializers.Serializer):
    status_code = serializers.ChoiceField(choices=["PENDING", "PASSED", "FAILED", "WAIVED"])
    notes = serializers.CharField(required=False, allow_blank=True)
    evidence = serializers.JSONField(required=False, default=dict)
    expected_version = serializers.IntegerField(min_value=1)
