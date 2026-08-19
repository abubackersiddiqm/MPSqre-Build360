from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("crm", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="activity",
            name="location",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
