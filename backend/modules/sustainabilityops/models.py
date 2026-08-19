from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from modules.platform.models import PublicIdModel, TimestampedModel
from modules.tenant.models import Company


def normalize_code(value: str) -> str:
    return value.strip().upper().replace(" ", "_").replace("-", "_")


class SustainabilityPolicyVersion(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="sustainability_policies")
    version = models.PositiveIntegerField(default=1)
    status_code = models.CharField(max_length=30, default="DRAFT")
    base_year = models.PositiveSmallIntegerField(null=True, blank=True)
    organizational_boundary_code = models.CharField(max_length=50, default="OPERATIONAL_CONTROL")
    reporting_frequency_code = models.CharField(max_length=30, default="MONTHLY")
    market_based_scope2 = models.BooleanField(default=False)
    configuration = models.JSONField(default=dict, blank=True)
    effective_from = models.DateTimeField(null=True, blank=True)
    effective_to = models.DateTimeField(null=True, blank=True)
    published_by_public_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "sustainops_policy"
        constraints = [
            models.UniqueConstraint(fields=["company", "version"], name="sus_policy_version_uq"),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_from__isnull=True)
                | models.Q(effective_to__gt=models.F("effective_from")),
                name="sus_policy_dates_ck",
            ),
        ]
        indexes = [models.Index(fields=["company", "status_code"], name="sus_policy_status_idx")]

    def clean(self) -> None:
        super().clean()
        self.status_code = normalize_code(self.status_code)
        self.organizational_boundary_code = normalize_code(self.organizational_boundary_code)
        self.reporting_frequency_code = normalize_code(self.reporting_frequency_code)


