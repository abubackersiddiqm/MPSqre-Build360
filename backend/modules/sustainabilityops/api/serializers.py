from decimal import Decimal

from rest_framework import serializers


class FactorCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=80)
    name = serializers.CharField(max_length=240)
    category_code = serializers.CharField(max_length=80)
    scope_code = serializers.ChoiceField(choices=["SCOPE_1", "SCOPE_2", "SCOPE_3"])
    activity_unit_code = serializers.CharField(max_length=40)
    factor_kg_co2e_per_unit = serializers.DecimalField(max_digits=20, decimal_places=8, min_value=Decimal("0"))
    region_code = serializers.CharField(max_length=80, required=False, allow_blank=True)
    source_name = serializers.CharField(max_length=240)
    source_reference = serializers.CharField(max_length=500, required=False, allow_blank=True)
    valid_from = serializers.DateField()
    valid_to = serializers.DateField(required=False, allow_null=True)
    active = serializers.BooleanField(default=True)


class ActivityCreateSerializer(serializers.Serializer):
    factor_public_id = serializers.UUIDField()
    project_public_id = serializers.UUIDField(required=False, allow_null=True)
    site_reference = serializers.CharField(max_length=160, required=False, allow_blank=True)
    activity_date = serializers.DateField()
    quantity = serializers.DecimalField(max_digits=20, decimal_places=4, min_value=Decimal("0"))
    activity_unit_code = serializers.CharField(max_length=40, required=False, allow_blank=True)
    source_type_code = serializers.CharField(max_length=60, default="MANUAL")
    source_reference = serializers.CharField(max_length=300, required=False, allow_blank=True)
    evidence = serializers.JSONField(required=False, default=dict)


class ActivityTransitionSerializer(serializers.Serializer):
    status_code = serializers.ChoiceField(choices=["VERIFIED", "REJECTED", "DRAFT"])
    expected_version = serializers.IntegerField(min_value=1)


class InventoryCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=80)
    period_start = serializers.DateField()
    period_end = serializers.DateField()
    offsets_kg_co2e = serializers.DecimalField(max_digits=20, decimal_places=4, min_value=Decimal("0"), default=Decimal("0"))
    methodology_code = serializers.CharField(max_length=80, default="GHG_PROTOCOL")


class LifecycleTransitionSerializer(serializers.Serializer):
    status_code = serializers.CharField(max_length=30)
    expected_version = serializers.IntegerField(min_value=1)


class ResourceCreateSerializer(serializers.Serializer):
    project_public_id = serializers.UUIDField(required=False, allow_null=True)
    site_reference = serializers.CharField(max_length=160, required=False, allow_blank=True)
    resource_type_code = serializers.ChoiceField(choices=["ENERGY", "WATER", "FUEL", "MATERIAL"])
    resource_subtype_code = serializers.CharField(max_length=80, required=False, allow_blank=True)
    period_start = serializers.DateField()
    period_end = serializers.DateField()
    quantity = serializers.DecimalField(max_digits=20, decimal_places=4, min_value=Decimal("0"))
    unit_code = serializers.CharField(max_length=40)
    renewable_percent = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal("0"), max_value=Decimal("100"), default=Decimal("0"))
    cost_amount = serializers.DecimalField(max_digits=20, decimal_places=2, min_value=Decimal("0"), default=Decimal("0"))
    currency = serializers.CharField(max_length=3, required=False)
    source_reference = serializers.CharField(max_length=300, required=False, allow_blank=True)
    evidence = serializers.JSONField(required=False, default=dict)


class WasteCreateSerializer(serializers.Serializer):
    project_public_id = serializers.UUIDField(required=False, allow_null=True)
    site_reference = serializers.CharField(max_length=160, required=False, allow_blank=True)
    movement_date = serializers.DateField()
    waste_type_code = serializers.CharField(max_length=80)
    classification_code = serializers.ChoiceField(choices=["NON_HAZARDOUS", "HAZARDOUS", "INERT"], default="NON_HAZARDOUS")
    quantity = serializers.DecimalField(max_digits=20, decimal_places=4, min_value=Decimal("0"))
    unit_code = serializers.CharField(max_length=40, default="KG")
    treatment_code = serializers.ChoiceField(choices=["RECYCLED", "REUSED", "RECOVERY", "COMPOSTED", "LANDFILL", "INCINERATED", "OTHER"])
    transporter_name = serializers.CharField(max_length=240, required=False, allow_blank=True)
    manifest_reference = serializers.CharField(max_length=200, required=False, allow_blank=True)
    destination = serializers.CharField(max_length=300, required=False, allow_blank=True)
    evidence = serializers.JSONField(required=False, default=dict)


class TargetCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=80)
    name = serializers.CharField(max_length=240)
    description = serializers.CharField(required=False, allow_blank=True)
    category_code = serializers.ChoiceField(choices=["CARBON", "ENERGY", "WATER", "WASTE", "MATERIAL", "SOCIAL", "GOVERNANCE"])
    metric_unit_code = serializers.CharField(max_length=40)
    direction_code = serializers.ChoiceField(choices=["REDUCE", "INCREASE", "MAINTAIN"], default="REDUCE")
    baseline_value = serializers.DecimalField(max_digits=20, decimal_places=4)
    target_value = serializers.DecimalField(max_digits=20, decimal_places=4)
    latest_value = serializers.DecimalField(max_digits=20, decimal_places=4, required=False, allow_null=True)
    progress_percent = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal("0"), max_value=Decimal("100"), default=Decimal("0"))
    start_date = serializers.DateField()
    target_date = serializers.DateField()
    owner_public_id = serializers.UUIDField(required=False, allow_null=True)


class TargetTransitionSerializer(serializers.Serializer):
    status_code = serializers.ChoiceField(choices=["ACTIVE", "AT_RISK", "ACHIEVED", "CANCELLED", "DRAFT"])
    expected_version = serializers.IntegerField(min_value=1)
    latest_value = serializers.DecimalField(max_digits=20, decimal_places=4, required=False, allow_null=True)
    progress_percent = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal("0"), max_value=Decimal("100"), required=False, allow_null=True)


class InitiativeCreateSerializer(serializers.Serializer):
    target_public_id = serializers.UUIDField(required=False, allow_null=True)
    code = serializers.CharField(max_length=80)
    name = serializers.CharField(max_length=240)
    description = serializers.CharField(required=False, allow_blank=True)
    pillar_code = serializers.ChoiceField(choices=["ENVIRONMENTAL", "SOCIAL", "GOVERNANCE"], default="ENVIRONMENTAL")
    project_public_id = serializers.UUIDField(required=False, allow_null=True)
    budget_amount = serializers.DecimalField(max_digits=20, decimal_places=2, min_value=Decimal("0"), default=Decimal("0"))
    realized_value = serializers.DecimalField(max_digits=20, decimal_places=2, min_value=Decimal("0"), default=Decimal("0"))
    currency = serializers.CharField(max_length=3, required=False)
    owner_public_id = serializers.UUIDField(required=False, allow_null=True)
    due_date = serializers.DateField(required=False, allow_null=True)


class InitiativeTransitionSerializer(serializers.Serializer):
    status_code = serializers.ChoiceField(choices=["IN_PROGRESS", "BLOCKED", "COMPLETED", "CANCELLED", "PLANNED"])
    expected_version = serializers.IntegerField(min_value=1)
    realized_value = serializers.DecimalField(max_digits=20, decimal_places=2, min_value=Decimal("0"), required=False, allow_null=True)


class AssessmentCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=80)
    assessment_type_code = serializers.ChoiceField(choices=["INTERNAL_AUDIT", "THIRD_PARTY", "CERTIFICATION", "COMPLIANCE_REVIEW"])
    framework_code = serializers.CharField(max_length=80, default="CUSTOM")
    period_start = serializers.DateField()
    period_end = serializers.DateField()
    findings_total = serializers.IntegerField(min_value=0, default=0)
    major_findings = serializers.IntegerField(min_value=0, default=0)
    minor_findings = serializers.IntegerField(min_value=0, default=0)
    opinion_code = serializers.CharField(max_length=40, default="PENDING")
    assessor_name = serializers.CharField(max_length=240, required=False, allow_blank=True)
    summary = serializers.CharField(required=False, allow_blank=True)
    evidence = serializers.JSONField(required=False, default=dict)


class DisclosureCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=80)
    title = serializers.CharField(max_length=240)
    framework_code = serializers.ChoiceField(choices=["GRI", "ISSB", "CSRD", "CDP", "CUSTOM"], default="CUSTOM")
    period_start = serializers.DateField()
    period_end = serializers.DateField()
    executive_summary = serializers.CharField(required=False, allow_blank=True)
    disclosed_metrics = serializers.JSONField(required=False, default=dict)
    climate_risks = serializers.ListField(child=serializers.DictField(), required=False, default=list)
