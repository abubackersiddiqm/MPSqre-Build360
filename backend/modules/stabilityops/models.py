from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from modules.platform.models import PublicIdModel, TimestampedModel
from modules.tenant.models import Company


class StabilityPolicyVersion(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="stability_policies")
    version = models.PositiveIntegerField(default=1)
    status_code = models.CharField(max_length=30, default="DRAFT")
    availability_target_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("99.90"))
    api_p95_budget_ms = models.PositiveIntegerField(default=750)
    page_load_budget_ms = models.PositiveIntegerField(default=2500)
    slow_request_threshold_ms = models.PositiveIntegerField(default=1000)
    error_budget_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.10"))
    incident_ack_sla_minutes = models.PositiveIntegerField(default=15)
    critical_resolution_sla_minutes = models.PositiveIntegerField(default=240)
    telemetry_retention_days = models.PositiveIntegerField(default=30)
    configuration = models.JSONField(default=dict, blank=True)
    effective_from = models.DateTimeField(null=True, blank=True)
    effective_to = models.DateTimeField(null=True, blank=True)
    published_by_public_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "stabilityops_policy_version"
        constraints = [
            models.UniqueConstraint(fields=["company", "version"], name="so_policy_version_uq"),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_from__isnull=True)
                | models.Q(effective_to__gt=models.F("effective_from")),
                name="so_policy_dates_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(availability_target_percent__gte=0)
                & models.Q(availability_target_percent__lte=100),
                name="so_policy_availability_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(error_budget_percent__gte=0)
                & models.Q(error_budget_percent__lte=100),
                name="so_policy_error_budget_ck",
            ),
        ]
        indexes = [models.Index(fields=["company", "status_code"], name="so_policy_status_idx")]


class ServiceEndpoint(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="stability_endpoints")
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=180)
    route_pattern = models.CharField(max_length=300)
    method_code = models.CharField(max_length=12, default="GET")
    service_code = models.CharField(max_length=50, default="BACKEND")
    critical = models.BooleanField(default=True)
    target_p95_ms = models.PositiveIntegerField(default=750)
    target_availability_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("99.90"))
    active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "stabilityops_service_endpoint"
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="so_endpoint_code_uq"),
            models.CheckConstraint(
                condition=models.Q(target_availability_percent__gte=0)
                & models.Q(target_availability_percent__lte=100),
                name="so_endpoint_availability_ck",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "active", "critical"], name="so_endpoint_active_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        if not self.route_pattern.startswith("/"):
            raise ValidationError({"route_pattern": "Route must start with /."})
        self.code = self.code.strip().upper().replace(" ", "_")
        self.method_code = self.method_code.strip().upper()
        self.service_code = self.service_code.strip().upper()