class EmissionFactor(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="emission_factors")
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=240)
    category_code = models.CharField(max_length=80)
    scope_code = models.CharField(max_length=20)
    activity_unit_code = models.CharField(max_length=40)
    factor_kg_co2e_per_unit = models.DecimalField(max_digits=20, decimal_places=8)
    region_code = models.CharField(max_length=80, blank=True)
    source_name = models.CharField(max_length=240)
    source_reference = models.CharField(max_length=500, blank=True)
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)
    active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "sustainops_factor"
        constraints = [
            models.UniqueConstraint(fields=["company", "code", "valid_from"], name="sus_factor_period_uq"),
            models.CheckConstraint(condition=models.Q(factor_kg_co2e_per_unit__gte=0), name="sus_factor_nonneg_ck"),
            models.CheckConstraint(
                condition=models.Q(valid_to__isnull=True) | models.Q(valid_to__gte=models.F("valid_from")),
                name="sus_factor_dates_ck",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "active", "scope_code"], name="sus_factor_active_idx"),
            models.Index(fields=["company", "category_code"], name="sus_factor_category_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.code = normalize_code(self.code)
        self.category_code = normalize_code(self.category_code)
        self.scope_code = normalize_code(self.scope_code)
        self.activity_unit_code = normalize_code(self.activity_unit_code)
        self.region_code = normalize_code(self.region_code) if self.region_code else ""
        if self.scope_code not in {"SCOPE_1", "SCOPE_2", "SCOPE_3"}:
            raise ValidationError({"scope_code": "Scope must be SCOPE_1, SCOPE_2 or SCOPE_3."})


class CarbonActivity(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="carbon_activities")
    factor = models.ForeignKey(EmissionFactor, on_delete=models.PROTECT, related_name="activities")
    project_public_id = models.UUIDField(null=True, blank=True)
    site_reference = models.CharField(max_length=160, blank=True)
    activity_date = models.DateField()
    quantity = models.DecimalField(max_digits=20, decimal_places=4)
    activity_unit_code = models.CharField(max_length=40)
    calculated_kg_co2e = models.DecimalField(max_digits=20, decimal_places=4, default=Decimal("0.0000"))
    source_type_code = models.CharField(max_length=60, default="MANUAL")
    source_reference = models.CharField(max_length=300, blank=True)
    status_code = models.CharField(max_length=30, default="DRAFT")
    captured_by_public_id = models.UUIDField()
    verified_by_public_id = models.UUIDField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    evidence = models.JSONField(default=dict, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "sustainops_activity"
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gte=0), name="sus_activity_qty_ck"),
            models.CheckConstraint(condition=models.Q(calculated_kg_co2e__gte=0), name="sus_activity_co2_ck"),
        ]
        indexes = [
            models.Index(fields=["company", "activity_date", "status_code"], name="sus_activity_date_idx"),
            models.Index(fields=["company", "project_public_id"], name="sus_activity_project_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.activity_unit_code = normalize_code(self.activity_unit_code)
        self.source_type_code = normalize_code(self.source_type_code)
        self.status_code = normalize_code(self.status_code)
        if self.factor_id and self.factor.company_id != self.company_id:
            raise ValidationError("Emission factor cannot cross companies.")
        if self.factor_id and self.activity_unit_code != self.factor.activity_unit_code:
            raise ValidationError({"activity_unit_code": "Activity unit must match the selected emission factor."})


class CarbonInventory(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="carbon_inventories")
    code = models.CharField(max_length=80)
    period_start = models.DateField()
    period_end = models.DateField()
    status_code = models.CharField(max_length=30, default="DRAFT")
    scope1_kg_co2e = models.DecimalField(max_digits=20, decimal_places=4, default=Decimal("0.0000"))
    scope2_kg_co2e = models.DecimalField(max_digits=20, decimal_places=4, default=Decimal("0.0000"))
    scope3_kg_co2e = models.DecimalField(max_digits=20, decimal_places=4, default=Decimal("0.0000"))
    offsets_kg_co2e = models.DecimalField(max_digits=20, decimal_places=4, default=Decimal("0.0000"))
    net_kg_co2e = models.DecimalField(max_digits=20, decimal_places=4, default=Decimal("0.0000"))
    activity_count = models.PositiveIntegerField(default=0)
    methodology_code = models.CharField(max_length=80, default="GHG_PROTOCOL")
    prepared_by_public_id = models.UUIDField()
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "sustainops_inventory"
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="sus_inventory_code_uq"),
            models.CheckConstraint(condition=models.Q(period_end__gte=models.F("period_start")), name="sus_inventory_dates_ck"),
            models.CheckConstraint(
                condition=models.Q(scope1_kg_co2e__gte=0)
                & models.Q(scope2_kg_co2e__gte=0)
                & models.Q(scope3_kg_co2e__gte=0)
                & models.Q(offsets_kg_co2e__gte=0)
                & models.Q(net_kg_co2e__gte=0),
                name="sus_inventory_values_ck",
            ),
        ]
        indexes = [models.Index(fields=["company", "period_end", "status_code"], name="sus_inventory_period_idx")]

    def clean(self) -> None:
        super().clean()
        self.code = normalize_code(self.code)
        self.status_code = normalize_code(self.status_code)
        self.methodology_code = normalize_code(self.methodology_code)


