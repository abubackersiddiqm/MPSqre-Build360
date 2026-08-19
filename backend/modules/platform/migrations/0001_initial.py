import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="BusinessEventOutbox",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("company_public_id", models.UUIDField(blank=True, null=True)),
                ("aggregate_type", models.CharField(max_length=100)),
                ("aggregate_public_id", models.UUIDField()),
                ("aggregate_version", models.PositiveBigIntegerField()),
                ("event_type", models.CharField(max_length=200)),
                ("event_version", models.PositiveSmallIntegerField(default=1)),
                ("payload", models.JSONField(default=dict)),
                ("occurred_at", models.DateTimeField()),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("next_attempt_at", models.DateTimeField(blank=True, null=True)),
                ("correlation_id", models.UUIDField()),
                ("causation_id", models.UUIDField(blank=True, null=True)),
            ],
            options={
                "db_table": "platform_business_event_outbox",
                "indexes": [
                    models.Index(
                        fields=["published_at", "next_attempt_at"],
                        name="outbox_publish_due_idx",
                    ),
                    models.Index(
                        fields=[
                            "aggregate_type",
                            "aggregate_public_id",
                            "aggregate_version",
                        ],
                        name="outbox_aggregate_order_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=(
                            "aggregate_type",
                            "aggregate_public_id",
                            "aggregate_version",
                            "event_type",
                            "event_version",
                        ),
                        name="outbox_unique_aggregate_fact",
                    )
                ],
            },
        )
    ]
