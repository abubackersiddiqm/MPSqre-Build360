from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("crm", "0004_universal_crm_foundation"),
    ]

    operations = [
        migrations.AddField(
            model_name="activity",
            name="contact",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="activities",
                to="crm.contact",
            ),
        ),
        migrations.AddField(
            model_name="activity",
            name="direction",
            field=models.CharField(
                choices=[
                    ("internal", "Internal"),
                    ("outbound", "Outbound"),
                    ("inbound", "Inbound"),
                ],
                default="internal",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="activity",
            name="outcome_code",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="activity",
            name="duration_seconds",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="activity",
            name="channel_metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.RemoveConstraint(
            model_name="activity",
            name="crm_activity_parent_required",
        ),
        migrations.AddConstraint(
            model_name="activity",
            constraint=models.CheckConstraint(
                condition=models.Q(customer__isnull=False)
                | models.Q(contact__isnull=False)
                | models.Q(lead__isnull=False)
                | models.Q(opportunity__isnull=False),
                name="crm_activity_parent_req_v2",
            ),
        ),
        migrations.AddIndex(
            model_name="activity",
            index=models.Index(
                fields=["company", "contact", "created_at"],
                name="crm_activity_contact_idx",
            ),
        ),
    ]
