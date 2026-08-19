from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from modules.ai.application.crm_lead_intelligence import (
    override,
    refresh,
    state,
)
from modules.ai.models import AIEntityInsight, AIInteraction, AIModelPolicy, AIProviderProfile
from modules.crm.application.services import RequestActor, create_activity, create_lead
from modules.crm.models import Activity, PipelineStage
from modules.subscription.models import EntitlementOverride

pytestmark = pytest.mark.django_db


def _actor(user, membership):
    return RequestActor(
        user_public_id=user.public_id,
        membership_public_id=membership.public_id,
        request_id=uuid.uuid4(),
        ip_address=None,
        user_agent="pytest",
    )


def _bootstrap(company, actor_public_id):
    EntitlementOverride.objects.create(
        company=company,
        entitlement_code="crm.ai_summary",
        enabled=True,
        effective_from=timezone.now(),
        reason_code="test",
        set_by_public_id=actor_public_id,
    )
    EntitlementOverride.objects.create(
        company=company,
        entitlement_code="crm.ai_recommendation",
        enabled=True,
        effective_from=timezone.now(),
        reason_code="test",
        set_by_public_id=actor_public_id,
    )
    provider = AIProviderProfile.objects.create(
        company=company,
        code="LOCAL_GROUNDED",
        display_name="Local",
        adapter_code="local_grounded",
        is_active=True,
    )
    AIModelPolicy.objects.create(
        company=company,
        provider=provider,
        code="CRM_LEAD_INTELLIGENCE",
        name="CRM lead intelligence",
        model_name="local-crm",
        purpose=AIModelPolicy.Purpose.ASSISTANT,
        system_instruction="Grounded CRM lead intelligence",
        allowed_source_types=["crm.lead", "crm.activity"],
        allowed_data_classifications=["internal"],
        max_context_records=30,
        max_output_characters=4000,
        human_review_required=False,
        citations_required=True,
        retention_days=90,
        effective_from=timezone.now() - timedelta(minutes=1),
        is_active=True,
        version=1,
    )


def _lead_stage(company):
    return PipelineStage.objects.create(
        company=company,
        entity_type=PipelineStage.EntityType.LEAD,
        code="new",
        name="New",
        outcome=PipelineStage.Outcome.OPEN,
        sort_order=10,
        probability_percent=0,
        allowed_next_codes=[],
        is_initial=True,
        effective_from=timezone.now() - timedelta(minutes=1),
    )


def test_crm_ai_cache_reuses_unchanged_source_and_stales_after_activity(
    settings,
    company_factory,
    user_factory,
    membership_factory,
):
    settings.AI_LOCAL_ADAPTER_ENABLED = True
    company = company_factory()
    user = user_factory(email="ai-crm@example.com")
    membership = membership_factory(user, company)
    actor = _actor(user, membership)
    _bootstrap(company, user.public_id)
    _lead_stage(company)

    lead = create_lead(
        company=company,
        actor=actor,
        title="Villa enquiry",
        source_code="META_ADS",
    )
    first = refresh(company=company, actor=actor, lead_public_id=lead.public_id)
    assert first["exists"] is True
    assert first["stale"] is False
    first_interaction = first["interaction_public_id"]
    assert first["effective"]["recommended_next_action"]["action_code"] == "FIRST_CONTACT"

    second = refresh(company=company, actor=actor, lead_public_id=lead.public_id)
    assert second["interaction_public_id"] == first_interaction
    assert AIInteraction.objects.filter(company=company).count() == 1

    create_activity(
        company=company,
        actor=actor,
        lead=lead,
        activity_type=Activity.ActivityType.CALL,
        status=Activity.Status.COMPLETED,
        subject="Initial customer call",
        notes="Customer asked for a follow-up tomorrow.",
        occurred_at=timezone.now(),
    )
    stale = state(company=company, lead_public_id=lead.public_id)
    assert stale["stale"] is True

    refreshed = refresh(company=company, actor=actor, lead_public_id=lead.public_id)
    assert refreshed["stale"] is False
    assert refreshed["interaction_public_id"] != first_interaction
    assert AIInteraction.objects.filter(company=company).count() == 2


def test_crm_ai_prioritizes_overdue_recorded_activity(
    settings,
    company_factory,
    user_factory,
    membership_factory,
):
    settings.AI_LOCAL_ADAPTER_ENABLED = True
    company = company_factory()
    user = user_factory(email="ai-overdue@example.com")
    membership = membership_factory(user, company)
    actor = _actor(user, membership)
    _bootstrap(company, user.public_id)
    _lead_stage(company)
    lead = create_lead(company=company, actor=actor, title="Office enquiry")

    create_activity(
        company=company,
        actor=actor,
        lead=lead,
        activity_type=Activity.ActivityType.FOLLOW_UP,
        status=Activity.Status.PLANNED,
        subject="Send requested information",
        scheduled_for=timezone.now() - timedelta(hours=2),
    )
    result = refresh(company=company, actor=actor, lead_public_id=lead.public_id)
    action = result["effective"]["recommended_next_action"]
    assert action["action_code"] == "COMPLETE_OVERDUE_ACTIVITY"
    assert "Send requested information" in action["reason"]


