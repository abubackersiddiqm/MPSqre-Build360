from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("qualityops", "0002_seed_permissions"),
    ]

    operations = [
        migrations.AlterField(
            model_name="inspectiontestplan",
            name="hold_points",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AlterField(
            model_name="inspectiontestplan",
            name="witness_points",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AlterField(
            model_name="inspectiontestplan",
            name="acceptance_criteria",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
