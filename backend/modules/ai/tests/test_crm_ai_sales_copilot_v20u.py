from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from modules.ai.application.crm_lead_intelligence import refresh, state
from modules.ai.models import AIModelPolicy, AIProviderProfile
from modules.crm.application.configuration import ensure_foundation
from modules.crm.application.services import (
    RequestActor,
    create_activity,
    create_contact,
    create_lead,
)
from modules.crm.models import Activity
from modules.subscription.models import EntitlementOverride

pytestmark = pytest.mark.django_db


def _actor(user, membership):
    return RequestActor(
        user_public_id=user.public_id,
        membership_public_id=membership.public_id,
        request_id=uuid.uuid4(),
    )


def _enable_ai(company, user_public_id):
    for code in ("crm.ai_summary", "crm.ai_recommendation"):
        EntitlementOverride.objects.create(
            company=company,
            entitlement_code=code,
            enabled=True,
            effective_from=timezone.now() - timedelta(seconds=1),
            reason_code="v20u-test",
            set_by_public_id=user_public_id,
        )
    provider = AIProviderProfile.objects.create(
        company=company,
        code="LOCAL_GROUNDED",
        display_name="Local grounded",
        adapter_code="local_grounded",
        is_active=True,
    )
    AIModelPolicy.objects.create(
        company=company,
        provider=provider,
        code="CRM_LEAD_INTELLIGENCE",
        name="CRM Sales Copilot",
        model_name="local-crm-sales-copilot",
        purpose=AIModelPolicy.Purpose.ASSISTANT,
        system_instruction="Grounded CRM sales preparation",
        allowed_source_types=["crm.lead", "crm.activity"],
        allowed_data_classifications=["internal"],
        allowed_tool_codes=[],
        max_context_records=30,
        max_output_characters=8000,
        human_review_required=False,
        citations_required=True,
        retention_days=90,
        effective_from=timezone.now() - timedelta(minutes=1),
        is_active=True,
        version=1,
    )


def test_sales_copilot_returns_english_and_tanglish_call_prep(
    settings,
    company_factory,
    user_factory,
    membership_factory,
):
    settings.AI_LOCAL_ADAPTER_ENABLED = True
    company = company_factory(display_name="AI Sales Copilot")
    user = user_factory(email="sales-copilot@example.com")
    membership = membership_factory(user, company)
    actor = _actor(user, membership)
    ensure_foundation(company)
    _enable_ai(company, user.public_id)

    contact = create_contact(
        company=company,
        actor=actor,
        first_name="Ravi",
        last_name="Kumar",
        phone="+919876543210",
        source_code="website",
    )
    lead = create_lead(
        company=company,
        actor=actor,
        title="Annual service enquiry",
        description="Customer is evaluating the annual service plan.",
        source_code="website",
        primary_contact=contact,
        next_follow_up_at=timezone.now() - timedelta(hours=1),
    )
    create_activity(
        company=company,
        actor=actor,
        contact=contact,
        activity_type=Activity.ActivityType.CALL,
        status=Activity.Status.COMPLETED,
        direction=Activity.Direction.OUTBOUND,
        outcome_code="callback_requested",
        subject="Discussed service options",
        notes="Customer asked us to call back after reviewing the proposal.",
        occurred_at=timezone.now() - timedelta(days=1),
    )

    result = refresh(company=company, actor=actor, lead_public_id=lead.public_id)
    effective = result["effective"]

    assert effective["summary"]
    assert "stage-la" in effective["summary_tanglish"]
    assert effective["recommended_next_action"]
    assert effective["recommended_next_action"]["label_tanglish"]
    assert "pannunga" in effective["recommended_next_action"]["label_tanglish"]
    assert effective["call_preparation"]["english"]["opening_line"].startswith("Hi Ravi Kumar")
    assert "call pannuren" in effective["call_preparation"]["tanglish"]["opening_line"]
    assert len(effective["call_preparation"]["english"]["questions"]) == 3
    assert "follow-up pannuren" in effective["message_drafts"]["whatsapp"]["tanglish"]
    callback_signal = next(signal for signal in effective["attention_signals"] if signal["code"] == "CUSTOMER_REQUESTED_NEXT_STEP")
    assert "pannirukkaru" in callback_signal["label_tanglish"]
    assert effective["data_gaps"][0].get("label_tanglish")
    assert result["citations"]


def test_contact_level_activity_marks_existing_lead_ai_cache_stale(
    settings,
    company_factory,
    user_factory,
    membership_factory,
):
    settings.AI_LOCAL_ADAPTER_ENABLED = True
    company = company_factory(display_name="Relationship-aware AI")
    user = user_factory(email="relationship-ai@example.com")
    membership = membership_factory(user, company)
    actor = _actor(user, membership)
    ensure_foundation(company)
    _enable_ai(company, user.public_id)

    contact = create_contact(company=company, actor=actor, first_name="Meera", phone="+919900001111")
    lead = create_lead(company=company, actor=actor, title="Consulting enquiry", primary_contact=contact)
    refresh(company=company, actor=actor, lead_public_id=lead.public_id)
    assert state(company=company, lead_public_id=lead.public_id)["stale"] is False

    create_activity(
        company=company,
        actor=actor,
        contact=contact,
        activity_type=Activity.ActivityType.WHATSAPP,
        status=Activity.Status.COMPLETED,
        direction=Activity.Direction.OUTBOUND,
        outcome_code="replied",
        subject="WhatsApp follow-up",
        notes="Customer shared a new requirement through WhatsApp.",
        occurred_at=timezone.now(),
    )

    assert state(company=company, lead_public_id=lead.public_id)["stale"] is True
