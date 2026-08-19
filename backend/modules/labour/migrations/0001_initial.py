import uuid
from decimal import Decimal
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [("fieldops", "0001_initial"), ("projects", "0001_initial"), ("tenant", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="WorkerProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)), ("created_at", models.DateTimeField(auto_now_add=True, editable=False)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=80)), ("display_name", models.CharField(max_length=200)), ("worker_type", models.CharField(choices=[("employee", "Employee"), ("contract", "Contract labour"), ("subcontract", "Subcontract labour")], max_length=30)), ("employee_public_id", models.UUIDField(blank=True, null=True)), ("vendor_public_id", models.UUIDField(blank=True, null=True)), ("trade_code", models.CharField(max_length=80)), ("skill_codes", models.JSONField(default=list)), ("daily_rate", models.DecimalField(decimal_places=4, default=Decimal("0"), max_digits=19)), ("currency", models.CharField(max_length=3)), ("joined_on", models.DateField()), ("exited_on", models.DateField(blank=True, null=True)), ("is_active", models.BooleanField(default=True)), ("version", models.PositiveBigIntegerField(default=1)), ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="tenant.company")),
            ],
            options={"db_table":"labour_worker_profile","constraints":[models.UniqueConstraint(fields=("company","code"),name="lab_worker_code_uq"),models.CheckConstraint(condition=models.Q(("daily_rate__gte",0)),name="lab_worker_rate_valid"),models.CheckConstraint(condition=models.Q(("exited_on__isnull",True),("exited_on__gte",models.F("joined_on")),_connector="OR"),name="lab_worker_dates_valid")],"indexes":[models.Index(fields=["company","trade_code","is_active"],name="lab_worker_trade_idx")]},
        ),
        migrations.CreateModel(
            name="WorkforceAllocation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)), ("created_at", models.DateTimeField(auto_now_add=True, editable=False)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("allocated_from", models.DateField()), ("allocated_to", models.DateField(blank=True, null=True)), ("planned_hours", models.DecimalField(decimal_places=2, default=Decimal("8"), max_digits=10)), ("supervisor_membership_public_id", models.UUIDField(blank=True, null=True)), ("notes", models.TextField(blank=True)), ("version", models.PositiveBigIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="tenant.company")), ("project", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="labour_allocations", to="projects.project")), ("stage", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="labour_allocations", to="fieldops.fieldstage")), ("task", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="labour_allocations", to="projects.projecttask")), ("worker", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="allocations", to="labour.workerprofile")),
            ],
            options={"db_table":"labour_workforce_allocation","constraints":[models.CheckConstraint(condition=models.Q(("allocated_to__isnull",True),("allocated_to__gte",models.F("allocated_from")),_connector="OR"),name="lab_alloc_dates_valid"),models.CheckConstraint(condition=models.Q(("planned_hours__gt",0)),name="lab_alloc_hours_valid")],"indexes":[models.Index(fields=["company","project","stage"],name="lab_alloc_project_idx"),models.Index(fields=["company","worker","allocated_from"],name="lab_alloc_worker_idx")]},
        ),
        migrations.CreateModel(
            name="AttendanceRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)), ("created_at", models.DateTimeField(auto_now_add=True, editable=False)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("work_date", models.DateField()), ("clock_in", models.DateTimeField(blank=True, null=True)), ("clock_out", models.DateTimeField(blank=True, null=True)), ("regular_hours", models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=8)), ("overtime_hours", models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=8)), ("source", models.CharField(choices=[("web","Web"),("mobile","Mobile"),("offline","Offline"),("import","Import")],default="web",max_length=20)), ("operation_id", models.UUIDField(blank=True, null=True)), ("evidence_file_public_ids", models.JSONField(default=list)), ("approved_by_public_id", models.UUIDField(blank=True, null=True)), ("approved_at", models.DateTimeField(blank=True, null=True)), ("correction_reason", models.TextField(blank=True)), ("version", models.PositiveBigIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to="tenant.company")), ("project", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="attendance",to="projects.project")), ("stage", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="attendance_records",to="fieldops.fieldstage")), ("worker", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="attendance",to="labour.workerprofile")),
            ],
            options={"db_table":"labour_attendance_record","constraints":[models.UniqueConstraint(fields=("company","worker","project","work_date"),name="lab_attendance_day_uq"),models.UniqueConstraint(condition=models.Q(("operation_id__isnull",False)),fields=("company","operation_id"),name="lab_attendance_operation_uq"),models.CheckConstraint(condition=models.Q(("clock_out__isnull",True),("clock_in__isnull",True),("clock_out__gte",models.F("clock_in")),_connector="OR"),name="lab_attendance_time_valid"),models.CheckConstraint(condition=models.Q(("regular_hours__gte",0),("overtime_hours__gte",0)),name="lab_attendance_hours_valid")],"indexes":[models.Index(fields=["company","project","work_date"],name="lab_attendance_project_idx"),models.Index(fields=["company","worker","work_date"],name="lab_attendance_worker_idx")]},
        ),
    ]
