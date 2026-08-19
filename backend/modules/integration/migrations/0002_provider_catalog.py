import uuid
from django.db import migrations, models


PROVIDERS = [
    ("META_WHATSAPP", "WhatsApp Business", "COMMUNICATION", "COMMUNICATION", "META_WHATSAPP", "meta_whatsapp", "Business messaging, templates and delivery events.", ["messages", "templates", "webhooks"], True, 10),
    ("TWILIO_VOICE", "Twilio Voice", "COMMUNICATION", "COMMUNICATION", "TWILIO", "twilio_voice", "Programmable voice provider adapter slot.", ["voice", "callbacks", "recording"], False, 20),
    ("EXOTEL", "Exotel", "COMMUNICATION", "COMMUNICATION", "EXOTEL", "exotel_voice", "India-focused cloud telephony adapter slot.", ["voice", "sms", "callbacks"], False, 30),
    ("RAZORPAY", "Razorpay", "PAYMENTS", "CUSTOM", "RAZORPAY", "razorpay", "Payment collection and settlement integration.", ["payments", "refunds", "webhooks"], True, 40),
    ("STRIPE", "Stripe", "PAYMENTS", "CUSTOM", "STRIPE", "stripe", "Global payment collection adapter slot.", ["payments", "refunds", "webhooks"], False, 50),
    ("TALLY", "Tally", "ACCOUNTING", "ACCOUNTING", "TALLY", "tally", "Accounting export/import and reconciliation adapter slot.", ["ledgers", "invoices", "payments"], True, 60),
    ("ZOHO_BOOKS", "Zoho Books", "ACCOUNTING", "ACCOUNTING", "ZOHO_BOOKS", "zoho_books", "Accounting connector slot for books, invoices and payments.", ["invoices", "payments", "contacts"], False, 70),
    ("QUICKBOOKS", "QuickBooks", "ACCOUNTING", "ACCOUNTING", "QUICKBOOKS", "quickbooks", "Accounting connector slot for global tenants.", ["invoices", "payments", "vendors"], False, 80),
    ("XERO", "Xero", "ACCOUNTING", "ACCOUNTING", "XERO", "xero", "Accounting connector slot for supported international tenants.", ["invoices", "payments", "vendors"], False, 90),
    ("AWS_S3", "Amazon S3", "STORAGE", "STORAGE", "AWS_S3", "aws_s3", "Private object storage connector slot.", ["documents", "recordings", "exports"], True, 100),
    ("AZURE_BLOB", "Azure Blob Storage", "STORAGE", "STORAGE", "AZURE_BLOB", "azure_blob", "Enterprise object storage connector slot.", ["documents", "exports"], False, 110),
    ("GOOGLE_DRIVE", "Google Drive", "STORAGE", "STORAGE", "GOOGLE_DRIVE", "google_drive", "User-governed document connector slot.", ["documents", "folders"], False, 120),
    ("ONEDRIVE", "Microsoft OneDrive", "STORAGE", "STORAGE", "ONEDRIVE", "onedrive", "Microsoft document connector slot.", ["documents", "folders"], False, 130),
    ("MICROSOFT_ENTRA", "Microsoft Entra ID", "IDENTITY", "IDENTITY", "MICROSOFT_ENTRA", "entra_oidc", "Enterprise identity and SSO adapter slot.", ["oidc", "sso", "provisioning"], True, 140),
    ("GOOGLE_IDENTITY", "Google Identity", "IDENTITY", "IDENTITY", "GOOGLE_IDENTITY", "google_oidc", "Google OIDC/SSO adapter slot.", ["oidc", "sso"], False, 150),
    ("AUTODESK", "Autodesk Platform Services", "DESIGN", "CUSTOM", "AUTODESK", "autodesk", "Design/BIM file and model integration slot.", ["models", "documents", "viewer"], True, 160),
    ("BIM360", "Autodesk BIM 360", "DESIGN", "CUSTOM", "BIM360", "bim360", "Project document/BIM connector slot.", ["documents", "issues", "models"], False, 170),
    ("CUSTOM_REST", "Custom REST API", "AUTOMATION", "CUSTOM", "CUSTOM_REST", "rest", "Tenant-controlled REST connector using governed API credentials.", ["api", "mappings", "sync"], True, 180),
    ("WEBHOOKS", "Webhooks", "AUTOMATION", "CUSTOM", "WEBHOOKS", "webhook", "Outbound/inbound business-event integration foundation.", ["events", "webhooks", "retries"], True, 190),
]


def seed_catalog(apps, schema_editor):
    Catalog = apps.get_model("integration", "IntegrationProviderCatalog")
    for code, name, category, connector_type, provider_code, adapter_code, description, capabilities, recommended, sort_order in PROVIDERS:
        Catalog.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "category": category,
                "connector_type": connector_type,
                "provider_code": provider_code,
                "adapter_code": adapter_code,
                "description": description,
                "capabilities": capabilities,
                "configuration_schema": {},
                "docs_url": "",
                "recommended": recommended,
                "is_active": True,
                "sort_order": sort_order,
            },
        )


def remove_catalog(apps, schema_editor):
    apps.get_model("integration", "IntegrationProviderCatalog").objects.filter(
        code__in=[item[0] for item in PROVIDERS]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("integration", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="IntegrationProviderCatalog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=100, unique=True)),
                ("name", models.CharField(max_length=160)),
                ("category", models.CharField(choices=[("COMMUNICATION", "Communication"), ("ACCOUNTING", "Accounting"), ("PAYMENTS", "Payments"), ("STORAGE", "Files & storage"), ("IDENTITY", "Identity"), ("DESIGN", "Design & BIM"), ("AUTOMATION", "Automation & API"), ("ANALYTICS", "Analytics")], max_length=30)),
                ("connector_type", models.CharField(choices=[("ACCOUNTING", "Accounting"), ("IDENTITY", "Identity"), ("STORAGE", "Storage"), ("COMMUNICATION", "Communication"), ("ANALYTICS", "Analytics"), ("CUSTOM", "Custom")], max_length=30)),
                ("provider_code", models.CharField(max_length=100, unique=True)),
                ("adapter_code", models.CharField(blank=True, max_length=120)),
                ("description", models.CharField(max_length=500)),
                ("capabilities", models.JSONField(default=list)),
                ("configuration_schema", models.JSONField(default=dict)),
                ("docs_url", models.URLField(blank=True, max_length=500)),
                ("recommended", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=100)),
            ],
            options={
                "db_table": "integration_provider_catalog",
                "ordering": ["sort_order", "category", "name"],
                "indexes": [models.Index(fields=["is_active", "category", "sort_order"], name="int_catalog_active_idx")],
            },
        ),
        migrations.RunPython(seed_catalog, remove_catalog),
    ]
