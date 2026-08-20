from __future__ import annotations

import uuid
from collections.abc import Mapping

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from modules.accessops.models import AccessInvitation, CompanyAccessProfile
from modules.identity.models import Role, User
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.models import AuditEvent
from modules.subscription.application.feature_control import feature_matrix
from modules.tenant.models import Company, Membership

from .services import (
    LEGACY_COMPANY_ADMIN_ROLE_CODES,
    SHARED_TENANT_PERMISSION_PREFIXES,
    STANDARD_COMPANY_ADMIN_ROLE_CODE,
    STANDARD_COMPANY_USER_ROLE_CODE,
    company_user_permission_codes,
    create_role,
    replace_membership_roles,
)

ACCESS_LEVELS = ("NONE", "VIEW", "EDIT", "FULL")
MANAGED_ACCESS_ROLE_PREFIX = "B360_ACCESS_"
NO_ACCESS_ROLE_CODE = f"{MANAGED_ACCESS_ROLE_PREFIX}NONE"
SHARED_ROLE_PREFIX = f"{MANAGED_ACCESS_ROLE_PREFIX}SHARED_"

ACCESS_AREAS: dict[str, dict[str, object]] = {
    "CRM": {
        "label": "CRM",
        "description": "Customers, contacts, leads, opportunities, activities and CRM add-ons.",
        "features": ("crm.core", "crm.meta_ads", "crm.ai_summary", "crm.ai_recommendation", "module.sales"),
        "prefixes": ("crm.", "integration.meta_leads.", "ai.crm_lead.", "sales."),
    },
    "PROJECTS": {
        "label": "Projects & delivery",
        "description": "Projects, design, estimates, work, approvals, documents, quality and safety.",
        "features": ("module.delivery", "module.documents", "module.quality", "module.hse", "module.digital_twin"),
        "prefixes": (
            "project.", "design.", "estimation.", "work.", "workflow.", "mywork.",
            "document.", "quality.", "safety.", "digitaltwin.",
        ),
    },
    "SUPPLY": {
        "label": "Supply & equipment",
        "description": "Vendors, procurement, inventory and equipment.",
        "features": ("module.supply", "module.equipment"),
        "prefixes": ("vendor.", "procurement.", "inventory.", "equipment."),
    },
    "FIELD": {
        "label": "Field & workforce",
        "description": "Field operations, labour and workforce execution.",
        "features": ("module.field", "module.workforce"),
        "prefixes": ("field.", "labour.", "workforce."),
    },
    "FINANCE": {
        "label": "Finance & commercial",
        "description": "Finance, commercial, capital, property, land and risk-transfer controls.",
        "features": ("module.finance", "module.commercial", "module.capital", "module.property", "module.land", "module.risk_transfer"),
        "prefixes": ("finance.", "commercial.", "capital.", "lease.", "land.", "risktransfer."),
    },
    "COMMUNICATIONS": {
        "label": "Communications & collaboration",
        "description": "Communication channels, notifications, portals and collaboration.",
        "features": ("module.communication", "module.partner"),
        "prefixes": ("communication.", "collaboration.", "portal."),
    },
    "REPORTING": {
        "label": "Reports & insights",
        "description": "Reporting, governed data operations and operational insights.",
        "features": ("module.reporting",),
        "prefixes": ("reporting.", "dataops.", "insights."),
    },
    "AI": {
        "label": "Governed AI",
        "description": "AI workspace and governed AI actions.",
        "features": ("module.ai",),
        "prefixes": ("ai.",),
    },
    "INTEGRATIONS": {
        "label": "Integrations & API",
        "description": "Integrations, connectors and API access.",
        "features": ("module.integrations", "platform.api_access"),
        "prefixes": ("integration.",),
    },
    "COMPLIANCE": {
        "label": "Compliance & sustainability",
        "description": "Compliance controls and sustainability evidence.",
        "features": ("module.compliance", "module.sustainability"),
        "prefixes": ("compliance.", "sustainability."),
    },
    "PEOPLE": {
        "label": "People & payroll",
        "description": "People operations, organisation and payroll.",
        "features": ("module.people", "module.payroll"),
        "prefixes": ("people.", "peopleorg.", "payroll."),
    },
    "OPERATIONS": {
        "label": "Facilities",
        "description": "Facilities and post-handover operations.",
        "features": ("module.facilities",),
        "prefixes": ("facility.",),
    },
}

