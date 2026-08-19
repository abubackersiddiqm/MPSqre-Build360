from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers


class ProgramCreateSerializer(serializers.Serializer):
    program_code = serializers.CharField(max_length=80)
    name = serializers.CharField(max_length=240)
    program_type_code = serializers.CharField(max_length=60, required=False, default="PROJECT_FINANCE")
    project_public_id = serializers.UUIDField(required=False, allow_null=True)
    land_opportunity_public_id = serializers.UUIDField(required=False, allow_null=True)
    currency_code = serializers.CharField(max_length=3, required=False, allow_blank=True, default="")
    target_capital = serializers.DecimalField(max_digits=20, decimal_places=2, min_value=Decimal("0.01"))
    target_equity = serializers.DecimalField(max_digits=20, decimal_places=2, required=False, default=Decimal("0"), min_value=Decimal("0"))
    target_debt = serializers.DecimalField(max_digits=20, decimal_places=2, required=False, default=Decimal("0"), min_value=Decimal("0"))
    committee_public_id = serializers.UUIDField(required=False, allow_null=True)
    start_on = serializers.DateField(required=False, allow_null=True)
    target_close_on = serializers.DateField(required=False, allow_null=True)


class InvestorCreateSerializer(serializers.Serializer):
    investor_code = serializers.CharField(max_length=80)
    legal_name = serializers.CharField(max_length=240)
    investor_type_code = serializers.CharField(max_length=60, required=False, default="INSTITUTIONAL")
    jurisdiction_code = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    contact_data = serializers.JSONField(required=False, default=dict)
    risk_rating_code = serializers.CharField(max_length=30, required=False, default="MEDIUM")
    accredited_flag = serializers.BooleanField(required=False, default=False)


class JointVentureCreateSerializer(serializers.Serializer):
    program_public_id = serializers.UUIDField()
    venture_code = serializers.CharField(max_length=80)
    partner_name = serializers.CharField(max_length=240)
    partner_reference = serializers.UUIDField(required=False, allow_null=True)
    ownership_percent = serializers.DecimalField(max_digits=7, decimal_places=4, min_value=Decimal("0.0001"), max_value=Decimal("100"))
    profit_share_percent = serializers.DecimalField(max_digits=7, decimal_places=4, min_value=Decimal("0"), max_value=Decimal("100"))
    governance = serializers.JSONField(required=False, default=dict)


class CommitmentCreateSerializer(serializers.Serializer):
    program_public_id = serializers.UUIDField()
    investor_public_id = serializers.UUIDField(required=False, allow_null=True)
    joint_venture_public_id = serializers.UUIDField(required=False, allow_null=True)
    commitment_number = serializers.CharField(max_length=80)
    commitment_type_code = serializers.CharField(max_length=60, required=False, default="EQUITY")
    committed_amount = serializers.DecimalField(max_digits=20, decimal_places=2, min_value=Decimal("0.01"))
    currency_code = serializers.CharField(max_length=3, required=False, allow_blank=True, default="")
    committed_on = serializers.DateField()
    expiry_on = serializers.DateField(required=False, allow_null=True)


class DebtFacilityCreateSerializer(serializers.Serializer):
    program_public_id = serializers.UUIDField()
    facility_code = serializers.CharField(max_length=80)
    lender_name = serializers.CharField(max_length=240)
    facility_type_code = serializers.CharField(max_length=60, required=False, default="TERM_LOAN")
    principal_limit = serializers.DecimalField(max_digits=20, decimal_places=2, min_value=Decimal("0.01"))
    currency_code = serializers.CharField(max_length=3, required=False, allow_blank=True, default="")
    interest_rate_percent = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, default=Decimal("0"), min_value=Decimal("0"))
    tenor_months = serializers.IntegerField(required=False, default=12, min_value=1)
    start_on = serializers.DateField(required=False, allow_null=True)
    maturity_on = serializers.DateField(required=False, allow_null=True)
    security_summary = serializers.CharField(required=False, allow_blank=True, default="")
    covenants = serializers.JSONField(required=False, default=dict)


class DrawdownCreateSerializer(serializers.Serializer):
    program_public_id = serializers.UUIDField()
    debt_facility_public_id = serializers.UUIDField(required=False, allow_null=True)
    commitment_public_id = serializers.UUIDField(required=False, allow_null=True)
    request_number = serializers.CharField(max_length=80)
    request_type_code = serializers.CharField(max_length=60, required=False, default="DEBT_DRAWDOWN")
    amount = serializers.DecimalField(max_digits=20, decimal_places=2, min_value=Decimal("0.01"))
    currency_code = serializers.CharField(max_length=3, required=False, allow_blank=True, default="")
    requested_on = serializers.DateField()
    required_by = serializers.DateField(required=False, allow_null=True)
    purpose = serializers.CharField(required=False, allow_blank=True, default="")


class CovenantCreateSerializer(serializers.Serializer):
    debt_facility_public_id = serializers.UUIDField()
    test_number = serializers.CharField(max_length=80)
    covenant_code = serializers.CharField(max_length=80)
    tested_on = serializers.DateField()
    metric_value = serializers.DecimalField(max_digits=20, decimal_places=6)
    threshold_operator = serializers.ChoiceField(choices=["LT", "LTE", "GT", "GTE", "EQ"], default="LTE")
    threshold_value = serializers.DecimalField(max_digits=20, decimal_places=6)
    evidence = serializers.JSONField(required=False, default=dict)


class DistributionCreateSerializer(serializers.Serializer):
    program_public_id = serializers.UUIDField()
    investor_public_id = serializers.UUIDField(required=False, allow_null=True)
    joint_venture_public_id = serializers.UUIDField(required=False, allow_null=True)
    distribution_number = serializers.CharField(max_length=80)
    distribution_type_code = serializers.CharField(max_length=60, required=False, default="RETURN_OF_CAPITAL")
    amount = serializers.DecimalField(max_digits=20, decimal_places=2, min_value=Decimal("0.01"))
    currency_code = serializers.CharField(max_length=3, required=False, allow_blank=True, default="")
    declared_on = serializers.DateField()
    payable_on = serializers.DateField(required=False, allow_null=True)


class EventCreateSerializer(serializers.Serializer):
    program_public_id = serializers.UUIDField()
    event_type_code = serializers.CharField(max_length=60)
    event_on = serializers.DateTimeField(required=False)
    summary = serializers.CharField(max_length=500)
    evidence = serializers.JSONField(required=False, default=dict)


class LifecycleTransitionSerializer(serializers.Serializer):
    status_code = serializers.CharField(max_length=30)
    expected_version = serializers.IntegerField(min_value=1)
    note = serializers.CharField(required=False, allow_blank=True, default="")


class DrawdownTransitionSerializer(LifecycleTransitionSerializer):
    disbursement_reference = serializers.CharField(max_length=160, required=False, allow_blank=True, default="")
    disbursed_on = serializers.DateField(required=False, allow_null=True)


class DistributionTransitionSerializer(LifecycleTransitionSerializer):
    payment_reference = serializers.CharField(max_length=160, required=False, allow_blank=True, default="")
    paid_on = serializers.DateField(required=False, allow_null=True)