class ResourceConsumption(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="resource_consumption")
    project_public_id = models.UUIDField(null=True, blank=True)
    site_reference = models.CharField(max_length=160, blank=True)
    resource_type_code = models.CharField(max_length=40)
    resource_subtype_code = models.CharField(max_length=80, blank=True)
    period_start = models.DateField()
    period_end = models.DateField()
    quantity = models.DecimalField(max_digits=20, decimal_places=4)
    unit_code = models.CharField(max_length=40)
    renewable_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    cost_amount = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=3)
    source_reference = models.CharField(max_length=300, blank=True)
    evidence = models.JSONField(default=dict, blank=True)
    captured_by_public_id = models.UUIDField()
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "sustainops_resource"
        constraints = [
            models.CheckConstraint(condition=models.Q(period_end__gte=models.F("period_start")), name="sus_resource_dates_ck"),
            models.CheckConstraint(condition=models.Q(quantity__gte=0) & models.Q(cost_amount__gte=0), name="sus_resource_values_ck"),
            models.CheckConstraint(
                condition=models.Q(renewable_percent__gte=0) & models.Q(renewable_percent__lte=100),
                name="sus_resource_renew_ck",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "resource_type_code", "period_end"], name="sus_resource_type_idx"),
            models.Index(fields=["company", "project_public_id"], name="sus_resource_project_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.resource_type_code = normalize_code(self.resource_type_code)
        self.resource_subtype_code = normalize_code(self.resource_subtype_code) if self.resource_subtype_code else ""
        self.unit_code = normalize_code(self.unit_code)
        self.currency = self.currency.strip().upper()


class WasteMovement(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="waste_movements")
    project_public_id = models.UUIDField(null=True, blank=True)
    site_reference = models.CharField(max_length=160, blank=True)
    movement_date = models.DateField()
    waste_type_code = models.CharField(max_length=80)
    classification_code = models.CharField(max_length=40, default="NON_HAZARDOUS")
    quantity = models.DecimalField(max_digits=20, decimal_places=4)
    unit_code = models.CharField(max_length=40, default="KG")
    treatment_code = models.CharField(max_length=40)
    transporter_name = models.CharField(max_length=240, blank=True)
    manifest_reference = models.CharField(max_length=200, blank=True)
    destination = models.CharField(max_length=300, blank=True)
    status_code = models.CharField(max_length=30, default="RECORDED")
    evidence = models.JSONField(default=dict, blank=True)
    captured_by_public_id = models.UUIDField()
    verified_by_public_id = models.UUIDField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "sustainops_waste"
        constraints = [models.CheckConstraint(condition=models.Q(quantity__gte=0), name="sus_waste_qty_ck")]
        indexes = [
            models.Index(fields=["company", "movement_date", "treatment_code"], name="sus_waste_date_idx"),
            models.Index(fields=["company", "classification_code"], name="sus_waste_class_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.waste_type_code = normalize_code(self.waste_type_code)
        self.classification_code = normalize_code(self.classification_code)
        self.unit_code = normalize_code(self.unit_code)
        self.treatment_code = normalize_code(self.treatment_code)
        self.status_code = normalize_code(self.status_code)


class SustainabilityTarget(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="sustainability_targets")
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    category_code = models.CharField(max_length=60)
    metric_unit_code = models.CharField(max_length=40)
    direction_code = models.CharField(max_length=20, default="REDUCE")
    baseline_value = models.DecimalField(max_digits=20, decimal_places=4)
    target_value = models.DecimalField(max_digits=20, decimal_places=4)
    latest_value = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    progress_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    start_date = models.DateField()
    target_date = models.DateField()
    status_code = models.CharField(max_length=30, default="DRAFT")
    owner_public_id = models.UUIDField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "sustainops_target"
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="sus_target_code_uq"),
            models.CheckConstraint(condition=models.Q(target_date__gte=models.F("start_date")), name="sus_target_dates_ck"),
            models.CheckConstraint(
                condition=models.Q(progress_percent__gte=0) & models.Q(progress_percent__lte=100),
                name="sus_target_progress_ck",
            ),
        ]
        indexes = [models.Index(fields=["company", "status_code", "target_date"], name="sus_target_status_idx")]

    def clean(self) -> None:
        super().clean()
        self.code = normalize_code(self.code)
        self.category_code = normalize_code(self.category_code)
        self.metric_unit_code = normalize_code(self.metric_unit_code)
        self.direction_code = normalize_code(self.direction_code)
        self.status_code = normalize_code(self.status_code)
        if self.direction_code not in {"REDUCE", "INCREASE", "MAINTAIN"}:
            raise ValidationError({"direction_code": "Direction must be REDUCE, INCREASE or MAINTAIN."})


class ESGInitiative(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="esg_initiatives")
    target = models.ForeignKey(
        SustainabilityTarget, on_delete=models.PROTECT, related_name="initiatives", null=True, blank=True
    )
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    pillar_code = models.CharField(max_length=40, default="ENVIRONMENTAL")
    status_code = models.CharField(max_length=30, default="PLANNED")
    project_public_id = models.UUIDField(null=True, blank=True)
    budget_amount = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    realized_value = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=3)
    owner_public_id = models.UUIDField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "sustainops_initiative"
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="sus_initiative_code_uq"),
            models.CheckConstraint(
                condition=models.Q(budget_amount__gte=0) & models.Q(realized_value__gte=0),
                name="sus_initiative_values_ck",
            ),
        ]
        indexes = [models.Index(fields=["company", "status_code", "due_date"], name="sus_initiative_status_idx")]

    def clean(self) -> None:
        super().clean()
        self.code = normalize_code(self.code)
        self.pillar_code = normalize_code(self.pillar_code)
        self.status_code = normalize_code(self.status_code)
        self.currency = self.currency.strip().upper()
        if self.target_id and self.target.company_id != self.company_id:
            raise ValidationError("Sustainability target cannot cross companies.")


