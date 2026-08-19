from decimal import Decimal

from rest_framework import serializers


class EstimateCreateSerializer(serializers.Serializer):
    project_public_id = serializers.UUIDField()
    code = serializers.SlugField(max_length=80)
    name = serializers.CharField(max_length=250)
    currency = serializers.CharField(max_length=3, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class EstimateVersionCreateSerializer(serializers.Serializer):
    source_version_public_id = serializers.UUIDField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class EstimateTransitionSerializer(serializers.Serializer):
    target_stage_public_id = serializers.UUIDField()
    expected_version = serializers.IntegerField(min_value=1)
    reason_code = serializers.CharField(max_length=100, required=False, allow_blank=True)


class EstimateBaselineSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)


class BoqSectionCreateSerializer(serializers.Serializer):
    code = serializers.SlugField(max_length=80)
    name = serializers.CharField(max_length=250)
    sort_order = serializers.IntegerField(min_value=0, required=False)


class BoqItemCreateSerializer(serializers.Serializer):
    section_public_id = serializers.UUIDField(required=False, allow_null=True)
    item_code = serializers.SlugField(max_length=80)
    description = serializers.CharField()
    unit_code = serializers.CharField(max_length=40)
    quantity = serializers.DecimalField(max_digits=19, decimal_places=4, min_value=Decimal("0"))
    rate = serializers.DecimalField(max_digits=19, decimal_places=4, min_value=Decimal("0"))
    tax_rate_percent = serializers.DecimalField(
        max_digits=7,
        decimal_places=4,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        required=False,
    )
    sort_order = serializers.IntegerField(min_value=0, required=False)
