import uuid
from decimal import Decimal

import pytest
from django.utils import timezone

from modules.crm.application.configuration import ensure_foundation
from modules.crm.application.services import (
    RequestActor,
    contact_duplicates,
    create_contact,
    create_or_reuse_lead_from_contact,
    reveal_contact,
)

pytestmark = pytest.mark.django_db


def actor(membership, user) -> RequestActor:
    return RequestActor(
        user_public_id=user.public_id,
        membership_public_id=membership.public_id,
        request_id=uuid.uuid4(),
    )


def test_contact_supports_protected_optional_alternate_phone(
    company_factory,
    user_factory,
    membership_factory,
):
    company = company_factory(display_name="Unified People CRM")
    user = user_factory()
    membership = membership_factory(user, company)
    request_actor = actor(membership, user)

    contact = create_contact(
        company=company,
        actor=request_actor,
        first_name="Ravi",
        phone="+91 98765 43210",
        alternate_phone="+91 90000 11111",
    )

    assert contact.phone_last_four == "3210"
    assert contact.alternate_phone_last_four == "1111"
    revealed = reveal_contact(
        company=company,
        actor=request_actor,
        contact_public_id=contact.public_id,
        reason_code="crm_call",
    )
    assert revealed["phone"].endswith("43210")
    assert revealed["alternate_phone"].endswith("11111")

    duplicates = contact_duplicates(company=company, phone="+919000011111")
    assert list(duplicates.values_list("public_id", flat=True)) == [contact.public_id]


def test_contact_is_person_master_and_lead_is_added_without_duplicate_contact(
    company_factory,
    user_factory,
    membership_factory,
):
    company = company_factory(display_name="Unified People CRM")
    user = user_factory()
    membership = membership_factory(user, company)
    ensure_foundation(company)
    request_actor = actor(membership, user)

    contact = create_contact(
        company=company,
        actor=request_actor,
        first_name="Meera",
        phone="+919811112222",
        alternate_phone="+919811113333",
        source_code="website",
    )

    lead, created = create_or_reuse_lead_from_contact(
        company=company,
        actor=request_actor,
        contact_public_id=contact.public_id,
        title="Premium service enquiry",
        estimated_value=Decimal("250000"),
        next_follow_up_at=timezone.now(),
    )
    second, second_created = create_or_reuse_lead_from_contact(
        company=company,
        actor=request_actor,
        contact_public_id=contact.public_id,
        title="Should reuse active lead",
    )

    assert created is True
    assert lead.primary_contact_id == contact.pk
    assert lead.source_code == "website"
    assert lead.estimated_value == Decimal("250000")
    assert second_created is False
    assert second.pk == lead.pk
    assert contact.leads.count() == 1
