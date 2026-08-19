from rest_framework import serializers

from modules.vendor.models import SupplyStage


class SupplyStageCreateSerializer(serializers.Serializer):
    entity_type = serializers.ChoiceField(choices=SupplyStage.EntityType.choices)
    code = serializers.CharField(max_length=50)
    name = serializers.CharField(max_length=120)
    outcome = serializers.ChoiceField(choices=SupplyStage.Outcome.choices)
    sort_order = serializers.IntegerField(min_value=1, required=False, default=100)
    allowed_next_codes = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        default=list,
    )
    is_initial = serializers.BooleanField(required=False, default=False)
    is_active = serializers.BooleanField(required=False, default=True)
    effective_from = serializers.DateTimeField(required=False)
    effective_to = serializers.DateTimeField(required=False, allow_null=True)


class VendorCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=50)
    legal_name = serializers.CharField(max_length=250)
    display_name = serializers.CharField(max_length=250)
    categories = serializers.ListField(
        child=serializers.CharField(max_length=100),
        required=False,
    )
    service_regions = serializers.ListField(
        child=serializers.CharField(max_length=100),
        required=False,
    )
    tax_reference_masked = serializers.CharField(
        max_length=80,
        required=False,
        allow_blank=True,
    )
    primary_contact_name = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=True,
    )
    primary_contact_email = serializers.EmailField(
        required=False,
        allow_blank=True,
    )
    primary_contact_phone = serializers.CharField(
        max_length=40,
        required=False,
        allow_blank=True,
    )


class VendorQualifySerializer(serializers.Serializer):
    score = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=0,
        max_value=100,
    )
    decision = serializers.ChoiceField(choices=["approved", "rejected"])
    notes = serializers.CharField(required=False, allow_blank=True)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)
    expected_version = serializers.IntegerField(min_value=1)


class VendorTransitionSerializer(serializers.Serializer):
    target_stage_public_id = serializers.UUIDField()
    expected_version = serializers.IntegerField(min_value=1)
    reason_code = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
    )
