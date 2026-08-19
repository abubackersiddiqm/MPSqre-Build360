from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("reporting", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="reportrun",
            name="parameters",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
