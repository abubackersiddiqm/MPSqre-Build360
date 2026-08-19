import uuid
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from modules.controlplane.application.context import PlatformActor
from modules.controlplane.application.services import (
    assign_subscription,
    collect_usage_snapshot,
    create_support_access_request,
    transition_tenant_lifecycle,
)
from modules.controlplane.models import (
    PlatformOperatorAssignment,
    PlatformRole,
    SupportAccessRequest,
    TenantAccount,
)
from modules.subscription.models import CompanySubscription, PlanVersion


@pytest.fixture
def platform_context(user_factory):
    user = user_factory(email="operator@example.test")
    role = PlatformRole.objects.create(
        code="TEST_OPERATOR",
        name="Test operator",
        effective_from=timezone.now() - timedelta(minutes=1),
    )
    assignment = PlatformOperatorAssignment.objects.create(
        user=user,
        role=role,
        assigned_by_public_id=user.public_id,
        effective_from=timezone.now() - timedelta(minutes=1),
    )
    actor = PlatformActor(
        user_public_id=user.public_id,
        operator_assignment_public_id=assignment.public_id,
        request_id=uuid.uuid4(),
        ip_address="127.0.0.1",
        user_agent="pytest",
    )
    return user, assignment, actor


@pytest.mark.django_db
def test_tenant_lifecycle_uses_optimistic_version_and_suspends_company(
    company_factory,
    platform_context,
):
    company = company_factory()
    tenant = TenantAccount.objects.create(
        company=company,
        lifecycle_status=TenantAccount.LifecycleStatus.PILOT,
        onboarding_status=TenantAccount.OnboardingStatus.LIVE,
        pilot_started_at=timezone.now(),
    )
    suspended = transition_tenant_lifecycle(
        tenant_public_id=tenant.public_id,
        target_status=TenantAccount.LifecycleStatus.SUSPENDED,
        expected_version=tenant.version,
        reason="pilot paused",
        actor=platform_context[2],
    )
    company.refresh_from_db()
    assert suspended.lifecycle_status == TenantAccount.LifecycleStatus.SUSPENDED
    assert company.is_active is False
    with pytest.raises(ValidationError, match="version conflict"):
        transition_tenant_lifecycle(
            tenant_public_id=tenant.public_id,
            target_status=TenantAccount.LifecycleStatus.ACTIVE,
            expected_version=1,
            reason="stale retry",
            actor=platform_context[2],
        )


@pytest.mark.django_db
def test_subscription_replacement_ends_previous_subscription(
    company_factory,
    platform_context,
):
    company = company_factory()
    tenant = TenantAccount.objects.create(company=company)
    now = timezone.now()
    first = PlanVersion.objects.create(
        code="PILOT",
        version=1,
        name="Pilot",
        status=PlanVersion.Status.PUBLISHED,
        entitlements={"crm": True},
        limits={"users": 5},
        effective_from=now - timedelta(days=1),
        published_at=now - timedelta(days=1),
    )
    second = PlanVersion.objects.create(
        code="ENTERPRISE",
        version=1,
        name="Enterprise",
        status=PlanVersion.Status.PUBLISHED,
        entitlements={"crm": True, "finance": True},
        limits={"users": 50},
        effective_from=now - timedelta(days=1),
        published_at=now - timedelta(days=1),
    )
    previous = CompanySubscription.objects.create(
        company=company,
        plan_version=first,
        status=CompanySubscription.Status.ACTIVE,
        starts_at=now - timedelta(hours=1),
    )
    current = assign_subscription(
        tenant_public_id=tenant.public_id,
        plan_public_id=second.public_id,
        status=CompanySubscription.Status.ACTIVE,
        starts_at=now,
        ends_at=None,
        grace_until=None,
        reason="upgrade",
        actor=platform_context[2],
    )
    previous.refresh_from_db()
    assert previous.status == CompanySubscription.Status.ENDED
    assert previous.ends_at is not None
    assert current.plan_version == second


@pytest.mark.django_db
def test_usage_snapshot_is_append_only_and_idempotent_for_same_period(
    company_factory,
    platform_context,
):
    company = company_factory()
    tenant = TenantAccount.objects.create(company=company)
    first = collect_usage_snapshot(
        tenant_public_id=tenant.public_id,
        actor=platform_context[2],
    )
    second = collect_usage_snapshot(
        tenant_public_id=tenant.public_id,
        actor=platform_context[2],
    )
    assert first.public_id == second.public_id
    assert len(first.checksum_sha256) == 64
    first.metrics = {"users": 999}
    with pytest.raises(ValidationError, match="append-only"):
        first.save()


@pytest.mark.django_db
def test_support_request_is_time_bounded_and_never_issues_access_token(
    company_factory,
    platform_context,
    settings,
):
    settings.CONTROLPLANE_SUPPORT_MAX_HOURS = 24
    company = company_factory()
    tenant = TenantAccount.objects.create(company=company)
    item = create_support_access_request(
        tenant_public_id=tenant.public_id,
        reason="Investigate tenant-specific health evidence",
        scope_codes=["tenant.diagnostics", "tenant.audit"],
        duration_hours=4,
        actor=platform_context[2],
        operator_assignment=platform_context[1],
    )
    assert item.status == SupportAccessRequest.Status.REQUESTED
    assert item.expires_at > item.requested_at
    assert not hasattr(item, "access_token")
    with pytest.raises(ValidationError, match="between 1 and 24"):
        create_support_access_request(
            tenant_public_id=tenant.public_id,
            reason="Excessive support request duration",
            scope_codes=["tenant.diagnostics"],
            duration_hours=25,
            actor=platform_context[2],
            operator_assignment=platform_context[1],
        )
