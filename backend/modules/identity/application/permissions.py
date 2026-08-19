import uuid
from collections.abc import Iterable

from django.db.models import Q
from django.utils import timezone

from modules.identity.models import Permission, RolePermission


def has_permission(
    *,
    company_public_id: uuid.UUID,
    role_public_ids: Iterable[uuid.UUID],
    permission_code: str,
) -> bool:
    now = timezone.now()
    return RolePermission.objects.filter(
        role__public_id__in=tuple(role_public_ids),
        role__company_public_id=company_public_id,
        role__effective_from__lte=now,
        role__retired_at__isnull=True,
        permission__code=permission_code,
    ).filter(Q(role__effective_to__isnull=True) | Q(role__effective_to__gt=now)).exists()



def effective_permission_codes(
    *,
    company_public_id: uuid.UUID,
    role_public_ids: Iterable[uuid.UUID],
) -> set[str]:
    now = timezone.now()
    return set(
        Permission.objects.filter(
            role_grants__role__public_id__in=tuple(role_public_ids),
            role_grants__role__company_public_id=company_public_id,
            role_grants__role__effective_from__lte=now,
            role_grants__role__retired_at__isnull=True,
        )
        .filter(
            Q(role_grants__role__effective_to__isnull=True)
            | Q(role_grants__role__effective_to__gt=now)
        )
        .values_list("code", flat=True)
        .distinct()
    )
