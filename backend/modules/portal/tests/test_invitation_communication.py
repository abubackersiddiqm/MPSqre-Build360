from __future__ import annotations

import uuid

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from modules.communication.models import (
    ChannelPolicy,
    CommunicationChannel,
    CommunicationRequest,
    MessageTemplate,
)
from modules.identity.models import User
from modules.platform.actors import RequestActor
from modules.portal.application.services import (
    accept_invitation_by_id_for_user,
    create_invitation,
    queue_invitation_communication,
)
from modules.portal.models import PortalScopeType, PortalType

pytestmark = pytest.mark.django_db


def _actor(user, membership):
    return RequestActor(
        user_public_id=user.public_id,
        membership_public_id=membership.public_id,
        request_id=uuid.uuid4(),
        ip_address=None,
        user_agent="pytest",
    )


def test_tokenless_invitation_accept_validates_email_before_membership(company_factory, user_factory, membership_factory):
    company = company_factory()
    admin = user_factory(email="admin-portal@example.com")
    membership = membership_factory(admin, company)
    invitation, _ = create_invitation(
        company=company,
        actor=_actor(admin, membership),
        email="client-match@example.com",
        portal_type=PortalType.CLIENT,
        scope_type=PortalScopeType.COMPANY,
        scope_public_id=None,
        permission_codes=["portal.dashboard.view"],
    )
    wrong = User.objects.create(email="wrong-client@example.com", is_active=True)
    with pytest.raises(ValidationError):
        accept_invitation_by_id_for_user(
            user=wrong,
            invitation_public_id=invitation.public_id,
            request_id=uuid.uuid4(),
            ip_address=None,
            user_agent="pytest",
        )
    assert not wrong.company_memberships.filter(company=company).exists()

    matching = User.objects.create(email="client-match@example.com", is_active=True)
    accepted_company, grant = accept_invitation_by_id_for_user(
        user=matching,
        invitation_public_id=invitation.public_id,
        request_id=uuid.uuid4(),
        ip_address=None,
        user_agent="pytest",
    )
    assert accepted_company.pk == company.pk
    assert grant.user_public_id == matching.public_id


def test_invitation_communication_does_not_store_raw_bearer_token(company_factory, user_factory, membership_factory):
    company = company_factory()
    admin = user_factory(email="admin-send@example.com")
    membership = membership_factory(admin, company)
    actor = _actor(admin, membership)
    ChannelPolicy.objects.create(
        company=company,
        channel=CommunicationChannel.EMAIL,
        is_enabled=True,
        consent_required=False,
        timezone=company.timezone,
    )
    MessageTemplate.objects.create(
        company=company,
        code="PORTAL_INVITATION_EMAIL",
        name="Portal invitation",
        channel=CommunicationChannel.EMAIL,
        locale=company.locale,
        version=1,
        status=MessageTemplate.Status.PUBLISHED,
        subject_template="{company_name} portal invitation",
        body_template="Open {accept_url}",
        variable_names=["company_name", "accept_url"],
        purpose_code="portal_invitation",
        created_by_public_id=admin.public_id,
        published_by_public_id=admin.public_id,
        published_at=timezone.now(),
    )
    invitation, raw_token = create_invitation(
        company=company,
        actor=actor,
        email="client-delivery@example.com",
        portal_type=PortalType.CLIENT,
        scope_type=PortalScopeType.COMPANY,
        scope_public_id=None,
        permission_codes=["portal.dashboard.view"],
    )
    request = queue_invitation_communication(
        company=company,
        actor=actor,
        invitation_public_id=invitation.public_id,
    )
    assert isinstance(request, CommunicationRequest)
    assert raw_token not in request.rendered_body
    assert f"invitation={invitation.public_id}" in request.rendered_body
