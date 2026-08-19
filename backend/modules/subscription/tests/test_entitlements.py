import uuid
from collections.abc import Callable
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from modules.subscription.application.entitlements import effective_entitlements
from modules.subscription.models import CompanySubscription, EntitlementOverride, PlanVersion
from modules.tenant.models import Company


@pytest.mark.django_db
def test_plan_and_effective_override_are_merged(
    company_factory: Callable[..., Company],
) -> None:
    company = company_factory()
    plan = PlanVersion.objects.create(
        code="TEST",
        version=1,
        name="Test plan",
        status=PlanVersion.Status.PUBLISHED,
        entitlements={"workflow": True, "files": False},
        limits={"users": 25},
        effective_from=timezone.now() - timedelta(days=1),
        published_at=timezone.now() - timedelta(days=1),
    )
    CompanySubscription.objects.create(
        company=company,
        plan_version=plan,
        status=CompanySubscription.Status.ACTIVE,
        starts_at=timezone.now() - timedelta(hours=1),
    )
    EntitlementOverride.objects.create(
        company=company,
        entitlement_code="files",
        enabled=True,
        limit_value=100,
        effective_from=timezone.now() - timedelta(minutes=1),
        reason_code="pilot_enablement",
        set_by_public_id=uuid.uuid4(),
    )

    effective = effective_entitlements(company=company)

    assert effective.plan_code == "TEST"
    assert effective.entitlements == {"workflow": True, "files": True}
    assert effective.limits == {"users": 25, "files": 100}


@pytest.mark.django_db
def test_published_plan_is_immutable() -> None:
    plan = PlanVersion.objects.create(
        code="IMMUTABLE",
        version=1,
        name="Immutable plan",
        status=PlanVersion.Status.PUBLISHED,
        entitlements={},
        limits={},
        effective_from=timezone.now() - timedelta(days=1),
        published_at=timezone.now() - timedelta(days=1),
    )
    plan.name = "Changed"

    with pytest.raises(ValidationError, match="immutable"):
        plan.save()


@pytest.mark.django_db
def test_expired_grace_subscription_is_not_effective(
    company_factory: Callable[..., Company],
) -> None:
    company = company_factory()
    plan = PlanVersion.objects.create(
        code="GRACE",
        version=1,
        name="Grace plan",
        status=PlanVersion.Status.PUBLISHED,
        entitlements={"workflow": True},
        limits={},
        effective_from=timezone.now() - timedelta(days=2),
        published_at=timezone.now() - timedelta(days=2),
    )
    CompanySubscription.objects.create(
        company=company,
        plan_version=plan,
        status=CompanySubscription.Status.GRACE,
        starts_at=timezone.now() - timedelta(days=2),
        grace_until=timezone.now() - timedelta(minutes=1),
    )

    effective = effective_entitlements(company=company)

    assert effective.subscription_status == "NONE"
    assert effective.plan_code is None
    assert effective.entitlements == {}
