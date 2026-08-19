from __future__ import annotations

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tenant", "0003_brand_asset_references"),
    ]

    operations = [
        migrations.CreateModel(
            name="CompanyEmailDeliveryProfile",
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
                (
                    "public_id",
                    models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "delivery_mode",
                    models.CharField(
                        choices=[
                            ("PLATFORM", "Build360 platform mail"),
                            ("TENANT_SMTP", "Company SMTP"),
                        ],
                        default="PLATFORM",
                        max_length=20,
                    ),
                ),
                ("smtp_host", models.CharField(blank=True, max_length=253)),
                ("smtp_port", models.PositiveIntegerField(default=587)),
                ("smtp_username", models.CharField(blank=True, max_length=320)),
                ("smtp_password_encrypted", models.TextField(blank=True)),
                ("smtp_use_tls", models.BooleanField(default=True)),
                ("smtp_use_ssl", models.BooleanField(default=False)),
                ("from_email", models.EmailField(blank=True, max_length=254)),
                ("reply_to_email", models.EmailField(blank=True, max_length=254)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("DISABLED", "Disabled"),
                            ("PENDING", "Pending verification"),
                            ("ACTIVE", "Active"),
                            ("FAILED", "Verification failed"),
                        ],
                        default="DISABLED",
                        max_length=20,
                    ),
                ),
                ("last_tested_at", models.DateTimeField(blank=True, null=True)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("last_error_code", models.CharField(blank=True, max_length=120)),
                ("updated_by_public_id", models.UUIDField(blank=True, null=True)),
                ("version", models.PositiveBigIntegerField(default=1)),
                (
                    "company",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="email_delivery_profile",
                        to="tenant.company",
                    ),
                ),
            ],
            options={"db_table": "tenant_company_email_delivery_profile"},
        ),
    ]
