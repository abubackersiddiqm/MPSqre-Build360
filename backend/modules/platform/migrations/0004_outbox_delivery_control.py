from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("build360_platform", "0003_audit_event_append_only"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="businesseventoutbox",
            name="outbox_publish_due_idx",
        ),
        migrations.AddField(
            model_name="businesseventoutbox",
            name="dead_lettered_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="businesseventoutbox",
            name="last_error",
            field=models.CharField(blank=True, max_length=1000),
        ),
        migrations.AddField(
            model_name="businesseventoutbox",
            name="lock_token",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="businesseventoutbox",
            name="locked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name="businesseventoutbox",
            index=models.Index(
                fields=["published_at", "dead_lettered_at", "next_attempt_at"],
                name="outbox_publish_due_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="businesseventoutbox",
            index=models.Index(
                fields=["lock_token", "locked_at"],
                name="outbox_claim_lookup_idx",
            ),
        ),
    ]
