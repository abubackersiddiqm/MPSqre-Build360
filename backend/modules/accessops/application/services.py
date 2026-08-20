from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

from modules.accessops.models import AccessInvitation, CompanyAccessProfile
from modules.employee.models import Employee
from modules.identity.models import Permission, Role, RolePermission, User
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.subscription.application.feature_control import (
    append_feature_override,
    apply_feature_preset,
    feature_matrix,
)
from modules.tenant.models import Company, Membership, MembershipRole

STANDARD_COMPANY_USER_ROLE_CODE = "COMPANY_USER"
STANDARD_COMPANY_ADMIN_ROLE_CODE = "COMPANY_ADMIN"
LEGACY_COMPANY_ADMIN_ROLE_CODES = {"COMPANY_ADMINISTRATOR", "company_administrator"}
COMPANY_ADMIN_PERMISSION_CODES = [
    "access.view",
    "access.user.manage",
    "tenant.branding.read",
    "tenant.branding.manage",
    "tenant.domain.read",
    "tenant.domain.manage",
]

# Default employee access is derived from purchased SaaS modules. This keeps the
# Company Administrator surface simple (user lifecycle only) while tenant users
# receive only permissions that correspond to modules currently enabled by
# ROOT_OPERATOR. Shared file/notification permissions are intentionally safe
# utilities used by several enabled business modules.
FEATURE_PERMISSION_PREFIXES: dict[str, tuple[str, ...]] = {
    "crm.core": ("crm.",),
    "module.delivery": ("project.", "design.", "estimation.", "work.", "workflow.", "mywork."),
    "module.supply": ("vendor.", "inventory.", "procurement."),
    "module.field": ("field.", "labour."),
    "module.finance": ("finance.",),
    "module.communication": ("communication.",),
    "module.reporting": ("reporting.", "dataops.", "insights."),
    "module.ai": ("ai.",),
    "module.integrations": ("integration.",),
    "module.compliance": ("compliance.",),
    "module.people": ("people.", "peopleorg."),
    "module.payroll": ("payroll.",),
    "module.workforce": ("workforce.",),
    "module.equipment": ("equipment.",),
    "module.hse": ("safety.",),
    "module.quality": ("quality.",),
    "module.documents": ("document.",),
    "module.commercial": ("commercial.",),
    "module.partner": ("collaboration.", "portal."),
    "module.sustainability": ("sustainability.",),
    "module.digital_twin": ("digitaltwin.",),
    "module.facilities": ("facility.",),
    "module.property": ("lease.",),
    "module.sales": ("sales.",),
    "module.land": ("land.",),
    "module.capital": ("capital.",),
    "module.risk_transfer": ("risktransfer.",),
    "crm.meta_ads": ("integration.meta_leads.",),
    "crm.ai_summary": ("ai.crm_lead.",),
    "crm.ai_recommendation": ("ai.crm_lead.",),
    "platform.api_access": ("integration.api_client.",),
}
SHARED_TENANT_PERMISSION_PREFIXES = ("files.", "notification.")


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _issue_token() -> tuple[str, str, str]:
    raw = secrets.token_urlsafe(32)
    return raw, _hash_token(raw), raw[:8]


def _audit_and_event(
    *,
    action: str,
    event_type: str,
    entity_type: str,
    entity_public_id: uuid.UUID,
    actor_public_id: uuid.UUID | None,
    company_public_id: uuid.UUID | None,
    correlation_id: uuid.UUID,
    after: dict[str, object],
    aggregate_version: int = 1,
    actor_type: str = "user",
    before: dict[str, object] | None = None,
    reason_code: str = "",
    event_payload: dict[str, object] | None = None,
) -> None:
    append_audit(
        AuditRecord(
            action=action,
            entity_type=entity_type,
            entity_public_id=entity_public_id,
            actor_public_id=actor_public_id,
            actor_type=actor_type,
            company_public_id=company_public_id,
            request_id=correlation_id,
            correlation_id=correlation_id,
            reason_code=reason_code,
            before=before or {},
            after=after,
        )
    )
    append_event(
        EventRecord(
            event_type=event_type,
            aggregate_type=entity_type,
            aggregate_public_id=entity_public_id,
            aggregate_version=aggregate_version,
            company_public_id=company_public_id,
            correlation_id=correlation_id,
            payload=event_payload if event_payload is not None else after,
        )
    )



@transaction.atomic
def set_company_feature_override(
    *,
    company: Company,
    feature_code: str,
    enabled: bool,
    reason_code: str,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
):
    override = append_feature_override(
        company=company,
        code=feature_code,
        enabled=enabled,
        reason_code=reason_code,
        set_by_public_id=actor_public_id,
        correlation_id=correlation_id,
    )
    reconcile_standard_company_access(
        company=company,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
    )
    return override


