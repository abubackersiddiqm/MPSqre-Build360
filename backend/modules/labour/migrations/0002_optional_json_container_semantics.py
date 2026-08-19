from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("labour", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="workerprofile",
            name="skill_codes",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
