from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers


class ParcelCreateSerializer(serializers.Serializer):
    parcel_code = serializers.CharField(max_length=80)
    name = serializers.CharField(max_length=240)
    parcel_type_code = serializers.CharField(max_length=60, required=False, default="FREEHOLD")
    jurisdiction_code = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    survey_reference = serializers.CharField(max_length=160, required=False, allow_blank=True, default="")
    title_reference = serializers.CharField(max_length=160, required=False, allow_blank=True, default="")
    address = serializers.JSONField(required=False, default=dict)
    gross_area = serializers.DecimalField(max_digits=18, decimal_places=3, min_value=Decimal("0.001"))
    usable_area = serializers.DecimalField(max_digits=18, decimal_places=3, required=False, allow_null=True, min_value=Decimal("0"))
    area_unit_code = serializers.CharField(max_length=30, required=False, default="SQ_M")
    zoning_code = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    current_use_code = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    latitude = serializers.DecimalField(max_digits=10, decimal_places=7, required=False, allow_null=True, min_value=Decimal("-90"), max_value=Decimal("90"))
    longitude = serializers.DecimalField(max_digits=10, decimal_places=7, required=False, allow_null=True, min_value=Decimal("-180"), max_value=Decimal("180"))
    status_code = serializers.CharField(max_length=30, required=False, default="PROSPECT")


class OwnershipCreateSerializer(serializers.Serializer):
    parcel_public_id = serializers.UUIDField()
    owner_name = serializers.CharField(max_length=240)
    owner_type_code = serializers.CharField(max_length=60, required=False, default="INDIVIDUAL")
    share_percent = serializers.DecimalField(max_digits=7, decimal_places=4, required=False, default=Decimal("100"), min_value=Decimal("0.0001"), max_value=Decimal("100"))
    ownership_document_reference = serializers.CharField(max_length=240, required=False, allow_blank=True, default="")
    encumbrance_flag = serializers.BooleanField(required=False, default=False)
    encumbrance_summary = serializers.CharField(required=False, allow_blank=True, default="")


class DiligenceCreateSerializer(serializers.Serializer):
    parcel_public_id = serializers.UUIDField()
    case_number = serializers.CharField(max_length=80)
    category_code = serializers.CharField(max_length=60, required=False, default="TITLE")
    opened_on = serializers.DateField(required=False, allow_null=True)
    target_on = serializers.DateField(required=False, allow_null=True)
    risk_rating_code = serializers.CharField(max_length=30, required=False, default="MEDIUM")
    findings = serializers.JSONField(required=False, default=list)
    blockers = serializers.JSONField(required=False, default=list)


class FeasibilityCreateSerializer(serializers.Serializer):
    parcel_public_id = serializers.UUIDField()
    scenario_code = serializers.CharField(max_length=80)
    name = serializers.CharField(max_length=240)
    scenario_type_code = serializers.CharField(max_length=60, required=False, default="BASE_CASE")
    gross_development_area = serializers.DecimalField(max_digits=18, decimal_places=3, required=False, default=Decimal("0"), min_value=Decimal("0"))
    saleable_area = serializers.DecimalField(max_digits=18, decimal_places=3, required=False, default=Decimal("0"), min_value=Decimal("0"))
    area_unit_code = serializers.CharField(max_length=30, required=False, default="SQ_M")
    planned_units = serializers.IntegerField(required=False, default=0, min_value=0)
    estimated_revenue = serializers.DecimalField(max_digits=20, decimal_places=2, required=False, default=Decimal("0"), min_value=Decimal("0"))
    land_cost = serializers.DecimalField(max_digits=20, decimal_places=2, required=False, default=Decimal("0"), min_value=Decimal("0"))
    construction_cost = serializers.DecimalField(max_digits=20, decimal_places=2, required=False, default=Decimal("0"), min_value=Decimal("0"))
    soft_cost = serializers.DecimalField(max_digits=20, decimal_places=2, required=False, default=Decimal("0"), min_value=Decimal("0"))
    finance_cost = serializers.DecimalField(max_digits=20, decimal_places=2, required=False, default=Decimal("0"), min_value=Decimal("0"))
    contingency_cost = serializers.DecimalField(max_digits=20, decimal_places=2, required=False, default=Decimal("0"), min_value=Decimal("0"))
    irr_percent = serializers.DecimalField(max_digits=7, decimal_places=4, required=False, allow_null=True)
    currency_code = serializers.CharField(max_length=3, required=False, allow_blank=True, default="")
    assumptions = serializers.JSONField(required=False, default=dict)