@transaction.atomic
def set_company_feature_preset(
    *,
    company: Company,
    preset_code: str,
    reason_code: str,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> None:
    apply_feature_preset(
        company=company,
        preset_code=preset_code,
        reason_code=reason_code,
        set_by_public_id=actor_public_id,
        correlation_id=correlation_id,
    )
    reconcile_standard_company_access(
        company=company,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
    )


@transaction.atomic
def assign_membership_role(
    *,
    membership: Membership,
    role: Role,
    assigned_by_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> MembershipRole:
    locked_membership = (
        Membership.objects.select_for_update()
        .select_related("company")
        .get(pk=membership.pk)
    )
    if role.company_public_id != locked_membership.company.public_id:
        raise ValidationError("Role assignment cannot cross companies")
    assignment = MembershipRole(
        membership=locked_membership,
        role_public_id=role.public_id,
        assigned_by_public_id=assigned_by_public_id,
        effective_from=timezone.now(),
    )
    assignment.full_clean()
    assignment.save()
    _audit_and_event(
        action="access.membership_role.assigned",
        event_type="access.membership_role_assigned",
        entity_type="membership_role",
        entity_public_id=assignment.public_id,
        actor_public_id=assigned_by_public_id,
        company_public_id=locked_membership.company.public_id,
        correlation_id=correlation_id,
        after={
            "membership_public_id": str(locked_membership.public_id),
            "role_public_id": str(role.public_id),
        },
    )
    return assignment

def _create_role(
    *, company: Company, code: str, name: str, permission_codes: list[str]
) -> Role:
    now = timezone.now()
    latest = (
        Role.objects.filter(company_public_id=company.public_id, code=code)
        .order_by("-version")
        .first()
    )
    version = (latest.version + 1) if latest else 1
    if latest and latest.retired_at is None:
        latest.retired_at = now
        latest.effective_to = now
        latest.save(update_fields=["retired_at", "effective_to", "updated_at"])
    role = Role.objects.create(
        company_public_id=company.public_id,
        code=code,
        name=name,
        version=version,
        effective_from=now,
    )
    permissions = list(Permission.objects.filter(code__in=permission_codes))
    RolePermission.objects.bulk_create(
        [RolePermission(role=role, permission=permission) for permission in permissions]
    )
    return role


def create_role(
    *,
    company: Company,
    code: str,
    name: str,
    permission_codes: list[str],
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> Role:
    normalized_code = code.strip().upper().replace(" ", "_")
    if not normalized_code:
        raise ValidationError("Role code is required")
    known_codes = set(
        Permission.objects.filter(code__in=permission_codes).values_list("code", flat=True)
    )
    unknown = sorted(set(permission_codes) - known_codes)
    if unknown:
        raise ValidationError({"permission_codes": f"Unknown permissions: {', '.join(unknown)}"})
    with transaction.atomic():
        previous_role = (
            Role.objects.filter(
                company_public_id=company.public_id,
                code=normalized_code,
                retired_at__isnull=True,
            )
            .order_by("-version")
            .first()
        )
        role = _create_role(
            company=company,
            code=normalized_code,
            name=name.strip(),
            permission_codes=permission_codes,
        )
        if previous_role is not None:
            now = timezone.now()
            assignments = list(
                MembershipRole.objects.select_related("membership", "membership__company").filter(
                    membership__company=company,
                    role_public_id=previous_role.public_id,
                    effective_to__isnull=True,
                )
            )
            MembershipRole.objects.filter(
                pk__in=[assignment.pk for assignment in assignments]
            ).update(effective_to=now)
            for assignment in assignments:
                assign_membership_role(
                    membership=assignment.membership,
                    role=role,
                    assigned_by_public_id=actor_public_id,
                    correlation_id=correlation_id,
                )
        _audit_and_event(
            action="access.role.published",
            event_type="access.role_published",
            entity_type="role",
            entity_public_id=role.public_id,
            actor_public_id=actor_public_id,
            company_public_id=company.public_id,
            correlation_id=correlation_id,
            after={
                "code": role.code,
                "version": role.version,
                "permission_count": len(permission_codes),
            },
        )
        return role


def company_user_permission_codes(company: Company) -> list[str]:
    matrix = feature_matrix(company=company)
    enabled_features = {
        str(item["code"])
        for item in matrix["items"]
        if bool(item["enabled"])
    }
    prefixes: list[str] = list(SHARED_TENANT_PERMISSION_PREFIXES)
    for feature_code in sorted(enabled_features):
        prefixes.extend(FEATURE_PERMISSION_PREFIXES.get(feature_code, ()))
    # Deduplicate prefixes before the DB predicate; module dependencies may add
    # overlapping namespaces (for example module.ai + CRM AI add-ons).
    prefixes = list(dict.fromkeys(prefixes))
    if not prefixes:
        return []
    predicate = Q()
    for prefix in prefixes:
        predicate |= Q(code__startswith=prefix)
    return list(Permission.objects.filter(predicate).order_by("code").values_list("code", flat=True))


def current_company_user_role(company: Company) -> Role | None:
    return (
        Role.objects.filter(
            company_public_id=company.public_id,
            code=STANDARD_COMPANY_USER_ROLE_CODE,
            retired_at__isnull=True,
        )
        .order_by("-version")
        .first()
    )


def current_company_admin_role(company: Company) -> Role | None:
    return (
        Role.objects.filter(
            company_public_id=company.public_id,
            code=STANDARD_COMPANY_ADMIN_ROLE_CODE,
            retired_at__isnull=True,
        )
        .order_by("-version")
        .first()
    )


def sync_company_admin_role(
    *,
    company: Company,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> Role:
    desired_codes = set(COMPANY_ADMIN_PERMISSION_CODES)
    current = current_company_admin_role(company)
    if current is not None:
        current_codes = set(
            current.permission_grants.values_list("permission__code", flat=True)
        )
        if current_codes == desired_codes:
            return current
    return create_role(
        company=company,
        code=STANDARD_COMPANY_ADMIN_ROLE_CODE,
        name="Company Administrator",
        permission_codes=COMPANY_ADMIN_PERMISSION_CODES,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
    )


def sync_company_user_role(
    *,
    company: Company,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> Role:
    desired_codes = company_user_permission_codes(company)
    current = current_company_user_role(company)
    if current is not None:
        current_codes = set(
            current.permission_grants.values_list("permission__code", flat=True)
        )
        if current_codes == set(desired_codes):
            return current
    return create_role(
        company=company,
        code=STANDARD_COMPANY_USER_ROLE_CODE,
        name="Company User",
        permission_codes=desired_codes,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
    )


def _active_membership_role_ids(*, membership: Membership, at) -> set[uuid.UUID]:
    return set(
        membership.role_assignments.filter(effective_from__lte=at)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=at))
        .values_list("role_public_id", flat=True)
    )


def _ensure_membership_has_role(
    *,
    membership: Membership,
    role: Role,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    at,
) -> bool:
    if role.public_id in _active_membership_role_ids(membership=membership, at=at):
        return False
    assign_membership_role(
        membership=membership,
        role=role,
        assigned_by_public_id=actor_public_id,
        correlation_id=correlation_id,
    )
    return True


def _is_primary_or_legacy_admin_membership(
    *,
    membership: Membership,
    profile: CompanyAccessProfile | None,
    at,
) -> bool:
    if (
        profile is not None
        and profile.primary_admin_email.strip()
        and membership.user.email.lower() == profile.primary_admin_email.strip().lower()
    ):
        return True
    active_role_ids = _active_membership_role_ids(membership=membership, at=at)
    if not active_role_ids:
        return False
    return Role.objects.filter(
        public_id__in=active_role_ids,
        company_public_id=membership.company.public_id,
    ).filter(
        Q(code=STANDARD_COMPANY_ADMIN_ROLE_CODE)
        | Q(code__in=LEGACY_COMPANY_ADMIN_ROLE_CODES)
        | Q(name__iexact="Company Administrator")
    ).exists()


def _retire_legacy_admin_assignments(
    *,
    company: Company,
    canonical_admin_role: Role,
    at,
) -> int:
    legacy_roles = list(
        Role.objects.filter(
            company_public_id=company.public_id,
            retired_at__isnull=True,
        )
        .filter(
            Q(code__in=LEGACY_COMPANY_ADMIN_ROLE_CODES)
            | Q(name__iexact="Company Administrator")
        )
        .exclude(public_id=canonical_admin_role.public_id)
    )
    if not legacy_roles:
        return 0
    legacy_ids = [role.public_id for role in legacy_roles]
    updated = MembershipRole.objects.filter(
        membership__company=company,
        role_public_id__in=legacy_ids,
        effective_from__lte=at,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gt=at)).update(effective_to=at)
    for role in legacy_roles:
        role.retired_at = at
        role.effective_to = at
        role.save(update_fields=["retired_at", "effective_to", "updated_at"])
    return int(updated)


def _align_pending_standard_invitations(
    *,
    company: Company,
    admin_role: Role,
    user_role: Role,
    at,
) -> int:
    changed = 0
    pending = AccessInvitation.objects.filter(
        company=company,
        accepted_at__isnull=True,
        revoked_at__isnull=True,
        expires_at__gt=at,
    )
    for invitation in pending:
        if invitation.invitation_type_code == "COMPANY_ADMIN":
            desired = [str(admin_role.public_id), str(user_role.public_id)]
        else:
            referenced = list(
                Role.objects.filter(
                    public_id__in=invitation.role_public_ids,
                    company_public_id=company.public_id,
                )
            )
            standard_only = not referenced or all(
                role.code in {
                    STANDARD_COMPANY_USER_ROLE_CODE,
                    STANDARD_COMPANY_ADMIN_ROLE_CODE,
                    *LEGACY_COMPANY_ADMIN_ROLE_CODES,
                }
                or role.name.lower() in {"company user", "company administrator"}
                for role in referenced
            )
            if not standard_only:
                continue
            desired = [str(user_role.public_id)]
        if list(invitation.role_public_ids) != desired:
            invitation.role_public_ids = desired
            invitation.version += 1
            invitation.save(update_fields=["role_public_ids", "version", "updated_at"])
            changed += 1
    return changed


@transaction.atomic
def reconcile_standard_company_access(
    *,
    company: Company,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> dict[str, int]:
    """Reconcile standard tenant roles after package/feature changes.

    Package entitlements define the maximum business capability. COMPANY_USER is
    republished from that effective feature matrix. COMPANY_ADMIN remains a small
    tenant-administration role and primary administrators receive both roles.
    Existing custom roles are preserved; only role-less memberships receive the
    default COMPANY_USER baseline automatically.
    """
    locked_company = Company.objects.select_for_update().get(pk=company.pk)
    now = timezone.now()
    profile = CompanyAccessProfile.objects.filter(company=locked_company).first()

    active_memberships = list(
        Membership.objects.select_related("user", "company")
        .filter(
            company=locked_company,
            effective_from__lte=now,
            suspended_at__isnull=True,
            terminated_at__isnull=True,
            user__is_active=True,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now))
    )
    admin_membership_ids = {
        membership.pk
        for membership in active_memberships
        if _is_primary_or_legacy_admin_membership(
            membership=membership,
            profile=profile,
            at=now,
        )
    }

    admin_role = sync_company_admin_role(
        company=locked_company,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
    )
    user_role = sync_company_user_role(
        company=locked_company,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
    )

    assigned_admin = 0
    assigned_user = 0
    for membership in active_memberships:
        active_ids = _active_membership_role_ids(membership=membership, at=now)
        if membership.pk in admin_membership_ids:
            if _ensure_membership_has_role(
                membership=membership,
                role=admin_role,
                actor_public_id=actor_public_id,
                correlation_id=correlation_id,
                at=now,
            ):
                assigned_admin += 1
            if _ensure_membership_has_role(
                membership=membership,
                role=user_role,
                actor_public_id=actor_public_id,
                correlation_id=correlation_id,
                at=now,
            ):
                assigned_user += 1
        elif not active_ids:
            if _ensure_membership_has_role(
                membership=membership,
                role=user_role,
                actor_public_id=actor_public_id,
                correlation_id=correlation_id,
                at=now,
            ):
                assigned_user += 1

    retired_legacy_assignments = _retire_legacy_admin_assignments(
        company=locked_company,
        canonical_admin_role=admin_role,
        at=now,
    )
    aligned_invitations = _align_pending_standard_invitations(
        company=locked_company,
        admin_role=admin_role,
        user_role=user_role,
        at=now,
    )

    from modules.accessops.application.managed_access import reconcile_managed_access_roles

    managed_roles_reconciled = reconcile_managed_access_roles(
        company=locked_company,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
    )

    summary = {
        "managed_access_roles_reconciled": managed_roles_reconciled,
        "active_memberships": len(active_memberships),
        "admin_memberships": len(admin_membership_ids),
        "admin_assignments_added": assigned_admin,
        "user_assignments_added": assigned_user,
        "legacy_assignments_retired": retired_legacy_assignments,
        "pending_invitations_aligned": aligned_invitations,
    }
    _audit_and_event(
        action="access.standard_roles.reconciled",
        event_type="access.standard_roles_reconciled",
        entity_type="company",
        entity_public_id=locked_company.public_id,
        actor_public_id=actor_public_id,
        company_public_id=locked_company.public_id,
        correlation_id=correlation_id,
        after=summary,
        aggregate_version=int(now.timestamp() * 1_000_000),
    )
    return summary


@transaction.atomic
def create_invitation(
    *,
    company: Company,
    email: str,
    display_name: str,
    invitation_type_code: str,
    role_public_ids: list[uuid.UUID],
    employee_number: str,
    job_title: str,
    invited_by_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    ttl_hours: int = 72,
    actor_type: str = "user",
) -> tuple[AccessInvitation, str]:
    if not role_public_ids:
        raise ValidationError("At least one company role is required")
    roles = list(
        Role.objects.filter(
            public_id__in=role_public_ids,
            company_public_id=company.public_id,
            retired_at__isnull=True,
        )
    )
    if len(roles) != len(set(role_public_ids)):
        raise ValidationError("One or more roles are invalid for this company")
    normalized_email = email.strip().lower()
    normalized_employee_number = employee_number.strip()
    if normalized_employee_number and Employee.objects.filter(
        company=company, employee_number__iexact=normalized_employee_number
    ).exists():
        raise ValidationError({"employee_number": "This employee number is already in use"})
    if normalized_employee_number and AccessInvitation.objects.filter(
        company=company,
        employee_number__iexact=normalized_employee_number,
        accepted_at__isnull=True,
        revoked_at__isnull=True,
    ).exclude(email__iexact=normalized_email).exists():
        raise ValidationError({"employee_number": "A pending invitation already uses this employee number"})
    now = timezone.now()
    AccessInvitation.objects.filter(
        company=company,
        email__iexact=normalized_email,
        accepted_at__isnull=True,
        revoked_at__isnull=True,
    ).update(revoked_at=now, version=models.F("version") + 1)
    raw_token, token_hash, token_hint = _issue_token()
    invitation = AccessInvitation.objects.create(
        company=company,
        email=normalized_email,
        display_name=display_name.strip(),
        invitation_type_code=invitation_type_code.strip().upper(),
        token_hash=token_hash,
        token_hint=token_hint,
        role_public_ids=[str(role.public_id) for role in roles],
        employee_number=normalized_employee_number,
        job_title=job_title.strip(),
        invited_by_public_id=invited_by_public_id,
        expires_at=now + timedelta(hours=max(1, min(ttl_hours, 168))),
    )
    _audit_and_event(
        action="access.invitation.created",
        event_type="access.invitation_created",
        entity_type="access_invitation",
        entity_public_id=invitation.public_id,
        actor_public_id=invited_by_public_id,
        company_public_id=company.public_id,
        correlation_id=correlation_id,
        after={
            "email": normalized_email,
            "invitation_type_code": invitation.invitation_type_code,
            "role_count": len(roles),
            "expires_at": invitation.expires_at.isoformat(),
        },
        actor_type=actor_type,
        event_payload={
            "invitation_public_id": str(invitation.public_id),
            "invitation_type_code": invitation.invitation_type_code,
            "role_count": len(roles),
            "expires_at": invitation.expires_at.isoformat(),
        },
    )
    return invitation, raw_token


@transaction.atomic
def create_company_with_admin_invitation(
    *,
    code: str,
    legal_name: str,
    display_name: str,
    locale: str,
    timezone_name: str,
    currency: str,
    unit_system_code: str,
    fiscal_year_start_month: int,
    plan_code: str,
    admin_email: str,
    admin_display_name: str,
    admin_employee_number: str,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    preset_code: str = "FULL_BUILD360",
) -> tuple[Company, AccessInvitation, str]:
    company = Company(
        code=code.strip().upper(),
        legal_name=legal_name.strip(),
        display_name=display_name.strip(),
        locale=locale.strip(),
        timezone=timezone_name.strip(),
        currency=currency.strip().upper(),
        unit_system_code=unit_system_code.strip(),
        fiscal_year_start_month=fiscal_year_start_month,
        is_active=True,
    )
    company.full_clean()
    company.save()
    CompanyAccessProfile.objects.create(
        company=company,
        plan_code=plan_code.strip(),
        onboarding_status_code="PENDING_ADMIN",
        primary_admin_email=admin_email.strip().lower(),
        created_by_public_id=actor_public_id,
    )
    admin_role = sync_company_admin_role(
        company=company,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
    )
    apply_feature_preset(
        company=company,
        preset_code=preset_code,
        reason_code="company-create-package",
        set_by_public_id=actor_public_id,
        correlation_id=correlation_id,
    )
    reconcile_standard_company_access(
        company=company,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
    )
    company_user_role = current_company_user_role(company)
    if company_user_role is None:
        raise ValidationError("Default Company User access level was not provisioned")
    invitation, token = create_invitation(
        company=company,
        email=admin_email,
        display_name=admin_display_name,
        invitation_type_code="COMPANY_ADMIN",
        role_public_ids=[admin_role.public_id, company_user_role.public_id],
        employee_number=admin_employee_number,
        job_title="Company Administrator",
        invited_by_public_id=actor_public_id,
        correlation_id=correlation_id,
        actor_type="platform_operator",
    )
    _audit_and_event(
        action="platform.company.created",
        event_type="platform.company_created",
        entity_type="company",
        entity_public_id=company.public_id,
        actor_public_id=actor_public_id,
        company_public_id=None,
        correlation_id=correlation_id,
        after={"code": company.code, "display_name": company.display_name, "plan_code": plan_code},
        actor_type="platform_operator",
    )
    return company, invitation, token


@transaction.atomic
def accept_invitation(
    *, raw_token: str, password: str, correlation_id: uuid.UUID
) -> tuple[User, Membership]:
    invitation = (
        AccessInvitation.objects.select_for_update()
        .select_related("company")
        .filter(token_hash=_hash_token(raw_token))
        .first()
    )
    now = timezone.now()
    if (
        not invitation
        or invitation.revoked_at
        or invitation.accepted_at
        or invitation.expires_at <= now
    ):
        raise ValidationError("Invitation is invalid or has expired")
    user = User.objects.filter(email__iexact=invitation.email).first()
    if user is None:
        user = User.objects.create_user(
            email=invitation.email,
            password=password,
            display_name=invitation.display_name,
            preferred_locale=invitation.company.locale,
        )
    else:
        password_changed = False
        if user.has_usable_password():
            if not user.check_password(password):
                raise ValidationError(
                    "This email already has a Build360 account. Enter its existing password."
                )
        else:
            user.set_password(password)
            password_changed = True
        user.display_name = invitation.display_name or user.display_name
        user.is_active = True
        user.suspended_at = None
        user.full_clean()
        update_fields = ["display_name", "is_active", "suspended_at", "updated_at"]
        if password_changed:
            update_fields.append("password")
        user.save(update_fields=update_fields)
    membership, _ = Membership.objects.get_or_create(
        company=invitation.company,
        user=user,
        defaults={"effective_from": now},
    )
    if membership.suspended_at or membership.terminated_at:
        membership.suspended_at = None
        membership.terminated_at = None
        membership.effective_to = None
        membership.save(
            update_fields=["suspended_at", "terminated_at", "effective_to", "updated_at"]
        )
    roles = list(
        Role.objects.filter(
            public_id__in=invitation.role_public_ids,
            company_public_id=invitation.company.public_id,
            retired_at__isnull=True,
        )
    )
    if len(roles) != len(set(invitation.role_public_ids)):
        raise ValidationError(
            "The invitation role configuration changed. Ask an administrator for a new invitation."
        )
    for role in roles:
        active_assignment = membership.role_assignments.filter(
            role_public_id=role.public_id, effective_to__isnull=True
        ).exists()
        if not active_assignment:
            assign_membership_role(
                membership=membership,
                role=role,
                assigned_by_public_id=invitation.invited_by_public_id,
                correlation_id=correlation_id,
            )
    if invitation.employee_number:
        Employee.objects.get_or_create(
            company=invitation.company,
            membership=membership,
            defaults={
                "employee_number": invitation.employee_number,
                "job_title": invitation.job_title or "Team member",
                "employment_start": now.date(),
            },
        )
    invitation.accepted_at = now
    invitation.version += 1
    invitation.save(update_fields=["accepted_at", "version", "updated_at"])
    profile = CompanyAccessProfile.objects.filter(company=invitation.company).first()
    if profile and invitation.invitation_type_code == "COMPANY_ADMIN":
        profile.onboarding_status_code = "ADMIN_ACTIVE"
        profile.activated_at = now
        profile.version += 1
        profile.save(
            update_fields=["onboarding_status_code", "activated_at", "version", "updated_at"]
        )
    _audit_and_event(
        action="access.invitation.accepted",
        event_type="access.invitation_accepted",
        entity_type="access_invitation",
        entity_public_id=invitation.public_id,
        actor_public_id=user.public_id,
        company_public_id=invitation.company.public_id,
        correlation_id=correlation_id,
        after={
            "invitation_public_id": str(invitation.public_id),
            "user_public_id": str(user.public_id),
            "role_count": len(roles),
        },
        event_payload={
            "invitation_public_id": str(invitation.public_id),
            "user_public_id": str(user.public_id),
            "role_count": len(roles),
        },
    )
    return user, membership


@transaction.atomic
def replace_membership_roles(
    *,
    membership: Membership,
    role_public_ids: list[uuid.UUID],
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> None:
    now = timezone.now()
    roles = list(
        Role.objects.filter(
            public_id__in=role_public_ids,
            company_public_id=membership.company.public_id,
            retired_at__isnull=True,
        )
    )
    if len(roles) != len(set(role_public_ids)):
        raise ValidationError("One or more roles are invalid for this company")
    if membership.user.public_id == actor_public_id:
        selected_permissions = set(
            RolePermission.objects.filter(role__in=roles).values_list(
                "permission__code", flat=True
            )
        )
        required_self_admin = {
            "access.view",
            "access.manage",
            "access.invite",
            "access.role.manage",
            "access.membership.manage",
        }
        if not required_self_admin.issubset(selected_permissions):
            raise ValidationError(
                "You cannot remove your own access-administration permissions"
            )
    membership.role_assignments.filter(
        Q(effective_to__isnull=True) | Q(effective_to__gt=now)
    ).update(effective_to=now)
    for role in roles:
        assign_membership_role(
            membership=membership,
            role=role,
            assigned_by_public_id=actor_public_id,
            correlation_id=correlation_id,
        )
    _audit_and_event(
        action="access.membership_roles.replaced",
        event_type="access.membership_roles_replaced",
        entity_type="membership",
        entity_public_id=membership.public_id,
        actor_public_id=actor_public_id,
        company_public_id=membership.company.public_id,
        correlation_id=correlation_id,
        after={"role_public_ids": [str(role.public_id) for role in roles]},
        aggregate_version=int(now.timestamp() * 1_000_000),
    )


@transaction.atomic
def transfer_primary_company_admin(
    *,
    company: Company,
    membership: Membership,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    reason_code: str,
) -> dict[str, object]:
    # Atomically transfer the single primary Company Administrator designation.
    normalized_reason = reason_code.strip()
    if not normalized_reason:
        raise ValidationError("A reason code is required to change the primary administrator")

    locked_company = Company.objects.select_for_update().get(pk=company.pk)
    profile = CompanyAccessProfile.objects.select_for_update().filter(company=locked_company).first()
    if profile is None:
        raise ValidationError("Company access profile is not provisioned")

    now = timezone.now()
    target = (
        Membership.objects.select_for_update()
        .select_related("user", "company")
        .filter(
            pk=membership.pk,
            company=locked_company,
            effective_from__lte=now,
            suspended_at__isnull=True,
            terminated_at__isnull=True,
            user__is_active=True,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now))
        .first()
    )
    if target is None:
        raise ValidationError("The new administrator must be an active user of this company")

    target_email = target.user.email.strip().lower()
    previous_email = profile.primary_admin_email.strip().lower()
    if previous_email == target_email:
        return {
            "changed": False,
            "previous_primary_admin_email": previous_email,
            "primary_admin_email": target_email,
            "membership_public_id": str(target.public_id),
        }

    admin_role = current_company_admin_role(locked_company)
    user_role = current_company_user_role(locked_company)
    if admin_role is None or user_role is None:
        raise ValidationError(
            "Standard Company Administrator/User roles are not provisioned. Re-apply the company SaaS package first."
        )

    _ensure_membership_has_role(
        membership=target,
        role=user_role,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        at=now,
    )
    _ensure_membership_has_role(
        membership=target,
        role=admin_role,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        at=now,
    )

    previous_membership = None
    if previous_email:
        previous_membership = (
            Membership.objects.select_for_update()
            .select_related("user")
            .filter(company=locked_company, user__email__iexact=previous_email)
            .first()
        )

    if previous_membership is not None and previous_membership.pk != target.pk:
        admin_role_ids = list(
            Role.objects.filter(company_public_id=locked_company.public_id)
            .filter(
                Q(code=STANDARD_COMPANY_ADMIN_ROLE_CODE)
                | Q(code__in=LEGACY_COMPANY_ADMIN_ROLE_CODES)
                | Q(name__iexact="Company Administrator")
            )
            .values_list("public_id", flat=True)
        )
        MembershipRole.objects.filter(
            membership=previous_membership,
            role_public_id__in=admin_role_ids,
            effective_from__lte=now,
        ).filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now)).update(effective_to=now)

    profile.primary_admin_email = target_email
    profile.onboarding_status_code = "ADMIN_ACTIVE"
    profile.activated_at = now
    profile.version += 1
    profile.save(
        update_fields=[
            "primary_admin_email",
            "onboarding_status_code",
            "activated_at",
            "version",
            "updated_at",
        ]
    )

    result = {
        "changed": True,
        "previous_primary_admin_email": previous_email,
        "primary_admin_email": target_email,
        "membership_public_id": str(target.public_id),
    }
    _audit_and_event(
        action="platform.primary_admin.transferred",
        event_type="platform.primary_admin_transferred",
        entity_type="company",
        entity_public_id=locked_company.public_id,
        actor_public_id=actor_public_id,
        company_public_id=locked_company.public_id,
        correlation_id=correlation_id,
        before={"primary_admin_email": previous_email},
        after=result,
        reason_code=normalized_reason,
        actor_type="platform_operator",
        aggregate_version=profile.version,
        event_payload=result,
    )
    return result


