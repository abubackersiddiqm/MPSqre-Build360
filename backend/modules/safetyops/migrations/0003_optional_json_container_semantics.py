from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("safetyops", "0002_seed_permissions"),
    ]

    operations = [
        migrations.AlterField(
            model_name="permittowork",
            name="conditions",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AlterField(
            model_name="permittowork",
            name="isolation_points",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
