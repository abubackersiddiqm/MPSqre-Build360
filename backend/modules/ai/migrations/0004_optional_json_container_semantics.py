from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ai", "0003_crm_ai_blank_json_semantics"),
    ]

    operations = [
        migrations.AlterField(
            model_name="aiinteraction",
            name="output_metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name="aiextractionjob",
            name="corrections",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name="aievaluationrun",
            name="failures",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
