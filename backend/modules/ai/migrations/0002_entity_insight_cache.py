import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ai", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AIEntityInsight",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("subject_type", models.CharField(max_length=100)),
                ("subject_public_id", models.UUIDField()),
                ("insight_code", models.CharField(max_length=100)),
                ("source_digest", models.CharField(max_length=64)),
                ("output_payload", models.JSONField(default=dict)),
                ("override_payload", models.JSONField(default=dict)),
                ("generated_at", models.DateTimeField()),
                ("overridden_by_public_id", models.UUIDField(blank=True, null=True)),
                ("overridden_at", models.DateTimeField(blank=True, null=True)),
                ("version", models.PositiveBigIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="tenant.company")),
                ("interaction", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="entity_insights", to="ai.aiinteraction")),
            ],
            options={
                "db_table": "ai_entity_insight",
                "indexes": [
                    models.Index(fields=["company", "subject_type", "subject_public_id"], name="ai_insight_subject_idx"),
                    models.Index(fields=["company", "insight_code", "generated_at"], name="ai_insight_code_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("company", "subject_type", "subject_public_id", "insight_code"),
                        name="ai_insight_subject_uq",
                    )
                ],
            },
        ),
    ]
