from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("crm", "0006_universal_automation_engine"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="contact",
            index=models.Index(
                fields=["company", "is_active", "first_name", "last_name"],
                name="crm_contact_name_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="lead",
            index=models.Index(
                fields=["company", "primary_contact", "next_follow_up_at"],
                name="crm_lead_contact_follow_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="opportunity",
            index=models.Index(
                fields=["company", "primary_contact", "stage"],
                name="crm_opp_contact_stage_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="activity",
            index=models.Index(
                fields=["company", "contact", "status", "scheduled_for"],
                name="crm_act_contact_due_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="activity",
            index=models.Index(
                fields=["company", "contact", "status", "follow_up_at"],
                name="crm_act_contact_follow_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="lead",
            index=models.Index(
                fields=["company", "owner_membership_public_id", "next_follow_up_at"],
                name="crm_lead_owner_follow_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="activity",
            index=models.Index(
                fields=["company", "owner_membership_public_id", "follow_up_at"],
                name="crm_act_owner_follow_idx",
            ),
        ),
    ]
