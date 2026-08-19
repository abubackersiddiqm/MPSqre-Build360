import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("crm", "0002_alter_activity_location"),
    ]

    operations = [
        migrations.AddField(
            model_name="contact",
            name="address",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="contact",
            name="source_code",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="contact",
            name="tags",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="contact",
            name="notes",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="contact",
            name="custom_fields",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="contact",
            name="owner_membership_public_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name="contact",
            index=models.Index(
                fields=["company", "owner_membership_public_id", "is_active"],
                name="crm_contact_owner_idx",
            ),
        ),
        migrations.AlterField(
            model_name="activity",
            name="activity_type",
            field=models.CharField(
                choices=[
                    ("note", "Note"),
                    ("call", "Call"),
                    ("whatsapp", "WhatsApp"),
                    ("sms", "SMS"),
                    ("email", "Email"),
                    ("meeting", "Meeting"),
                    ("site_visit", "Site visit"),
                    ("follow_up", "Follow-up"),
                    ("voice_note", "Voice note"),
                    ("document", "Document"),
                    ("photo", "Photo"),
                    ("video", "Video"),
                    ("task", "Task"),
                    ("status_change", "Status change"),
                    ("assignment_change", "Assignment change"),
                ],
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="activity",
            name="follow_up_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="activity",
            name="priority",
            field=models.CharField(
                choices=[
                    ("low", "Low"),
                    ("normal", "Normal"),
                    ("high", "High"),
                    ("urgent", "Urgent"),
                ],
                default="normal",
                max_length=20,
            ),
        ),
        migrations.AddIndex(
            model_name="activity",
            index=models.Index(
                fields=["company", "priority", "scheduled_for"],
                name="crm_activity_priority_idx",
            ),
        ),
        migrations.CreateModel(
            name="ActivityAttachment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("file_object_public_id", models.UUIDField()),
                (
                    "attachment_kind",
                    models.CharField(
                        choices=[
                            ("document", "Document"),
                            ("photo", "Photo"),
                            ("video", "Video"),
                            ("audio", "Audio"),
                            ("other", "Other"),
                        ],
                        default="document",
                        max_length=30,
                    ),
                ),
                ("caption", models.CharField(blank=True, max_length=500)),
                ("created_by_public_id", models.UUIDField()),
                (
                    "activity",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attachments",
                        to="crm.activity",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenant.company",
                    ),
                ),
            ],
            options={
                "db_table": "crm_activity_attachment",
            },
        ),
        migrations.AddConstraint(
            model_name="activityattachment",
            constraint=models.UniqueConstraint(
                fields=("company", "activity", "file_object_public_id"),
                name="crm_act_attach_file_uq",
            ),
        ),
        migrations.AddIndex(
            model_name="activityattachment",
            index=models.Index(
                fields=["company", "activity", "created_at"],
                name="crm_act_attach_activity_idx",
            ),
        ),
    ]
