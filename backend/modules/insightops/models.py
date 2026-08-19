from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from modules.platform.models import PublicIdModel, TimestampedModel
from modules.tenant.models import Company


def normalize_code(value: str) -> str:
    return value.strip().upper().replace(" ", "_").replace("-", "_")


class InsightPolicyVersion(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="insight_policies")
    version = models.PositiveIntegerField(default=1)
    status_code = models.CharField(max_length=30, default="DRAFT")
    review_frequency_code = models.CharField(max_length=30, default="MONTHLY")
    on_target_threshold = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("90.00"))
    warning_threshold = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("75.00"))
    configuration = models.JSONField(default=dict, blank=True)
    effective_from = models.DateTimeField(null=True, blank=True)
    effective_to = models.DateTimeField(null=True, blank=True)
    published_by_public_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "insightops_policy_version"
        constraints = [
            models.UniqueConstraint(fields=["company", "version"], name="ins_policy_version_uq"),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_from__isnull=True)
                | models.Q(effective_to__gt=models.F("effective_from")),
                name="ins_policy_dates_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(on_target_threshold__gte=0)
                & models.Q(on_target_threshold__lte=100)
                & models.Q(warning_threshold__gte=0)
                & models.Q(warning_threshold__lte=100),
                name="ins_policy_threshold_ck",
            ),
        ]
        indexes = [models.Index(fields=["company", "status_code"], name="ins_policy_status_idx")]


class StrategicObjective(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="strategic_objectives")
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    perspective_code = models.CharField(max_length=40, default="OPERATIONS")
    status_code = models.CharField(max_length=30, default="DRAFT")
    owner_public_id = models.UUIDField(null=True, blank=True)
    weight_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    start_date = models.DateField(null=True, blank=True)
    target_date = models.DateField(null=True, blank=True)
    target_outcome = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "insightops_objective"
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="ins_objective_code_uq"),
            models.CheckConstraint(
                condition=models.Q(weight_percent__gte=0) & models.Q(weight_percent__lte=100),
                name="ins_objective_weight_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(target_date__isnull=True)
                | models.Q(start_date__isnull=True)
                | models.Q(target_date__gte=models.F("start_date")),
                name="ins_objective_dates_ck",
            ),
        ]
        indexes = [models.Index(fields=["company", "status_code", "perspective_code"], name="ins_objective_status_idx")]

    def clean(self) -> None:
        super().clean()
        self.code = normalize_code(self.code)
        self.perspective_code = normalize_code(self.perspective_code)


class KPIDefinition(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="kpi_definitions")
    objective = models.ForeignKey(
        StrategicObjective, on_delete=models.PROTECT, related_name="kpis", null=True, blank=True
    )
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    unit_code = models.CharField(max_length=40, default="PERCENT")
    direction_code = models.CharField(max_length=30, default="HIGHER_BETTER")
    aggregation_code = models.CharField(max_length=30, default="LATEST")
    frequency_code = models.CharField(max_length=30, default="MONTHLY")
    target_value = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    warning_value = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    critical_value = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    target_low = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    target_high = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    owner_public_id = models.UUIDField(null=True, blank=True)
    active = models.BooleanField(default=True)
    configuration = models.JSONField(default=dict, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "insightops_kpi_definition"
        constraints = [models.UniqueConstraint(fields=["company", "code"], name="ins_kpi_code_uq")]
        indexes = [
            models.Index(fields=["company", "active", "frequency_code"], name="ins_kpi_active_idx"),
            models.Index(fields=["company", "objective"], name="ins_kpi_objective_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.code = normalize_code(self.code)
        self.unit_code = normalize_code(self.unit_code)
        self.direction_code = normalize_code(self.direction_code)
        self.aggregation_code = normalize_code(self.aggregation_code)
        self.frequency_code = normalize_code(self.frequency_code)
        if self.direction_code not in {"HIGHER_BETTER", "LOWER_BETTER", "TARGET_RANGE"}:
            raise ValidationError({"direction_code": "Unsupported KPI direction."})
        if self.objective_id and self.objective.company_id != self.company_id:
            raise ValidationError("KPI objective cannot cross companies.")
        if self.direction_code == "TARGET_RANGE":
            if self.target_low is None or self.target_high is None:
                raise ValidationError("Target range KPIs require target_low and target_high.")
            if self.target_high < self.target_low:
                raise ValidationError("target_high cannot be lower than target_low.")


class KPIObservation(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="kpi_observations")
    kpi = models.ForeignKey(KPIDefinition, on_delete=models.PROTECT, related_name="observations")
    period_start = models.DateField()
    period_end = models.DateField()
    actual_value = models.DecimalField(max_digits=20, decimal_places=4)
    source_code = models.CharField(max_length=80, default="MANUAL")
    source_reference = models.CharField(max_length=240, blank=True)
    data_quality_code = models.CharField(max_length=30, default="VERIFIED")
    captured_by_public_id = models.UUIDField()
    captured_at = models.DateTimeField()
    evidence = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "insightops_kpi_observation"
        constraints = [
            models.UniqueConstraint(fields=["company", "kpi", "period_end"], name="ins_kpi_observation_uq"),
            models.CheckConstraint(condition=models.Q(period_end__gte=models.F("period_start")), name="ins_kpi_period_ck"),
        ]
        indexes = [models.Index(fields=["company", "period_end"], name="ins_kpi_period_idx")]

    def clean(self) -> None:
        super().clean()
        self.source_code = normalize_code(self.source_code)
        self.data_quality_code = normalize_code(self.data_quality_code)
        if self.kpi_id and self.kpi.company_id != self.company_id:
            raise ValidationError("KPI observation cannot cross companies.")


class PortfolioSnapshot(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="portfolio_snapshots")
    code = models.CharField(max_length=80)
    as_of_date = models.DateField()
    status_code = models.CharField(max_length=30, default="DRAFT")
    projects_total = models.PositiveIntegerField(default=0)
    projects_healthy = models.PositiveIntegerField(default=0)
    projects_at_risk = models.PositiveIntegerField(default=0)
    projects_critical = models.PositiveIntegerField(default=0)
    schedule_performance_percent = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("0.00"))
    cost_performance_percent = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("0.00"))
    portfolio_value = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=3)
    narrative = models.TextField(blank=True)
    created_by_public_id = models.UUIDField()
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "insightops_portfolio_snapshot"
        constraints = [models.UniqueConstraint(fields=["company", "code"], name="ins_portfolio_code_uq")]
        indexes = [models.Index(fields=["company", "as_of_date", "status_code"], name="ins_portfolio_date_idx")]

    def clean(self) -> None:
        super().clean()
        self.code = normalize_code(self.code)
        self.currency = self.currency.strip().upper()
        classified = self.projects_healthy + self.projects_at_risk + self.projects_critical
        if classified > self.projects_total:
            raise ValidationError("Classified project counts cannot exceed projects_total.")


