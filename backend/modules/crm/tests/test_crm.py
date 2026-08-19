import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from modules.crm.application.protection import decrypt_value
from modules.crm.application.services import (
    RequestActor,
    contact_duplicates,
    convert_lead,
    create_contact,
    create_lead,
    transition_lead,
)
from modules.crm.models import ConversionSnapshot, Customer, Opportunity, PipelineStage

pytestmark = pytest.mark.django_db


def actor(membership, user) -> RequestActor:
    return RequestActor(
        user_public_id=user.public_id,
        membership_public_id=membership.public_id,
        request_id=uuid.uuid4(),
    )


def install_stages(company):
    now = timezone.now() - timedelta(minutes=1)
    new = PipelineStage.objects.create(
        company=company,
        entity_type=PipelineStage.EntityType.LEAD,
        code="new",
        name="New",
        outcome=PipelineStage.Outcome.OPEN,
        sort_order=10,
        probability_percent=5,
        allowed_next_codes=["qualified", "disqualified"],
        is_initial=True,
        effective_from=now,
    )
    qualified = PipelineStage.objects.create(
        company=company,
        entity_type=PipelineStage.EntityType.LEAD,
        code="qualified",
        name="Qualified",
        outcome=PipelineStage.Outcome.QUALIFIED,
        sort_order=20,
        probability_percent=30,
        allowed_next_codes=["converted", "disqualified"],
        allows_conversion=True,
        effective_from=now,
    )
    PipelineStage.objects.create(
        company=company,
        entity_type=PipelineStage.EntityType.LEAD,
        code="converted",
        name="Converted",
        outcome=PipelineStage.Outcome.CONVERTED,
        sort_order=90,
        probability_percent=100,
        allowed_next_codes=[],
        effective_from=now,
    )
    PipelineStage.objects.create(
        company=company,
        entity_type=PipelineStage.EntityType.LEAD,
        code="disqualified",
        name="Disqualified",
        outcome=PipelineStage.Outcome.DISQUALIFIED,
        sort_order=100,
        probability_percent=0,
        allowed_next_codes=[],
        effective_from=now,
    )
    PipelineStage.objects.create(
        company=company,
        entity_type=PipelineStage.EntityType.OPPORTUNITY,
        code="qualification",
        name="Qualification",
        outcome=PipelineStage.Outcome.OPEN,
        sort_order=10,
        probability_percent=20,
        allowed_next_codes=["won", "lost"],
        is_initial=True,
        effective_from=now,
    )
    PipelineStage.objects.create(
        company=company,
        entity_type=PipelineStage.EntityType.OPPORTUNITY,
        code="won",
        name="Won",
        outcome=PipelineStage.Outcome.WON,
        sort_order=90,
        probability_percent=100,
        allowed_next_codes=[],
        effective_from=now,
    )
    PipelineStage.objects.create(
        company=company,
        entity_type=PipelineStage.EntityType.OPPORTUNITY,
        code="lost",
        name="Lost",
        outcome=PipelineStage.Outcome.LOST,
        sort_order=100,
        probability_percent=0,
        allowed_next_codes=[],
        effective_from=now,
    )
    return new, qualified


def test_contact_values_are_encrypted_and_duplicates_are_tenant_scoped(
    company_factory,
    user_factory,
    membership_factory,
):
    company = company_factory()
    other_company = company_factory()
    user = user_factory()
    membership = membership_factory(user, company)
    other_user = user_factory()
    other_membership = membership_factory(other_user, other_company)
    contact = create_contact(
        company=company,
        actor=actor(membership, user),
        first_name="Asha",
        email="asha@example.test",
        phone="+91 98765 43210",
    )
    create_contact(
        company=other_company,
        actor=actor(other_membership, other_user),
        first_name="Other Asha",
        email="asha@example.test",
        phone="+91 98765 43210",
    )

    assert "asha@example.test" not in contact.email_ciphertext
    assert "9876543210" not in contact.phone_ciphertext
    assert decrypt_value(contact.email_ciphertext) == "asha@example.test"
    assert list(
        contact_duplicates(
            company=company,
            email="ASHA@example.test ",
            phone="98765 43210",
        )
    ) == [contact]


def test_lead_transition_uses_optimistic_versioning(
    company_factory,
    user_factory,
    membership_factory,
):
    company = company_factory()
    user = user_factory()
    membership = membership_factory(user, company)
    _, qualified = install_stages(company)
    lead = create_lead(
        company=company,
        actor=actor(membership, user),
        title="Head office project",
    )

    transitioned = transition_lead(
        company=company,
        actor=actor(membership, user),
        lead_public_id=lead.public_id,
        target_stage_public_id=qualified.public_id,
        expected_version=1,
    )

    assert transitioned.stage.code == "qualified"
    assert transitioned.version == 2
    with pytest.raises(ValidationError, match="refresh before retrying"):
        transition_lead(
            company=company,
            actor=actor(membership, user),
            lead_public_id=lead.public_id,
            target_stage_public_id=qualified.public_id,
            expected_version=1,
        )


def test_qualified_lead_conversion_is_idempotent(
    company_factory,
    user_factory,
    membership_factory,
):
    company = company_factory()
    user = user_factory()
    membership = membership_factory(user, company)
    _, qualified = install_stages(company)
    lead = create_lead(
        company=company,
        actor=actor(membership, user),
        title="Residential tower",
        estimated_value=Decimal("12500000"),
    )
    lead = transition_lead(
        company=company,
        actor=actor(membership, user),
        lead_public_id=lead.public_id,
        target_stage_public_id=qualified.public_id,
        expected_version=1,
    )

    first = convert_lead(
        company=company,
        actor=actor(membership, user),
        lead_public_id=lead.public_id,
        expected_version=2,
    )
    second = convert_lead(
        company=company,
        actor=actor(membership, user),
        lead_public_id=lead.public_id,
        expected_version=2,
    )

    assert first.public_id == second.public_id
    assert ConversionSnapshot.objects.filter(company=company, lead=lead).count() == 1
    assert Customer.objects.filter(company=company).count() == 1
    assert Opportunity.objects.filter(company=company, source_lead=lead).count() == 1
