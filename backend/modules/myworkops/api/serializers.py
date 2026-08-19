from decimal import Decimal

from rest_framework import serializers


class StatusTransitionSerializer(serializers.Serializer):
    status_code = serializers.CharField(max_length=50)
    expected_version = serializers.IntegerField(min_value=1)


class ChecklistCompletionSerializer(serializers.Serializer):
    is_completed = serializers.BooleanField()
    expected_version = serializers.IntegerField(min_value=1)


class ProgressSerializer(serializers.Serializer):
    work_item_public_id = serializers.UUIDField()
    progress_date = serializers.DateField()
    quantity_completed = serializers.DecimalField(
        max_digits=18,
        decimal_places=3,
        min_value=Decimal("0"),
        default=Decimal("0"),
    )
    unit_code = serializers.CharField(max_length=50, required=False, allow_blank=True)
    progress_percent = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        required=False,
        allow_null=True,
    )
    hours_worked = serializers.DecimalField(
        max_digits=8,
        decimal_places=2,
        min_value=Decimal("0"),
        default=Decimal("0"),
    )
    note = serializers.CharField(required=False, allow_blank=True)
    blockers = serializers.CharField(required=False, allow_blank=True)


class TimesheetSerializer(serializers.Serializer):
    project_public_id = serializers.UUIDField()
    work_item_public_id = serializers.UUIDField(required=False, allow_null=True)
    work_date = serializers.DateField()
    hours = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0.01"),
        max_value=Decimal("24"),
    )
    description = serializers.CharField(required=False, allow_blank=True)
    submit_now = serializers.BooleanField(default=False)


class VersionSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)


class DecisionSerializer(serializers.Serializer):
    decision_code = serializers.ChoiceField(choices=("APPROVED", "REJECTED"))
    decision_note = serializers.CharField(required=False, allow_blank=True)
    expected_version = serializers.IntegerField(min_value=1)


class TeamTimesheetDecisionSerializer(serializers.Serializer):
    decision_code = serializers.ChoiceField(choices=("APPROVED", "REJECTED"))
    review_note = serializers.CharField(required=False, allow_blank=True)
    expected_version = serializers.IntegerField(min_value=1)


class OfflineDraftSerializer(serializers.Serializer):
    client_draft_id = serializers.UUIDField()
    device_id = serializers.UUIDField()
    draft_type_code = serializers.CharField(max_length=100)
    work_item_public_id = serializers.UUIDField(required=False, allow_null=True)
    payload = serializers.DictField()
    client_updated_at = serializers.DateTimeField()


class NotificationStateSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=("READ", "UNREAD", "DISMISS"))
    expected_version = serializers.IntegerField(min_value=1)
