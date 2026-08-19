import django.db.models.deletion
import uuid
from django.db import migrations, models


DEFAULT_TERMINOLOGY = {
    "customer": "Customer",
    "contact": "Contact",
    "lead": "Lead",
    "opportunity": "Opportunity",
    "pipeline": "Pipeline",
    "quote": "Quote",
}

COMMON_SOURCES = [
    ("manual", "Manual entry", "manual"),
    ("website", "Website", "website"),
    ("phone", "Phone call", "phone"),
    ("whatsapp", "WhatsApp", "whatsapp"),
    ("email", "Email", "email"),
    ("referral", "Referral", "referral"),
    ("partner", "Partner", "partner"),
    ("event", "Event / expo", "event"),
    ("meta_ads", "Meta Ads", "ads"),
    ("google_ads", "Google Ads", "ads"),
    ("import", "Import", "import"),
    ("api", "API / integration", "api"),
]


def seed_existing_crm(apps, schema_editor):
    PipelineStage = apps.get_model("crm", "PipelineStage")
    CrmPipeline = apps.get_model("crm", "CrmPipeline")
    CrmTenantProfile = apps.get_model("crm", "CrmTenantProfile")
    CrmLeadSource = apps.get_model("crm", "CrmLeadSource")

    company_ids = list(
        PipelineStage.objects.order_by().values_list("company_id", flat=True).distinct()
    )
    for company_id in company_ids:
        CrmTenantProfile.objects.get_or_create(
            company_id=company_id,
            defaults={"industry_code": "general", "terminology": DEFAULT_TERMINOLOGY},
        )
        for entity_type, code, name in (
            ("lead", "default-lead", "Lead Pipeline"),
            ("opportunity", "default-opportunity", "Sales Pipeline"),
        ):
            pipeline, _ = CrmPipeline.objects.get_or_create(
                company_id=company_id,
                entity_type=entity_type,
                code=code,
                defaults={
                    "name": name,
                    "sort_order": 10,
                    "is_default": True,
                    "is_active": True,
                    "source_pack_code": "general",
                },
            )
            CrmPipeline.objects.filter(
                company_id=company_id,
                entity_type=entity_type,
                is_default=True,
            ).exclude(pk=pipeline.pk).update(is_default=False)
            PipelineStage.objects.filter(
                company_id=company_id,
                entity_type=entity_type,
                pipeline__isnull=True,
            ).update(pipeline=pipeline)
        if not CrmLeadSource.objects.filter(company_id=company_id).exists():
            for index, (code, name, channel_type) in enumerate(COMMON_SOURCES, start=1):
                CrmLeadSource.objects.create(
                    company_id=company_id,
                    code=code,
                    name=name,
                    channel_type=channel_type,
                    sort_order=index * 10,
                    source_pack_code="general",
                )


