from rest_framework import serializers


class EquipmentCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=80)
    name = serializers.CharField(max_length=200)
    category_code = serializers.CharField(max_length=80)
    currency = serializers.CharField(min_length=3, max_length=3)
    ownership_type = serializers.CharField(max_length=30, default="owned")
    hourly_cost = serializers.DecimalField(max_digits=19, decimal_places=4, default="0")
    meter_unit = serializers.CharField(max_length=20, default="hours")
    serial_number = serializers.CharField(required=False, allow_blank=True, default="")
    registration_number = serializers.CharField(required=False, allow_blank=True, default="")


class EquipmentAllocationSerializer(serializers.Serializer):
    equipment_public_id = serializers.UUIDField()
    project_public_id = serializers.UUIDField()
    allocated_from = serializers.DateTimeField()
    allocated_to = serializers.DateTimeField(required=False, allow_null=True)
    planned_meter_usage = serializers.DecimalField(max_digits=14, decimal_places=2, default="0")
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class MeterReadingSerializer(serializers.Serializer):
    equipment_public_id = serializers.UUIDField()
    reading = serializers.DecimalField(max_digits=14, decimal_places=2)
    reading_at = serializers.DateTimeField()
    source = serializers.CharField(max_length=20, default="web")
    operation_id = serializers.UUIDField(required=False, allow_null=True)


class MaintenanceCreateSerializer(serializers.Serializer):
    equipment_public_id = serializers.UUIDField()
    work_order_number = serializers.CharField(max_length=80)
    maintenance_type = serializers.CharField(max_length=40)
    summary = serializers.CharField(max_length=250)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    due_date = serializers.DateField(required=False, allow_null=True)
    currency = serializers.CharField(min_length=3, max_length=3)
