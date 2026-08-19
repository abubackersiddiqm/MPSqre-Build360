from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("integration", "0004_mapping_transformations_blank"),
    ]

    operations = [
        migrations.AlterField(
            model_name="metaleadreceipt",
            name="field_names",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
