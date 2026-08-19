from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("projects", "0001_initial")]

    operations = [
        migrations.AddConstraint(
            model_name="project",
            constraint=models.UniqueConstraint(
                fields=("company", "opportunity_public_id"),
                condition=models.Q(opportunity_public_id__isnull=False),
                name="prj_company_opportunity_uq",
            ),
        ),
    ]
