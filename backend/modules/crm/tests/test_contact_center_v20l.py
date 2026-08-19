import uuid

import pytest
from django.core.exceptions import ValidationError

from modules.crm.application.configuration import ensure_foundation
from modules.crm.application.services import (
    RequestActor,
    create_activity,
    create_contact,
    create_lead,
    update_activity,
)
from modules.crm.models import Activity

pytestmark = pytest.mark.django_db


def actor(membership, user) -> RequestActor:
    return RequestActor(
        user_public_id=user.public_id,
        membership_public_id=membership.public_id,
        request_id=uuid.uuid4(),
    )


def test_standalone_contact_can_own_communication_activity(
    company_factory,
    user_factory,
    membership_factory,
):
    company = company_factory()
    user = user_factory()
    membership = membership_factory(user, company)
    contact = create_contact(
        company=company,
        actor=actor(membership, user),
        first_name="Asha",
        phone="+91 98765 43210",
    )

    activity = create_activity(
        company=company,
        actor=actor(membership, user),
        contact=contact,
        activity_type=Activity.ActivityType.CALL,
        status=Activity.Status.PLANNED,
        direction=Activity.Direction.OUTBOUND,
        outcome_code="started",
        subject="Call Asha",
        channel_metadata={
            "source": "crm_contact_center",
            "launch_mode": "device_handoff",
            "phone": "+91 98765 43210",
        },
    )

    assert activity.contact_id == contact.id
    assert activity.customer_id is None
    assert activity.lead_id is None
    assert activity.direction == Activity.Direction.OUTBOUND
    assert activity.outcome_code == "started"
    assert "phone" not in activity.channel_metadata


def test_interaction_outcome_update_is_versioned_and_auditable(
    company_factory,
    user_factory,
    membership_factory,
):
    company = company_factory()
    user = user_factory()
    membership = membership_factory(user, company)
    request_actor = actor(membership, user)
    contact = create_contact(
        company=company,
        actor=request_actor,
        first_name="Ravi",
        email="ravi@example.com",
    )
    activity = create_activity(
        company=company,
        actor=request_actor,
        contact=contact,
        activity_type=Activity.ActivityType.EMAIL,
        status=Activity.Status.PLANNED,
        direction=Activity.Direction.OUTBOUND,
        outcome_code="started",
        subject="Email Ravi",
    )

    updated = update_activity(
        company=company,
        actor=request_actor,
        activity_public_id=activity.public_id,
        expected_version=1,
        status=Activity.Status.COMPLETED,
        outcome_code="email_sent",
        duration_seconds=45,
        notes="Sent requested information.",
    )

    assert updated.status == Activity.Status.COMPLETED
    assert updated.outcome_code == "email_sent"
    assert updated.duration_seconds == 45
    assert updated.completed_at is not None
    assert updated.version == 2

    with pytest.raises(ValidationError, match="changed; refresh"):
        update_activity(
            company=company,
            actor=request_actor,
            activity_public_id=activity.public_id,
            expected_version=1,
            outcome_code="replied",
        )


def test_lead_communication_auto_links_primary_contact(
    company_factory,
    user_factory,
    membership_factory,
):
    company = company_factory()
    user = user_factory()
    membership = membership_factory(user, company)
    request_actor = actor(membership, user)
    ensure_foundation(company)
    lead = create_lead(
        company=company,
        actor=request_actor,
        title="Website enquiry",
        contact_first_name="Meera",
        contact_phone="+91 90000 00000",
    )

    activity = create_activity(
        company=company,
        actor=request_actor,
        lead=lead,
        activity_type=Activity.ActivityType.WHATSAPP,
        direction=Activity.Direction.OUTBOUND,
        subject="WhatsApp Meera",
    )

    assert lead.primary_contact_id is not None
    assert activity.contact_id == lead.primary_contact_id
