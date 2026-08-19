from decimal import Decimal

from rest_framework import serializers

from modules.peopleops.models import LeaveRequest, PayrollRun, Timesheet


class LeaveRequestCreateSerializer(serializers.Serializer):
    employee_public_id = serializers.UUIDField()
    policy_public_id = serializers.UUIDField()
    start_on = serializers.DateField()
    end_on = serializers.DateField()
    requested_days = serializers.DecimalField(max_digits=6, decimal_places=2, min_value=Decimal("0.25"))
    reason = serializers.CharField(max_length=1000, required=False, allow_blank=True)


class LeaveRequestTransitionSerializer(serializers.Serializer):
    target_status = serializers.ChoiceField(choices=LeaveRequest.Status.choices)
    expected_version = serializers.IntegerField(min_value=1)
    decision_reason = serializers.CharField(max_length=1000, required=False, allow_blank=True)


class TimesheetLineSerializer(serializers.Serializer):
    work_date = serializers.DateField()
    project_public_id = serializers.UUIDField(required=False, allow_null=True)
    hours = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal("0.25"), max_value=Decimal("24"))
    description = serializers.CharField(max_length=500, required=False, allow_blank=True)


class TimesheetCreateSerializer(serializers.Serializer):
    employee_public_id = serializers.UUIDField()
    week_start = serializers.DateField()
    lines = TimesheetLineSerializer(many=True, allow_empty=False)


class TimesheetTransitionSerializer(serializers.Serializer):
    target_status = serializers.ChoiceField(choices=Timesheet.Status.choices)
    expected_version = serializers.IntegerField(min_value=1)
    decision_reason = serializers.CharField(max_length=1000, required=False, allow_blank=True)


class PayrollRunCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=80)
    period_start = serializers.DateField()
    period_end = serializers.DateField()
    currency = serializers.CharField(max_length=3)


class PayrollRunTransitionSerializer(serializers.Serializer):
    target_status = serializers.ChoiceField(choices=PayrollRun.Status.choices)
    expected_version = serializers.IntegerField(min_value=1)
