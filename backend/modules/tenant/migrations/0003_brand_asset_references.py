from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tenant", "0002_white_label_experience"),
    ]

    operations = [
        migrations.AddField(
            model_name="companybrandprofile",
            name="logo_file_public_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="companybrandprofile",
            name="compact_logo_file_public_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="companybrandprofile",
            name="favicon_file_public_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="companybrandprofile",
            name="login_background_file_public_id",
            field=models.UUIDField(blank=True, null=True),
        ),
    ]
