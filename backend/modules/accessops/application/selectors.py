from __future__ import annotations

from django.db.models import Count, Q
from django.utils import timezone

from modules.accessops.models import AccessInvitation, PlatformOperator
from modules.identity.models import Permission, Role, User
from modules.tenant.models import Company, Membership


def _primary_admin_summary(company: Company, now) -> dict[str, object] | None:
    profile = getattr(company, "accessops_profile", None)
    if profile is None or not profile.primary_admin_email.strip():
        return None
    email = profile.primary_admin_email.strip().lower()
    user = User.objects.filter(email__iexact=email).first()
    active_membership = bool(
        user
        and Membership.objects.filter(
            company=company,
            user=user,
            suspended_at__isnull=True,
            terminated_at__isnull=True,
        ).exists()
    )
    invitation = (
        AccessInvitation.objects.filter(
            company=company,
            email__iexact=email,
            invitation_type_code="COMPANY_ADMIN",
        )
        .order_by("-created_at")
        .first()
    )
    if active_membership:
        status = "ACTIVE"
    elif invitation is None:
        status = "NOT_INVITED"
    elif invitation.accepted_at is not None:
        status = "ACCEPTED"
    elif invitation.revoked_at is not None:
        status = "REVOKED"
    elif invitation.expires_at <= now:
        status = "EXPIRED"
    else:
        status = "INVITE_PENDING"
    return {
        "email": email,
        "display_name": (invitation.display_name if invitation else "") or (user.display_name if user else ""),
        "status": status,
        "invitation_public_id": str(invitation.public_id) if invitation else None,
        "expires_at": invitation.expires_at.isoformat() if invitation else None,
        "accepted_at": invitation.accepted_at.isoformat() if invitation and invitation.accepted_at else None,
        "delivery_status_code": invitation.delivery_status_code if invitation else "NOT_ATTEMPTED",
        "delivery_attempted_at": invitation.delivery_attempted_at.isoformat() if invitation and invitation.delivery_attempted_at else None,
        "delivery_error_code": invitation.delivery_error_code if invitation else "",
        "delivery_brand_name": (invitation.delivery_brand_snapshot or {}).get("product_name", "") if invitation else "",
    }


def platform_overview() -> dict[str, object]:
    now = timezone.now()
    company_counts = Company.objects.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True, closed_at__isnull=True)),
        suspended=Count("id", filter=Q(is_active=False, suspended_at__isnull=False)),
    )
    return {
        "generated_at": now.isoformat(),
        "summary": {
            "company_count": company_counts["total"] or 0,
            "active_company_count": company_counts["active"] or 0,
            "suspended_company_count": company_counts["suspended"] or 0,
            "active_operator_count": PlatformOperator.objects.filter(is_active=True).count(),
            "pending_admin_invitation_count": AccessInvitation.objects.filter(
                invitation_type_code="COMPANY_ADMIN",
                accepted_at__isnull=True,
                revoked_at__isnull=True,
                expires_at__gt=now,
            ).count(),
            "membership_count": Membership.objects.filter(
                suspended_at__isnull=True,
                terminated_at__isnull=True,
            ).count(),
        },
        "companies": [
            {
                "public_id": str(company.public_id),
                "code": company.code,
                "legal_name": company.legal_name,
                "display_name": company.display_name,
                "locale": company.locale,
                "timezone": company.timezone,
                "currency": company.currency,
                "unit_system_code": company.unit_system_code,
                "is_active": company.is_active,
                "suspended_at": company.suspended_at.isoformat() if company.suspended_at else None,
                "membership_count": company.memberships.filter(
                    suspended_at__isnull=True,
                    terminated_at__isnull=True,
                ).count(),
                "plan_code": getattr(getattr(company, "accessops_profile", None), "plan_code", ""),
                "onboarding_status_code": getattr(
                    getattr(company, "accessops_profile", None),
                    "onboarding_status_code",
                    "UNTRACKED",
                ),
                "primary_admin": _primary_admin_summary(company, now),
            }
            for company in Company.objects.select_related("accessops_profile").order_by("display_name")[:200]
        ],
        "recent_invitations": [
            {
                "public_id": str(invitation.public_id),
                "company_public_id": str(invitation.company.public_id),
                "company_name": invitation.company.display_name,
                "email": invitation.email,
                "display_name": invitation.display_name,
                "invitation_type_code": invitation.invitation_type_code,
                "expires_at": invitation.expires_at.isoformat(),
                "accepted_at": invitation.accepted_at.isoformat() if invitation.accepted_at else None,
                "revoked_at": invitation.revoked_at.isoformat() if invitation.revoked_at else None,
                "delivery_status_code": invitation.delivery_status_code,
                "delivery_attempted_at": invitation.delivery_attempted_at.isoformat() if invitation.delivery_attempted_at else None,
                "delivery_sent_at": invitation.delivery_sent_at.isoformat() if invitation.delivery_sent_at else None,
                "delivery_error_code": invitation.delivery_error_code,
                "delivery_brand_name": (invitation.delivery_brand_snapshot or {}).get("product_name", ""),
            }
            for invitation in AccessInvitation.objects.select_related("company").order_by("-created_at")[:50]
        ],
    }


