import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("communication", "0001_initial"),
        ("tenant", "0001_initial"),
    ]
    operations = [
        migrations.CreateModel(
            name="NotificationPreference",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user_public_id", models.UUIDField()),
                ("event_code", models.CharField(max_length=120)),
                ("channel", models.CharField(choices=[("in_app", "In-app"), ("email", "Email"), ("sms", "SMS"), ("whatsapp", "WhatsApp"), ("voice", "Voice")], max_length=20)),
                ("enabled", models.BooleanField(default=True)),
                ("digest_mode", models.CharField(choices=[("immediate", "Immediate"), ("daily", "Daily digest"), ("weekly", "Weekly digest"), ("muted", "Muted")], default="immediate", max_length=20)),
                ("quiet_hours_start", models.TimeField(blank=True, null=True)),
                ("quiet_hours_end", models.TimeField(blank=True, null=True)),
                ("version", models.PositiveBigIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="tenant.company")),
            ],
            options={
                "db_table": "notification_preference",
                "constraints": [models.UniqueConstraint(fields=("company", "user_public_id", "event_code", "channel"), name="not_pref_user_event_uq")],
                "indexes": [models.Index(fields=["company", "user_public_id", "enabled"], name="not_pref_user_active_idx")],
            },
        ),
        migrations.CreateModel(
            name="NotificationRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("event_code", models.CharField(max_length=120)),
                ("name", models.CharField(max_length=200)),
                ("default_title_template", models.CharField(max_length=250)),
                ("default_body_template", models.TextField()),
                ("severity", models.CharField(choices=[("info", "Information"), ("success", "Success"), ("warning", "Warning"), ("critical", "Critical")], default="info", max_length=20)),
                ("channels", models.JSONField(default=list)),
                ("is_active", models.BooleanField(default=True)),
                ("version", models.PositiveBigIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="tenant.company")),
            ],
            options={
                "db_table": "notification_rule",
                "constraints": [models.UniqueConstraint(fields=("company", "event_code"), name="not_rule_company_event_uq")],
                "indexes": [models.Index(fields=["company", "is_active", "event_code"], name="not_rule_active_idx")],
            },
        ),
        migrations.CreateModel(
            name="Notification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user_public_id", models.UUIDField()),
                ("event_code", models.CharField(max_length=120)),
                ("title", models.CharField(max_length=250)),
                ("body", models.TextField()),
                ("severity", models.CharField(choices=[("info", "Information"), ("success", "Success"), ("warning", "Warning"), ("critical", "Critical")], default="info", max_length=20)),
                ("action_path", models.CharField(blank=True, max_length=300)),
                ("source_type", models.CharField(blank=True, max_length=100)),
                ("source_public_id", models.UUIDField(blank=True, null=True)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="tenant.company")),
            ],
            options={
                "db_table": "notification_item",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["company", "user_public_id", "read_at", "created_at"], name="not_item_inbox_idx"),
                    models.Index(fields=["company", "event_code", "created_at"], name="not_item_event_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="NotificationDelivery",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("channel", models.CharField(choices=[("in_app", "In-app"), ("email", "Email"), ("sms", "SMS"), ("whatsapp", "WhatsApp"), ("voice", "Voice")], max_length=20)),
                ("status", models.CharField(choices=[("queued", "Queued"), ("sent", "Sent"), ("delivered", "Delivered"), ("failed", "Failed"), ("suppressed", "Suppressed")], max_length=20)),
                ("attempted_at", models.DateTimeField(blank=True, null=True)),
                ("delivered_at", models.DateTimeField(blank=True, null=True)),
                ("failure_code", models.CharField(blank=True, max_length=100)),
                ("communication_request", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="notification_deliveries", to="communication.communicationrequest")),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="tenant.company")),
                ("notification", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="deliveries", to="notifications.notification")),
            ],
            options={
                "db_table": "notification_delivery",
                "constraints": [models.UniqueConstraint(fields=("company", "notification", "channel"), name="not_delivery_channel_uq")],
                "indexes": [models.Index(fields=["company", "status", "attempted_at"], name="not_delivery_queue_idx")],
            },
        ),
    ]