class OpportunityCreateSerializer(serializers.Serializer):
    parcel_public_id = serializers.UUIDField()
    feasibility_public_id = serializers.UUIDField(required=False, allow_null=True)
    opportunity_code = serializers.CharField(max_length=80)
    seller_name = serializers.CharField(max_length=240)
    acquisition_method_code = serializers.CharField(max_length=60, required=False, default="PURCHASE")
    stage_code = serializers.CharField(max_length=30, required=False, default="IDENTIFIED")
    asking_price = serializers.DecimalField(max_digits=20, decimal_places=2, required=False, allow_null=True, min_value=Decimal("0"))
    target_price = serializers.DecimalField(max_digits=20, decimal_places=2, required=False, allow_null=True, min_value=Decimal("0"))
    approved_budget = serializers.DecimalField(max_digits=20, decimal_places=2, required=False, allow_null=True, min_value=Decimal("0"))
    currency_code = serializers.CharField(max_length=3, required=False, allow_blank=True, default="")
    probability_percent = serializers.DecimalField(max_digits=7, decimal_places=4, required=False, default=Decimal("0"), min_value=Decimal("0"), max_value=Decimal("100"))
    expected_close_on = serializers.DateField(required=False, allow_null=True)
    sponsor_public_id = serializers.UUIDField(required=False, allow_null=True)


class OfferCreateSerializer(serializers.Serializer):
    opportunity_public_id = serializers.UUIDField()
    offer_number = serializers.CharField(max_length=80)
    offer_date = serializers.DateField()
    amount = serializers.DecimalField(max_digits=20, decimal_places=2, min_value=Decimal("0"))
    currency_code = serializers.CharField(max_length=3, required=False, allow_blank=True, default="")
    validity_until = serializers.DateField(required=False, allow_null=True)
    conditions = serializers.JSONField(required=False, default=dict)


class ApprovalCreateSerializer(serializers.Serializer):
    parcel_public_id = serializers.UUIDField()
    opportunity_public_id = serializers.UUIDField(required=False, allow_null=True)
    approval_code = serializers.CharField(max_length=80)
    approval_type_code = serializers.CharField(max_length=80)
    authority_name = serializers.CharField(max_length=240)
    application_reference = serializers.CharField(max_length=160, required=False, allow_blank=True, default="")
    submitted_on = serializers.DateField(required=False, allow_null=True)
    expected_on = serializers.DateField(required=False, allow_null=True)
    approved_on = serializers.DateField(required=False, allow_null=True)
    expiry_on = serializers.DateField(required=False, allow_null=True)
    status_code = serializers.CharField(max_length=30, required=False, default="PLANNED")
    mandatory_for_acquisition = serializers.BooleanField(required=False, default=False)
    conditions = serializers.JSONField(required=False, default=dict)
    evidence_reference = serializers.CharField(max_length=240, required=False, allow_blank=True, default="")


class RiskCreateSerializer(serializers.Serializer):
    parcel_public_id = serializers.UUIDField()
    opportunity_public_id = serializers.UUIDField(required=False, allow_null=True)
    risk_number = serializers.CharField(max_length=80)
    category_code = serializers.CharField(max_length=60, required=False, default="LEGAL")
    severity_code = serializers.CharField(max_length=30, required=False, default="MEDIUM")
    probability_code = serializers.CharField(max_length=30, required=False, default="POSSIBLE")
    title = serializers.CharField(max_length=240)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    mitigation_plan = serializers.CharField(required=False, allow_blank=True, default="")
    due_on = serializers.DateField(required=False, allow_null=True)


class EventCreateSerializer(serializers.Serializer):
    opportunity_public_id = serializers.UUIDField()
    event_type_code = serializers.CharField(max_length=60)
    event_on = serializers.DateTimeField(required=False)
    summary = serializers.CharField(max_length=500)
    evidence = serializers.JSONField(required=False, default=dict)


class LifecycleTransitionSerializer(serializers.Serializer):
    status_code = serializers.CharField(max_length=30)
    expected_version = serializers.IntegerField(min_value=1)
    note = serializers.CharField(required=False, allow_blank=True, default="")
