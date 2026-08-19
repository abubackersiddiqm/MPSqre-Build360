# Generated for MPSqre Build360 Phase 36.

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
            name="SupportPolicyVersion",
            fields=common() + [
                ("version", models.PositiveIntegerField(default=1)),
                ("status_code", models.CharField(default="DRAFT", max_length=30)),
                ("default_response_minutes", models.PositiveIntegerField(default=240)),
                ("default_resolution_minutes", models.PositiveIntegerField(default=2880)),
                ("escalation_warning_percent", models.DecimalField(decimal_places=2, default=decimal.Decimal("80.00"), max_digits=5)),
                ("customer_feedback_required", models.BooleanField(default=True)),
                ("configuration", models.JSONField(blank=True, default=dict)),
                ("effective_from", models.DateTimeField(blank=True, null=True)),
                ("effective_to", models.DateTimeField(blank=True, null=True)),
                ("published_by_public_id", models.UUIDField(blank=True, null=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="support_policies", to="tenant.company")),
            ],
            options={
                "db_table": "supportops_policy_version",
                "constraints": [
                    models.UniqueConstraint(fields=("company", "version"), name="sup_policy_version_uq"),
                    models.CheckConstraint(condition=models.Q(effective_to__isnull=True) | models.Q(effective_from__isnull=True) | models.Q(effective_to__gt=models.F("effective_from")), name="sup_policy_dates_ck"),
                    models.CheckConstraint(condition=models.Q(escalation_warning_percent__gte=0) & models.Q(escalation_warning_percent__lte=100), name="sup_policy_warning_ck"),
                ],
                "indexes": [models.Index(fields=["company", "status_code"], name="sup_policy_status_idx")],
            },
        ),
        migrations.CreateModel(
            name="ServiceCatalogItem",
            fields=common() + [
                ("code", models.CharField(max_length=80)),
                ("name", models.CharField(max_length=220)),
                ("category_code", models.CharField(default="GENERAL", max_length=80)),
                ("description", models.TextField(blank=True)),
                ("response_minutes", models.PositiveIntegerField(default=240)),
                ("resolution_minutes", models.PositiveIntegerField(default=2880)),
                ("business_hours_only", models.BooleanField(default=True)),
                ("active", models.BooleanField(default=True)),
                ("configuration", models.JSONField(blank=True, default=dict)),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="support_catalog_items", to="tenant.company")),
            ],
            options={
                "db_table": "supportops_catalog_item",
                "constraints": [models.UniqueConstraint(fields=("company", "code"), name="sup_catalog_code_uq")],
                "indexes": [models.Index(fields=["company", "active", "category_code"], name="sup_catalog_active_idx")],
            },
        ),
        migrations.CreateModel(
            name="SupportTicket",
            fields=common() + [
                ("code", models.CharField(max_length=80)),
                ("title", models.CharField(max_length=240)),
                ("description", models.TextField(blank=True)),
                ("category_code", models.CharField(default="GENERAL", max_length=80)),
                ("priority_code", models.CharField(default="P3", max_length=10)),
                ("channel_code", models.CharField(default="PORTAL", max_length=30)),
                ("status_code", models.CharField(default="NEW", max_length=30)),
                ("requester_name", models.CharField(max_length=180)),
                ("requester_email", models.EmailField(blank=True, max_length=254)),
                ("requester_public_id", models.UUIDField(blank=True, null=True)),
                ("assigned_to_public_id", models.UUIDField(blank=True, null=True)),
                ("created_by_public_id", models.UUIDField()),
                ("response_due_at", models.DateTimeField(blank=True, null=True)),
                ("resolution_due_at", models.DateTimeField(blank=True, null=True)),
                ("first_responded_at", models.DateTimeField(blank=True, null=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("resolution_summary", models.TextField(blank=True)),
                ("sla_breached", models.BooleanField(default=False)),
                ("escalation_level", models.PositiveIntegerField(default=0)),
                ("tags", models.JSONField(blank=True, default=list)),
                ("version", models.PositiveIntegerField(default=1)),
                ("catalog_item", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="tickets", to="supportops.servicecatalogitem")),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="support_tickets", to="tenant.company")),
            ],
            options={
                "db_table": "supportops_ticket",
                "constraints": [models.UniqueConstraint(fields=("company", "code"), name="sup_ticket_code_uq")],
                "indexes": [
                    models.Index(fields=["company", "status_code", "priority_code"], name="sup_ticket_status_idx"),
                    models.Index(fields=["company", "resolution_due_at"], name="sup_ticket_due_idx"),
                    models.Index(fields=["company", "assigned_to_public_id"], name="sup_ticket_owner_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="KnowledgeArticle",
            fields=common() + [
                ("code", models.CharField(max_length=80)),
                ("title", models.CharField(max_length=240)),
                ("summary", models.TextField(blank=True)),
                ("content", models.TextField()),
                ("category_code", models.CharField(default="GENERAL", max_length=80)),
                ("audience_code", models.CharField(default="INTERNAL", max_length=40)),
                ("status_code", models.CharField(default="DRAFT", max_length=30)),
                ("keywords", models.JSONField(blank=True, default=list)),
                ("created_by_public_id", models.UUIDField()),
                ("published_by_public_id", models.UUIDField(blank=True, null=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="support_knowledge_articles", to="tenant.company")),
            ],
            options={
                "db_table": "supportops_knowledge_article",
                "constraints": [models.UniqueConstraint(fields=("company", "code"), name="sup_article_code_uq")],
                "indexes": [models.Index(fields=["company", "status_code", "category_code"], name="sup_article_status_idx")],
            },
        ),
        migrations.CreateModel(
            name="ProblemRecord",
            fields=common() + [
                ("code", models.CharField(max_length=80)),
                ("title", models.CharField(max_length=240)),
                ("impact_summary", models.TextField(blank=True)),
                ("root_cause", models.TextField(blank=True)),
                ("workaround", models.TextField(blank=True)),
                ("permanent_fix", models.TextField(blank=True)),
                ("priority_code", models.CharField(default="P2", max_length=10)),
                ("status_code", models.CharField(default="OPEN", max_length=30)),
                ("owner_public_id", models.UUIDField(blank=True, null=True)),
                ("created_by_public_id", models.UUIDField()),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="support_problems", to="tenant.company")),
                ("source_ticket", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="problems", to="supportops.supportticket")),
            ],
            options={
                "db_table": "supportops_problem",
                "constraints": [models.UniqueConstraint(fields=("company", "code"), name="sup_problem_code_uq")],
                "indexes": [models.Index(fields=["company", "status_code", "priority_code"], name="sup_problem_status_idx")],
            },
        ),
        migrations.CreateModel(
            name="TicketInteraction",
            fields=common() + [
                ("interaction_type_code", models.CharField(default="COMMENT", max_length=30)),
                ("visibility_code", models.CharField(default="INTERNAL", max_length=30)),
                ("body", models.TextField()),
                ("actor_public_id", models.UUIDField()),
                ("customer_visible", models.BooleanField(default=False)),
                ("occurred_at", models.DateTimeField()),
                ("attachments", models.JSONField(blank=True, default=list)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="support_interactions", to="tenant.company")),
                ("ticket", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="interactions", to="supportops.supportticket")),
            ],
            options={
                "db_table": "supportops_interaction",
                "indexes": [
                    models.Index(fields=["ticket", "occurred_at"], name="sup_interaction_time_idx"),
                    models.Index(fields=["company", "customer_visible"], name="sup_interaction_vis_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="ChangeRequest",
            fields=common() + [
                ("code", models.CharField(max_length=80)),
                ("title", models.CharField(max_length=240)),
                ("description", models.TextField(blank=True)),
                ("change_type_code", models.CharField(default="NORMAL", max_length=40)),
                ("risk_code", models.CharField(default="MEDIUM", max_length=20)),
                ("status_code", models.CharField(default="DRAFT", max_length=30)),
                ("planned_start_at", models.DateTimeField(blank=True, null=True)),
                ("planned_end_at", models.DateTimeField(blank=True, null=True)),
                ("rollback_plan", models.TextField(blank=True)),
                ("test_evidence", models.JSONField(blank=True, default=dict)),
                ("created_by_public_id", models.UUIDField()),
                ("approved_by_public_id", models.UUIDField(blank=True, null=True)),
                ("implemented_at", models.DateTimeField(blank=True, null=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="support_changes", to="tenant.company")),
                ("problem", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="change_requests", to="supportops.problemrecord")),
                ("source_ticket", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="change_requests", to="supportops.supportticket")),
            ],
            options={
                "db_table": "supportops_change_request",
                "constraints": [
                    models.UniqueConstraint(fields=("company", "code"), name="sup_change_code_uq"),
                    models.CheckConstraint(condition=models.Q(planned_end_at__isnull=True) | models.Q(planned_start_at__isnull=True) | models.Q(planned_end_at__gt=models.F("planned_start_at")), name="sup_change_dates_ck"),
                ],
                "indexes": [models.Index(fields=["company", "status_code", "risk_code"], name="sup_change_status_idx")],
            },
        ),
        migrations.CreateModel(
            name="CustomerFeedback",
            fields=common() + [
                ("rating", models.PositiveSmallIntegerField()),
                ("comments", models.TextField(blank=True)),
                ("submitted_by_name", models.CharField(blank=True, max_length=180)),
                ("submitted_by_email", models.EmailField(blank=True, max_length=254)),
                ("submitted_at", models.DateTimeField()),
                ("follow_up_required", models.BooleanField(default=False)),
                ("follow_up_notes", models.TextField(blank=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="support_feedback", to="tenant.company")),
                ("ticket", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="feedback", to="supportops.supportticket")),
            ],
            options={
                "db_table": "supportops_feedback",
                "indexes": [models.Index(fields=["company", "rating", "submitted_at"], name="sup_feedback_rating_idx")],
            },
        ),
        migrations.CreateModel(
            name="ImprovementItem",
            fields=common() + [
                ("code", models.CharField(max_length=80)),
                ("title", models.CharField(max_length=240)),
                ("description", models.TextField(blank=True)),
                ("theme_code", models.CharField(default="SERVICE_QUALITY", max_length=80)),
                ("priority_code", models.CharField(default="P3", max_length=10)),
                ("status_code", models.CharField(default="BACKLOG", max_length=30)),
                ("expected_benefit", models.TextField(blank=True)),
                ("measured_benefit", models.TextField(blank=True)),
                ("owner_public_id", models.UUIDField(blank=True, null=True)),
                ("due_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_by_public_id", models.UUIDField()),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="support_improvements", to="tenant.company")),
                ("source_feedback", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="improvements", to="supportops.customerfeedback")),
                ("source_problem", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="improvements", to="supportops.problemrecord")),
                ("source_ticket", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="improvements", to="supportops.supportticket")),
            ],
            options={
                "db_table": "supportops_improvement_item",
                "constraints": [models.UniqueConstraint(fields=("company", "code"), name="sup_improvement_code_uq")],
                "indexes": [
                    models.Index(fields=["company", "status_code", "priority_code"], name="sup_improvement_status_idx"),
                    models.Index(fields=["company", "due_at"], name="sup_improvement_due_idx"),
                ],
            },
        ),
    ]
