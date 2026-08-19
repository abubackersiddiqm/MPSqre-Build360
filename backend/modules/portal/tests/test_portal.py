import uuid

import pytest
from django.core.exceptions import ValidationError

from modules.platform.actors import RequestActor
from modules.portal.application.services import (
    accept_invitation_for_user,
    create_invitation,
    validate_permission_codes,
)
from modules.portal.models import PortalScopeType, PortalType
from modules.tenant.models import Membership


@pytest.fixture
def portal_actor(company_factory, user_factory, membership_factory):
    company = company_factory()
    administrator = user_factory(email="portal-admin@example.test")
    membership = membership_factory(administrator, company)
    return company, RequestActor(
        user_public_id=administrator.public_id,
        membership_public_id=membership.public_id,
        request_id=uuid.uuid4(),
        ip_address="127.0.0.1",
        user_agent="pytest",
    )


def test_portal_permission_allowlist_rejects_internal_permissions():
    with pytest.raises(ValidationError, match="Unsupported portal permissions"):
        validate_permission_codes(PortalType.CLIENT, ["finance.ledger.read"])


@pytest.mark.django_db
def test_invitation_acceptance_creates_bounded_membership_and_grant(
    portal_actor,
    user_factory,
):
    company, actor = portal_actor
    external = user_factory(email="client@example.test")
    invitation, token = create_invitation(
        company=company,
        actor=actor,
        email=external.email,
        portal_type=PortalType.CLIENT,
        scope_type=PortalScopeType.COMPANY,
        scope_public_id=None,
        permission_codes=["portal.dashboard.view", "portal.project.view"],
        expires_in_days=7,
    )
    accepted_company, grant = accept_invitation_for_user(
        user=external,
        token=token,
        request_id=uuid.uuid4(),
        ip_address="127.0.0.1",
        user_agent="pytest",
    )
    invitation.refresh_from_db()
    assert accepted_company.public_id == company.public_id
    assert grant.user_public_id == external.public_id
    assert grant.permission_codes == ["portal.dashboard.view", "portal.project.view"]
    assert invitation.status == invitation.Status.ACCEPTED
    assert Membership.objects.filter(company=company, user=external).exists()


@pytest.mark.django_db
def test_estimate_share_requires_approved_baseline_and_explicit_client_permission(
    portal_actor,
    user_factory,
):
    from datetime import timedelta
    from decimal import Decimal

    from django.utils import timezone

    from modules.estimation.models import Estimate, EstimateVersion
    from modules.portal.application.services import create_share, shares_for_user
    from modules.portal.models import PortalAccessGrant
    from modules.projects.application.services import create_project
    from modules.projects.models import DeliveryStage

    company, actor = portal_actor
    DeliveryStage.objects.create(
        company=company,
        entity_type=DeliveryStage.EntityType.PROJECT,
        code="preconstruction",
        name="Preconstruction",
        outcome=DeliveryStage.Outcome.OPEN,
        sort_order=10,
        is_initial=True,
        effective_from=timezone.now() - timedelta(minutes=1),
    )
    estimate_stage = DeliveryStage.objects.create(
        company=company,
        entity_type=DeliveryStage.EntityType.ESTIMATE_VERSION,
        code="approved",
        name="Approved",
        outcome=DeliveryStage.Outcome.APPROVED,
        sort_order=80,
        is_initial=True,
        allows_baseline=True,
        effective_from=timezone.now() - timedelta(minutes=1),
    )
    project = create_project(
        company=company,
        actor=actor,
        code="PRE-001",
        name="Client Residence",
    )
    estimate = Estimate.objects.create(
        company=company,
        project=project,
        code="EST-001",
        name="Detailed Estimate",
        currency="INR",
        created_by_public_id=actor.user_public_id,
        active_version_number=1,
    )
    approved = EstimateVersion.objects.create(
        company=company,
        estimate=estimate,
        version_number=1,
        stage=estimate_stage,
        subtotal=Decimal("1000000"),
        tax_total=Decimal("180000"),
        grand_total=Decimal("1180000"),
        created_by_public_id=actor.user_public_id,
        approved_at=timezone.now(),
        baselined_at=timezone.now(),
    )
    client = user_factory(email="estimate-client@example.test")
    allowed_grant = PortalAccessGrant.objects.create(
        company=company,
        user_public_id=client.public_id,
        portal_type=PortalType.CLIENT,
        scope_type=PortalScopeType.COMPANY,
        permission_codes=["portal.estimate.view"],
        effective_from=timezone.now() - timedelta(minutes=1),
        granted_by_public_id=actor.user_public_id,
    )
    share = create_share(
        company=company,
        actor=actor,
        grant_public_id=allowed_grant.public_id,
        entity_type="estimation.version",
        entity_public_id=approved.public_id,
        access_level="view",
    )
    assert [item.public_id for item in shares_for_user(company, client.public_id)] == [share.public_id]

    other = user_factory(email="no-estimate@example.test")
    denied_grant = PortalAccessGrant.objects.create(
        company=company,
        user_public_id=other.public_id,
        portal_type=PortalType.CLIENT,
        scope_type=PortalScopeType.COMPANY,
        permission_codes=["portal.project.view"],
        effective_from=timezone.now() - timedelta(minutes=1),
        granted_by_public_id=actor.user_public_id,
    )
    with pytest.raises(ValidationError, match="does not permit estimate viewing"):
        create_share(
            company=company,
            actor=actor,
            grant_public_id=denied_grant.public_id,
            entity_type="estimation.version",
            entity_public_id=approved.public_id,
            access_level="view",
        )
