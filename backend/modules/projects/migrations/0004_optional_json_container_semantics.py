from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0003_project_location_optional"),
    ]

    operations = [
        migrations.AlterField(
            model_name="projecttask",
            name="dependencies",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
