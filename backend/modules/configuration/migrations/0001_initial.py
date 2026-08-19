import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("tenant", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ConfigurationDefinition",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=150, unique=True)),
                ("name", models.CharField(max_length=200)),
                ("description", models.CharField(blank=True, max_length=500)),
                ("schema", models.JSONField(default=dict)),
                ("data_class", models.CharField(blank=True, max_length=100)),
                ("is_secret", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"db_table": "configuration_definition"},
        ),
        migrations.CreateModel(
            name="ConfigurationVersion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("version", models.PositiveIntegerField()),
                ("status", models.CharField(choices=[("DRAFT", "Draft"), ("PUBLISHED", "Published"), ("RETIRED", "Retired")], default="DRAFT", max_length=20)),
                ("payload", models.JSONField(default=dict)),
                ("effective_from", models.DateTimeField()),
                ("effective_to", models.DateTimeField(blank=True, null=True)),
                ("created_by_public_id", models.UUIDField()),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("checksum", models.CharField(blank=True, max_length=64)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="configuration_versions", to="tenant.company")),
                ("definition", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="versions", to="configuration.configurationdefinition")),
            ],
            options={
                "db_table": "configuration_version",
                "indexes": [models.Index(fields=["company", "definition", "status", "effective_from"], name="cfg_active_lookup_idx")],
                "constraints": [
                    models.UniqueConstraint(fields=("company", "definition", "version"), name="configuration_company_definition_version_unique"),
                    models.CheckConstraint(condition=models.Q(("effective_to__isnull", True), ("effective_to__gt", models.F("effective_from")), _connector="OR"), name="configuration_effective_range_valid"),
                    models.CheckConstraint(condition=models.Q(models.Q(("published_at__isnull", True), ("status", "DRAFT")), models.Q(("published_at__isnull", False), ("status__in", ["PUBLISHED", "RETIRED"])), _connector="OR"), name="configuration_publish_state_valid"),
                ],
            },
        ),
    ]
