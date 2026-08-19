# Generated for MPSqre Build360 Phase 25 Quality & QA/QC Operations.

import uuid
from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


def base_fields():
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
            name="QualityPolicyVersion",
            fields=base_fields() + [
                ("code", models.CharField(max_length=80)),
                ("name", models.CharField(max_length=200)),
                ("version", models.PositiveIntegerField()),
                ("status_code", models.CharField(max_length=80)),
                ("effective_from", models.DateTimeField()),
                ("effective_to", models.DateTimeField(blank=True, null=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("retired_at", models.DateTimeField(blank=True, null=True)),
                ("configuration", models.JSONField(default=dict)),
                ("change_note", models.TextField(blank=True)),
                ("created_by_membership_public_id", models.UUIDField(blank=True, null=True)),
                ("published_by_membership_public_id", models.UUIDField(blank=True, null=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="quality_policy_versions", to="tenant.company")),
            ],
            options={
                "db_table": "qualityops_policy_version",
                "constraints": [
                    models.UniqueConstraint(fields=("company", "code", "version"), name="qops_pol_code_ver_uq"),
                    models.CheckConstraint(condition=models.Q(("effective_to__isnull", True), ("effective_to__gt", models.F("effective_from")), _connector="OR"), name="qops_pol_range_ck"),
                    models.CheckConstraint(condition=models.Q(("retired_at__isnull", True), ("published_at__isnull", False), _connector="OR"), name="qops_pol_retire_ck"),
                ],
                "indexes": [models.Index(fields=["company", "code", "published_at", "retired_at"], name="qops_pol_active_ix")],
            },
        ),
        migrations.CreateModel(
            name="InspectionTestPlan",
            fields=base_fields() + [
                ("itp_code", models.CharField(max_length=80)),
                ("project_public_id", models.UUIDField(blank=True, null=True)),
                ("discipline_code", models.CharField(max_length=100)),
                ("work_package_code", models.CharField(max_length=120)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("status_code", models.CharField(max_length=80)),
                ("title", models.CharField(max_length=240)),
                ("description", models.TextField(blank=True)),
                ("hold_points", models.JSONField(default=list)),
                ("witness_points", models.JSONField(default=list)),
                ("acceptance_criteria", models.JSONField(default=dict)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("approved_by_membership_public_id", models.UUIDField(blank=True, null=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="quality_itps", to="tenant.company")),
                ("policy", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="itps", to="qualityops.qualitypolicyversion")),
            ],
            options={
                "db_table": "qualityops_itp",
                "constraints": [
                    models.UniqueConstraint(fields=("company", "itp_code", "revision"), name="qops_itp_code_rev_uq"),
                    models.CheckConstraint(condition=models.Q(("revision__gte", 1)), name="qops_itp_rev_ck"),
                    models.CheckConstraint(condition=models.Q(("approved_at__isnull", True), ("approved_by_membership_public_id__isnull", False), _connector="OR"), name="qops_itp_approve_ck"),
                ],
                "indexes": [models.Index(fields=["company", "status_code", "discipline_code"], name="qops_itp_status_ix")],
            },
        ),
        migrations.CreateModel(
            name="QualityInspectionRequest",
            fields=base_fields() + [
                ("request_code", models.CharField(max_length=80)),
                ("request_type_code", models.CharField(max_length=80)),
                ("project_public_id", models.UUIDField(blank=True, null=True)),
                ("location_public_id", models.UUIDField(blank=True, null=True)),
                ("activity_code", models.CharField(max_length=120)),
                ("lot_or_batch_code", models.CharField(blank=True, max_length=120)),
                ("supplier_public_id", models.UUIDField(blank=True, null=True)),
                ("status_code", models.CharField(max_length=80)),
                ("requested_for", models.DateTimeField()),
                ("requested_by_membership_public_id", models.UUIDField()),
                ("assigned_inspector_membership_public_id", models.UUIDField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="quality_inspection_requests", to="tenant.company")),
                ("itp", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="inspection_requests", to="qualityops.inspectiontestplan")),
                ("policy", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="inspection_requests", to="qualityops.qualitypolicyversion")),
            ],
            options={
                "db_table": "qualityops_inspection_request",
                "constraints": [models.UniqueConstraint(fields=("company", "request_code"), name="qops_req_code_uq")],
                "indexes": [
                    models.Index(fields=["company", "status_code", "requested_for"], name="qops_req_status_ix"),
                    models.Index(fields=["company", "request_type_code", "project_public_id"], name="qops_req_type_ix"),
                ],
            },
        ),
        migrations.CreateModel(
            name="QualityInspection",
            fields=base_fields() + [
                ("inspection_code", models.CharField(max_length=80)),
                ("project_public_id", models.UUIDField(blank=True, null=True)),
                ("location_public_id", models.UUIDField(blank=True, null=True)),
                ("inspection_type_code", models.CharField(max_length=100)),
                ("status_code", models.CharField(max_length=80)),
                ("result_code", models.CharField(blank=True, max_length=80)),
                ("scheduled_at", models.DateTimeField()),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("inspector_membership_public_id", models.UUIDField(blank=True, null=True)),
                ("score_percent", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, validators=[django.core.validators.MinValueValidator(Decimal("0.00")), django.core.validators.MaxValueValidator(Decimal("100.00"))])),
                ("sample_size", models.PositiveIntegerField(default=0)),
                ("accepted_quantity", models.PositiveIntegerField(default=0)),
                ("rejected_quantity", models.PositiveIntegerField(default=0)),
                ("checklist_result", models.JSONField(default=dict)),
                ("evidence_reference", models.CharField(blank=True, max_length=500)),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="quality_inspections", to="tenant.company")),
                ("policy", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="inspections", to="qualityops.qualitypolicyversion")),
                ("request", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="inspections", to="qualityops.qualityinspectionrequest")),
            ],
            options={
                "db_table": "qualityops_inspection",
                "constraints": [
                    models.UniqueConstraint(fields=("company", "inspection_code"), name="qops_insp_code_uq"),
                    models.CheckConstraint(condition=models.Q(("completed_at__isnull", True), ("completed_at__gte", models.F("scheduled_at")), _connector="OR"), name="qops_insp_time_ck"),
                    models.CheckConstraint(condition=models.Q(("score_percent__isnull", True), models.Q(("score_percent__gte", 0), ("score_percent__lte", 100)), _connector="OR"), name="qops_insp_score_ck"),
                    models.CheckConstraint(condition=models.Q(("accepted_quantity__lte", models.F("sample_size"))), name="qops_insp_accept_ck"),
                    models.CheckConstraint(condition=models.Q(("rejected_quantity__lte", models.F("sample_size"))), name="qops_insp_reject_ck"),
                ],
                "indexes": [
                    models.Index(fields=["company", "status_code", "scheduled_at"], name="qops_insp_sched_ix"),
                    models.Index(fields=["company", "result_code", "completed_at"], name="qops_insp_result_ix"),
                ],
            },
        ),
        migrations.CreateModel(
            name="QualityTestResult",
            fields=base_fields() + [
                ("test_code", models.CharField(max_length=80)),
                ("test_type_code", models.CharField(max_length=100)),
                ("specimen_code", models.CharField(blank=True, max_length=120)),
                ("laboratory_reference", models.CharField(blank=True, max_length=160)),
                ("result_code", models.CharField(max_length=80)),
                ("measured_value", models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True)),
                ("unit_code", models.CharField(blank=True, max_length=40)),
                ("specification_min", models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True)),
                ("specification_max", models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True)),
                ("tested_at", models.DateTimeField()),
                ("tested_by_membership_public_id", models.UUIDField(blank=True, null=True)),
                ("certificate_reference", models.CharField(blank=True, max_length=500)),
                ("remarks", models.TextField(blank=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="quality_test_results", to="tenant.company")),
                ("inspection", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="test_results", to="qualityops.qualityinspection")),
                ("policy", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="test_results", to="qualityops.qualitypolicyversion")),
            ],
            options={
                "db_table": "qualityops_test_result",
                "constraints": [
                    models.UniqueConstraint(fields=("company", "test_code"), name="qops_test_code_uq"),
                    models.CheckConstraint(condition=models.Q(("specification_min__isnull", True), ("specification_max__isnull", True), ("specification_max__gte", models.F("specification_min")), _connector="OR"), name="qops_test_spec_ck"),
                ],
                "indexes": [models.Index(fields=["company", "result_code", "tested_at"], name="qops_test_result_ix")],
            },
        ),
        migrations.CreateModel(
            name="NonConformanceReport",
            fields=base_fields() + [
                ("ncr_code", models.CharField(max_length=80)),
                ("project_public_id", models.UUIDField(blank=True, null=True)),
                ("location_public_id", models.UUIDField(blank=True, null=True)),
                ("source_type_code", models.CharField(max_length=80)),
                ("source_public_id", models.UUIDField(blank=True, null=True)),
                ("category_code", models.CharField(max_length=100)),
                ("severity_code", models.CharField(max_length=80)),
                ("status_code", models.CharField(max_length=80)),
                ("title", models.CharField(max_length=240)),
                ("description", models.TextField()),
                ("detected_at", models.DateTimeField()),
                ("detected_by_membership_public_id", models.UUIDField()),
                ("responsible_membership_public_id", models.UUIDField(blank=True, null=True)),
                ("root_cause", models.TextField(blank=True)),
                ("disposition_code", models.CharField(blank=True, max_length=100)),
                ("due_at", models.DateTimeField(blank=True, null=True)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("closure_note", models.TextField(blank=True)),
                ("evidence_reference", models.CharField(blank=True, max_length=500)),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="quality_ncrs", to="tenant.company")),
                ("policy", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="ncrs", to="qualityops.qualitypolicyversion")),
            ],
            options={
                "db_table": "qualityops_ncr",
                "constraints": [
                    models.UniqueConstraint(fields=("company", "ncr_code"), name="qops_ncr_code_uq"),
                    models.CheckConstraint(condition=models.Q(("closed_at__isnull", True), ("closed_at__gte", models.F("detected_at")), _connector="OR"), name="qops_ncr_close_ck"),
                ],
                "indexes": [
                    models.Index(fields=["company", "status_code", "due_at"], name="qops_ncr_status_ix"),
                    models.Index(fields=["company", "severity_code", "detected_at"], name="qops_ncr_severity_ix"),
                ],
            },
        ),
        migrations.CreateModel(
            name="QualityCorrectiveAction",
            fields=base_fields() + [
                ("action_code", models.CharField(max_length=80)),
                ("source_type_code", models.CharField(max_length=80)),
                ("source_public_id", models.UUIDField(blank=True, null=True)),
                ("project_public_id", models.UUIDField(blank=True, null=True)),
                ("category_code", models.CharField(max_length=100)),
                ("priority_code", models.CharField(max_length=80)),
                ("status_code", models.CharField(max_length=80)),
                ("title", models.CharField(max_length=240)),
                ("description", models.TextField(blank=True)),
                ("owner_membership_public_id", models.UUIDField(blank=True, null=True)),
                ("due_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("verified_by_membership_public_id", models.UUIDField(blank=True, null=True)),
                ("closure_note", models.TextField(blank=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="quality_corrective_actions", to="tenant.company")),
                ("policy", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="corrective_actions", to="qualityops.qualitypolicyversion")),
            ],
            options={
                "db_table": "qualityops_corrective_action",
                "constraints": [
                    models.UniqueConstraint(fields=("company", "action_code"), name="qops_act_code_uq"),
                    models.CheckConstraint(condition=models.Q(("verified_at__isnull", True), ("completed_at__isnull", False), _connector="OR"), name="qops_act_verify_ck"),
                ],
                "indexes": [
                    models.Index(fields=["company", "status_code", "due_at"], name="qops_act_due_ix"),
                    models.Index(fields=["company", "source_type_code", "source_public_id"], name="qops_act_source_ix"),
                ],
            },
        ),
        migrations.CreateModel(
            name="QualityApproval",
            fields=base_fields() + [
                ("entity_type_code", models.CharField(max_length=80)),
                ("entity_public_id", models.UUIDField()),
                ("step_code", models.CharField(max_length=100)),
                ("status_code", models.CharField(max_length=80)),
                ("requested_by_membership_public_id", models.UUIDField()),
                ("requested_from_membership_public_id", models.UUIDField()),
                ("requested_at", models.DateTimeField()),
                ("due_at", models.DateTimeField(blank=True, null=True)),
                ("decided_by_membership_public_id", models.UUIDField(blank=True, null=True)),
                ("decided_at", models.DateTimeField(blank=True, null=True)),
                ("decision_note", models.TextField(blank=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="quality_approvals", to="tenant.company")),
                ("policy", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="approvals", to="qualityops.qualitypolicyversion")),
            ],
            options={
                "db_table": "qualityops_approval",
                "constraints": [
                    models.UniqueConstraint(fields=("company", "entity_type_code", "entity_public_id", "step_code"), name="qops_appr_step_uq"),
                    models.CheckConstraint(condition=models.Q(("decided_at__isnull", True), ("decided_by_membership_public_id__isnull", False), _connector="OR"), name="qops_appr_decide_ck"),
                ],
                "indexes": [models.Index(fields=["company", "status_code", "due_at"], name="qops_appr_due_ix")],
            },
        ),
        migrations.CreateModel(
            name="QualityRisk",
            fields=base_fields() + [
                ("linked_entity_type_code", models.CharField(max_length=80)),
                ("linked_entity_public_id", models.UUIDField(blank=True, null=True)),
                ("risk_code", models.CharField(max_length=100)),
                ("severity_code", models.CharField(max_length=80)),
                ("status_code", models.CharField(max_length=80)),
                ("message", models.CharField(max_length=500)),
                ("due_at", models.DateTimeField(blank=True, null=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("resolved_by_membership_public_id", models.UUIDField(blank=True, null=True)),
                ("resolution_note", models.TextField(blank=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="quality_risks", to="tenant.company")),
                ("policy", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="risks", to="qualityops.qualitypolicyversion")),
            ],
            options={
                "db_table": "qualityops_risk",
                "constraints": [models.CheckConstraint(condition=models.Q(("resolved_at__isnull", True), ("resolved_by_membership_public_id__isnull", False), _connector="OR"), name="qops_risk_resolve_ck")],
                "indexes": [
                    models.Index(fields=["company", "status_code", "severity_code"], name="qops_risk_status_ix"),
                    models.Index(fields=["company", "linked_entity_type_code", "linked_entity_public_id"], name="qops_risk_entity_ix"),
                ],
            },
        ),
    ]
