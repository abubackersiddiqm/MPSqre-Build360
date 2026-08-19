import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [("tenant", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="SupplyStage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("entity_type", models.CharField(choices=[("vendor","Vendor"),("purchase_request","Purchase request"),("rfq","Request for quotation"),("quote","Vendor quote"),("purchase_order","Purchase order"),("receipt","Goods receipt")], max_length=40)),
                ("code", models.CharField(max_length=50)),
                ("name", models.CharField(max_length=120)),
                ("outcome", models.CharField(choices=[("open","Open"),("review","Review"),("approved","Approved"),("issued","Issued"),("complete","Complete"),("rejected","Rejected"),("cancelled","Cancelled")], default="open", max_length=20)),
                ("sort_order", models.PositiveIntegerField(default=100)),
                ("allowed_next_codes", models.JSONField(default=list)),
                ("is_initial", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("effective_from", models.DateTimeField()),
                ("effective_to", models.DateTimeField(blank=True, null=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="tenant.company")),
            ],
            options={"db_table":"vendor_supply_stage","ordering":["entity_type","sort_order","code"],"indexes":[models.Index(fields=["company","entity_type","is_active"],name="supply_stage_lookup_idx")],"constraints":[models.UniqueConstraint(fields=("company","entity_type","code"),name="supply_stage_code_uniq"),models.UniqueConstraint(condition=models.Q(("is_initial",True)),fields=("company","entity_type"),name="supply_initial_stage_uniq"),models.CheckConstraint(condition=models.Q(("effective_to__isnull",True),models.Q(("effective_to__gt",models.F("effective_from"))),_connector="OR"),name="supply_stage_range_valid")]},
        ),
        migrations.CreateModel(
            name="VendorProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),("public_id",models.UUIDField(default=uuid.uuid4,editable=False,unique=True)),("created_at",models.DateTimeField(auto_now_add=True,editable=False)),("updated_at",models.DateTimeField(auto_now=True)),
                ("code",models.CharField(max_length=50)),("legal_name",models.CharField(max_length=250)),("display_name",models.CharField(max_length=250)),("categories",models.JSONField(default=list)),("service_regions",models.JSONField(default=list)),("tax_reference_masked",models.CharField(blank=True,max_length=80)),("primary_contact_name",models.CharField(blank=True,max_length=150)),("primary_contact_email",models.EmailField(blank=True,max_length=254)),("primary_contact_phone",models.CharField(blank=True,max_length=40)),("version",models.PositiveBigIntegerField(default=1)),("qualified_at",models.DateTimeField(blank=True,null=True)),("suspended_at",models.DateTimeField(blank=True,null=True)),("retired_at",models.DateTimeField(blank=True,null=True)),
                ("company",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to="tenant.company")),("stage",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="vendors",to="vendor.supplystage")),
            ],
            options={"db_table":"vendor_profile","indexes":[models.Index(fields=["company","stage","created_at"],name="vendor_stage_time_idx"),models.Index(fields=["company","display_name"],name="vendor_name_lookup_idx")],"constraints":[models.UniqueConstraint(fields=("company","code"),name="vendor_company_code_uniq")]},
        ),
        migrations.CreateModel(
            name="VendorQualification",
            fields=[
                ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("public_id",models.UUIDField(default=uuid.uuid4,editable=False,unique=True)),("created_at",models.DateTimeField(auto_now_add=True,editable=False)),("updated_at",models.DateTimeField(auto_now=True)),("checklist_version",models.PositiveIntegerField(default=1)),("score",models.DecimalField(decimal_places=2,default=0,max_digits=5)),("decision",models.CharField(choices=[("pending","Pending"),("approved","Approved"),("rejected","Rejected")],default="pending",max_length=20)),("notes",models.TextField(blank=True)),("decided_by_public_id",models.UUIDField(blank=True,null=True)),("decided_at",models.DateTimeField(blank=True,null=True)),("expires_at",models.DateTimeField(blank=True,null=True)),
                ("company",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to="tenant.company")),("vendor",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="qualifications",to="vendor.vendorprofile")),
            ],
            options={"db_table":"vendor_qualification","ordering":["-created_at"],"indexes":[models.Index(fields=["company","vendor","decision"],name="vendor_qual_lookup_idx")]},
        ),
    ]
