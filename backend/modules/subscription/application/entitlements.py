from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from django.db.models import Q
from django.utils import timezone

from modules.subscription.models import (
    CompanySubscription,
    EntitlementOverride,
    PlanVersion,
)
from modules.tenant.models import Company


@dataclass(frozen=True, slots=True)
class EffectiveEntitlements:
    subscription_status: str
    plan_code: str | None
    plan_version: int | None
    entitlements: dict[str, bool]
    limits: dict[str, int | None]

    def allows(self, code: str) -> bool:
        return self.entitlements.get(code, False)


def effective_entitlements(
    *,
    company: Company,
    at: datetime | None = None,
) -> EffectiveEntitlements:
    moment = at or timezone.now()
    subscription = (
        CompanySubscription.objects.select_related("plan_version")
        .filter(
            company=company,
            starts_at__lte=moment,
            plan_version__status=PlanVersion.Status.PUBLISHED,
            plan_version__effective_from__lte=moment,
        )
        .filter(
            Q(plan_version__effective_to__isnull=True)
            | Q(plan_version__effective_to__gt=moment)
        )
        .filter(
            Q(
                status__in=[
                    CompanySubscription.Status.TRIAL,
                    CompanySubscription.Status.ACTIVE,
                ]
            )
            | Q(
                status=CompanySubscription.Status.GRACE,
                grace_until__gt=moment,
            )
        )
        .filter(Q(ends_at__isnull=True) | Q(ends_at__gt=moment))
        .order_by("-starts_at")
        .first()
    )
    entitlements: dict[str, bool] = {}
    limits: dict[str, int | None] = {}
    status = "NONE"
    plan_code: str | None = None
    plan_version: int | None = None
    if subscription:
        status = subscription.status
        plan_code = subscription.plan_version.code
        plan_version = subscription.plan_version.version
        if isinstance(subscription.plan_version.entitlements, dict):
            entitlements = {
                str(code): bool(enabled)
                for code, enabled in subscription.plan_version.entitlements.items()
            }
        if isinstance(subscription.plan_version.limits, dict):
            for code, value in subscription.plan_version.limits.items():
                limits[str(code)] = value if isinstance(value, int) and value >= 0 else None
    overrides = (
        EntitlementOverride.objects.filter(
            company=company,
            effective_from__lte=moment,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=moment))
        .order_by("entitlement_code", "-effective_from")
    )
    seen: set[str] = set()
    for override in overrides:
        if override.entitlement_code in seen:
            continue
        seen.add(override.entitlement_code)
        entitlements[override.entitlement_code] = override.enabled
        if override.limit_value is not None:
            limits[override.entitlement_code] = override.limit_value
    return EffectiveEntitlements(
        subscription_status=status,
        plan_code=plan_code,
        plan_version=plan_version,
        entitlements=entitlements,
        limits=limits,
    )


def require_entitlement(*, company: Company, code: str) -> None:
    if not effective_entitlements(company=company).allows(code):
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied("This capability is not included in the active subscription")
