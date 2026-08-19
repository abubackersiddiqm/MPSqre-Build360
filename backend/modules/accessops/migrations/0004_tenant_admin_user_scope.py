from django.db import migrations
from django.db.models import Q
from django.utils import timezone


ADMIN_CODES = {"COMPANY_ADMIN", "COMPANY_ADMINISTRATOR"}
ADMIN_PERMISSION_CODES = {"access.view", "access.user.manage"}

# Compatibility role used for existing tenant administrators when v20g is first
# installed. After installation, every Super Admin package/feature change
# republishes COMPANY_USER from the effective SaaS module matrix.
EXCLUDED_COMPANY_USER_PREFIXES = (
    "access.",
    "adminops.",
    "cloudops.",
    "controlplane.",
    "pilot.",
    "release.",
    "stability.",
    "golive.",
    "success.",
    "support.",
    "subscription.",
    "platform.",
    "tenant.",
    "configuration.",
    "module.",
)
EXCLUDED_COMPANY_USER_CODES = {"audit.read"}


def _permission_codes(permission_model):
    codes = []
    for code in permission_model.objects.order_by("code").values_list("code", flat=True):
        if code in EXCLUDED_COMPANY_USER_CODES:
            continue
        if any(code.startswith(prefix) for prefix in EXCLUDED_COMPANY_USER_PREFIXES):
            continue
        codes.append(code)
    return codes


def _publish_role(*, Role, RolePermission, company_public_id, code, name, permission_ids, now):
    current = (
        Role.objects.filter(
            company_public_id=company_public_id,
            code=code,
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
            return current, current

    latest = (
        Role.objects.filter(company_public_id=company_public_id, code=code)
        .order_by("-version")
        .first()
    )
    role = Role.objects.create(
        company_public_id=company_public_id,
        code=code,
        name=name,
        version=(latest.version + 1) if latest else 1,
        effective_from=now,
    )
    RolePermission.objects.bulk_create(
        [RolePermission(role_id=role.id, permission_id=permission_id) for permission_id in permission_ids]
    )
    if current is not None:
        current.retired_at = now
        current.effective_to = now
        current.save(update_fields=["retired_at", "effective_to", "updated_at"])
    return role, current


def _replace_assignment(*, MembershipRole, membership_id, old_role_public_id, new_role_public_id, assigned_by_public_id, now):
    if old_role_public_id == new_role_public_id:
        return
    active = MembershipRole.objects.filter(
        membership_id=membership_id,
        role_public_id=old_role_public_id,
        effective_from__lte=now,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now))
    if not active.exists():
        return
    active.update(effective_to=now)
    already = MembershipRole.objects.filter(
        membership_id=membership_id,
        role_public_id=new_role_public_id,
        effective_from__lte=now,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now)).exists()
    if not already:
        MembershipRole.objects.create(
            membership_id=membership_id,
            role_public_id=new_role_public_id,
            assigned_by_public_id=assigned_by_public_id,
            effective_from=now,
        )


def establish_tenant_user_scope(apps, schema_editor):
    Company = apps.get_model("tenant", "Company")
    MembershipRole = apps.get_model("tenant", "MembershipRole")
    Permission = apps.get_model("identity", "Permission")
    Role = apps.get_model("identity", "Role")
    RolePermission = apps.get_model("identity", "RolePermission")

    user_manage, _ = Permission.objects.update_or_create(
        code="access.user.manage",
        defaults={
            "description": "Invite, suspend, reactivate and terminate company users",
            "data_class": "ACCESS_CONTROL",
        },
    )
    access_view = Permission.objects.filter(code="access.view").first()
    admin_permission_ids = [item.id for item in (access_view, user_manage) if item is not None]

    company_user_codes = _permission_codes(Permission)
    company_user_permission_ids = list(
        Permission.objects.filter(code__in=company_user_codes).values_list("id", flat=True)
    )
    now = timezone.now()

    for company in Company.objects.order_by("id"):
        # Capture memberships that are administrators BEFORE the old admin role is
        # retired. They receive COMPANY_USER as a second role so they can still use
        # purchased business modules while their administration scope becomes users-only.
        admin_roles = list(
            Role.objects.filter(
                company_public_id=company.public_id,
                retired_at__isnull=True,
            ).filter(Q(code__in=ADMIN_CODES) | Q(name__iexact="Company Administrator"))
        )
        admin_assignments = []
        for old_admin in admin_roles:
            for assignment in MembershipRole.objects.filter(
                role_public_id=old_admin.public_id,
                effective_from__lte=now,
            ).filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now)):
                admin_assignments.append((assignment.membership_id, assignment.assigned_by_public_id, old_admin.public_id))

        admin_role, previous_admin = _publish_role(
            Role=Role,
            RolePermission=RolePermission,
            company_public_id=company.public_id,
            code="COMPANY_ADMIN",
            name="Company Administrator",
            permission_ids=admin_permission_ids,
            now=now,
        )
        company_user_role, previous_user = _publish_role(
            Role=Role,
            RolePermission=RolePermission,
            company_public_id=company.public_id,
            code="COMPANY_USER",
            name="Company User",
            permission_ids=company_user_permission_ids,
            now=now,
        )

        # Move assignments from the canonical previous versions when a new version
        # was published. Historical alternate COMPANY_ADMINISTRATOR roles are also
        # moved below through the captured assignment list.
        if previous_user is not None and previous_user.public_id != company_user_role.public_id:
            assignments = list(
                MembershipRole.objects.filter(
                    role_public_id=previous_user.public_id,
                    effective_from__lte=now,
                ).filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now))
            )
            for assignment in assignments:
                _replace_assignment(
                    MembershipRole=MembershipRole,
                    membership_id=assignment.membership_id,
                    old_role_public_id=previous_user.public_id,
                    new_role_public_id=company_user_role.public_id,
                    assigned_by_public_id=assignment.assigned_by_public_id,
                    now=now,
                )

        for membership_id, assigned_by_public_id, old_admin_public_id in admin_assignments:
            _replace_assignment(
                MembershipRole=MembershipRole,
                membership_id=membership_id,
                old_role_public_id=old_admin_public_id,
                new_role_public_id=admin_role.public_id,
                assigned_by_public_id=assigned_by_public_id,
                now=now,
            )
            has_company_user = MembershipRole.objects.filter(
                membership_id=membership_id,
                role_public_id=company_user_role.public_id,
                effective_from__lte=now,
            ).filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now)).exists()
            if not has_company_user:
                MembershipRole.objects.create(
                    membership_id=membership_id,
                    role_public_id=company_user_role.public_id,
                    assigned_by_public_id=assigned_by_public_id,
                    effective_from=now,
                )

        # Retire any non-canonical old administrator role codes after moving their
        # active assignments to COMPANY_ADMIN.
        for old_admin in admin_roles:
            if old_admin.public_id == admin_role.public_id:
                continue
            if old_admin.retired_at is None:
                old_admin.retired_at = now
                old_admin.effective_to = now
                old_admin.save(update_fields=["retired_at", "effective_to", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("accessops", "0003_bootstrap_existing_companies"),
        ("identity", "0021_crm_ai_lead_permissions"),
        ("tenant", "0003_brand_asset_references"),
    ]

    operations = [migrations.RunPython(establish_tenant_user_scope, migrations.RunPython.noop)]