def company_overview(company: Company) -> dict[str, object]:
    now = timezone.now()
    memberships = Membership.objects.filter(company=company).select_related("user")
    invitations = AccessInvitation.objects.filter(company=company)
    return {
        "generated_at": now.isoformat(),
        "company": {
            "public_id": str(company.public_id),
            "code": company.code,
            "display_name": company.display_name,
            "locale": company.locale,
            "timezone": company.timezone,
            "currency": company.currency,
        },
        "summary": {
            "active_people_count": memberships.filter(
                suspended_at__isnull=True, terminated_at__isnull=True
            ).count(),
            "suspended_people_count": memberships.filter(suspended_at__isnull=False).count(),
            "active_role_count": Role.objects.filter(
                company_public_id=company.public_id,
                retired_at__isnull=True,
            ).count(),
            "permission_catalog_count": Permission.objects.count(),
            "pending_invitation_count": invitations.filter(
                accepted_at__isnull=True,
                revoked_at__isnull=True,
                expires_at__gt=now,
            ).count(),
        },
        "people": [
            {
                "membership_public_id": str(membership.public_id),
                "user_public_id": str(membership.user.public_id),
                "email": membership.user.email,
                "display_name": membership.user.display_name,
                "is_active": membership.user.is_active,
                "suspended_at": membership.suspended_at.isoformat() if membership.suspended_at else None,
                "terminated_at": membership.terminated_at.isoformat() if membership.terminated_at else None,
                "employee": (
                    {
                        "employee_number": membership.employee.employee_number,
                        "job_title": membership.employee.job_title,
                        "employment_start": membership.employee.employment_start.isoformat(),
                    }
                    if hasattr(membership, "employee")
                    else None
                ),
                "roles": [
                    {
                        "public_id": str(role.public_id),
                        "code": role.code,
                        "name": role.name,
                    }
                    for role in Role.objects.filter(
                        public_id__in=membership.role_assignments.filter(
                            effective_from__lte=now,
                        ).filter(
                            Q(effective_to__isnull=True) | Q(effective_to__gt=now)
                        ).values_list("role_public_id", flat=True),
                        company_public_id=company.public_id,
                        retired_at__isnull=True,
                    ).order_by("name")
                ],
            }
            for membership in memberships.order_by("user__display_name")[:500]
        ],
        "roles": [
            {
                "public_id": str(role.public_id),
                "code": role.code,
                "name": role.name,
                "version": role.version,
                "permission_codes": list(
                    role.permission_grants.values_list("permission__code", flat=True).order_by(
                        "permission__code"
                    )
                ),
            }
            for role in Role.objects.filter(
                company_public_id=company.public_id, retired_at__isnull=True
            ).prefetch_related("permission_grants__permission").order_by("name")[:300]
        ],
        "permissions": [
            {"code": permission.code, "description": permission.description}
            for permission in Permission.objects.order_by("code")[:1000]
        ],
        "invitations": [
            {
                "public_id": str(invitation.public_id),
                "email": invitation.email,
                "display_name": invitation.display_name,
                "invitation_type_code": invitation.invitation_type_code,
                "employee_number": invitation.employee_number,
                "job_title": invitation.job_title,
                "expires_at": invitation.expires_at.isoformat(),
                "accepted_at": invitation.accepted_at.isoformat() if invitation.accepted_at else None,
                "revoked_at": invitation.revoked_at.isoformat() if invitation.revoked_at else None,
                "delivery_status_code": invitation.delivery_status_code,
                "delivery_attempted_at": invitation.delivery_attempted_at.isoformat() if invitation.delivery_attempted_at else None,
                "delivery_sent_at": invitation.delivery_sent_at.isoformat() if invitation.delivery_sent_at else None,
                "delivery_error_code": invitation.delivery_error_code,
                "delivery_brand_name": (invitation.delivery_brand_snapshot or {}).get("product_name", ""),
            }
            for invitation in invitations.order_by("-created_at")[:300]
        ],
    }
