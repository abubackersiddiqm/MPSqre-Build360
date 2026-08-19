from rest_framework import serializers


class ItemCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=80)
    name = serializers.CharField(max_length=250)
    base_unit_code = serializers.CharField(max_length=30)
    category_code = serializers.CharField(max_length=80, required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    track_inventory = serializers.BooleanField(required=False, default=True)


class WarehouseCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=60)
    name = serializers.CharField(max_length=200)
    project_public_id = serializers.UUIDField(required=False, allow_null=True)
    location = serializers.JSONField(required=False)


class MovementCreateSerializer(serializers.Serializer):
    item_public_id = serializers.UUIDField()
    warehouse_public_id = serializers.UUIDField()
    movement_type = serializers.ChoiceField(choices=["issue", "return", "adjustment"])
    quantity = serializers.DecimalField(max_digits=20, decimal_places=4)
    unit_cost = serializers.DecimalField(max_digits=20, decimal_places=4, required=False, default=0, min_value=0)
    source_type = serializers.CharField(max_length=80, default="manual_movement")
    source_public_id = serializers.UUIDField()
    source_line_key = serializers.CharField(max_length=120, required=False, allow_blank=True)
    reason_code = serializers.CharField(max_length=100, required=False, allow_blank=True)

    def validate(self, attrs):
        quantity = attrs["quantity"]
        movement_type = attrs["movement_type"]
        if movement_type == "issue" and quantity > 0:
            attrs["quantity"] = -quantity
        elif movement_type in {"return", "adjustment"} and quantity == 0:
            raise serializers.ValidationError("Movement quantity cannot be zero")
        return attrs