class AssuranceAssessment(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="sustainability_assessments")
    code = models.CharField(max_length=80)
    assessment_type_code = models.CharField(max_length=60)
    framework_code = models.CharField(max_length=80, default="CUSTOM")
    period_start = models.DateField()
    period_end = models.DateField()
    status_code = models.CharField(max_length=30, default="DRAFT")
    findings_total = models.PositiveIntegerField(default=0)
    major_findings = models.PositiveIntegerField(default=0)
    minor_findings = models.PositiveIntegerField(default=0)
    opinion_code = models.CharField(max_length=40, default="PENDING")
    assessor_name = models.CharField(max_length=240, blank=True)
    summary = models.TextField(blank=True)
    evidence = models.JSONField(default=dict, blank=True)
    prepared_by_public_id = models.UUIDField()
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "sustainops_assessment"
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="sus_assessment_code_uq"),
            models.CheckConstraint(condition=models.Q(period_end__gte=models.F("period_start")), name="sus_assessment_dates_ck"),
        ]
        indexes = [models.Index(fields=["company", "status_code", "period_end"], name="sus_assessment_status_idx")]

    def clean(self) -> None:
        super().clean()
        self.code = normalize_code(self.code)
        self.assessment_type_code = normalize_code(self.assessment_type_code)
        self.framework_code = normalize_code(self.framework_code)
        self.status_code = normalize_code(self.status_code)
        self.opinion_code = normalize_code(self.opinion_code)
        if self.major_findings + self.minor_findings > self.findings_total:
            raise ValidationError("Classified findings cannot exceed findings_total.")


class DisclosureReport(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="sustainability_disclosures")
    code = models.CharField(max_length=80)
    title = models.CharField(max_length=240)
    framework_code = models.CharField(max_length=80, default="CUSTOM")
    period_start = models.DateField()
    period_end = models.DateField()
    status_code = models.CharField(max_length=30, default="DRAFT")
    executive_summary = models.TextField(blank=True)
    disclosed_metrics = models.JSONField(default=dict, blank=True)
    climate_risks = models.JSONField(default=list, blank=True)
    prepared_by_public_id = models.UUIDField()
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "sustainops_disclosure"
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="sus_disclosure_code_uq"),
            models.CheckConstraint(condition=models.Q(period_end__gte=models.F("period_start")), name="sus_disclosure_dates_ck"),
        ]
        indexes = [models.Index(fields=["company", "status_code", "period_end"], name="sus_disclosure_status_idx")]

    def clean(self) -> None:
        super().clean()
        self.code = normalize_code(self.code)
        self.framework_code = normalize_code(self.framework_code)
        self.status_code = normalize_code(self.status_code)
