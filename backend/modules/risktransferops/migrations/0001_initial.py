import uuid
from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models


def base_fields():
    return [
        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
        ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
        ("created_at", models.DateTimeField(auto_now_add=True)),
        ("updated_at", models.DateTimeField(auto_now=True)),
    ]


class Migration(migrations.Migration):
    initial = True
    dependencies = [("tenant", "0001_initial"), ("capitalops", "0003_seed_defaults")]

    operations = [
        migrations.CreateModel(
            name="RiskTransferPolicyVersion",
            fields=base_fields() + [
                ("version", models.PositiveIntegerField(default=1)),
                ("status_code", models.CharField(default="DRAFT", max_length=30)),
                ("expiry_alert_days", models.PositiveIntegerField(default=45)),
                ("claim_notification_sla_days", models.PositiveIntegerField(default=7)),
                ("minimum_coverage_percent", models.DecimalField(decimal_places=4, default=Decimal("100.0000"), max_digits=7)),
                ("configuration", models.JSONField(blank=True, default=dict)),
                ("effective_from", models.DateTimeField(blank=True, null=True)),
                ("effective_to", models.DateTimeField(blank=True, null=True)),
                ("published_by_public_id", models.UUIDField(blank=True, null=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="risk_transfer_policies", to="tenant.company")),
            ],
            options={
                "db_table": "riskxfer_policy",
                "indexes": [models.Index(fields=["company", "status_code"], name="rx_policy_status_idx")],
                "constraints": [
                    models.UniqueConstraint(fields=("company", "version"), name="rx_policy_ver_uq"),
                    models.CheckConstraint(condition=models.Q(effective_to__isnull=True) | models.Q(effective_from__isnull=True) | models.Q(effective_to__gt=models.F("effective_from")), name="rx_policy_dates_ck"),
                    models.CheckConstraint(condition=models.Q(minimum_coverage_percent__gte=0) & models.Q(minimum_coverage_percent__lte=500), name="rx_policy_cover_ck"),
                ],
            },
        ),
        migrations.CreateModel(
            name="RiskCounterparty",
            fields=base_fields() + [
                ("counterparty_code", models.CharField(max_length=80)),
                ("legal_name", models.CharField(max_length=240)),
                ("counterparty_type_code", models.CharField(default="INSURER", max_length=60)),
                ("jurisdiction_code", models.CharField(blank=True, max_length=80)),
                ("financial_rating_code", models.CharField(default="UNRATED", max_length=30)),
                ("contact_data", models.JSONField(blank=True, default=dict)),
                ("status_code", models.CharField(default="PENDING", max_length=30)),
                ("created_by_public_id", models.UUIDField()),
                ("verified_by_public_id", models.UUIDField(blank=True, null=True)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("verification_note", models.TextField(blank=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="risk_counterparties", to="tenant.company")),
            ],
            options={
                "db_table": "riskxfer_counterparty",
                "indexes": [
                    models.Index(fields=["company", "status_code"], name="rx_party_status_idx"),
                    models.Index(fields=["company", "counterparty_type_code"], name="rx_party_type_idx"),
                ],
                "constraints": [models.UniqueConstraint(fields=("company", "counterparty_code"), name="rx_party_code_uq")],
            },
        ),
        migrations.CreateModel(
            name="InsuranceProgram",
            fields=base_fields() + [
                ("program_code", models.CharField(max_length=80)),
                ("name", models.CharField(max_length=240)),
                ("program_type_code", models.CharField(default="CONSTRUCTION_RISK", max_length=60)),
                ("project_public_id", models.UUIDField(blank=True, null=True)),
                ("contract_public_id", models.UUIDField(blank=True, null=True)),
                ("status_code", models.CharField(default="DRAFT", max_length=30)),
                ("currency_code", models.CharField(default="INR", max_length=3)),
                ("aggregate_exposure", models.DecimalField(decimal_places=2, default=0, max_digits=20)),
                ("owner_public_id", models.UUIDField()),
                ("starts_on", models.DateField(blank=True, null=True)),
                ("ends_on", models.DateField(blank=True, null=True)),
                ("approved_by_public_id", models.UUIDField(blank=True, null=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("decision_note", models.TextField(blank=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="risk_insurance_programs", to="tenant.company")),
            ],
            options={
                "db_table": "riskxfer_program",
                "indexes": [
                    models.Index(fields=["company", "status_code", "ends_on"], name="rx_program_status_idx"),
                    models.Index(fields=["company", "project_public_id"], name="rx_program_proj_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("company", "program_code"), name="rx_program_code_uq"),
                    models.CheckConstraint(condition=models.Q(aggregate_exposure__gte=0), name="rx_program_exposure_ck"),
                ],
            },
        ),
        migrations.CreateModel(
            name="InsuranceCoverage",
            fields=base_fields() + [
                ("policy_number", models.CharField(max_length=120)),
                ("coverage_type_code", models.CharField(default="CONSTRUCTION_ALL_RISK", max_length=80)),
                ("insured_subject_type_code", models.CharField(default="PROGRAM", max_length=60)),
                ("insured_subject_public_id", models.UUIDField(blank=True, null=True)),
                ("coverage_limit", models.DecimalField(decimal_places=2, max_digits=20)),
                ("deductible_amount", models.DecimalField(decimal_places=2, default=0, max_digits=20)),
                ("annual_premium", models.DecimalField(decimal_places=2, default=0, max_digits=20)),
                ("currency_code", models.CharField(default="INR", max_length=3)),
                ("starts_on", models.DateField()),
                ("ends_on", models.DateField()),
                ("status_code", models.CharField(default="DRAFT", max_length=30)),
                ("created_by_public_id", models.UUIDField()),
                ("approved_by_public_id", models.UUIDField(blank=True, null=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("decision_note", models.TextField(blank=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="risk_coverages", to="tenant.company")),
                ("counterparty", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="coverages", to="risktransferops.riskcounterparty")),
                ("program", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="coverages", to="risktransferops.insuranceprogram")),
            ],
            options={
                "db_table": "riskxfer_coverage",
                "indexes": [
                    models.Index(fields=["company", "status_code", "ends_on"], name="rx_coverage_status_idx"),
                    models.Index(fields=["company", "coverage_type_code"], name="rx_coverage_type_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("company", "policy_number"), name="rx_coverage_policy_uq"),
                    models.CheckConstraint(condition=models.Q(coverage_limit__gt=0), name="rx_coverage_limit_ck"),
                    models.CheckConstraint(condition=models.Q(deductible_amount__gte=0), name="rx_coverage_deduct_ck"),
                    models.CheckConstraint(condition=models.Q(annual_premium__gte=0), name="rx_coverage_premium_ck"),
                ],
            },
        ),
        migrations.CreateModel(
            name="PremiumSchedule",
            fields=base_fields() + [
                ("installment_number", models.CharField(max_length=80)),
                ("due_on", models.DateField()),
                ("amount", models.DecimalField(decimal_places=2, max_digits=20)),
                ("paid_amount", models.DecimalField(decimal_places=2, default=0, max_digits=20)),
                ("currency_code", models.CharField(default="INR", max_length=3)),
                ("status_code", models.CharField(default="DUE", max_length=30)),
                ("paid_on", models.DateField(blank=True, null=True)),
                ("payment_reference", models.CharField(blank=True, max_length=160)),
                ("created_by_public_id", models.UUIDField()),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="risk_premium_schedules", to="tenant.company")),
                ("coverage", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="premium_schedules", to="risktransferops.insurancecoverage")),
            ],
            options={
                "db_table": "riskxfer_premium",
                "indexes": [models.Index(fields=["company", "status_code", "due_on"], name="rx_premium_status_idx")],
                "constraints": [
                    models.UniqueConstraint(fields=("coverage", "installment_number"), name="rx_premium_inst_uq"),
                    models.CheckConstraint(condition=models.Q(amount__gt=0), name="rx_premium_amount_ck"),
                    models.CheckConstraint(condition=models.Q(paid_amount__gte=0), name="rx_premium_paid_ck"),
                ],
            },
        ),
        migrations.CreateModel(
            name="LossEvent",
            fields=base_fields() + [
                ("loss_number", models.CharField(max_length=80)),
                ("occurrence_on", models.DateTimeField()),
                ("reported_on", models.DateTimeField()),
                ("loss_type_code", models.CharField(default="PROPERTY_DAMAGE", max_length=80)),
                ("description", models.TextField()),
                ("estimated_loss", models.DecimalField(decimal_places=2, default=0, max_digits=20)),
                ("currency_code", models.CharField(default="INR", max_length=3)),
                ("severity_code", models.CharField(default="MEDIUM", max_length=30)),
                ("status_code", models.CharField(default="OPEN", max_length=30)),
                ("reporter_public_id", models.UUIDField()),
                ("closed_by_public_id", models.UUIDField(blank=True, null=True)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("closure_note", models.TextField(blank=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="risk_loss_events", to="tenant.company")),
                ("program", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="loss_events", to="risktransferops.insuranceprogram")),
            ],
            options={
                "db_table": "riskxfer_loss",
                "indexes": [
                    models.Index(fields=["company", "status_code", "reported_on"], name="rx_loss_status_idx"),
                    models.Index(fields=["company", "severity_code"], name="rx_loss_severity_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("company", "loss_number"), name="rx_loss_number_uq"),
                    models.CheckConstraint(condition=models.Q(estimated_loss__gte=0), name="rx_loss_estimate_ck"),
                ],
            },
        ),
        migrations.CreateModel(
            name="InsuranceClaim",
            fields=base_fields() + [
                ("claim_number", models.CharField(max_length=120)),
                ("notified_on", models.DateField()),
                ("claimed_amount", models.DecimalField(decimal_places=2, max_digits=20)),
                ("reserved_amount", models.DecimalField(decimal_places=2, default=0, max_digits=20)),
                ("recovered_amount", models.DecimalField(decimal_places=2, default=0, max_digits=20)),
                ("currency_code", models.CharField(default="INR", max_length=3)),
                ("status_code", models.CharField(default="DRAFT", max_length=30)),
                ("adjuster_reference", models.CharField(blank=True, max_length=160)),
                ("created_by_public_id", models.UUIDField()),
                ("approved_by_public_id", models.UUIDField(blank=True, null=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("settlement_reference", models.CharField(blank=True, max_length=160)),
                ("settled_on", models.DateField(blank=True, null=True)),
                ("decision_note", models.TextField(blank=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="risk_insurance_claims", to="tenant.company")),
                ("coverage", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="claims", to="risktransferops.insurancecoverage")),
                ("loss_event", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="claims", to="risktransferops.lossevent")),
            ],
            options={
                "db_table": "riskxfer_claim",
                "indexes": [models.Index(fields=["company", "status_code", "notified_on"], name="rx_claim_status_idx")],
                "constraints": [
                    models.UniqueConstraint(fields=("company", "claim_number"), name="rx_claim_number_uq"),
                    models.CheckConstraint(condition=models.Q(claimed_amount__gt=0), name="rx_claim_amount_ck"),
                    models.CheckConstraint(condition=models.Q(reserved_amount__gte=0), name="rx_claim_reserved_ck"),
                    models.CheckConstraint(condition=models.Q(recovered_amount__gte=0), name="rx_claim_recovered_ck"),
                ],
            },
        ),
        migrations.CreateModel(
            name="GuaranteeInstrument",
            fields=base_fields() + [
                ("instrument_number", models.CharField(max_length=120)),
                ("instrument_type_code", models.CharField(default="PERFORMANCE_BOND", max_length=80)),
                ("beneficiary_name", models.CharField(max_length=240)),
                ("applicant_name", models.CharField(max_length=240)),
                ("secured_obligation_public_id", models.UUIDField(blank=True, null=True)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=20)),
                ("currency_code", models.CharField(default="INR", max_length=3)),
                ("issued_on", models.DateField()),
                ("expiry_on", models.DateField()),
                ("auto_renew_flag", models.BooleanField(default=False)),
                ("status_code", models.CharField(default="DRAFT", max_length=30)),
                ("created_by_public_id", models.UUIDField()),
                ("approved_by_public_id", models.UUIDField(blank=True, null=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("decision_note", models.TextField(blank=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="risk_guarantee_instruments", to="tenant.company")),
                ("counterparty", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="guarantee_instruments", to="risktransferops.riskcounterparty")),
                ("program", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="guarantee_instruments", to="risktransferops.insuranceprogram")),
            ],
            options={
                "db_table": "riskxfer_instrument",
                "indexes": [
                    models.Index(fields=["company", "status_code", "expiry_on"], name="rx_instr_status_idx"),
                    models.Index(fields=["company", "instrument_type_code"], name="rx_instr_type_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("company", "instrument_number"), name="rx_instr_number_uq"),
                    models.CheckConstraint(condition=models.Q(amount__gt=0), name="rx_instr_amount_ck"),
                ],
            },
        ),
        migrations.CreateModel(
            name="InstrumentCall",
            fields=base_fields() + [
                ("call_number", models.CharField(max_length=120)),
                ("called_on", models.DateField()),
                ("amount", models.DecimalField(decimal_places=2, max_digits=20)),
                ("currency_code", models.CharField(default="INR", max_length=3)),
                ("reason", models.TextField()),
                ("status_code", models.CharField(default="DRAFT", max_length=30)),
                ("created_by_public_id", models.UUIDField()),
                ("approved_by_public_id", models.UUIDField(blank=True, null=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("settlement_reference", models.CharField(blank=True, max_length=160)),
                ("settled_on", models.DateField(blank=True, null=True)),
                ("decision_note", models.TextField(blank=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="risk_instrument_calls", to="tenant.company")),
                ("instrument", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="calls", to="risktransferops.guaranteeinstrument")),
            ],
            options={
                "db_table": "riskxfer_call",
                "indexes": [models.Index(fields=["company", "status_code", "called_on"], name="rx_call_status_idx")],
                "constraints": [
                    models.UniqueConstraint(fields=("company", "call_number"), name="rx_call_number_uq"),
                    models.CheckConstraint(condition=models.Q(amount__gt=0), name="rx_call_amount_ck"),
                ],
            },
        ),
        migrations.CreateModel(
            name="RiskTransferEvent",
            fields=base_fields() + [
                ("event_type_code", models.CharField(max_length=80)),
                ("event_on", models.DateTimeField()),
                ("summary", models.CharField(max_length=500)),
                ("evidence", models.JSONField(blank=True, default=dict)),
                ("actor_public_id", models.UUIDField()),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="risk_transfer_events", to="tenant.company")),
                ("program", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="events", to="risktransferops.insuranceprogram")),
            ],
            options={
                "db_table": "riskxfer_event",
                "indexes": [
                    models.Index(fields=["company", "event_on"], name="rx_event_time_idx"),
                    models.Index(fields=["company", "event_type_code"], name="rx_event_type_idx"),
                ],
            },
        ),
    ]
