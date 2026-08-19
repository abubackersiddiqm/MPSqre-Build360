import uuid

from django.db import migrations, models
import django.db.models.deletion


def seed_meta_provider(apps, schema_editor):
    Catalog = apps.get_model("integration", "IntegrationProviderCatalog")
    Catalog.objects.update_or_create(
        code="META_LEAD_ADS",
        defaults={
            "name": "Meta Lead Ads",
            "category": "AUTOMATION",
            "connector_type": "CUSTOM",
            "provider_code": "META_LEAD_ADS",
            "adapter_code": "meta_lead_ads",
            "description": "Inbound Meta Lead Ads webhook and CRM lead ingestion adapter.",
            "capabilities": [
                "leadgen_webhook",
                "field_mapping",
                "deduplication",
                "crm_contact",
                "crm_lead",
            ],
            "configuration_schema": {
                "page_id": "string",
                "lead_form_ids": "string[]",
                "graph_api_version": "string",
                "default_owner_membership_public_id": "uuid",
                "secret_ref": "env:// reference",
            },
            "docs_url": "",
            "recommended": True,
            "is_active": True,
            "sort_order": 15,
        },
    )


def remove_meta_provider(apps, schema_editor):
    apps.get_model("integration", "IntegrationProviderCatalog").objects.filter(
        code="META_LEAD_ADS"
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("integration", "0002_provider_catalog"),
        ("identity", "0020_meta_lead_ads_permissions"),
    ]

    operations = [
        migrations.CreateModel(
            name="MetaLeadReceipt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("external_lead_id", models.CharField(max_length=160)),
                ("page_id", models.CharField(blank=True, max_length=160)),
                ("form_id", models.CharField(blank=True, max_length=160)),
                ("ad_id", models.CharField(blank=True, max_length=160)),
                ("adset_id", models.CharField(blank=True, max_length=160)),
                ("campaign_id", models.CharField(blank=True, max_length=160)),
                ("source_created_at", models.DateTimeField(blank=True, null=True)),
                ("field_names", models.JSONField(default=list)),
                ("payload_digest_sha256", models.CharField(max_length=64)),
                ("status", models.CharField(choices=[
                    ("RECEIVED", "Received"),
                    ("PROCESSING", "Processing"),
                    ("PROCESSED", "Processed"),
                    ("DUPLICATE", "Duplicate/reused"),
                    ("IGNORED", "Ignored"),
                    ("FAILED", "Failed"),
                ], default="RECEIVED", max_length=30)),
                ("contact_public_id", models.UUIDField(blank=True, null=True)),
                ("lead_public_id", models.UUIDField(blank=True, null=True)),
                ("attempt_count", models.PositiveIntegerField(default=0)),
                ("last_attempt_at", models.DateTimeField(blank=True, null=True)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("error_summary", models.CharField(blank=True, max_length=500)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="meta_lead_receipts", to="tenant.company")),
                ("connector", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="meta_lead_receipts", to="integration.connectorprofile")),
            ],
            options={"db_table": "integration_meta_lead_receipt"},
        ),
        migrations.AddConstraint(
            model_name="metaleadreceipt",
            constraint=models.UniqueConstraint(fields=("connector", "external_lead_id"), name="int_meta_lead_ext_uq"),
        ),
        migrations.AddIndex(
            model_name="metaleadreceipt",
            index=models.Index(fields=["company", "status", "created_at"], name="int_meta_lead_status_idx"),
        ),
        migrations.AddIndex(
            model_name="metaleadreceipt",
            index=models.Index(fields=["connector", "form_id", "created_at"], name="int_meta_lead_form_idx"),
        ),
        migrations.RunPython(seed_meta_provider, remove_meta_provider),
    ]
