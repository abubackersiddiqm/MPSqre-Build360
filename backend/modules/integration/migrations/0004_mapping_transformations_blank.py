from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("integration", "0003_meta_lead_ads"),
    ]

    operations = [
        migrations.AlterField(
            model_name="datamappingprofile",
            name="transformations",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
