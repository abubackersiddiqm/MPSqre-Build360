# Generated for MPSqre Build360 Phase 28.

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("tenant", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlatformOperator",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("operator_type_code", models.CharField(default="PLATFORM_OPERATOR", max_length=100)),
                ("is_active", models.BooleanField(default=True)),
                ("created_by_public_id", models.UUIDField(blank=True, null=True)),
                ("last_access_review_at", models.DateTimeField(blank=True, null=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="accessops_platform_operator", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "accessops_platform_operator"},
        ),
        migrations.CreateModel(
            name="CompanyAccessProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("plan_code", models.CharField(blank=True, max_length=100)),
                ("onboarding_status_code", models.CharField(default="PENDING_ADMIN", max_length=100)),
                ("primary_admin_email", models.EmailField(blank=True, max_length=254)),
                ("created_by_public_id", models.UUIDField(blank=True, null=True)),
                ("activated_at", models.DateTimeField(blank=True, null=True)),
                ("setup_completed_at", models.DateTimeField(blank=True, null=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="accessops_profile", to="tenant.company")),
            ],
            options={"db_table": "accessops_company_profile"},
        ),
        migrations.CreateModel(
            name="AccessInvitation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("email", models.EmailField(max_length=254)),
                ("display_name", models.CharField(max_length=200)),
                ("invitation_type_code", models.CharField(default="EMPLOYEE", max_length=100)),
                ("token_hash", models.CharField(max_length=64, unique=True)),
                ("token_hint", models.CharField(blank=True, max_length=12)),
                ("role_public_ids", models.JSONField(default=list)),
                ("employee_number", models.CharField(blank=True, max_length=50)),
                ("job_title", models.CharField(blank=True, max_length=150)),
                ("invited_by_public_id", models.UUIDField()),
                ("expires_at", models.DateTimeField()),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="accessops_invitations", to="tenant.company")),
            ],
            options={"db_table": "accessops_invitation"},
        ),
        migrations.AddIndex(
            model_name="platformoperator",
            index=models.Index(fields=["is_active", "operator_type_code"], name="accessops_operator_active_idx"),
        ),
        migrations.AddIndex(
            model_name="companyaccessprofile",
            index=models.Index(fields=["onboarding_status_code", "created_at"], name="accessops_company_onboard_idx"),
        ),
        migrations.AddIndex(
            model_name="accessinvitation",
            index=models.Index(fields=["company", "email", "expires_at"], name="accessops_invite_company_idx"),
        ),
        migrations.AddIndex(
            model_name="accessinvitation",
            index=models.Index(fields=["company", "accepted_at", "revoked_at"], name="accessops_invite_state_idx"),
        ),
    ]
