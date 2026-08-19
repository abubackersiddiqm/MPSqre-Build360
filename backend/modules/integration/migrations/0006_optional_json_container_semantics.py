from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("integration", "0005_meta_lead_receipt_field_names_blank"),
    ]

    operations = [
        migrations.AlterField(
            model_name="connectorprofile",
            name="public_config",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name="connectorprofile",
            name="allowed_data_classes",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AlterField(
            model_name="apiclientcredential",
            name="allowed_ip_ranges",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
