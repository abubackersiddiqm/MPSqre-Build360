from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("labour", "0002_optional_json_container_semantics"),
    ]

    operations = [
        migrations.AlterField(
            model_name="attendancerecord",
            name="evidence_file_public_ids",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