class PerformanceSample(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="stability_samples")
    endpoint = models.ForeignKey(
        ServiceEndpoint,
        on_delete=models.PROTECT,
        related_name="samples",
        null=True,
        blank=True,
    )
    source_code = models.CharField(max_length=30, default="BROWSER")
    route_label = models.CharField(max_length=300)
    method_code = models.CharField(max_length=12, default="GET")
    http_status = models.PositiveSmallIntegerField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField()
    observed_at = models.DateTimeField()
    request_id = models.UUIDField(null=True, blank=True)
    session_fingerprint = models.CharField(max_length=64, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "stabilityops_performance_sample"
        indexes = [
            models.Index(fields=["company", "observed_at"], name="so_sample_company_time_idx"),
            models.Index(fields=["company", "endpoint", "observed_at"], name="so_sample_endpoint_idx"),
            models.Index(fields=["company", "http_status", "observed_at"], name="so_sample_status_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        if self.endpoint_id and self.endpoint.company_id != self.company_id:
            raise ValidationError("Performance endpoint cannot cross companies")


class StabilityScan(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="stability_scans")
    status_code = models.CharField(max_length=30, default="RUNNING")
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    checks_total = models.PositiveIntegerField(default=0)
    checks_passed = models.PositiveIntegerField(default=0)
    checks_failed = models.PositiveIntegerField(default=0)
    api_p50_ms = models.PositiveIntegerField(null=True, blank=True)
    api_p95_ms = models.PositiveIntegerField(null=True, blank=True)
    api_p99_ms = models.PositiveIntegerField(null=True, blank=True)
    error_rate_percent = models.DecimalField(max_digits=6, decimal_places=3, default=Decimal("0.000"))
    results = models.JSONField(default=list)
    executed_by_public_id = models.UUIDField()
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "stabilityops_scan"
        constraints = [
            models.CheckConstraint(condition=models.Q(checks_passed__lte=models.F("checks_total")), name="so_scan_passed_ck"),
            models.CheckConstraint(condition=models.Q(checks_failed__lte=models.F("checks_total")), name="so_scan_failed_ck"),
        ]
        indexes = [models.Index(fields=["company", "status_code", "started_at"], name="so_scan_status_idx")]


class ProductionIncident(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="production_incidents")
    code = models.CharField(max_length=80)
    title = models.CharField(max_length=240)
    severity_code = models.CharField(max_length=10, default="P2")
    status_code = models.CharField(max_length=30, default="OPEN")
    source_code = models.CharField(max_length=50, default="MANUAL")
    affected_service_code = models.CharField(max_length=80, blank=True)
    impact_summary = models.TextField(blank=True)
    root_cause = models.TextField(blank=True)
    resolution_summary = models.TextField(blank=True)
    detected_at = models.DateTimeField()
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    owner_public_id = models.UUIDField(null=True, blank=True)
    created_by_public_id = models.UUIDField()
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "stabilityops_incident"
        constraints = [models.UniqueConstraint(fields=["company", "code"], name="so_incident_code_uq")]
        indexes = [
            models.Index(fields=["company", "status_code", "severity_code"], name="so_incident_status_idx"),
            models.Index(fields=["company", "detected_at"], name="so_incident_time_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.code = self.code.strip().upper().replace(" ", "_")
        if self.severity_code not in {"P0", "P1", "P2", "P3"}:
            raise ValidationError({"severity_code": "Severity must be P0, P1, P2 or P3."})


class RegressionRecord(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="stability_regressions")
    incident = models.ForeignKey(
        ProductionIncident,
        on_delete=models.PROTECT,
        related_name="regressions",
        null=True,
        blank=True,
    )
    code = models.CharField(max_length=80)
    title = models.CharField(max_length=240)
    area_code = models.CharField(max_length=80, default="GENERAL")
    severity_code = models.CharField(max_length=10, default="MEDIUM")
    status_code = models.CharField(max_length=30, default="OPEN")
    baseline_value = models.DecimalField(max_digits=16, decimal_places=3, null=True, blank=True)
    current_value = models.DecimalField(max_digits=16, decimal_places=3, null=True, blank=True)
    threshold_value = models.DecimalField(max_digits=16, decimal_places=3, null=True, blank=True)
    unit_code = models.CharField(max_length=30, blank=True)
    detected_at = models.DateTimeField()
    fixed_at = models.DateTimeField(null=True, blank=True)
    evidence = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    created_by_public_id = models.UUIDField()
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "stabilityops_regression"
        constraints = [models.UniqueConstraint(fields=["company", "code"], name="so_regression_code_uq")]
        indexes = [
            models.Index(fields=["company", "status_code", "severity_code"], name="so_regression_status_idx"),
            models.Index(fields=["company", "detected_at"], name="so_regression_time_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.code = self.code.strip().upper().replace(" ", "_")
        if self.incident_id and self.incident.company_id != self.company_id:
            raise ValidationError("Regression incident cannot cross companies")


class StabilizationGate(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="stabilization_gates")
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=220)
    category_code = models.CharField(max_length=60, default="GENERAL")
    description = models.TextField(blank=True)
    is_required = models.BooleanField(default=True)
    status_code = models.CharField(max_length=30, default="PENDING")
    evidence = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by_public_id = models.UUIDField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "stabilityops_gate"
        constraints = [models.UniqueConstraint(fields=["company", "code"], name="so_gate_code_uq")]
        indexes = [models.Index(fields=["company", "status_code", "is_required"], name="so_gate_status_idx")]

    def clean(self) -> None:
        super().clean()
        self.code = self.code.strip().upper().replace(" ", "_")
