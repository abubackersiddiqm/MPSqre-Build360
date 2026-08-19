from rest_framework import serializers

from modules.labour.models import AttendanceRecord, WorkerProfile


class WorkerCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=80)
    display_name = serializers.CharField(max_length=200)
    worker_type = serializers.ChoiceField(choices=WorkerProfile.WorkerType.choices)
    trade_code = serializers.CharField(max_length=80)
    joined_on = serializers.DateField()
    currency = serializers.CharField(min_length=3, max_length=3)
    daily_rate = serializers.DecimalField(max_digits=19, decimal_places=4, default="0")
    skill_codes = serializers.ListField(child=serializers.CharField(max_length=80), default=list)


class AllocationCreateSerializer(serializers.Serializer):
    worker_public_id = serializers.UUIDField()
    project_public_id = serializers.UUIDField()
    allocated_from = serializers.DateField()
    allocated_to = serializers.DateField(required=False, allow_null=True)
    planned_hours = serializers.DecimalField(max_digits=10, decimal_places=2, default="8")
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class AttendanceCreateSerializer(serializers.Serializer):
    worker_public_id = serializers.UUIDField()
    project_public_id = serializers.UUIDField()
    work_date = serializers.DateField()
    regular_hours = serializers.DecimalField(max_digits=8, decimal_places=2)
    overtime_hours = serializers.DecimalField(max_digits=8, decimal_places=2, default="0")
    source = serializers.ChoiceField(choices=AttendanceRecord.EntrySource.choices, default="web")
    operation_id = serializers.UUIDField(required=False, allow_null=True)


class AttendanceTransitionSerializer(serializers.Serializer):
    target_stage_code = serializers.CharField(max_length=80)
    expected_version = serializers.IntegerField(min_value=1)
