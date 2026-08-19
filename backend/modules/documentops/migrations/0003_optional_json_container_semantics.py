from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documentops", "0002_seed_permissions"),
    ]

    operations = [
        migrations.AlterField(
            model_name="controlleddocument",
            name="attributes",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
