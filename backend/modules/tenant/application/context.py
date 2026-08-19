import uuid
from dataclasses import dataclass

from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.request import Request

from modules.identity.application.permissions import (
    effective_permission_codes,
    has_permission,
)
from modules.identity.application.tokens import AccessPrincipal
from modules.tenant.models import Company, Membership

COMPANY_HEADER = "HTTP_X_COMPANY_ID"


@dataclass(frozen=True, slots=True)
class TenantContext:
    company: Company
    membership: Membership
    principal: AccessPrincipal

    def can(self, permission_code: str) -> bool:
        now = timezone.now()
        role_ids = self.membership.role_assignments.filter(
            effective_from__lte=now,
        ).filter(
            Q(effective_to__isnull=True) | Q(effective_to__gt=now)
        ).values_list("role_public_id", flat=True)
        return has_permission(
            company_public_id=self.company.public_id,
            role_public_ids=role_ids,
            permission_code=permission_code,
        )

    def role_public_ids(self) -> set[uuid.UUID]:
        now = timezone.now()
        return set(
            self.membership.role_assignments.filter(
                effective_from__lte=now,
            )
            .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now))
            .values_list("role_public_id", flat=True)
        )

    def permission_codes(self) -> set[str]:
        return effective_permission_codes(
            company_public_id=self.company.public_id,
            role_public_ids=self.role_public_ids(),
        )

    def require(self, permission_code: str) -> None:
        if not self.can(permission_code):
            raise PermissionDenied("Permission denied")


def resolve_tenant_context(request: Request) -> TenantContext:
    if not isinstance(request.auth, AccessPrincipal):
        raise PermissionDenied("An authenticated session is required")
    user = request.auth.user
    raw_company_id = request.META.get(COMPANY_HEADER)
    try:
        company_public_id = uuid.UUID(raw_company_id)
    except (TypeError, ValueError, AttributeError) as exc:
        raise PermissionDenied("A valid tenant context is required") from exc

    now = timezone.now()
    membership = (
        Membership.objects.select_related("company", "user")
        .filter(
            company__public_id=company_public_id,
            company__is_active=True,
            user=user,
            user__is_active=True,
            effective_from__lte=now,
            suspended_at__isnull=True,
            terminated_at__isnull=True,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now))
        .first()
    )
    if not membership:
        raise NotFound("Resource not found")
    context = TenantContext(
        company=membership.company,
        membership=membership,
        principal=request.auth,
    )
    request.tenant_context = context  # type: ignore[attr-defined]
    return context
