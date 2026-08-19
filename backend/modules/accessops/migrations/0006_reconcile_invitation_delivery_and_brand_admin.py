from __future__ import annotations

from django.db import migrations
from django.db.models import Q
from django.utils import timezone


ADMIN_CODES = {"COMPANY_ADMIN", "COMPANY_ADMINISTRATOR"}
ADMIN_PERMISSION_CODES = {
    "access.view",
    "access.user.manage",
    "tenant.branding.read",
    "tenant.branding.manage",
    "tenant.domain.read",
    "tenant.domain.manage",
}
INVITATION_DELIVERY_FIELDS = (
    "delivery_attempted_at",
    "delivery_brand_snapshot",
    "delivery_error_code",
    "delivery_sent_at",
    "delivery_status_code",
)


def _publish_company_admin_role(*, Role, RolePermission, MembershipRole, company, permission_ids, now):
    current = (
        Role.objects.filter(
            company_public_id=company.public_id,
            code="COMPANY_ADMIN",
            retired_at__isnull=True,
        )
        .order_by("-version")
        .first()
    )
    if current is not None:
        current_permission_ids = set(
            RolePermission.objects.filter(role_id=current.id).values_list("permission_id", flat=True)
        )
        if current_permission_ids == set(permission_ids):
            return current

    old_roles = list(
        Role.objects.filter(
            company_public_id=company.public_id,
            retired_at__isnull=True,
        ).filter(Q(code__in=ADMIN_CODES) | Q(name__iexact="Company Administrator"))
    )
    assignments = []
    for role in old_roles:
        rows = MembershipRole.objects.filter(
            role_public_id=role.public_id,
            effective_from__lte=now,
        ).filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now))
        for row in rows:
            assignments.append((row.membership_id, row.assigned_by_public_id, role.public_id))

    latest = (
        Role.objects.filter(company_public_id=company.public_id, code="COMPANY_ADMIN")
        .order_by("-version")
        .first()
    )
    role = Role.objects.create(
        company_public_id=company.public_id,
        code="COMPANY_ADMIN",
        name="Company Administrator",
        version=(latest.version + 1) if latest else 1,
        effective_from=now,
    )
    RolePermission.objects.bulk_create(
        [RolePermission(role_id=role.id, permission_id=permission_id) for permission_id in permission_ids]
    )

    for membership_id, assigned_by_public_id, old_public_id in assignments:
        MembershipRole.objects.filter(
            membership_id=membership_id,
            role_public_id=old_public_id,
            effective_from__lte=now,
        ).filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now)).update(effective_to=now)
        already = MembershipRole.objects.filter(
            membership_id=membership_id,
            role_public_id=role.public_id,
            effective_from__lte=now,
        ).filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now)).exists()
        if not already:
            MembershipRole.objects.create(
                membership_id=membership_id,
                role_public_id=role.public_id,
                assigned_by_public_id=assigned_by_public_id,
                effective_from=now,
            )

    for old in old_roles:
        if old.public_id == role.public_id:
            continue
        old.retired_at = now
        old.effective_to = now
        old.save(update_fields=["retired_at", "effective_to", "updated_at"])
    return role


def reconcile_schema_and_brand_admin_scope(apps, schema_editor):
    AccessInvitation = apps.get_model("accessops", "AccessInvitation")
    Company = apps.get_model("tenant", "Company")
    MembershipRole = apps.get_model("tenant", "MembershipRole")
    Permission = apps.get_model("identity", "Permission")
    Role = apps.get_model("identity", "Role")
    RolePermission = apps.get_model("identity", "RolePermission")

    table_name = AccessInvitation._meta.db_table
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        table_names = set(connection.introspection.table_names(cursor))
        if table_name not in table_names:
            raise RuntimeError(f"Required invitation table is missing: {table_name}")
        existing_columns = {
            column.name
            for column in connection.introspection.get_table_description(cursor, table_name)
        }

    # v20j R1 could be recorded in django_migrations while the physical schema
    # additions were absent. Repair only missing columns, leaving healthy databases
    # untouched. schema_editor.add_field keeps this portable across supported DBs.
    for field_name in INVITATION_DELIVERY_FIELDS:
        if field_name in existing_columns:
            continue
        field = AccessInvitation._meta.get_field(field_name)
        schema_editor.add_field(AccessInvitation, field)
        existing_columns.add(field_name)

    descriptions = {
        "access.view": "View company access administration",
        "access.user.manage": "Invite, suspend, reactivate and terminate company users",
        "tenant.branding.read": "View company white-label branding and identity settings",
        "tenant.branding.manage": "Manage company white-label branding and identity settings",
        "tenant.domain.read": "View company platform and custom domains",
        "tenant.domain.manage": "Manage company platform and custom domains",
    }
    for code in ADMIN_PERMISSION_CODES:
        Permission.objects.get_or_create(
            code=code,
            defaults={"description": descriptions[code], "data_class": "ACCESS_CONTROL"},
        )

    permission_ids = list(
        Permission.objects.filter(code__in=ADMIN_PERMISSION_CODES).values_list("id", flat=True)
    )
    now = timezone.now()
    for company in Company.objects.order_by("id"):
        _publish_company_admin_role(
            Role=Role,
            RolePermission=RolePermission,
            MembershipRole=MembershipRole,
            company=company,
            permission_ids=permission_ids,
            now=now,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("accessops", "0005_tenant_brand_admin_and_invite_delivery"),
    ]

    operations = [
        migrations.RunPython(reconcile_schema_and_brand_admin_scope, migrations.RunPython.noop),
    ]