def test_human_override_persists_across_regeneration(
    settings,
    company_factory,
    user_factory,
    membership_factory,
):
    settings.AI_LOCAL_ADAPTER_ENABLED = True
    company = company_factory()
    user = user_factory(email="ai-override@example.com")
    membership = membership_factory(user, company)
    actor = _actor(user, membership)
    _bootstrap(company, user.public_id)
    _lead_stage(company)
    lead = create_lead(company=company, actor=actor, title="Commercial enquiry")

    refresh(company=company, actor=actor, lead_public_id=lead.public_id)
    changed = override(
        company=company,
        actor=actor,
        lead_public_id=lead.public_id,
        summary="Sales manager reviewed this lead and added a human summary.",
        action_label="Call decision maker",
        action_reason="Human-reviewed commercial priority.",
    )
    assert changed["override_active"] is True
    assert changed["effective"]["summary"].startswith("Sales manager reviewed")

    create_activity(
        company=company,
        actor=actor,
        lead=lead,
        activity_type=Activity.ActivityType.NOTE,
        status=Activity.Status.COMPLETED,
        subject="New evidence",
        notes="Additional requirement received.",
        occurred_at=timezone.now(),
    )
    regenerated = refresh(company=company, actor=actor, lead_public_id=lead.public_id)
    assert regenerated["override_active"] is True
    assert regenerated["effective"]["recommended_next_action"]["action_code"] == "HUMAN_OVERRIDE"
    assert regenerated["effective"]["recommended_next_action"]["label"] == "Call decision maker"


def test_specific_entitlement_can_disable_recommendation(
    settings,
    company_factory,
    user_factory,
    membership_factory,
):
    settings.AI_LOCAL_ADAPTER_ENABLED = True
    company = company_factory()
    user = user_factory(email="ai-entitlement@example.com")
    membership = membership_factory(user, company)
    actor = _actor(user, membership)
    _bootstrap(company, user.public_id)
    EntitlementOverride.objects.create(
        company=company,
        entitlement_code="crm.ai_recommendation",
        enabled=False,
        effective_from=timezone.now() + timedelta(seconds=1),
        reason_code="specific-disable",
        set_by_public_id=user.public_id,
    )
    _lead_stage(company)
    lead = create_lead(company=company, actor=actor, title="Entitlement enquiry")

    # Preserve append-only entitlement history. The future disable above must remain
    # untouched; append a second disable that is effective now so the resolver
    # correctly selects the latest effective override without mutating history.
    EntitlementOverride.objects.create(
        company=company,
        entitlement_code="crm.ai_recommendation",
        enabled=False,
        effective_from=timezone.now(),
        reason_code="specific-disable-now",
        set_by_public_id=user.public_id,
    )

    result = refresh(company=company, actor=actor, lead_public_id=lead.public_id)
    assert result["feature_access"]["summary"] is True
    assert result["feature_access"]["recommendation"] is False
    assert result["effective"]["summary"]
    assert result["effective"]["recommended_next_action"] is None


def test_ai_insight_is_generic_cache_not_second_lead_table(
    settings,
    company_factory,
    user_factory,
    membership_factory,
):
    settings.AI_LOCAL_ADAPTER_ENABLED = True
    company = company_factory()
    user = user_factory(email="ai-cache@example.com")
    membership = membership_factory(user, company)
    actor = _actor(user, membership)
    _bootstrap(company, user.public_id)
    _lead_stage(company)
    lead = create_lead(company=company, actor=actor, title="Cache enquiry")

    refresh(company=company, actor=actor, lead_public_id=lead.public_id)
    insight = AIEntityInsight.objects.get(
        company=company,
        subject_type="crm.lead",
        subject_public_id=lead.public_id,
        insight_code="CRM_LEAD_INTELLIGENCE",
    )
    assert insight.interaction.company_id == company.id
    assert insight.subject_public_id == lead.public_id



def test_crm_ai_idempotency_key_stays_within_model_limit(
    settings,
    company_factory,
    user_factory,
    membership_factory,
):
    settings.AI_LOCAL_ADAPTER_ENABLED = True
    company = company_factory()
    user = user_factory(email="ai-idempotency@example.com")
    membership = membership_factory(user, company)
    actor = _actor(user, membership)
    _bootstrap(company, user.public_id)
    _lead_stage(company)
    lead = create_lead(company=company, actor=actor, title="Idempotency length enquiry")

    result = refresh(company=company, actor=actor, lead_public_id=lead.public_id)
    interaction = AIInteraction.objects.get(public_id=result["interaction_public_id"])

    assert len(interaction.idempotency_key) <= 120
    assert interaction.idempotency_key.startswith("crm-li:")
    assert interaction.idempotency_key == (
        f"crm-li:{lead.public_id.hex}:{interaction.prompt_digest}"
    )
