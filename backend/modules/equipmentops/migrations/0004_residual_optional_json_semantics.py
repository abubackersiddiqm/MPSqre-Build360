from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("equipmentops", "0003_optional_json_container_semantics"),
    ]

    operations = [
        migrations.AlterField(
            model_name="equipmentasset",
            name="metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name="equipmentapproval",
            name="metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
