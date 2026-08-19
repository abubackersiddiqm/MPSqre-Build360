from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("vendor", "0001_initial")]

    operations = [
        migrations.RemoveConstraint(
            model_name="supplystage",
            name="supply_stage_range_valid",
        ),
        migrations.AddConstraint(
            model_name="supplystage",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("effective_to__isnull", True),
                    ("effective_to__gt", models.F("effective_from")),
                    _connector="OR",
                ),
                name="supply_stage_range_valid",
            ),
        ),
    ]
