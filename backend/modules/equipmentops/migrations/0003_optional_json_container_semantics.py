from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("equipmentops", "0002_seed_permissions"),
    ]

    operations = [
        migrations.AlterField(
            model_name="equipmentmeterreading",
            name="metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name="maintenanceworkorder",
            name="metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
