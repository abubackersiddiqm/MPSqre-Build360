from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("workforceops", "0003_optional_json_container_semantics"),
    ]

    operations = [
        migrations.AlterField(
            model_name="workforcedemand",
            name="configuration",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
