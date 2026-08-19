from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("communication", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="communicationattempt",
            name="response_metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
