from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers


class InventoryCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=80)
    name = serializers.CharField(max_length=240)
    project_public_id = serializers.UUIDField(required=False, allow_null=True)
    property_public_id = serializers.UUIDField(required=False, allow_null=True)
    development_type_code = serializers.CharField(max_length=60, required=False, default="RESIDENTIAL")
    location = serializers.JSONField(required=False, default=dict)
    launch_on = serializers.DateField(required=False, allow_null=True)
    currency_code = serializers.CharField(max_length=3, required=False, allow_blank=True, default="")
    status_code = serializers.CharField(max_length=30, required=False, default="PLANNING")


class UnitCreateSerializer(serializers.Serializer):
    inventory_public_id = serializers.UUIDField()
    code = serializers.CharField(max_length=80)
    name = serializers.CharField(max_length=240)
    unit_type_code = serializers.CharField(max_length=60, required=False, default="APARTMENT")
    tower_reference = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    floor_reference = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    carpet_area = serializers.DecimalField(max_digits=18, decimal_places=3, required=False, allow_null=True, min_value=Decimal("0"))
    saleable_area = serializers.DecimalField(max_digits=18, decimal_places=3, required=False, allow_null=True, min_value=Decimal("0"))
    area_unit_code = serializers.CharField(max_length=30, required=False, default="SQ_M")
    list_price = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0"))
    currency_code = serializers.CharField(max_length=3, required=False, allow_blank=True, default="")
    tax_code = serializers.CharField(max_length=60, required=False, allow_blank=True, default="")
    status_code = serializers.CharField(max_length=30, required=False, default="RELEASED")
    attributes = serializers.JSONField(required=False, default=dict)


class BuyerCreateSerializer(serializers.Serializer):
    account_code = serializers.CharField(max_length=80)
    legal_name = serializers.CharField(max_length=240)
    display_name = serializers.CharField(max_length=240)
    buyer_type_code = serializers.CharField(max_length=40, required=False, default="INDIVIDUAL")
    contact_name = serializers.CharField(max_length=160, required=False, allow_blank=True, default="")
    contact_email = serializers.EmailField(required=False, allow_blank=True, default="")
    contact_phone = serializers.CharField(max_length=40, required=False, allow_blank=True, default="")
    tax_reference = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    address = serializers.JSONField(required=False, default=dict)
    crm_party_public_id = serializers.UUIDField(required=False, allow_null=True)


class ReservationCreateSerializer(serializers.Serializer):
    unit_public_id = serializers.UUIDField()
    buyer_public_id = serializers.UUIDField()
    reservation_number = serializers.CharField(max_length=80)
    reserved_at = serializers.DateTimeField(required=False, allow_null=True)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)
    token_amount = serializers.DecimalField(max_digits=18, decimal_places=2, required=False, default=Decimal("0"), min_value=Decimal("0"))
    currency_code = serializers.CharField(max_length=3, required=False, allow_blank=True, default="")
    source_code = serializers.CharField(max_length=60, required=False, default="DIRECT")


class BookingCreateSerializer(serializers.Serializer):
    unit_public_id = serializers.UUIDField()
    buyer_public_id = serializers.UUIDField()
    reservation_public_id = serializers.UUIDField(required=False, allow_null=True)
    booking_number = serializers.CharField(max_length=80)
    booking_date = serializers.DateField()
    agreement_date = serializers.DateField(required=False, allow_null=True)
    base_price = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0"))
    discount_amount = serializers.DecimalField(max_digits=18, decimal_places=2, required=False, default=Decimal("0"), min_value=Decimal("0"))
    tax_amount = serializers.DecimalField(max_digits=18, decimal_places=2, required=False, default=Decimal("0"), min_value=Decimal("0"))
    other_charges = serializers.DecimalField(max_digits=18, decimal_places=2, required=False, default=Decimal("0"), min_value=Decimal("0"))
    total_consideration = serializers.DecimalField(max_digits=18, decimal_places=2, required=False, min_value=Decimal("0"))
    currency_code = serializers.CharField(max_length=3, required=False, allow_blank=True, default="")


class MilestoneCreateSerializer(serializers.Serializer):
    booking_public_id = serializers.UUIDField()
    sequence = serializers.IntegerField(min_value=1)
    milestone_code = serializers.CharField(max_length=80)
    description = serializers.CharField(max_length=240)
    due_on = serializers.DateField()
    percentage = serializers.DecimalField(max_digits=7, decimal_places=4, required=False, allow_null=True, min_value=Decimal("0"), max_value=Decimal("100"))
    amount = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0"))
    tax_amount = serializers.DecimalField(max_digits=18, decimal_places=2, required=False, default=Decimal("0"), min_value=Decimal("0"))


class ReceiptCreateSerializer(serializers.Serializer):
    booking_public_id = serializers.UUIDField()
    milestone_public_id = serializers.UUIDField(required=False, allow_null=True)
    receipt_number = serializers.CharField(max_length=80)
    receipt_date = serializers.DateField()
    amount = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0.01"))
    currency_code = serializers.CharField(max_length=3, required=False, allow_blank=True, default="")
    payment_method_code = serializers.CharField(max_length=40, required=False, default="BANK_TRANSFER")
    payment_reference = serializers.CharField(max_length=160, required=False, allow_blank=True, default="")
    finance_reference = serializers.CharField(max_length=160, required=False, allow_blank=True, default="")


class CommissionCreateSerializer(serializers.Serializer):
    booking_public_id = serializers.UUIDField()
    broker_reference = serializers.CharField(max_length=160)
    broker_name = serializers.CharField(max_length=240)
    commission_percent = serializers.DecimalField(max_digits=7, decimal_places=4, required=False, default=Decimal("0"), min_value=Decimal("0"), max_value=Decimal("100"))
    commission_amount = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0"))
    currency_code = serializers.CharField(max_length=3, required=False, allow_blank=True, default="")


class HandoverCreateSerializer(serializers.Serializer):
    booking_public_id = serializers.UUIDField()
    planned_on = serializers.DateField(required=False, allow_null=True)
    checklist = serializers.JSONField(required=False, default=dict)
    evidence = serializers.JSONField(required=False, default=dict)
    open_defect_count = serializers.IntegerField(required=False, default=0, min_value=0)


class LifecycleTransitionSerializer(serializers.Serializer):
    status_code = serializers.CharField(max_length=30)
    expected_version = serializers.IntegerField(min_value=1)
    note = serializers.CharField(required=False, allow_blank=True, default="")