class BenefitPlan(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="benefit_plans")
    objective = models.ForeignKey(
        StrategicObjective, on_delete=models.PROTECT, related_name="benefits", null=True, blank=True
    )
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    category_code = models.CharField(max_length=80, default="EFFICIENCY")
    status_code = models.CharField(max_length=30, default="PLANNED")
    unit_code = models.CharField(max_length=40, default="PERCENT")
    baseline_value = models.DecimalField(max_digits=20, decimal_places=4, default=Decimal("0.0000"))
    target_value = models.DecimalField(max_digits=20, decimal_places=4, default=Decimal("0.0000"))
    expected_financial_value = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=3)
    owner_public_id = models.UUIDField(null=True, blank=True)
    target_date = models.DateField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "insightops_benefit_plan"
        constraints = [models.UniqueConstraint(fields=["company", "code"], name="ins_benefit_code_uq")]
        indexes = [models.Index(fields=["company", "status_code", "target_date"], name="ins_benefit_status_idx")]

    def clean(self) -> None:
        super().clean()
        self.code = normalize_code(self.code)
        self.category_code = normalize_code(self.category_code)
        self.unit_code = normalize_code(self.unit_code)
        self.currency = self.currency.strip().upper()
        if self.objective_id and self.objective.company_id != self.company_id:
            raise ValidationError("Benefit objective cannot cross companies.")


class BenefitMeasurement(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="benefit_measurements")
    benefit = models.ForeignKey(BenefitPlan, on_delete=models.PROTECT, related_name="measurements")
    measured_at = models.DateField()
    actual_value = models.DecimalField(max_digits=20, decimal_places=4)
    realized_financial_value = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=3)
    confidence_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("100.00"))
    captured_by_public_id = models.UUIDField()
    evidence = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "insightops_benefit_measurement"
        constraints = [
            models.UniqueConstraint(fields=["company", "benefit", "measured_at"], name="ins_benefit_measure_uq"),
            models.CheckConstraint(
                condition=models.Q(confidence_percent__gte=0) & models.Q(confidence_percent__lte=100),
                name="ins_benefit_confidence_ck",
            ),
        ]
        indexes = [models.Index(fields=["company", "measured_at"], name="ins_benefit_measure_idx")]

    def clean(self) -> None:
        super().clean()
        self.currency = self.currency.strip().upper()
        if self.benefit_id and self.benefit.company_id != self.company_id:
            raise ValidationError("Benefit measurement cannot cross companies.")
        if self.benefit_id and self.currency != self.benefit.currency:
            raise ValidationError("Benefit measurement currency must match the benefit plan currency.")


class ExecutiveAction(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="executive_actions")
    code = models.CharField(max_length=80)
    title = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    priority_code = models.CharField(max_length=10, default="P2")
    status_code = models.CharField(max_length=30, default="OPEN")
    source_type_code = models.CharField(max_length=80, default="EXECUTIVE_REVIEW")
    source_public_id = models.UUIDField(null=True, blank=True)
    owner_public_id = models.UUIDField(null=True, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    resolution_summary = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "insightops_executive_action"
        constraints = [models.UniqueConstraint(fields=["company", "code"], name="ins_action_code_uq")]
        indexes = [
            models.Index(fields=["company", "status_code", "priority_code"], name="ins_action_status_idx"),
            models.Index(fields=["company", "due_at"], name="ins_action_due_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.code = normalize_code(self.code)
        self.priority_code = self.priority_code.strip().upper()
        self.source_type_code = normalize_code(self.source_type_code)
        if self.priority_code not in {"P0", "P1", "P2", "P3", "P4"}:
            raise ValidationError({"priority_code": "Priority must be P0 through P4."})


class BoardReport(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="board_reports")
    code = models.CharField(max_length=80)
    title = models.CharField(max_length=240)
    period_start = models.DateField()
    period_end = models.DateField()
    status_code = models.CharField(max_length=30, default="DRAFT")
    executive_summary = models.TextField(blank=True)
    scorecard = models.JSONField(default=dict, blank=True)
    decisions = models.JSONField(default=list, blank=True)
    prepared_by_public_id = models.UUIDField()
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "insightops_board_report"
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="ins_board_report_code_uq"),
            models.CheckConstraint(condition=models.Q(period_end__gte=models.F("period_start")), name="ins_board_period_ck"),
        ]
        indexes = [models.Index(fields=["company", "period_end", "status_code"], name="ins_board_period_idx")]

    def clean(self) -> None:
        super().clean()
        self.code = normalize_code(self.code)
