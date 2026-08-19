from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("pilotops", "0002_optional_json_container_semantics"),
    ]

    operations = [
        migrations.AlterField(
            model_name="goliveplan",
            name="cutover_steps",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
