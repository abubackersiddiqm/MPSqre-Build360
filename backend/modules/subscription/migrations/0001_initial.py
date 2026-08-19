import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [("tenant", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="PlanVersion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=100)),
                ("version", models.PositiveIntegerField()),
                ("name", models.CharField(max_length=200)),
                ("status", models.CharField(choices=[("DRAFT", "Draft"), ("PUBLISHED", "Published"), ("RETIRED", "Retired")], default="DRAFT", max_length=20)),
                ("entitlements", models.JSONField(default=dict)),
                ("limits", models.JSONField(default=dict)),
                ("effective_from", models.DateTimeField()),
                ("effective_to", models.DateTimeField(blank=True, null=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "db_table": "subscription_plan_version",
                "constraints": [
                    models.UniqueConstraint(fields=("code", "version"), name="subscription_plan_code_version_unique"),
                    models.CheckConstraint(condition=models.Q(("effective_to__isnull", True), ("effective_to__gt", models.F("effective_from")), _connector="OR"), name="subscription_plan_effective_range_valid"),
                    models.CheckConstraint(condition=models.Q(models.Q(("published_at__isnull", True), ("status", "DRAFT")), models.Q(("published_at__isnull", False), ("status__in", ["PUBLISHED", "RETIRED"])), _connector="OR"), name="subscription_plan_publish_state_valid"),
                ],
            },
        ),
        migrations.CreateModel(
            name="CompanySubscription",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("status", models.CharField(choices=[("TRIAL", "Trial"), ("ACTIVE", "Active"), ("GRACE", "Grace"), ("SUSPENDED", "Suspended"), ("ENDED", "Ended")], max_length=20)),
                ("starts_at", models.DateTimeField()),
                ("ends_at", models.DateTimeField(blank=True, null=True)),
                ("grace_until", models.DateTimeField(blank=True, null=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="subscriptions", to="tenant.company")),
                ("plan_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="company_subscriptions", to="subscription.planversion")),
            ],
            options={
                "db_table": "subscription_company_subscription",
                "indexes": [models.Index(fields=["company", "status", "starts_at"], name="sub_company_active_idx")],
                "constraints": [models.CheckConstraint(condition=models.Q(("ends_at__isnull", True), ("ends_at__gt", models.F("starts_at")), _connector="OR"), name="subscription_company_range_valid")],
            },
        ),
        migrations.CreateModel(
            name="EntitlementOverride",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("entitlement_code", models.CharField(max_length=150)),
                ("enabled", models.BooleanField()),
                ("limit_value", models.PositiveBigIntegerField(blank=True, null=True)),
                ("effective_from", models.DateTimeField()),
                ("effective_to", models.DateTimeField(blank=True, null=True)),
                ("reason_code", models.CharField(max_length=100)),
                ("set_by_public_id", models.UUIDField()),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="entitlement_overrides", to="tenant.company")),
            ],
            options={
                "db_table": "subscription_entitlement_override",
                "indexes": [models.Index(fields=["company", "entitlement_code", "effective_from"], name="sub_override_lookup_idx")],
                "constraints": [
                    models.UniqueConstraint(fields=("company", "entitlement_code", "effective_from"), name="subscription_override_effective_unique"),
                    models.CheckConstraint(condition=models.Q(("effective_to__isnull", True), ("effective_to__gt", models.F("effective_from")), _connector="OR"), name="subscription_override_range_valid"),
                ],
            },
        ),
    ]
