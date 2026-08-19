from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from rest_framework.views import APIView

from modules.controlplane.models import PlatformOperatorAssignment
from modules.identity.application.tokens import AccessPrincipal
from modules.platform.audit import request_metadata


@dataclass(frozen=True, slots=True)
class PlatformActor:
    user_public_id: uuid.UUID
    operator_assignment_public_id: uuid.UUID
    request_id: uuid.UUID
    ip_address: str | None
    user_agent: str


@dataclass(frozen=True, slots=True)
class PlatformContext:
    principal: AccessPrincipal
    assignments: tuple[PlatformOperatorAssignment, ...]
    permission_codes: frozenset[str]

    @property
    def primary_assignment(self) -> PlatformOperatorAssignment:
        return self.assignments[0]

    def can(self, permission_code: str) -> bool:
        return permission_code in self.permission_codes

    def require(self, permission_code: str) -> None:
        if not self.can(permission_code):
            raise PermissionDenied("Platform operator permission denied")


def resolve_platform_context(request: Request) -> PlatformContext:
    if not isinstance(request.auth, AccessPrincipal):
        raise PermissionDenied("An authenticated platform session is required")
    now = timezone.now()
    assignments = tuple(
        PlatformOperatorAssignment.objects.select_related("role", "user")
        .prefetch_related("role__permission_grants__permission")
        .filter(
            user=request.auth.user,
            user__is_active=True,
            suspended_at__isnull=True,
            effective_from__lte=now,
            role__retired_at__isnull=True,
            role__effective_from__lte=now,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now))
        .filter(Q(role__effective_to__isnull=True) | Q(role__effective_to__gt=now))
        .order_by("role__code", "-role__version")
    )
    if not assignments:
        raise PermissionDenied("Platform operator access is required")
    permissions = {
        grant.permission.code
        for assignment in assignments
        for grant in assignment.role.permission_grants.all()
    }
    context = PlatformContext(
        principal=request.auth,
        assignments=assignments,
        permission_codes=frozenset(permissions),
    )
    request.platform_context = context  # type: ignore[attr-defined]
    return context


def platform_actor(request: Request, context: PlatformContext) -> PlatformActor:
    request_id, ip_address, user_agent = request_metadata(request._request)
    return PlatformActor(
        user_public_id=context.principal.user.public_id,
        operator_assignment_public_id=context.primary_assignment.public_id,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )


class PlatformScopedAPIView(APIView):
    platform_context: PlatformContext

    def initial(self, request: Request, *args: Any, **kwargs: Any) -> None:
        super().initial(request, *args, **kwargs)
        self.platform_context = resolve_platform_context(request)
