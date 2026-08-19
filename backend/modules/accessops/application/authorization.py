from __future__ import annotations

from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request

from modules.accessops.models import PlatformOperator
from modules.identity.application.tokens import AccessPrincipal


def require_platform_operator(request: Request) -> PlatformOperator:
    if not isinstance(request.auth, AccessPrincipal):
        raise PermissionDenied("An authenticated platform session is required")
    operator = (
        PlatformOperator.objects.select_related("user")
        .filter(user=request.auth.user, is_active=True, user__is_active=True)
        .first()
    )
    if not operator:
        raise PermissionDenied("Platform operator access is required")
    return operator
