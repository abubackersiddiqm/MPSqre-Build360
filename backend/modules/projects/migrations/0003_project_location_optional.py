from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("projects", "0002_project_opportunity_idempotency")]

    operations = [
        migrations.AlterField(
            model_name="project",
            name="location",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