@transaction.atomic
def set_company_active(
    *,
    company: Company,
    is_active: bool,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    reason_code: str = "",
) -> Company:
    locked = Company.objects.select_for_update().get(pk=company.pk)
    now = timezone.now()
    before = {"is_active": locked.is_active}
    if is_active and locked.closed_at is not None:
        raise ValidationError("A closed company cannot be reactivated")
    locked.is_active = is_active
    locked.suspended_at = None if is_active else now
    locked.save(update_fields=["is_active", "suspended_at", "updated_at"])
    _audit_and_event(
        action="platform.company.status_changed",
        event_type="platform.company_status_changed",
        entity_type="company",
        entity_public_id=locked.public_id,
        actor_public_id=actor_public_id,
        company_public_id=None,
        correlation_id=correlation_id,
        before=before,
        after={"is_active": locked.is_active},
        reason_code=reason_code,
        actor_type="platform_operator",
        aggregate_version=int(now.timestamp() * 1_000_000),
        event_payload={"is_active": locked.is_active, "reason_code": reason_code},
    )
    return locked


@transaction.atomic
def revoke_invitation(
    *,
    invitation: AccessInvitation,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> AccessInvitation:
    locked = AccessInvitation.objects.select_for_update().select_related("company").get(
        pk=invitation.pk
    )
    if locked.accepted_at:
        raise ValidationError("Accepted invitations cannot be revoked")
    if locked.revoked_at:
        return locked
    locked.revoked_at = timezone.now()
    locked.version += 1
    locked.save(update_fields=["revoked_at", "version", "updated_at"])
    _audit_and_event(
        action="access.invitation.revoked",
        event_type="access.invitation_revoked",
        entity_type="access_invitation",
        entity_public_id=locked.public_id,
        actor_public_id=actor_public_id,
        company_public_id=locked.company.public_id,
        correlation_id=correlation_id,
        after={"email": locked.email, "revoked_at": locked.revoked_at.isoformat()},
        aggregate_version=locked.version,
        event_payload={
            "invitation_public_id": str(locked.public_id),
            "revoked_at": locked.revoked_at.isoformat(),
        },
    )
    return locked


@transaction.atomic
def set_membership_status(
    *,
    membership: Membership,
    status_code: str,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    reason_code: str = "",
) -> Membership:
    locked = Membership.objects.select_for_update().select_related("company").get(
        pk=membership.pk
    )
    now = timezone.now()
    before = {
        "suspended_at": locked.suspended_at.isoformat() if locked.suspended_at else None,
        "terminated_at": locked.terminated_at.isoformat() if locked.terminated_at else None,
    }
    if locked.user.public_id == actor_public_id and status_code != "ACTIVE":
        raise ValidationError("You cannot suspend or terminate your own membership")
    if locked.terminated_at is not None and status_code != "TERMINATED":
        raise ValidationError("Terminated memberships cannot be reactivated")
    if status_code == "ACTIVE":
        locked.suspended_at = None
        locked.terminated_at = None
        locked.effective_to = None
    elif status_code == "SUSPENDED":
        locked.suspended_at = now
        locked.terminated_at = None
    elif status_code == "TERMINATED":
        locked.terminated_at = now
        locked.effective_to = now
    else:
        raise ValidationError("Membership status is invalid")
    locked.save(
        update_fields=["suspended_at", "terminated_at", "effective_to", "updated_at"]
    )
    _audit_and_event(
        action="access.membership.status_changed",
        event_type="access.membership_status_changed",
        entity_type="membership",
        entity_public_id=locked.public_id,
        actor_public_id=actor_public_id,
        company_public_id=locked.company.public_id,
        correlation_id=correlation_id,
        before=before,
        after={"status_code": status_code},
        reason_code=reason_code,
        aggregate_version=int(now.timestamp() * 1_000_000),
        event_payload={"status_code": status_code, "reason_code": reason_code},
    )
    return locked


@transaction.atomic
def regenerate_company_user_invitation(
    *,
    invitation: AccessInvitation,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    ttl_hours: int = 72,
) -> tuple[AccessInvitation, str]:
    """Create a fresh employee invitation and revoke any older pending token.

    Company Administrators control employee lifecycle only. Primary administrator
    activation remains a ROOT_OPERATOR action. The refreshed invite always uses the
    current Company User role so package changes cannot be bypassed by an old token.
    """
    locked = (
        AccessInvitation.objects.select_for_update()
        .select_related("company")
        .filter(public_id=invitation.public_id, company=invitation.company)
        .first()
    )
    if locked is None:
        raise ValidationError("Invitation was not found")
    if locked.accepted_at is not None:
        raise ValidationError("Accepted invitations cannot be resent")
    if locked.invitation_type_code == "COMPANY_ADMIN":
        raise ValidationError("Primary Company Administrator activation is controlled by Build360 Super Admin")
    default_role = current_company_user_role(locked.company)
    if default_role is None:
        raise ValidationError("Default Company User access level is not provisioned. Ask Build360 Super Admin to re-apply the company SaaS package.")
    return create_invitation(
        company=locked.company,
        email=locked.email,
        display_name=locked.display_name,
        invitation_type_code=locked.invitation_type_code,
        role_public_ids=[default_role.public_id],
        employee_number=locked.employee_number,
        job_title=locked.job_title,
        invited_by_public_id=actor_public_id,
        correlation_id=correlation_id,
        ttl_hours=ttl_hours,
    )


@transaction.atomic
def regenerate_primary_admin_invitation(
    *,
    company: Company,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    ttl_hours: int = 72,
) -> tuple[AccessInvitation, str]:
    """Re-issue activation for an unactivated primary Company Administrator.

    Accepted/active administrators use self-service password recovery instead of
    receiving another membership activation invitation.
    """
    profile = CompanyAccessProfile.objects.select_for_update().filter(company=company).first()
    if profile is None or not profile.primary_admin_email.strip():
        raise ValidationError("Primary Company Administrator email is not configured")

    email = profile.primary_admin_email.strip().lower()
    user = User.objects.filter(email__iexact=email).first()
    if user is not None and Membership.objects.filter(
        company=company,
        user=user,
        suspended_at__isnull=True,
        terminated_at__isnull=True,
    ).exists():
        raise ValidationError(
            "Primary Company Administrator is already active. Use Forgot password for credential recovery."
        )

    reconcile_standard_company_access(
        company=company,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
    )
    admin_role = current_company_admin_role(company)
    company_user_role = current_company_user_role(company)
    if admin_role is None or company_user_role is None:
        raise ValidationError(
            "Company administrator access is not provisioned. Re-apply the company SaaS package first."
        )

    latest = (
        AccessInvitation.objects.filter(
            company=company,
            email__iexact=email,
            invitation_type_code="COMPANY_ADMIN",
        )
        .order_by("-created_at")
        .first()
    )
    display_name = (
        (latest.display_name if latest else "")
        or (user.display_name if user is not None else "")
        or email.split("@", 1)[0]
    )
    return create_invitation(
        company=company,
        email=email,
        display_name=display_name,
        invitation_type_code="COMPANY_ADMIN",
        role_public_ids=[admin_role.public_id, company_user_role.public_id],
        employee_number=latest.employee_number if latest else "",
        job_title=latest.job_title if latest and latest.job_title else "Company Administrator",
        invited_by_public_id=actor_public_id,
        correlation_id=correlation_id,
        ttl_hours=ttl_hours,
        actor_type="platform_operator",
    )
