from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("workforceops", "0002_seed_permissions"),
    ]

    operations = [
        migrations.AlterField(
            model_name="workforceplan",
            name="metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name="workforceassignment",
            name="metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name="workforceapproval",
            name="metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
