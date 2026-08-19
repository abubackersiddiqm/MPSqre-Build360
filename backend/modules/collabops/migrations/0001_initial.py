# Generated for MPSqre Build360 Phase 32.

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

    dependencies = [
        ("tenant", "0001_initial"),
        ("workops", "0003_grant_existing_admin_roles"),
    ]

    operations = [
        migrations.CreateModel(
            name="CollaborationPolicyVersion",
            fields=common() + [
                ("version", models.PositiveIntegerField(default=1)),
                ("status_code", models.CharField(default="DRAFT", max_length=30)),
                ("invitation_ttl_hours", models.PositiveSmallIntegerField(default=72)),
                ("require_project_grant", models.BooleanField(default=True)),
                ("require_submission_review", models.BooleanField(default=True)),
                ("allow_external_decisions", models.BooleanField(default=False)),
                ("configuration", models.JSONField(blank=True, default=dict)),
                ("effective_from", models.DateTimeField(blank=True, null=True)),
                ("effective_to", models.DateTimeField(blank=True, null=True)),
                ("published_by_public_id", models.UUIDField(blank=True, null=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="collaboration_policies", to="tenant.company")),
            ],
            options={
                "db_table": "collabops_policy_version",
                "constraints": [
                    models.UniqueConstraint(fields=("company", "version"), name="co_policy_version_uq"),
                    models.CheckConstraint(condition=models.Q(("effective_to__isnull", True), ("effective_from__isnull", True), ("effective_to__gt", models.F("effective_from")), _connector="OR"), name="co_policy_dates_ck"),
                ],
                "indexes": [models.Index(fields=["company", "status_code"], name="co_policy_status_idx")],
            },
        ),
        migrations.CreateModel(
            name="PartnerOrganization",
            fields=common() + [
                ("code", models.CharField(max_length=60)),
                ("legal_name", models.CharField(max_length=250)),
                ("display_name", models.CharField(max_length=250)),
                ("organization_type_code", models.CharField(default="VENDOR", max_length=40)),
                ("registration_number", models.CharField(blank=True, max_length=120)),
                ("tax_registration_number", models.CharField(blank=True, max_length=120)),
                ("country_code", models.CharField(blank=True, max_length=2)),
                ("primary_email", models.EmailField(blank=True, max_length=254)),
                ("primary_phone", models.CharField(blank=True, max_length=40)),
                ("status_code", models.CharField(default="ACTIVE", max_length=30)),
                ("risk_rating_code", models.CharField(default="UNASSESSED", max_length=30)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="partner_organizations", to="tenant.company")),
            ],
            options={
                "db_table": "collabops_partner_org",
                "constraints": [models.UniqueConstraint(fields=("company", "code"), name="co_partner_code_uq")],
                "indexes": [models.Index(fields=["company", "organization_type_code", "status_code"], name="co_partner_status_idx")],
            },
        ),
        migrations.CreateModel(
            name="PartnerContact",
            fields=common() + [
                ("full_name", models.CharField(max_length=200)),
                ("email", models.EmailField(max_length=254)),
                ("mobile", models.CharField(blank=True, max_length=40)),
                ("job_title", models.CharField(blank=True, max_length=150)),
                ("is_primary", models.BooleanField(default=False)),
                ("can_approve", models.BooleanField(default=False)),
                ("status_code", models.CharField(default="INVITED", max_length=30)),
                ("invitation_public_id", models.UUIDField(blank=True, null=True)),
                ("invited_at", models.DateTimeField(blank=True, null=True)),
                ("activated_at", models.DateTimeField(blank=True, null=True)),
                ("suspended_at", models.DateTimeField(blank=True, null=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="partner_contacts", to="tenant.company")),
                ("membership", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="external_collaboration_contact", to="tenant.membership")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="contacts", to="collabops.partnerorganization")),
            ],
            options={
                "db_table": "collabops_partner_contact",
                "constraints": [models.UniqueConstraint(fields=("company", "email"), name="co_contact_email_uq")],
                "indexes": [models.Index(fields=["company", "status_code"], name="co_contact_status_idx")],
            },
        ),
        migrations.CreateModel(
            name="ProjectAccessGrant",
            fields=common() + [
                ("scopes", models.JSONField(default=list)),
                ("effective_from", models.DateTimeField()),
                ("effective_to", models.DateTimeField(blank=True, null=True)),
                ("status_code", models.CharField(default="ACTIVE", max_length=30)),
                ("granted_by_public_id", models.UUIDField()),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="partner_project_grants", to="tenant.company")),
                ("contact", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="project_grants", to="collabops.partnercontact")),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="external_access_grants", to="workops.project")),
                ("site", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="external_access_grants", to="workops.projectsite")),
            ],
            options={
                "db_table": "collabops_project_grant",
                "constraints": [
                    models.UniqueConstraint(fields=("contact", "project", "site"), name="co_grant_scope_uq"),
                    models.CheckConstraint(condition=models.Q(("effective_to__isnull", True), ("effective_to__gt", models.F("effective_from")), _connector="OR"), name="co_grant_dates_ck"),
                ],
                "indexes": [models.Index(fields=["company", "project", "status_code"], name="co_grant_project_idx")],
            },
        ),
        migrations.CreateModel(
            name="CollaborationItem",
            fields=common() + [
                ("reference", models.CharField(max_length=100)),
                ("item_type_code", models.CharField(default="GENERAL", max_length=50)),
                ("title", models.CharField(max_length=250)),
                ("description", models.TextField(blank=True)),
                ("status_code", models.CharField(default="DRAFT", max_length=40)),
                ("priority_code", models.CharField(default="NORMAL", max_length=30)),
                ("due_at", models.DateTimeField(blank=True, null=True)),
                ("response_required", models.BooleanField(default=True)),
                ("approval_required", models.BooleanField(default=False)),
                ("amount", models.DecimalField(blank=True, decimal_places=2, max_digits=18, null=True)),
                ("currency", models.CharField(blank=True, max_length=3)),
                ("source_module", models.CharField(blank=True, max_length=50)),
                ("source_public_id", models.UUIDField(blank=True, null=True)),
                ("created_by_public_id", models.UUIDField()),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("assigned_contact", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="assigned_items", to="collabops.partnercontact")),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="collaboration_items", to="tenant.company")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="collaboration_items", to="collabops.partnerorganization")),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="collaboration_items", to="workops.project")),
                ("site", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="collaboration_items", to="workops.projectsite")),
            ],
            options={
                "db_table": "collabops_item",
                "constraints": [
                    models.UniqueConstraint(fields=("company", "reference"), name="co_item_reference_uq"),
                    models.CheckConstraint(condition=models.Q(("amount__isnull", True), ("amount__gte", 0), _connector="OR"), name="co_item_amount_ck"),
                ],
                "indexes": [
                    models.Index(fields=["company", "status_code", "due_at"], name="co_item_due_idx"),
                    models.Index(fields=["company", "organization", "project"], name="co_item_partner_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="CollaborationSubmission",
            fields=common() + [
                ("revision", models.PositiveIntegerField(default=1)),
                ("status_code", models.CharField(default="SUBMITTED", max_length=30)),
                ("summary", models.TextField(blank=True)),
                ("data", models.JSONField(blank=True, default=dict)),
                ("attachment_references", models.JSONField(blank=True, default=list)),
                ("submitted_at", models.DateTimeField()),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("reviewed_by_public_id", models.UUIDField(blank=True, null=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="collaboration_submissions", to="tenant.company")),
                ("contact", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="submissions", to="collabops.partnercontact")),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="submissions", to="collabops.collaborationitem")),
            ],
            options={
                "db_table": "collabops_submission",
                "constraints": [models.UniqueConstraint(fields=("item", "revision"), name="co_submission_revision_uq")],
                "indexes": [models.Index(fields=["company", "status_code", "submitted_at"], name="co_submission_status_idx")],
            },
        ),
        migrations.CreateModel(
            name="CollaborationDecision",
            fields=common() + [
                ("decision_code", models.CharField(max_length=40)),
                ("notes", models.TextField(blank=True)),
                ("decided_by_public_id", models.UUIDField()),
                ("decided_by_type", models.CharField(default="INTERNAL", max_length=30)),
                ("decided_at", models.DateTimeField()),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="collaboration_decisions", to="tenant.company")),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="decisions", to="collabops.collaborationitem")),
                ("submission", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="decisions", to="collabops.collaborationsubmission")),
            ],
            options={
                "db_table": "collabops_decision",
                "indexes": [models.Index(fields=["company", "decision_code", "decided_at"], name="co_decision_status_idx")],
            },
        ),
        migrations.CreateModel(
            name="CollaborationMessage",
            fields=common() + [
                ("sender_type_code", models.CharField(default="INTERNAL", max_length=30)),
                ("sender_public_id", models.UUIDField()),
                ("body", models.TextField()),
                ("attachment_references", models.JSONField(blank=True, default=list)),
                ("is_internal", models.BooleanField(default=False)),
                ("sent_at", models.DateTimeField()),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="collaboration_messages", to="tenant.company")),
                ("contact", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="messages", to="collabops.partnercontact")),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="messages", to="collabops.collaborationitem")),
            ],
            options={
                "db_table": "collabops_message",
                "indexes": [models.Index(fields=["company", "item", "sent_at"], name="co_message_thread_idx")],
            },
        ),
    ]
