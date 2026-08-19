from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ai", "0002_entity_insight_cache"),
    ]

    operations = [
        migrations.AlterField(
            model_name="aimodelpolicy",
            name="allowed_tool_codes",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AlterField(
            model_name="aientityinsight",
            name="override_payload",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
