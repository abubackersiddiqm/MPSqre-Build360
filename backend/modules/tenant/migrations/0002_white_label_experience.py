from __future__ import annotations

import uuid
from django.db import migrations, models
import django.db.models.deletion


PERMISSIONS = (
    ("tenant.branding.read", "View company white-label branding and identity settings", "restricted"),
    ("tenant.branding.manage", "Manage company white-label branding and identity settings", "restricted"),
    ("tenant.domain.read", "View company platform and custom domains", "restricted"),
    ("tenant.domain.manage", "Manage company platform and custom domains", "restricted"),
)


def seed_brand_profiles_and_permissions(apps, schema_editor):
    Company = apps.get_model("tenant", "Company")
    CompanyBrandProfile = apps.get_model("tenant", "CompanyBrandProfile")
    Permission = apps.get_model("identity", "Permission")
    Role = apps.get_model("identity", "Role")
    RolePermission = apps.get_model("identity", "RolePermission")

    for company in Company.objects.all().iterator():
        CompanyBrandProfile.objects.get_or_create(
            company_id=company.id,
            defaults={
                "product_name": company.display_name,
                "tagline": "Construction Operating System",
                "primary_color": "#174D3C",
                "accent_color": "#0F766E",
                "sidebar_style": "LIGHT",
                "sender_name": company.display_name,
                "powered_by_build360": True,
                "version": 1,
            },
        )

    permissions = []
    for code, description, data_class in PERMISSIONS:
        permission, _ = Permission.objects.get_or_create(
            code=code,
            defaults={"description": description, "data_class": data_class},
        )
        permissions.append(permission)

    admin_roles = Role.objects.filter(retired_at__isnull=True).filter(
        models.Q(code__icontains="ADMIN") | models.Q(name__icontains="ADMINISTRATOR")
    )
    for role in admin_roles.iterator():
        for permission in permissions:
            RolePermission.objects.get_or_create(
                role_id=role.id,
                permission_id=permission.id,
            )


def remove_white_label_permissions(apps, schema_editor):
    Permission = apps.get_model("identity", "Permission")
    RolePermission = apps.get_model("identity", "RolePermission")
    codes = [code for code, _, _ in PERMISSIONS]
    permission_ids = list(Permission.objects.filter(code__in=codes).values_list("id", flat=True))
    if permission_ids:
        RolePermission.objects.filter(permission_id__in=permission_ids).delete()
        Permission.objects.filter(id__in=permission_ids).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("tenant", "0001_initial"),
        ("identity", "0019_phase20_peopleops_permissions"),
    ]

    operations = [
        migrations.CreateModel(
            name="CompanyBrandProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("product_name", models.CharField(blank=True, max_length=120)),
                ("tagline", models.CharField(blank=True, max_length=220)),
                ("logo_url", models.URLField(blank=True, max_length=1000)),
                ("compact_logo_url", models.URLField(blank=True, max_length=1000)),
                ("favicon_url", models.URLField(blank=True, max_length=1000)),
                ("login_background_url", models.URLField(blank=True, max_length=1000)),
                ("primary_color", models.CharField(default="#174D3C", max_length=7)),
                ("accent_color", models.CharField(default="#0F766E", max_length=7)),
                ("sidebar_style", models.CharField(choices=[("LIGHT", "Light"), ("DARK", "Dark"), ("BRAND", "Brand")], default="LIGHT", max_length=20)),
                ("sender_name", models.CharField(blank=True, max_length=160)),
                ("support_email", models.EmailField(blank=True, max_length=254)),
                ("document_footer", models.CharField(blank=True, max_length=500)),
                ("powered_by_build360", models.BooleanField(default=True)),
                ("updated_by_public_id", models.UUIDField(blank=True, null=True)),
                ("version", models.PositiveBigIntegerField(default=1)),
                ("company", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="brand_profile", to="tenant.company")),
            ],
            options={"db_table": "tenant_company_brand_profile"},
        ),
        migrations.CreateModel(
            name="TenantDomain",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("domain", models.CharField(max_length=253, unique=True)),
                ("domain_type", models.CharField(choices=[("PLATFORM_SUBDOMAIN", "Build360 subdomain"), ("CUSTOM_DOMAIN", "Custom domain")], max_length=30)),
                ("status", models.CharField(choices=[("PENDING", "Pending"), ("ACTIVE", "Active"), ("FAILED", "Failed"), ("SUSPENDED", "Suspended")], default="PENDING", max_length=20)),
                ("is_primary", models.BooleanField(default=False)),
                ("verification_token", models.CharField(blank=True, max_length=96)),
                ("verification_record_name", models.CharField(blank=True, max_length=300)),
                ("verification_record_value", models.CharField(blank=True, max_length=500)),
                ("expected_cname", models.CharField(blank=True, max_length=253)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("ssl_status", models.CharField(choices=[("NOT_APPLICABLE", "Not applicable"), ("PENDING", "Pending"), ("ACTIVE", "Active"), ("FAILED", "Failed")], default="PENDING", max_length=20)),
                ("activated_at", models.DateTimeField(blank=True, null=True)),
                ("suspended_at", models.DateTimeField(blank=True, null=True)),
                ("version", models.PositiveBigIntegerField(default=1)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="tenant_domains", to="tenant.company")),
            ],
            options={
                "db_table": "tenant_domain",
                "ordering": ["-is_primary", "domain"],
                "indexes": [models.Index(fields=["company", "status", "domain_type"], name="tenant_domain_status_idx")],
            },
        ),
        migrations.AddConstraint(
            model_name="tenantdomain",
            constraint=models.UniqueConstraint(
                condition=models.Q(is_primary=True),
                fields=("company",),
                name="tenant_one_primary_domain_uq",
            ),
        ),
        migrations.RunPython(seed_brand_profiles_and_permissions, remove_white_label_permissions),
    ]