_READ_TERMS = {"read", "view", "list"}
_EDIT_TERMS = {
    "manage", "create", "update", "write", "edit", "add", "upload", "comment",
    "record", "complete", "schedule", "submit", "send", "respond", "acknowledge",
}
_HIGH_RISK_TERMS = {
    "approve", "approval", "reject", "delete", "remove", "reveal", "assign",
    "transition", "convert", "override", "publish", "void", "refund",
    "impersonate", "rotate", "restore", "admin", "permission", "role",
}


def _permission_terms(code: str) -> set[str]:
    return {part.strip().lower() for part in code.replace("-", ".").split(".") if part.strip()}


def filter_permission_codes_for_level(codes: list[str], level: str) -> list[str]:
    normalized = level.strip().upper()
    if normalized not in ACCESS_LEVELS:
        raise ValidationError(f"Unsupported access level: {level}")
    if normalized == "NONE":
        return []
    if normalized == "FULL":
        return sorted(set(codes))

    selected: list[str] = []
    for code in codes:
        terms = _permission_terms(code)
        if normalized == "VIEW":
            if terms & _READ_TERMS:
                selected.append(code)
            continue
        if terms & _HIGH_RISK_TERMS:
            continue
        if terms & (_READ_TERMS | _EDIT_TERMS):
            selected.append(code)
    return sorted(set(selected))


def _enabled_feature_codes(company: Company) -> set[str]:
    matrix = feature_matrix(company=company)
    return {str(item["code"]) for item in matrix["items"] if bool(item["enabled"])}


def _package_permission_codes(company: Company) -> set[str]:
    return set(company_user_permission_codes(company))


def _prefix_match(code: str, prefixes: tuple[str, ...]) -> bool:
    return any(code.startswith(prefix) for prefix in prefixes)


def access_area_catalog(company: Company) -> list[dict[str, object]]:
    enabled_features = _enabled_feature_codes(company)
    allowed_codes = _package_permission_codes(company)
    catalog: list[dict[str, object]] = []

    for code, definition in ACCESS_AREAS.items():
        features = tuple(str(value) for value in definition["features"])
        if not enabled_features.intersection(features):
            continue
        prefixes = tuple(str(value) for value in definition["prefixes"])
        area_codes = sorted(permission for permission in allowed_codes if _prefix_match(permission, prefixes))
        if not area_codes:
            continue
        catalog.append(
            {
                "code": code,
                "label": str(definition["label"]),
                "description": str(definition["description"]),
                "permission_counts": {
                    "VIEW": len(filter_permission_codes_for_level(area_codes, "VIEW")),
                    "EDIT": len(filter_permission_codes_for_level(area_codes, "EDIT")),
                    "FULL": len(area_codes),
                },
            }
        )
    return catalog


def changed_access_levels(
    before: Mapping[str, str],
    after: Mapping[str, str],
) -> list[dict[str, str]]:
    """Return deterministic semantic access changes for audit/UI rendering."""
    items: list[dict[str, str]] = []
    for area_code in sorted(set(before) | set(after)):
        old_level = str(before.get(area_code, "NONE")).upper()
        new_level = str(after.get(area_code, "NONE")).upper()
        if old_level == new_level:
            continue
        items.append(
            {
                "area_code": area_code,
                "before": old_level,
                "after": new_level,
            }
        )
    return items


def normalize_access_levels(*, company: Company, access_levels: Mapping[str, str]) -> dict[str, str]:
    available_codes = {str(item["code"]) for item in access_area_catalog(company)}
    normalized_input = {
        str(key).strip().upper(): str(value).strip().upper()
        for key, value in access_levels.items()
    }
    unknown_areas = sorted(set(normalized_input) - available_codes)
    if unknown_areas:
        raise ValidationError({"access_levels": f"Unavailable package areas: {', '.join(unknown_areas)}"})
    invalid_levels = sorted({level for level in normalized_input.values() if level not in ACCESS_LEVELS})
    if invalid_levels:
        raise ValidationError({"access_levels": f"Unsupported access levels: {', '.join(invalid_levels)}"})
    return {area_code: normalized_input.get(area_code, "NONE") for area_code in sorted(available_codes)}


def _area_permission_codes(company: Company, area_code: str, level: str) -> list[str]:
    definition = ACCESS_AREAS.get(area_code)
    if definition is None:
        return []
    allowed_codes = _package_permission_codes(company)
    prefixes = tuple(str(value) for value in definition["prefixes"])
    area_codes = sorted(permission for permission in allowed_codes if _prefix_match(permission, prefixes))
    return filter_permission_codes_for_level(area_codes, level)


