from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("pilotops", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="pilotchecklistitem",
            name="evidence",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
