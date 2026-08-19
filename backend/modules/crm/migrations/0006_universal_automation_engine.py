from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [("crm", "0005_universal_contact_center")]

    operations = [
        migrations.CreateModel(
            name="CrmAutomationRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=80)),
                ("name", models.CharField(max_length=180)),
                ("description", models.CharField(blank=True, max_length=500)),
                ("trigger_code", models.CharField(choices=[("contact.created", "Contact created"), ("lead.created", "Lead created"), ("lead.stage_changed", "Lead stage changed"), ("opportunity.created", "Opportunity created"), ("opportunity.stage_changed", "Opportunity stage changed"), ("activity.completed", "Activity completed")], max_length=50)),
                ("condition_tree", models.JSONField(blank=True, default=dict)),
                ("actions", models.JSONField(blank=True, default=list)),
                ("priority", models.PositiveIntegerField(default=100)),
                ("stop_on_match", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("last_triggered_at", models.DateTimeField(blank=True, null=True)),
                ("version", models.PositiveBigIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="tenant.company")),
            ],
            options={"db_table": "crm_automation_rule", "ordering": ["priority", "name"]},
        ),
        migrations.CreateModel(
            name="CrmAutomationExecution",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("trigger_code", models.CharField(max_length=50)),
                ("entity_type", models.CharField(max_length=40)),
                ("entity_public_id", models.UUIDField()),
                ("entity_version", models.PositiveBigIntegerField(default=1)),
                ("event_key", models.CharField(max_length=220)),
                ("status", models.CharField(choices=[("running", "Running"), ("succeeded", "Succeeded"), ("skipped", "Skipped"), ("failed", "Failed")], max_length=20)),
                ("matched", models.BooleanField(default=False)),
                ("trigger_payload", models.JSONField(blank=True, default=dict)),
                ("action_results", models.JSONField(blank=True, default=list)),
                ("error_code", models.CharField(blank=True, max_length=80)),
                ("error_message", models.CharField(blank=True, max_length=1000)),
                ("actor_user_public_id", models.UUIDField(blank=True, null=True)),
                ("actor_membership_public_id", models.UUIDField(blank=True, null=True)),
                ("started_at", models.DateTimeField()),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="tenant.company")),
                ("rule", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="executions", to="crm.crmautomationrule")),
            ],
            options={"db_table": "crm_automation_execution", "ordering": ["-started_at"]},
        ),
        migrations.AddConstraint(
            model_name="crmautomationrule",
            constraint=models.UniqueConstraint(fields=("company", "code"), name="crm_auto_rule_code_uq"),
        ),
        migrations.AddIndex(
            model_name="crmautomationrule",
            index=models.Index(fields=["company", "trigger_code", "is_active", "priority"], name="crm_auto_rule_trigger_idx"),
        ),
        migrations.AddConstraint(
            model_name="crmautomationexecution",
            constraint=models.UniqueConstraint(fields=("company", "rule", "event_key"), name="crm_auto_exec_event_uq"),
        ),
        migrations.AddIndex(
            model_name="crmautomationexecution",
            index=models.Index(fields=["company", "status", "started_at"], name="crm_auto_exec_status_idx"),
        ),
        migrations.AddIndex(
            model_name="crmautomationexecution",
            index=models.Index(fields=["company", "entity_type", "entity_public_id"], name="crm_auto_exec_entity_idx"),
        ),
    ]
