# Generated for MPSqre Build360 Phase 13.
import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("identity", "0013_phase13_controlplane_permissions"),
        ("subscription", "0002_seed_foundation_plan"),
        ("tenant", "0001_initial"),
    ]
    operations = [
        migrations.CreateModel(
            name="PlatformRole",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=100)),
                ("name", models.CharField(max_length=200)),
                ("version", models.PositiveIntegerField(default=1)),
                ("effective_from", models.DateTimeField()),
                ("effective_to", models.DateTimeField(blank=True, null=True)),
                ("retired_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "db_table": "controlplane_platform_role",
                "ordering": ["code", "-version"],
                "indexes": [
                    models.Index(
                        fields=["code", "retired_at", "effective_from"],
                        name="cp_role_active_idx",
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("code", "version"),
                        name="cp_role_code_ver_uq",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("effective_to__isnull", True), ("effective_to__gt", models.F("effective_from")), _connector="OR"),
                        name="cp_role_range_valid",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="TenantAccount",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "lifecycle_status",
                    models.CharField(
                        choices=[
                            ("pilot", "Pilot"),
                            ("active", "Active"),
                            ("grace", "Grace"),
                            ("suspended", "Suspended"),
                            ("closed", "Closed"),
                        ],
                        default="pilot",
                        max_length=20,
                    ),
                ),
                (
                    "onboarding_status",
                    models.CharField(
                        choices=[
                            ("discovery", "Discovery"),
                            ("configuration", "Configuration"),
                            ("data_migration", "Data migration"),
                            ("training", "Training"),
                            ("live", "Live"),
                            ("paused", "Paused"),
                            ("complete", "Complete"),
                        ],
                        default="discovery",
                        max_length=24,
                    ),
                ),
                ("segment_code", models.CharField(blank=True, max_length=100)),
                ("deployment_region", models.CharField(blank=True, max_length=100)),
                ("data_residency", models.CharField(blank=True, max_length=100)),
                ("pilot_started_at", models.DateTimeField(blank=True, null=True)),
                ("activated_at", models.DateTimeField(blank=True, null=True)),
                ("grace_until", models.DateTimeField(blank=True, null=True)),
                ("suspended_at", models.DateTimeField(blank=True, null=True)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("lifecycle_reason", models.CharField(blank=True, max_length=500)),
                ("version", models.PositiveBigIntegerField(default=1)),
                (
                    "company",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="controlplane_account",
                        to="tenant.company",
                    ),
                ),
            ],
            options={
                "db_table": "controlplane_tenant_account",
                "ordering": ["company__display_name"],
                "indexes": [
                    models.Index(
                        fields=["lifecycle_status", "onboarding_status"],
                        name="cp_tenant_status_idx",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="PlatformRolePermission",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                (
                    "permission",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="platform_role_grants",
                        to="identity.permission",
                    ),
                ),
                (
                    "role",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="permission_grants",
                        to="controlplane.platformrole",
                    ),
                ),
            ],
            options={
                "db_table": "controlplane_role_permission",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("role", "permission"),
                        name="cp_role_perm_uq",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="PlatformOperatorAssignment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("assigned_by_public_id", models.UUIDField()),
                ("effective_from", models.DateTimeField()),
                ("effective_to", models.DateTimeField(blank=True, null=True)),
                ("suspended_at", models.DateTimeField(blank=True, null=True)),
                (
                    "role",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="operator_assignments",
                        to="controlplane.platformrole",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="platform_operator_assignments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "controlplane_operator_assignment",
                "indexes": [
                    models.Index(
                        fields=["user", "suspended_at", "effective_from"],
                        name="cp_operator_active_idx",
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("user", "role", "effective_from"),
                        name="cp_operator_assign_uq",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("effective_to__isnull", True), ("effective_to__gt", models.F("effective_from")), _connector="OR"),
                        name="cp_operator_range_valid",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="TenantUsageSnapshot",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("period_start", models.DateField()),
                ("period_end", models.DateField()),
                ("metrics", models.JSONField(default=dict)),
                ("quota_status", models.JSONField(default=dict)),
                ("checksum_sha256", models.CharField(max_length=64)),
                ("collected_by_public_id", models.UUIDField()),
                ("collected_at", models.DateTimeField()),
                (
                    "tenant_account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="usage_snapshots",
                        to="controlplane.tenantaccount",
                    ),
                ),
            ],
            options={
                "db_table": "controlplane_usage_snapshot",
                "ordering": ["-period_end", "tenant_account__company__display_name"],
                "indexes": [
                    models.Index(
                        fields=["tenant_account", "period_end"],
                        name="cp_usage_tenant_idx",
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("tenant_account", "period_start", "period_end"),
                        name="cp_usage_period_uq",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("period_end__gte", models.F("period_start"))),
                        name="cp_usage_period_valid",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="SupportAccessRequest",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("requested_by_public_id", models.UUIDField()),
                ("reason", models.CharField(max_length=1000)),
                ("scope_codes", models.JSONField(default=list)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("requested", "Requested"),
                            ("approved", "Approved"),
                            ("rejected", "Rejected"),
                            ("revoked", "Revoked"),
                            ("expired", "Expired"),
                        ],
                        default="requested",
                        max_length=20,
                    ),
                ),
                ("requested_at", models.DateTimeField()),
                ("expires_at", models.DateTimeField()),
                ("decided_by_membership_public_id", models.UUIDField(blank=True, null=True)),
                ("decided_at", models.DateTimeField(blank=True, null=True)),
                ("decision_reason", models.CharField(blank=True, max_length=500)),
                ("revoked_by_public_id", models.UUIDField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("version", models.PositiveBigIntegerField(default=1)),
                (
                    "operator_assignment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="support_requests",
                        to="controlplane.platformoperatorassignment",
                    ),
                ),
                (
                    "tenant_account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="support_requests",
                        to="controlplane.tenantaccount",
                    ),
                ),
            ],
            options={
                "db_table": "controlplane_support_request",
                "ordering": ["-requested_at"],
                "indexes": [
                    models.Index(
                        fields=["tenant_account", "status", "expires_at"],
                        name="cp_support_status_idx",
                    )
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("expires_at__gt", models.F("requested_at"))),
                        name="cp_support_expiry_valid",
                    )
                ],
            },
        ),
    ]
