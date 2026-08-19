# Generated for MPSqre Build360 Phase 10.
import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [("tenant", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="PortalInvitation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("email", models.EmailField(max_length=254)),
                ("portal_type", models.CharField(choices=[("client", "Client"), ("vendor", "Vendor")], max_length=20)),
                ("scope_type", models.CharField(choices=[("company", "Company"), ("project", "Project"), ("customer", "Customer"), ("vendor", "Vendor")], max_length=20)),
                ("scope_public_id", models.UUIDField(blank=True, null=True)),
                ("permission_codes", models.JSONField(default=list)),
                ("token_digest", models.CharField(max_length=64, unique=True)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("accepted", "Accepted"), ("revoked", "Revoked"), ("expired", "Expired")], default="pending", max_length=20)),
                ("invited_by_public_id", models.UUIDField()),
                ("expires_at", models.DateTimeField()),
                ("accepted_by_public_id", models.UUIDField(blank=True, null=True)),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_by_public_id", models.UUIDField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("version", models.PositiveBigIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="tenant.company")),
            ],
            options={
                "db_table": "portal_invitation",
                "ordering": ["-created_at"],
                "indexes": [models.Index(fields=["company", "status", "expires_at"], name="portal_invite_status_idx")],
                "constraints": [models.UniqueConstraint(condition=models.Q(("status", "pending")), fields=("company", "email", "portal_type", "scope_type", "scope_public_id"), name="portal_pending_invite_uq")],
            },
        ),
        migrations.CreateModel(
            name="PortalAccessGrant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user_public_id", models.UUIDField()),
                ("portal_type", models.CharField(choices=[("client", "Client"), ("vendor", "Vendor")], max_length=20)),
                ("scope_type", models.CharField(choices=[("company", "Company"), ("project", "Project"), ("customer", "Customer"), ("vendor", "Vendor")], max_length=20)),
                ("scope_public_id", models.UUIDField(blank=True, null=True)),
                ("permission_codes", models.JSONField(default=list)),
                ("effective_from", models.DateTimeField()),
                ("effective_to", models.DateTimeField(blank=True, null=True)),
                ("granted_by_public_id", models.UUIDField()),
                ("revoked_by_public_id", models.UUIDField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("revoke_reason", models.CharField(blank=True, max_length=500)),
                ("version", models.PositiveBigIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="tenant.company")),
            ],
            options={
                "db_table": "portal_access_grant",
                "indexes": [models.Index(fields=["company", "user_public_id", "revoked_at"], name="portal_user_grant_idx")],
                "constraints": [
                    models.UniqueConstraint(condition=models.Q(("revoked_at__isnull", True)), fields=("company", "user_public_id", "portal_type", "scope_type", "scope_public_id"), name="portal_active_grant_uq"),
                    models.CheckConstraint(condition=models.Q(("effective_to__isnull", True), ("effective_to__gt", models.F("effective_from")), _connector="OR"), name="portal_grant_range_ok"),
                ],
            },
        ),
        migrations.CreateModel(
            name="PortalShare",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("entity_type", models.CharField(max_length=100)),
                ("entity_public_id", models.UUIDField()),
                ("access_level", models.CharField(choices=[("view", "View"), ("comment", "Comment"), ("submit", "Submit")], default="view", max_length=20)),
                ("created_by_public_id", models.UUIDField()),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_by_public_id", models.UUIDField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("version", models.PositiveBigIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="tenant.company")),
                ("grant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="shares", to="portal.portalaccessgrant")),
            ],
            options={
                "db_table": "portal_share",
                "indexes": [models.Index(fields=["company", "entity_type", "entity_public_id", "revoked_at"], name="portal_share_entity_idx")],
                "constraints": [models.UniqueConstraint(condition=models.Q(("revoked_at__isnull", True)), fields=("company", "grant", "entity_type", "entity_public_id"), name="portal_active_share_uq")],
            },
        ),
    ]
