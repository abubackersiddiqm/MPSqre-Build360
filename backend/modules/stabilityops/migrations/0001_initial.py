# Generated for MPSqre Build360 Phase 34.

import decimal
import uuid

import django.db.models.deletion
from django.db import migrations, models


def common():
    return [
        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
        ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
        ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
        ("updated_at", models.DateTimeField(auto_now=True)),
    ]


class Migration(migrations.Migration):
    initial = True

    dependencies = [("tenant", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="StabilityPolicyVersion",
            fields=common() + [
                ("version", models.PositiveIntegerField(default=1)),
                ("status_code", models.CharField(default="DRAFT", max_length=30)),
                ("availability_target_percent", models.DecimalField(decimal_places=2, default=decimal.Decimal("99.90"), max_digits=5)),
                ("api_p95_budget_ms", models.PositiveIntegerField(default=750)),
                ("page_load_budget_ms", models.PositiveIntegerField(default=2500)),
                ("slow_request_threshold_ms", models.PositiveIntegerField(default=1000)),
                ("error_budget_percent", models.DecimalField(decimal_places=2, default=decimal.Decimal("0.10"), max_digits=5)),
                ("incident_ack_sla_minutes", models.PositiveIntegerField(default=15)),
                ("critical_resolution_sla_minutes", models.PositiveIntegerField(default=240)),
                ("telemetry_retention_days", models.PositiveIntegerField(default=30)),
                ("configuration", models.JSONField(blank=True, default=dict)),
                ("effective_from", models.DateTimeField(blank=True, null=True)),
                ("effective_to", models.DateTimeField(blank=True, null=True)),
                ("published_by_public_id", models.UUIDField(blank=True, null=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stability_policies", to="tenant.company")),
            ],
            options={
                "db_table": "stabilityops_policy_version",
                "constraints": [
                    models.UniqueConstraint(fields=("company", "version"), name="so_policy_version_uq"),
                    models.CheckConstraint(condition=models.Q(effective_to__isnull=True) | models.Q(effective_from__isnull=True) | models.Q(effective_to__gt=models.F("effective_from")), name="so_policy_dates_ck"),
                    models.CheckConstraint(condition=models.Q(availability_target_percent__gte=0) & models.Q(availability_target_percent__lte=100), name="so_policy_availability_ck"),
                    models.CheckConstraint(condition=models.Q(error_budget_percent__gte=0) & models.Q(error_budget_percent__lte=100), name="so_policy_error_budget_ck"),
                ],
                "indexes": [models.Index(fields=["company", "status_code"], name="so_policy_status_idx")],
            },
        ),
        migrations.CreateModel(
            name="ServiceEndpoint",
            fields=common() + [
                ("code", models.CharField(max_length=80)),
                ("name", models.CharField(max_length=180)),
                ("route_pattern", models.CharField(max_length=300)),
                ("method_code", models.CharField(default="GET", max_length=12)),
                ("service_code", models.CharField(default="BACKEND", max_length=50)),
                ("critical", models.BooleanField(default=True)),
                ("target_p95_ms", models.PositiveIntegerField(default=750)),
                ("target_availability_percent", models.DecimalField(decimal_places=2, default=decimal.Decimal("99.90"), max_digits=5)),
                ("active", models.BooleanField(default=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stability_endpoints", to="tenant.company")),
            ],
            options={
                "db_table": "stabilityops_service_endpoint",
                "constraints": [
                    models.UniqueConstraint(fields=("company", "code"), name="so_endpoint_code_uq"),
                    models.CheckConstraint(condition=models.Q(target_availability_percent__gte=0) & models.Q(target_availability_percent__lte=100), name="so_endpoint_availability_ck"),
                ],
                "indexes": [models.Index(fields=["company", "active", "critical"], name="so_endpoint_active_idx")],
            },
        ),
        migrations.CreateModel(
            name="PerformanceSample",
            fields=common() + [
                ("source_code", models.CharField(default="BROWSER", max_length=30)),
                ("route_label", models.CharField(max_length=300)),
                ("method_code", models.CharField(default="GET", max_length=12)),
                ("http_status", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("duration_ms", models.PositiveIntegerField()),
                ("observed_at", models.DateTimeField()),
                ("request_id", models.UUIDField(blank=True, null=True)),
                ("session_fingerprint", models.CharField(blank=True, max_length=64)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stability_samples", to="tenant.company")),
                ("endpoint", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="samples", to="stabilityops.serviceendpoint")),
            ],
            options={
                "db_table": "stabilityops_performance_sample",
                "indexes": [
                    models.Index(fields=["company", "observed_at"], name="so_sample_company_time_idx"),
                    models.Index(fields=["company", "endpoint", "observed_at"], name="so_sample_endpoint_idx"),
                    models.Index(fields=["company", "http_status", "observed_at"], name="so_sample_status_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="StabilityScan",
            fields=common() + [
                ("status_code", models.CharField(default="RUNNING", max_length=30)),
                ("started_at", models.DateTimeField()),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("checks_total", models.PositiveIntegerField(default=0)),
                ("checks_passed", models.PositiveIntegerField(default=0)),
                ("checks_failed", models.PositiveIntegerField(default=0)),
                ("api_p50_ms", models.PositiveIntegerField(blank=True, null=True)),
                ("api_p95_ms", models.PositiveIntegerField(blank=True, null=True)),
                ("api_p99_ms", models.PositiveIntegerField(blank=True, null=True)),
                ("error_rate_percent", models.DecimalField(decimal_places=3, default=decimal.Decimal("0.000"), max_digits=6)),
                ("results", models.JSONField(default=list)),
                ("executed_by_public_id", models.UUIDField()),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stability_scans", to="tenant.company")),
            ],
            options={
                "db_table": "stabilityops_scan",
                "constraints": [
                    models.CheckConstraint(condition=models.Q(checks_passed__lte=models.F("checks_total")), name="so_scan_passed_ck"),
                    models.CheckConstraint(condition=models.Q(checks_failed__lte=models.F("checks_total")), name="so_scan_failed_ck"),
                ],
                "indexes": [models.Index(fields=["company", "status_code", "started_at"], name="so_scan_status_idx")],
            },
        ),
        migrations.CreateModel(
            name="ProductionIncident",
            fields=common() + [
                ("code", models.CharField(max_length=80)),
                ("title", models.CharField(max_length=240)),
                ("severity_code", models.CharField(default="P2", max_length=10)),
                ("status_code", models.CharField(default="OPEN", max_length=30)),
                ("source_code", models.CharField(default="MANUAL", max_length=50)),
                ("affected_service_code", models.CharField(blank=True, max_length=80)),
                ("impact_summary", models.TextField(blank=True)),
                ("root_cause", models.TextField(blank=True)),
                ("resolution_summary", models.TextField(blank=True)),
                ("detected_at", models.DateTimeField()),
                ("acknowledged_at", models.DateTimeField(blank=True, null=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("owner_public_id", models.UUIDField(blank=True, null=True)),
                ("created_by_public_id", models.UUIDField()),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="production_incidents", to="tenant.company")),
            ],
            options={
                "db_table": "stabilityops_incident",
                "constraints": [models.UniqueConstraint(fields=("company", "code"), name="so_incident_code_uq")],
                "indexes": [
                    models.Index(fields=["company", "status_code", "severity_code"], name="so_incident_status_idx"),
                    models.Index(fields=["company", "detected_at"], name="so_incident_time_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="RegressionRecord",
            fields=common() + [
                ("code", models.CharField(max_length=80)),
                ("title", models.CharField(max_length=240)),
                ("area_code", models.CharField(default="GENERAL", max_length=80)),
                ("severity_code", models.CharField(default="MEDIUM", max_length=10)),
                ("status_code", models.CharField(default="OPEN", max_length=30)),
                ("baseline_value", models.DecimalField(blank=True, decimal_places=3, max_digits=16, null=True)),
                ("current_value", models.DecimalField(blank=True, decimal_places=3, max_digits=16, null=True)),
                ("threshold_value", models.DecimalField(blank=True, decimal_places=3, max_digits=16, null=True)),
                ("unit_code", models.CharField(blank=True, max_length=30)),
                ("detected_at", models.DateTimeField()),
                ("fixed_at", models.DateTimeField(blank=True, null=True)),
                ("evidence", models.JSONField(blank=True, default=dict)),
                ("notes", models.TextField(blank=True)),
                ("created_by_public_id", models.UUIDField()),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stability_regressions", to="tenant.company")),
                ("incident", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="regressions", to="stabilityops.productionincident")),
            ],
            options={
                "db_table": "stabilityops_regression",
                "constraints": [models.UniqueConstraint(fields=("company", "code"), name="so_regression_code_uq")],
                "indexes": [
                    models.Index(fields=["company", "status_code", "severity_code"], name="so_regression_status_idx"),
                    models.Index(fields=["company", "detected_at"], name="so_regression_time_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="StabilizationGate",
            fields=common() + [
                ("code", models.CharField(max_length=80)),
                ("name", models.CharField(max_length=220)),
                ("category_code", models.CharField(default="GENERAL", max_length=60)),
                ("description", models.TextField(blank=True)),
                ("is_required", models.BooleanField(default=True)),
                ("status_code", models.CharField(default="PENDING", max_length=30)),
                ("evidence", models.JSONField(blank=True, default=dict)),
                ("notes", models.TextField(blank=True)),
                ("decided_at", models.DateTimeField(blank=True, null=True)),
                ("decided_by_public_id", models.UUIDField(blank=True, null=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stabilization_gates", to="tenant.company")),
            ],
            options={
                "db_table": "stabilityops_gate",
                "constraints": [models.UniqueConstraint(fields=("company", "code"), name="so_gate_code_uq")],
                "indexes": [models.Index(fields=["company", "status_code", "is_required"], name="so_gate_status_idx")],
            },
        ),
    ]
