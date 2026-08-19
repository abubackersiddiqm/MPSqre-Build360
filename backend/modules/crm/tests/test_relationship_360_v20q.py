import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from modules.crm.application.configuration import ensure_foundation
from modules.crm.application.relationship import (
    my_work_payload,
    people_page,
    relationship_workspace,
)
from modules.crm.application.services import (
    RequestActor,
    create_activity,
    create_contact,
    create_customer,
    create_lead,
    create_opportunity,
)

pytestmark = pytest.mark.django_db


def actor(membership, user) -> RequestActor:
    return RequestActor(
        user_public_id=user.public_id,
        membership_public_id=membership.public_id,
        request_id=uuid.uuid4(),
    )


def test_people_page_prioritizes_next_follow_up_and_keeps_person_as_master(
    company_factory,
    user_factory,
    membership_factory,
):
    company = company_factory(display_name="Relationship CRM")
    user = user_factory()
    membership = membership_factory(user, company)
    ensure_foundation(company)
    request_actor = actor(membership, user)

    account = create_customer(
        company=company,
        actor=request_actor,
        kind="organization",
        display_name="ABC Industries",
    )
    later = create_contact(
        company=company,
        actor=request_actor,
        first_name="Later",
        phone="+919900000001",
        customer=account,
    )
    urgent = create_contact(
        company=company,
        actor=request_actor,
        first_name="Urgent",
        phone="+919900000002",
        customer=account,
    )
    create_lead(
        company=company,
        actor=request_actor,
        title="Later enquiry",
        primary_contact=later,
        customer=account,
        next_follow_up_at=timezone.now() + timedelta(days=2),
    )
    create_lead(
        company=company,
        actor=request_actor,
        title="Urgent enquiry",
        primary_contact=urgent,
        customer=account,
        next_follow_up_at=timezone.now() - timedelta(hours=1),
    )

    payload = people_page(
        company=company,
        membership_public_id=membership.public_id,
        view="all",
        sort="next_action",
    )

    assert payload["pagination"]["total"] == 2
    assert payload["items"][0]["person"]["display_name"] == "Urgent"
    assert payload["items"][0]["relationship"] == "lead"
    assert payload["items"][0]["is_overdue"] is True
    assert payload["items"][0]["company"]["display_name"] == "ABC Industries"


def test_relationship_workspace_aggregates_leads_opportunities_activity_and_files_without_duplicate_person(
    company_factory,
    user_factory,
    membership_factory,
):
    company = company_factory(display_name="Relationship CRM")
    user = user_factory()
    membership = membership_factory(user, company)
    ensure_foundation(company)
    request_actor = actor(membership, user)

    account = create_customer(
        company=company,
        actor=request_actor,
        kind="organization",
        display_name="Unified Account",
    )
    contact = create_contact(
        company=company,
        actor=request_actor,
        first_name="Ravi",
        last_name="Kumar",
        phone="+919876543210",
        email="ravi@example.com",
        customer=account,
    )
    lead = create_lead(
        company=company,
        actor=request_actor,
        title="New machine enquiry",
        primary_contact=contact,
        customer=account,
        estimated_value=Decimal("800000"),
        next_follow_up_at=timezone.now() + timedelta(hours=2),
    )
    opportunity = create_opportunity(
        company=company,
        actor=request_actor,
        name="Machine order",
        customer=account,
        primary_contact=contact,
        source_lead=lead,
        amount=Decimal("800000"),
    )
    create_activity(
        company=company,
        actor=request_actor,
        activity_type="call",
        subject="Discuss commercial terms",
        notes="Customer asked for revised quotation.",
        contact=contact,
        lead=lead,
        opportunity=opportunity,
        status="completed",
        occurred_at=timezone.now(),
    )

    payload = relationship_workspace(company=company, contact_public_id=contact.public_id)

    assert payload["person"]["public_id"] == str(contact.public_id)
    assert payload["person"]["display_name"] == "Ravi Kumar"
    assert len(payload["leads"]) == 1
    assert len(payload["opportunities"]) == 1
    assert payload["timeline"][0]["subject"] == "Discuss commercial terms"
    assert payload["next_action"]["lead_public_id"] == str(lead.public_id)
    assert payload["summary"]["open_pipeline_value"] == "800000.0000"


