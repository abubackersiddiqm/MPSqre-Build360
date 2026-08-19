from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers


class PropertyCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=80)
    name = serializers.CharField(max_length=240)
    property_type_code = serializers.CharField(max_length=60, required=False, default="RESIDENTIAL")
    facility_public_id = serializers.UUIDField(required=False, allow_null=True)
    project_public_id = serializers.UUIDField(required=False, allow_null=True)
    external_reference = serializers.CharField(max_length=160, required=False, allow_blank=True, default="")
    address = serializers.JSONField(required=False, default=dict)
    timezone = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    gross_area = serializers.DecimalField(max_digits=18, decimal_places=3, required=False, allow_null=True, min_value=Decimal("0"))
    area_unit_code = serializers.CharField(max_length=30, required=False, default="SQ_M")
    ownership_code = serializers.CharField(max_length=40, required=False, default="OWNED")


class UnitCreateSerializer(serializers.Serializer):
    property_public_id = serializers.UUIDField()
    code = serializers.CharField(max_length=80)
    name = serializers.CharField(max_length=240)
    unit_type_code = serializers.CharField(max_length=60, required=False, default="APARTMENT")
    floor_reference = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    area = serializers.DecimalField(max_digits=18, decimal_places=3, required=False, allow_null=True, min_value=Decimal("0"))
    area_unit_code = serializers.CharField(max_length=30, required=False, default="SQ_M")
    bedroom_count = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    parking_count = serializers.IntegerField(required=False, default=0, min_value=0)
    market_rent = serializers.DecimalField(max_digits=18, decimal_places=2, required=False, allow_null=True, min_value=Decimal("0"))
    currency_code = serializers.CharField(max_length=3, required=False, allow_blank=True, default="")
    attributes = serializers.JSONField(required=False, default=dict)


class TenantCreateSerializer(serializers.Serializer):
    account_code = serializers.CharField(max_length=80)
    legal_name = serializers.CharField(max_length=240)
    display_name = serializers.CharField(max_length=240)
    tenant_type_code = serializers.CharField(max_length=40, required=False, default="ORGANIZATION")
    contact_name = serializers.CharField(max_length=160, required=False, allow_blank=True, default="")
    contact_email = serializers.EmailField(required=False, allow_blank=True, default="")
    contact_phone = serializers.CharField(max_length=40, required=False, allow_blank=True, default="")
    tax_reference = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    billing_address = serializers.JSONField(required=False, default=dict)


class LeaseCreateSerializer(serializers.Serializer):
    property_public_id = serializers.UUIDField()
    unit_public_id = serializers.UUIDField()
    tenant_public_id = serializers.UUIDField()
    lease_number = serializers.CharField(max_length=80)
    lease_type_code = serializers.CharField(max_length=40, required=False, default="STANDARD")
    start_on = serializers.DateField()
    end_on = serializers.DateField()
    billing_cycle_code = serializers.CharField(max_length=30, required=False, default="MONTHLY")
    base_rent = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0"))
    currency_code = serializers.CharField(max_length=3, required=False, allow_blank=True, default="")
    security_deposit = serializers.DecimalField(max_digits=18, decimal_places=2, required=False, default=Decimal("0"), min_value=Decimal("0"))
    escalation_percent = serializers.DecimalField(max_digits=7, decimal_places=4, required=False, default=Decimal("0"), min_value=Decimal("0"))
    escalation_frequency_months = serializers.IntegerField(required=False, default=12, min_value=1)
    notice_days = serializers.IntegerField(required=False, default=30, min_value=0)


class ChargeCreateSerializer(serializers.Serializer):
    lease_public_id = serializers.UUIDField()
    charge_code = serializers.CharField(max_length=80)
    charge_type_code = serializers.CharField(max_length=60, required=False, default="RENT")
    description = serializers.CharField(max_length=240)
    amount = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0"))
    currency_code = serializers.CharField(max_length=3, required=False, allow_blank=True, default="")
    frequency_code = serializers.CharField(max_length=30, required=False, default="MONTHLY")
    effective_from = serializers.DateField()
    effective_to = serializers.DateField(required=False, allow_null=True)
    tax_code = serializers.CharField(max_length=60, required=False, allow_blank=True, default="")
    recoverable = serializers.BooleanField(required=False, default=True)


class OccupancyCreateSerializer(serializers.Serializer):
    lease_public_id = serializers.UUIDField()
    occupant_reference = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    move_in_on = serializers.DateField(required=False, allow_null=True)
    move_out_on = serializers.DateField(required=False, allow_null=True)
    occupant_count = serializers.IntegerField(required=False, default=1, min_value=1)
    key_handover_evidence = serializers.JSONField(required=False, default=dict)
    meter_readings = serializers.JSONField(required=False, default=dict)


class InvoiceCreateSerializer(serializers.Serializer):
    lease_public_id = serializers.UUIDField()
    invoice_number = serializers.CharField(max_length=80)
    period_start = serializers.DateField()
    period_end = serializers.DateField()
    issue_date = serializers.DateField()
    due_date = serializers.DateField()
    gross_amount = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0"))
    tax_amount = serializers.DecimalField(max_digits=18, decimal_places=2, required=False, default=Decimal("0"), min_value=Decimal("0"))
    currency_code = serializers.CharField(max_length=3, required=False, allow_blank=True, default="")
    external_finance_reference = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class CaseCreateSerializer(serializers.Serializer):
    tenant_public_id = serializers.UUIDField()
    property_public_id = serializers.UUIDField()
    unit_public_id = serializers.UUIDField(required=False, allow_null=True)
    case_number = serializers.CharField(max_length=80)
    category_code = serializers.CharField(max_length=60, required=False, default="SERVICE")
    priority_code = serializers.CharField(max_length=30, required=False, default="NORMAL")
    channel_code = serializers.CharField(max_length=30, required=False, default="PORTAL")
    title = serializers.CharField(max_length=240)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    assigned_to_public_id = serializers.UUIDField(required=False, allow_null=True)


class LifecycleTransitionSerializer(serializers.Serializer):
    status_code = serializers.CharField(max_length=30)
    expected_version = serializers.IntegerField(min_value=1)
    note = serializers.CharField(required=False, allow_blank=True, default="")


class InvoiceTransitionSerializer(LifecycleTransitionSerializer):
    paid_amount = serializers.DecimalField(max_digits=18, decimal_places=2, required=False, allow_null=True, min_value=Decimal("0"))


class CaseTransitionSerializer(LifecycleTransitionSerializer):
    satisfaction_score = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=5)