def _shared_permission_codes(company: Company, level: str) -> list[str]:
    allowed_codes = _package_permission_codes(company)
    shared = sorted(
        permission
        for permission in allowed_codes
        if _prefix_match(permission, SHARED_TENANT_PERMISSION_PREFIXES)
    )
    return filter_permission_codes_for_level(shared, level)


def _current_role(company: Company, code: str) -> Role | None:
    return (
        Role.objects.filter(company_public_id=company.public_id, code=code, retired_at__isnull=True)
        .order_by("-version")
        .first()
    )


def _sync_role(
    *,
    company: Company,
    code: str,
    name: str,
    permission_codes: list[str],
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> tuple[Role, uuid.UUID | None]:
    current = _current_role(company, code)
    desired = set(permission_codes)
    previous_public_id: uuid.UUID | None = None
    if current is not None:
        current_codes = set(current.permission_grants.values_list("permission__code", flat=True))
        if current_codes == desired:
            return current, None
        previous_public_id = current.public_id
    role = create_role(
        company=company,
        code=code,
        name=name,
        permission_codes=sorted(desired),
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
    )
    return role, previous_public_id


def _area_role_code(area_code: str, level: str) -> str:
    return f"{MANAGED_ACCESS_ROLE_PREFIX}{area_code}_{level}"


def _shared_role_code(level: str) -> str:
    return f"{SHARED_ROLE_PREFIX}{level}"


def _sync_area_role(
    *,
    company: Company,
    area_code: str,
    level: str,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> tuple[Role, uuid.UUID | None]:
    definition = ACCESS_AREAS[area_code]
    return _sync_role(
        company=company,
        code=_area_role_code(area_code, level),
        name=f"{definition['label']} · {level.title()}",
        permission_codes=_area_permission_codes(company, area_code, level),
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
    )


def _sync_shared_role(
    *,
    company: Company,
    level: str,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> tuple[Role, uuid.UUID | None]:
    return _sync_role(
        company=company,
        code=_shared_role_code(level),
        name=f"Shared utilities · {level.title()}",
        permission_codes=_shared_permission_codes(company, level),
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
    )


def _sync_no_access_role(
    *,
    company: Company,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> tuple[Role, uuid.UUID | None]:
    return _sync_role(
        company=company,
        code=NO_ACCESS_ROLE_CODE,
        name="No business access",
        permission_codes=[],
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
    )


def managed_role_public_ids_for_levels(
    *,
    company: Company,
    access_levels: Mapping[str, str],
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> tuple[list[uuid.UUID], dict[str, str]]:
    normalized = normalize_access_levels(company=company, access_levels=access_levels)
    role_ids: list[uuid.UUID] = []
    rank = {"NONE": 0, "VIEW": 1, "EDIT": 2, "FULL": 3}
    highest_rank = 0

    for area_code, level in normalized.items():
        highest_rank = max(highest_rank, rank[level])
        if level == "NONE":
            continue
        role, _ = _sync_area_role(
            company=company,
            area_code=area_code,
            level=level,
            actor_public_id=actor_public_id,
            correlation_id=correlation_id,
        )
        role_ids.append(role.public_id)

    if highest_rank == 0:
        role, _ = _sync_no_access_role(
            company=company,
            actor_public_id=actor_public_id,
            correlation_id=correlation_id,
        )
        role_ids.append(role.public_id)
    else:
        shared_level = {1: "VIEW", 2: "EDIT", 3: "FULL"}[highest_rank]
        if _shared_permission_codes(company, shared_level):
            shared_role, _ = _sync_shared_role(
                company=company,
                level=shared_level,
                actor_public_id=actor_public_id,
                correlation_id=correlation_id,
            )
            role_ids.append(shared_role.public_id)

    return role_ids, normalized


def _parse_managed_role_code(code: str) -> tuple[str, str] | None:
    if code == NO_ACCESS_ROLE_CODE:
        return ("NONE", "NONE")
    if code.startswith(SHARED_ROLE_PREFIX):
        return ("SHARED", code[len(SHARED_ROLE_PREFIX):])
    if not code.startswith(MANAGED_ACCESS_ROLE_PREFIX):
        return None
    suffix = code[len(MANAGED_ACCESS_ROLE_PREFIX):]
    if "_" not in suffix:
        return None
    area_code, level = suffix.rsplit("_", 1)
    if area_code not in ACCESS_AREAS or level not in ACCESS_LEVELS:
        return None
    return (area_code, level)


def _active_roles(membership: Membership, at) -> list[Role]:
    role_ids = (
        membership.role_assignments.filter(effective_from__lte=at)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=at))
        .values_list("role_public_id", flat=True)
    )
    return list(
        Role.objects.filter(
            public_id__in=role_ids,
            company_public_id=membership.company.public_id,
            retired_at__isnull=True,
        ).order_by("code")
    )


def _is_admin_membership(
    *,
    membership: Membership,
    roles: list[Role],
    profile: CompanyAccessProfile | None,
) -> bool:
    if (
        profile is not None
        and profile.primary_admin_email.strip()
        and membership.user.email.strip().lower() == profile.primary_admin_email.strip().lower()
    ):
        return True
    return any(
        role.code == STANDARD_COMPANY_ADMIN_ROLE_CODE
        or role.code in LEGACY_COMPANY_ADMIN_ROLE_CODES
        or role.name.strip().lower() == "company administrator"
        for role in roles
    )


def _access_profile_for_membership(
    *,
    membership: Membership,
    areas: list[dict[str, object]],
    profile: CompanyAccessProfile | None,
    at,
) -> dict[str, object]:
    roles = _active_roles(membership, at)
    area_codes = [str(area["code"]) for area in areas]
    levels = {code: "NONE" for code in area_codes}

    if _is_admin_membership(membership=membership, roles=roles, profile=profile):
        return {
            "membership_public_id": str(membership.public_id),
            "levels": {code: "FULL" for code in area_codes},
            "locked": True,
            "locked_reason": "Company Administrator access is governed separately.",
            "access_source": "ADMIN",
        }

    custom_roles = [
        role
        for role in roles
        if role.code != STANDARD_COMPANY_USER_ROLE_CODE
        and not role.code.startswith(MANAGED_ACCESS_ROLE_PREFIX)
    ]
    if custom_roles:
        return {
            "membership_public_id": str(membership.public_id),
            "levels": levels,
            "locked": True,
            "locked_reason": "This user has a custom governed role. Use advanced access governance.",
            "access_source": "CUSTOM",
        }

    if any(role.code == STANDARD_COMPANY_USER_ROLE_CODE for role in roles):
        levels = {code: "FULL" for code in area_codes}
        source = "FULL_PACKAGE"
    else:
        source = "MANAGED"
        for role in roles:
            parsed = _parse_managed_role_code(role.code)
            if parsed is None:
                continue
            area_code, level = parsed
            if area_code in levels and level in ACCESS_LEVELS:
                levels[area_code] = level

    locked = membership.terminated_at is not None
    return {
        "membership_public_id": str(membership.public_id),
        "levels": levels,
        "locked": locked,
        "locked_reason": "Removed users are locked." if locked else "",
        "access_source": source,
    }


def managed_access_matrix(company: Company) -> dict[str, object]:
    now = timezone.now()
    areas = access_area_catalog(company)
    profile = CompanyAccessProfile.objects.filter(company=company).first()
    memberships = list(
        Membership.objects.filter(company=company)
        .select_related("user")
        .order_by("user__display_name", "user__email")[:500]
    )
    return {
        "levels": [
            {"code": "NONE", "label": "No access"},
            {"code": "VIEW", "label": "View only"},
            {"code": "EDIT", "label": "Read + edit"},
            {"code": "FULL", "label": "Full"},
        ],
        "areas": areas,
        "people": [
            _access_profile_for_membership(
                membership=membership,
                areas=areas,
                profile=profile,
                at=now,
            )
            for membership in memberships
        ],
    }


def managed_access_history(
    *,
    company: Company,
    membership: Membership,
    limit: int = 50,
) -> dict[str, object]:
    safe_limit = max(1, min(int(limit), 100))
    events = list(
        AuditEvent.objects.filter(
            company_public_id=company.public_id,
            action="access.managed_profile.updated",
            entity_type="membership",
            entity_public_id=membership.public_id,
        ).order_by("-occurred_at", "-pk")[:safe_limit]
    )
    actor_ids = {
        event.actor_public_id
        for event in events
        if event.actor_public_id is not None
    }
    actors = {
        str(user.public_id): {
            "display_name": user.display_name,
            "email": user.email,
        }
        for user in User.objects.filter(public_id__in=actor_ids)
    }

    items: list[dict[str, object]] = []
    for event in events:
        before_levels = dict(event.before.get("access_levels", {}))
        after_levels = dict(event.after.get("access_levels", {}))
        actor = actors.get(str(event.actor_public_id)) if event.actor_public_id else None
        items.append(
            {
                "public_id": str(event.public_id),
                "occurred_at": event.occurred_at.isoformat(),
                "actor_public_id": str(event.actor_public_id) if event.actor_public_id else None,
                "actor_display_name": actor["display_name"] if actor else "System",
                "actor_email": actor["email"] if actor else "",
                "reason_code": event.reason_code,
                "correlation_id": str(event.correlation_id),
                "before_levels": before_levels,
                "after_levels": after_levels,
                "changes": changed_access_levels(before_levels, after_levels),
            }
        )
    return {"items": items}


@transaction.atomic
def set_membership_managed_access(
    *,
    membership: Membership,
    access_levels: Mapping[str, str],
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    reason_code: str = "company-admin-permission-change",
) -> dict[str, str]:
    locked = (
        Membership.objects.select_for_update()
        .select_related("company", "user")
        .get(pk=membership.pk)
    )
    if locked.terminated_at is not None:
        raise ValidationError("Removed users cannot receive access changes")

    now = timezone.now()
    profile = CompanyAccessProfile.objects.filter(company=locked.company).first()
    roles = _active_roles(locked, now)
    areas = access_area_catalog(locked.company)
    before_profile = _access_profile_for_membership(
        membership=locked,
        areas=areas,
        profile=profile,
        at=now,
    )
    before_levels = dict(before_profile["levels"])
    if _is_admin_membership(membership=locked, roles=roles, profile=profile):
        raise ValidationError(
            "Company Administrator access cannot be changed from the user permission matrix"
        )

    custom_roles = [
        role
        for role in roles
        if role.code != STANDARD_COMPANY_USER_ROLE_CODE
        and not role.code.startswith(MANAGED_ACCESS_ROLE_PREFIX)
    ]
    if custom_roles:
        raise ValidationError(
            "This user has a custom governed role and cannot be changed from the simple permission matrix"
        )

    role_ids, normalized = managed_role_public_ids_for_levels(
        company=locked.company,
        access_levels=access_levels,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
    )
    replace_membership_roles(
        membership=locked,
        role_public_ids=role_ids,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
    )

    changes = changed_access_levels(before_levels, normalized)
    if changes:
        append_audit(
            AuditRecord(
                action="access.managed_profile.updated",
                entity_type="membership",
                entity_public_id=locked.public_id,
                actor_public_id=actor_public_id,
                actor_type="user",
                company_public_id=locked.company.public_id,
                request_id=correlation_id,
                correlation_id=correlation_id,
                reason_code=reason_code.strip() or "company-admin-permission-change",
                before={"access_levels": before_levels},
                after={
                    "access_levels": normalized,
                    "changes": changes,
                    "user_public_id": str(locked.user.public_id),
                },
            )
        )
    return normalized


@transaction.atomic
def reconcile_managed_access_roles(
    *,
    company: Company,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> int:
    current_roles = list(
        Role.objects.filter(
            company_public_id=company.public_id,
            code__startswith=MANAGED_ACCESS_ROLE_PREFIX,
            retired_at__isnull=True,
        ).order_by("code")
    )
    replacements: dict[str, str] = {}
    changed = 0

    for current in current_roles:
        parsed = _parse_managed_role_code(current.code)
        if parsed is None:
            continue
        area_code, level = parsed
        if area_code == "NONE":
            desired_codes: list[str] = []
            name = "No business access"
        elif area_code == "SHARED":
            desired_codes = _shared_permission_codes(company, level)
            name = f"Shared utilities · {level.title()}"
        else:
            desired_codes = _area_permission_codes(company, area_code, level)
            name = f"{ACCESS_AREAS[area_code]['label']} · {level.title()}"

        current_codes = set(current.permission_grants.values_list("permission__code", flat=True))
        if current_codes == set(desired_codes):
            continue

        new_role = create_role(
            company=company,
            code=current.code,
            name=name,
            permission_codes=desired_codes,
            actor_public_id=actor_public_id,
            correlation_id=correlation_id,
        )
        replacements[str(current.public_id)] = str(new_role.public_id)
        changed += 1

    if replacements:
        pending = AccessInvitation.objects.filter(
            company=company,
            accepted_at__isnull=True,
            revoked_at__isnull=True,
        )
        for invitation in pending:
            original = [str(role_id) for role_id in invitation.role_public_ids]
            updated_ids = [replacements.get(role_id, role_id) for role_id in original]
            if updated_ids != original:
                invitation.role_public_ids = updated_ids
                invitation.version += 1
                invitation.save(update_fields=["role_public_ids", "version", "updated_at"])

    return changed