def test_my_work_is_owned_and_prioritizes_overdue_actions(
    company_factory,
    user_factory,
    membership_factory,
):
    company = company_factory(display_name="Relationship CRM")
    user = user_factory()
    membership = membership_factory(user, company)
    other_user = user_factory()
    other_membership = membership_factory(other_user, company)
    ensure_foundation(company)
    request_actor = actor(membership, user)
    other_actor = actor(other_membership, other_user)

    contact = create_contact(
        company=company,
        actor=request_actor,
        first_name="Priority",
        phone="+919800000001",
    )
    create_lead(
        company=company,
        actor=request_actor,
        title="Priority lead",
        primary_contact=contact,
        next_follow_up_at=timezone.now() - timedelta(minutes=30),
    )
    other_contact = create_contact(
        company=company,
        actor=other_actor,
        first_name="Other",
        phone="+919800000002",
    )
    create_lead(
        company=company,
        actor=other_actor,
        title="Other lead",
        primary_contact=other_contact,
        next_follow_up_at=timezone.now() - timedelta(days=1),
    )

    payload = my_work_payload(company=company, membership_public_id=membership.public_id)

    assert payload["counts"]["overdue"] >= 1
    assert payload["queue"][0]["person"]["public_id"] == str(contact.public_id)
    assert all(
        item["person"] is None or item["person"]["public_id"] != str(other_contact.public_id)
        for item in payload["queue"]
    )


def test_relationship_read_models_respect_permission_projection_flags(
    company_factory,
    user_factory,
    membership_factory,
):
    company = company_factory(display_name="Permission Projection CRM")
    user = user_factory()
    membership = membership_factory(user, company)
    ensure_foundation(company)
    request_actor = actor(membership, user)

    contact = create_contact(
        company=company,
        actor=request_actor,
        first_name="Restricted",
        phone="+919811111111",
    )
    lead = create_lead(
        company=company,
        actor=request_actor,
        title="Hidden lead",
        primary_contact=contact,
        next_follow_up_at=timezone.now() - timedelta(hours=2),
    )
    create_activity(
        company=company,
        actor=request_actor,
        activity_type="note",
        subject="Hidden activity",
        notes="Should not be projected without activity.read",
        contact=contact,
        lead=lead,
        status="completed",
        occurred_at=timezone.now(),
    )

    people = people_page(
        company=company,
        membership_public_id=membership.public_id,
        include_leads=False,
        include_opportunities=False,
        include_activities=False,
        include_customers=False,
    )
    assert people["pagination"]["total"] == 1
    assert people["items"][0]["relationship"] == "contact"
    assert people["items"][0]["active_lead"] is None
    assert people["items"][0]["open_opportunity"] is None
    assert people["items"][0]["next_follow_up_at"] is None
    assert people["items"][0]["last_activity_at"] is None
    assert people["items"][0]["company"] is None

    restricted_view = people_page(
        company=company,
        membership_public_id=membership.public_id,
        view="active_leads",
        include_leads=False,
        include_opportunities=False,
        include_activities=False,
    )
    assert restricted_view["pagination"]["total"] == 0

    workspace = relationship_workspace(
        company=company,
        contact_public_id=contact.public_id,
        include_leads=False,
        include_opportunities=False,
        include_activities=False,
        include_customers=False,
    )
    assert workspace["leads"] == []
    assert workspace["opportunities"] == []
    assert workspace["timeline"] == []
    assert workspace["files"] == []
    assert workspace["next_action"] is None
    assert workspace["company"] is None
    assert workspace["person"]["customer_public_id"] is None

    work = my_work_payload(
        company=company,
        membership_public_id=membership.public_id,
        include_contacts=False,
        include_customers=False,
        include_leads=False,
        include_activities=False,
    )
    assert work["queue"] == []
    assert all(value == 0 for value in work["counts"].values())


def test_people_next_action_includes_planned_activity_not_only_lead_follow_up(
    company_factory,
    user_factory,
    membership_factory,
):
    company = company_factory(display_name="Activity Priority CRM")
    user = user_factory()
    membership = membership_factory(user, company)
    ensure_foundation(company)
    request_actor = actor(membership, user)

    activity_person = create_contact(
        company=company,
        actor=request_actor,
        first_name="Meeting First",
        phone="+919822222221",
    )
    lead_person = create_contact(
        company=company,
        actor=request_actor,
        first_name="Lead Later",
        phone="+919822222222",
    )
    create_activity(
        company=company,
        actor=request_actor,
        activity_type="meeting",
        subject="Customer meeting",
        contact=activity_person,
        status="planned",
        scheduled_for=timezone.now() + timedelta(hours=1),
    )
    create_lead(
        company=company,
        actor=request_actor,
        title="Later follow-up",
        primary_contact=lead_person,
        next_follow_up_at=timezone.now() + timedelta(hours=4),
    )

    payload = people_page(
        company=company,
        membership_public_id=membership.public_id,
        sort="next_action",
    )

    assert payload["items"][0]["person"]["public_id"] == str(activity_person.public_id)
    assert payload["items"][0]["next_action_kind"] == "activity"
    assert payload["items"][0]["next_action_label"] == "Customer meeting"