class Migration(migrations.Migration):
    dependencies = [
        ("crm", "0003_lead_logbook_foundation"),
    ]

    operations = [
        migrations.CreateModel(
            name="CrmTenantProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("industry_code", models.CharField(choices=[("general", "General business"), ("construction", "Construction"), ("real_estate", "Real estate"), ("interior", "Interior design"), ("automobile", "Automobile"), ("financial_services", "Financial services"), ("manufacturing", "Manufacturing"), ("professional_services", "Professional services"), ("other", "Other / custom")], default="general", max_length=80)),
                ("terminology", models.JSONField(blank=True, default=dict)),
                ("settings", models.JSONField(blank=True, default=dict)),
                ("version", models.PositiveBigIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="tenant.company")),
            ],
            options={"db_table": "crm_tenant_profile"},
        ),
        migrations.AddConstraint(
            model_name="crmtenantprofile",
            constraint=models.UniqueConstraint(fields=("company",), name="crm_profile_company_uq"),
        ),
        migrations.CreateModel(
            name="CrmPipeline",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("entity_type", models.CharField(choices=[("lead", "Lead"), ("opportunity", "Opportunity")], max_length=30)),
                ("code", models.CharField(max_length=80)),
                ("name", models.CharField(max_length=160)),
                ("description", models.CharField(blank=True, max_length=500)),
                ("sort_order", models.PositiveIntegerField(default=100)),
                ("is_default", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("source_pack_code", models.CharField(blank=True, max_length=80)),
                ("version", models.PositiveBigIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="tenant.company")),
            ],
            options={"db_table": "crm_pipeline", "ordering": ["entity_type", "sort_order", "name"]},
        ),
        migrations.AddConstraint(
            model_name="crmpipeline",
            constraint=models.UniqueConstraint(fields=("company", "entity_type", "code"), name="crm_pipeline_company_code_uq"),
        ),
        migrations.AddConstraint(
            model_name="crmpipeline",
            constraint=models.UniqueConstraint(condition=models.Q(is_active=True, is_default=True), fields=("company", "entity_type"), name="crm_pipeline_default_uq"),
        ),
        migrations.AddIndex(
            model_name="crmpipeline",
            index=models.Index(fields=["company", "entity_type", "is_active", "sort_order"], name="crm_pipeline_active_idx"),
        ),
        migrations.CreateModel(
            name="CrmLeadSource",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=80)),
                ("name", models.CharField(max_length=160)),
                ("channel_type", models.CharField(choices=[("manual", "Manual"), ("website", "Website"), ("ads", "Ads"), ("social", "Social"), ("phone", "Phone"), ("whatsapp", "WhatsApp"), ("email", "Email"), ("referral", "Referral"), ("partner", "Partner"), ("event", "Event"), ("import", "Import"), ("api", "API"), ("other", "Other")], default="manual", max_length=30)),
                ("sort_order", models.PositiveIntegerField(default=100)),
                ("is_active", models.BooleanField(default=True)),
                ("source_pack_code", models.CharField(blank=True, max_length=80)),
                ("version", models.PositiveBigIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="tenant.company")),
            ],
            options={"db_table": "crm_lead_source", "ordering": ["sort_order", "name"]},
        ),
        migrations.AddConstraint(
            model_name="crmleadsource",
            constraint=models.UniqueConstraint(fields=("company", "code"), name="crm_source_company_code_uq"),
        ),
        migrations.AddIndex(
            model_name="crmleadsource",
            index=models.Index(fields=["company", "is_active", "sort_order"], name="crm_source_active_idx"),
        ),
        migrations.CreateModel(
            name="CrmCustomFieldDefinition",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("entity_type", models.CharField(choices=[("customer", "Customer / account"), ("contact", "Contact"), ("lead", "Lead"), ("opportunity", "Opportunity")], max_length=30)),
                ("code", models.CharField(max_length=80)),
                ("label", models.CharField(max_length=160)),
                ("field_type", models.CharField(choices=[("text", "Text"), ("long_text", "Long text"), ("number", "Number"), ("currency", "Currency"), ("percent", "Percentage"), ("date", "Date"), ("datetime", "Date & time"), ("select", "Dropdown"), ("multiselect", "Multi-select"), ("boolean", "Yes / no"), ("email", "Email"), ("phone", "Phone"), ("url", "URL"), ("user", "User"), ("lookup", "Lookup"), ("file", "File"), ("formula", "Formula")], max_length=30)),
                ("help_text", models.CharField(blank=True, max_length=500)),
                ("is_required", models.BooleanField(default=False)),
                ("options", models.JSONField(blank=True, default=list)),
                ("validation", models.JSONField(blank=True, default=dict)),
                ("sort_order", models.PositiveIntegerField(default=100)),
                ("is_active", models.BooleanField(default=True)),
                ("source_pack_code", models.CharField(blank=True, max_length=80)),
                ("version", models.PositiveBigIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="tenant.company")),
            ],
            options={"db_table": "crm_custom_field_definition", "ordering": ["entity_type", "sort_order", "label"]},
        ),
        migrations.AddConstraint(
            model_name="crmcustomfielddefinition",
            constraint=models.UniqueConstraint(fields=("company", "entity_type", "code"), name="crm_custom_field_code_uq"),
        ),
        migrations.AddIndex(
            model_name="crmcustomfielddefinition",
            index=models.Index(fields=["company", "entity_type", "is_active", "sort_order"], name="crm_custom_field_active_idx"),
        ),
        migrations.AddField(
            model_name="pipelinestage",
            name="pipeline",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="stages", to="crm.crmpipeline"),
        ),
        migrations.RemoveConstraint(
            model_name="pipelinestage",
            name="crm_stage_company_code_uq",
        ),
        migrations.AddConstraint(
            model_name="pipelinestage",
            constraint=models.UniqueConstraint(
                fields=("company", "pipeline", "code"),
                name="crm_stage_pipeline_code_uq",
            ),
        ),
        migrations.AddField(model_name="customer", name="custom_fields", field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name="lead", name="custom_fields", field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name="opportunity", name="custom_fields", field=models.JSONField(blank=True, default=dict)),
        migrations.RunPython(seed_existing_crm, migrations.RunPython.noop),
    ]
