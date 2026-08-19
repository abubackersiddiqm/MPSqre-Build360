import uuid
from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("finance", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="CommercialAdjustment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("posting_number", models.CharField(max_length=80)),
                ("entry_type", models.CharField(choices=[("commitment", "Commitment"), ("actual", "Actual"), ("accrual", "Accrual"), ("forecast", "Forecast")], max_length=30)),
                ("cost_code", models.CharField(max_length=80)),
                ("amount", models.DecimalField(decimal_places=4, max_digits=20)),
                ("currency", models.CharField(max_length=3)),
                ("description", models.CharField(max_length=500)),
                ("created_by_public_id", models.UUIDField()),
                ("posted_at", models.DateTimeField()),
                ("version", models.PositiveBigIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="tenant.company")),
                ("period", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="adjustments", to="finance.financialperiod")),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="commercial_adjustments", to="projects.project")),
            ],
            options={
                "db_table": "finance_commercial_adjustment",
                "constraints": [
                    models.UniqueConstraint(fields=("company", "posting_number"), name="fin_adjustment_number_uq"),
                    models.CheckConstraint(condition=models.Q(("amount", 0), _negated=True), name="fin_adjustment_nonzero"),
                ],
                "indexes": [models.Index(fields=["company", "project", "period", "entry_type"], name="fin_adjustment_lookup_idx")],
            },
        )
    ]
