import uuid

import pytest

from modules.crm.application.automation import create_rule, dispatch_automation_event
from modules.crm.application.configuration import ensure_foundation
from modules.crm.application.services import (
    RequestActor,
    create_activity,
    create_contact,
    create_lead,
    update_activity,
)
from modules.crm.models import Activity, CrmAutomationExecution, Lead

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def automation_enabled(monkeypatch):
    monkeypatch.setattr("modules.crm.application.automation.feature_enabled", lambda **kwargs: True)


def actor(membership, user) -> RequestActor:
    return RequestActor(
        user_public_id=user.public_id,
        membership_public_id=membership.public_id,
        request_id=uuid.uuid4(),
    )


def test_lead_created_rule_creates_task_and_is_idempotent(company_factory, user_factory, membership_factory):
    company = company_factory()
    user = user_factory()
    membership = membership_factory(user, company)
    request_actor = actor(membership, user)
    ensure_foundation(company)

    rule = create_rule(
        company=company,
        code="website-follow-up",
        name="Website lead follow-up",
        trigger_code="lead.created",
        condition_tree={"mode": "all", "items": [{"field": "source_code", "operator": "eq", "value": "website"}]},
        actions=[{"type": "create_task", "subject": "Contact website lead", "due_in_hours": 2, "priority": "high"}],
    )

    lead = create_lead(company=company, actor=request_actor, title="New website enquiry", source_code="website")

    execution = CrmAutomationExecution.objects.get(company=company, rule=rule)
    assert execution.status == CrmAutomationExecution.Status.SUCCEEDED
    assert execution.matched is True
    task = Activity.objects.get(company=company, lead=lead, activity_type=Activity.ActivityType.TASK)
    assert task.subject == "Contact website lead"
    assert task.priority == Activity.Priority.HIGH

    dispatch_automation_event(company=company, actor=request_actor, trigger_code="lead.created", record=lead)
    assert CrmAutomationExecution.objects.filter(company=company, rule=rule).count() == 1
    assert Activity.objects.filter(company=company, lead=lead, activity_type=Activity.ActivityType.TASK).count() == 1


def test_completed_call_outcome_can_schedule_follow_up(company_factory, user_factory, membership_factory):
    company = company_factory()
    user = user_factory()
    membership = membership_factory(user, company)
    request_actor = actor(membership, user)
    contact = create_contact(company=company, actor=request_actor, first_name="Asha", phone="+919876543210")
    create_rule(
        company=company,
        code="retry-no-answer",
        name="Retry no answer",
        trigger_code="activity.completed",
        condition_tree={
            "mode": "all",
            "items": [
                {"field": "activity_type", "operator": "eq", "value": "call"},
                {"field": "outcome_code", "operator": "eq", "value": "no_answer"},
            ],
        },
        actions=[{"type": "schedule_follow_up", "subject": "Retry call", "due_in_hours": 24}],
    )
    call = create_activity(
        company=company,
        actor=request_actor,
        contact=contact,
        activity_type=Activity.ActivityType.CALL,
        subject="Call Asha",
        direction=Activity.Direction.OUTBOUND,
    )

    update_activity(
        company=company,
        actor=request_actor,
        activity_public_id=call.public_id,
        expected_version=1,
        status=Activity.Status.COMPLETED,
        outcome_code="no_answer",
    )

    follow_up = Activity.objects.get(company=company, contact=contact, activity_type=Activity.ActivityType.FOLLOW_UP)
    assert follow_up.subject == "Retry call"
    assert follow_up.scheduled_for is not None


def test_bad_rule_action_records_failure_without_rolling_back_lead(company_factory, user_factory, membership_factory):
    company = company_factory()
    user = user_factory()
    membership = membership_factory(user, company)
    request_actor = actor(membership, user)
    ensure_foundation(company)
    create_rule(
        company=company,
        code="invalid-owner-test",
        name="Invalid owner test",
        trigger_code="lead.created",
        condition_tree={},
        actions=[{"type": "assign_owner", "owner_membership_public_id": str(uuid.uuid4())}],
    )

    lead = create_lead(company=company, actor=request_actor, title="Lead must survive automation failure")

    assert Lead.objects.filter(pk=lead.pk).exists()
    execution = CrmAutomationExecution.objects.get(company=company, entity_public_id=lead.public_id)
    assert execution.status == CrmAutomationExecution.Status.FAILED
    assert "not active" in execution.error_message
