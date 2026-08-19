from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("crm", "0007_relationship_360_indexes"),
    ]

    operations = [
        migrations.AddField(
            model_name="contact",
            name="alternate_phone_ciphertext",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="contact",
            name="alternate_phone_blind_index",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="contact",
            name="alternate_phone_last_four",
            field=models.CharField(blank=True, max_length=4),
        ),
        migrations.AddIndex(
            model_name="contact",
            index=models.Index(
                fields=["company", "alternate_phone_blind_index"],
                name="crm_contact_alt_phone_idx",
            ),
        ),
    ]
