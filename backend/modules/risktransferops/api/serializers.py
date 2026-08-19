from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers


class CounterpartyCreateSerializer(serializers.Serializer):
    counterparty_code = serializers.CharField(max_length=80)
    legal_name = serializers.CharField(max_length=240)
    counterparty_type_code = serializers.CharField(max_length=60, required=False, default="INSURER")
    jurisdiction_code = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    financial_rating_code = serializers.CharField(max_length=30, required=False, default="UNRATED")
    contact_data = serializers.JSONField(required=False, default=dict)


class ProgramCreateSerializer(serializers.Serializer):
    program_code = serializers.CharField(max_length=80)
    name = serializers.CharField(max_length=240)
    program_type_code = serializers.CharField(max_length=60, required=False, default="CONSTRUCTION_RISK")
    project_public_id = serializers.UUIDField(required=False, allow_null=True)
    contract_public_id = serializers.UUIDField(required=False, allow_null=True)
    currency_code = serializers.CharField(max_length=3, required=False, allow_blank=True, default="")
    aggregate_exposure = serializers.DecimalField(max_digits=20, decimal_places=2, min_value=Decimal("0.01"))
    starts_on = serializers.DateField(required=False, allow_null=True)
    ends_on = serializers.DateField(required=False, allow_null=True)


class CoverageCreateSerializer(serializers.Serializer):
    program_public_id = serializers.UUIDField()
    counterparty_public_id = serializers.UUIDField()
    policy_number = serializers.CharField(max_length=120)
    coverage_type_code = serializers.CharField(max_length=80, required=False, default="CONSTRUCTION_ALL_RISK")
    insured_subject_type_code = serializers.CharField(max_length=60, required=False, default="PROGRAM")
    insured_subject_public_id = serializers.UUIDField(required=False, allow_null=True)
    coverage_limit = serializers.DecimalField(max_digits=20, decimal_places=2, min_value=Decimal("0.01"))
    deductible_amount = serializers.DecimalField(max_digits=20, decimal_places=2, required=False, default=Decimal("0"), min_value=Decimal("0"))
    annual_premium = serializers.DecimalField(max_digits=20, decimal_places=2, required=False, default=Decimal("0"), min_value=Decimal("0"))
    currency_code = serializers.CharField(max_length=3, required=False, allow_blank=True, default="")
    starts_on = serializers.DateField()
    ends_on = serializers.DateField()


class PremiumCreateSerializer(serializers.Serializer):
    coverage_public_id = serializers.UUIDField()
    installment_number = serializers.CharField(max_length=80)
    due_on = serializers.DateField()
    amount = serializers.DecimalField(max_digits=20, decimal_places=2, min_value=Decimal("0.01"))
    currency_code = serializers.CharField(max_length=3, required=False, allow_blank=True, default="")


class LossCreateSerializer(serializers.Serializer):
    program_public_id = serializers.UUIDField()
    loss_number = serializers.CharField(max_length=80)
    occurrence_on = serializers.DateTimeField()
    reported_on = serializers.DateTimeField()
    loss_type_code = serializers.CharField(max_length=80, required=False, default="PROPERTY_DAMAGE")
    description = serializers.CharField()
    estimated_loss = serializers.DecimalField(max_digits=20, decimal_places=2, required=False, default=Decimal("0"), min_value=Decimal("0"))
    currency_code = serializers.CharField(max_length=3, required=False, allow_blank=True, default="")
    severity_code = serializers.CharField(max_length=30, required=False, default="MEDIUM")


class ClaimCreateSerializer(serializers.Serializer):
    loss_event_public_id = serializers.UUIDField()
    coverage_public_id = serializers.UUIDField()
    claim_number = serializers.CharField(max_length=120)
    notified_on = serializers.DateField()
    claimed_amount = serializers.DecimalField(max_digits=20, decimal_places=2, min_value=Decimal("0.01"))
    reserved_amount = serializers.DecimalField(max_digits=20, decimal_places=2, required=False, default=Decimal("0"), min_value=Decimal("0"))
    currency_code = serializers.CharField(max_length=3, required=False, allow_blank=True, default="")
    adjuster_reference = serializers.CharField(max_length=160, required=False, allow_blank=True, default="")


class InstrumentCreateSerializer(serializers.Serializer):
    program_public_id = serializers.UUIDField()
    counterparty_public_id = serializers.UUIDField()
    instrument_number = serializers.CharField(max_length=120)
    instrument_type_code = serializers.CharField(max_length=80, required=False, default="PERFORMANCE_BOND")
    beneficiary_name = serializers.CharField(max_length=240)
    applicant_name = serializers.CharField(max_length=240)
    secured_obligation_public_id = serializers.UUIDField(required=False, allow_null=True)
    amount = serializers.DecimalField(max_digits=20, decimal_places=2, min_value=Decimal("0.01"))
    currency_code = serializers.CharField(max_length=3, required=False, allow_blank=True, default="")
    issued_on = serializers.DateField()
    expiry_on = serializers.DateField()
    auto_renew_flag = serializers.BooleanField(required=False, default=False)


class CallCreateSerializer(serializers.Serializer):
    instrument_public_id = serializers.UUIDField()
    call_number = serializers.CharField(max_length=120)
    called_on = serializers.DateField()
    amount = serializers.DecimalField(max_digits=20, decimal_places=2, min_value=Decimal("0.01"))
    currency_code = serializers.CharField(max_length=3, required=False, allow_blank=True, default="")
    reason = serializers.CharField()


class EventCreateSerializer(serializers.Serializer):
    program_public_id = serializers.UUIDField(required=False, allow_null=True)
    event_type_code = serializers.CharField(max_length=80)
    event_on = serializers.DateTimeField(required=False)
    summary = serializers.CharField(max_length=500)
    evidence = serializers.JSONField(required=False, default=dict)


class LifecycleTransitionSerializer(serializers.Serializer):
    status_code = serializers.CharField(max_length=30)
    expected_version = serializers.IntegerField(min_value=1)
    note = serializers.CharField(required=False, allow_blank=True, default="")


class PremiumTransitionSerializer(LifecycleTransitionSerializer):
    paid_amount = serializers.DecimalField(max_digits=20, decimal_places=2, required=False, min_value=Decimal("0"))
    paid_on = serializers.DateField(required=False, allow_null=True)
    payment_reference = serializers.CharField(max_length=160, required=False, allow_blank=True, default="")


class ClaimTransitionSerializer(LifecycleTransitionSerializer):
    recovered_amount = serializers.DecimalField(max_digits=20, decimal_places=2, required=False, min_value=Decimal("0"))
    settlement_reference = serializers.CharField(max_length=160, required=False, allow_blank=True, default="")
    settled_on = serializers.DateField(required=False, allow_null=True)


class CallTransitionSerializer(LifecycleTransitionSerializer):
    settlement_reference = serializers.CharField(max_length=160, required=False, allow_blank=True, default="")
    settled_on = serializers.DateField(required=False, allow_null=True)
