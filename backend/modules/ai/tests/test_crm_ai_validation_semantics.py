from __future__ import annotations

import uuid

import pytest
from django.utils import timezone

from modules.ai.models import AIEntityInsight, AIInteraction, AIModelPolicy, AIProviderProfile

pytestmark = pytest.mark.django_db


def test_ai_policy_full_clean_allows_empty_tool_list(company_factory):
    company = company_factory()
    provider = AIProviderProfile.objects.create(
        company=company,
        code="LOCAL_VALIDATION",
        display_name="Local validation",
        adapter_code="local_grounded",
        is_active=True,
    )
    policy = AIModelPolicy(
        company=company,
        provider=provider,
        code="VALIDATION_POLICY",
        name="Validation policy",
        model_name="local-validation",
        purpose=AIModelPolicy.Purpose.ASSISTANT,
        system_instruction="No tools.",
        allowed_source_types=["crm.lead"],
        allowed_data_classifications=["internal"],
        allowed_tool_codes=[],
        max_context_records=20,
        max_output_characters=4000,
        human_review_required=False,
        citations_required=True,
        retention_days=30,
        effective_from=timezone.now(),
        is_active=True,
        version=1,
    )
    policy.full_clean()


def test_ai_entity_insight_full_clean_allows_empty_override(company_factory, user_factory, membership_factory):
    company = company_factory()
    user = user_factory(email="ai-validation@example.com")
    membership = membership_factory(user, company)
    provider = AIProviderProfile.objects.create(
        company=company,
        code="LOCAL_INSIGHT_VALIDATION",
        display_name="Local validation",
        adapter_code="local_grounded",
        is_active=True,
    )
    policy = AIModelPolicy.objects.create(
        company=company,
        provider=provider,
        code="INSIGHT_VALIDATION_POLICY",
        name="Insight validation policy",
        model_name="local-validation",
        purpose=AIModelPolicy.Purpose.ASSISTANT,
        allowed_source_types=["crm.lead"],
        allowed_data_classifications=["internal"],
        allowed_tool_codes=[],
        max_context_records=20,
        max_output_characters=4000,
        human_review_required=False,
        citations_required=True,
        retention_days=30,
        effective_from=timezone.now(),
        is_active=True,
        version=1,
    )
    interaction = AIInteraction.objects.create(
        company=company,
        policy=policy,
        requested_by_public_id=user.public_id,
        membership_public_id=membership.public_id,
        idempotency_key=f"validation-{uuid.uuid4()}",
        purpose=AIModelPolicy.Purpose.ASSISTANT,
        prompt_digest="a" * 64,
        prompt_excerpt="validation",
        status=AIInteraction.Status.COMPLETED,
        response_text="validation",
        citations_required=True,
        review_status=AIInteraction.ReviewStatus.NOT_REQUIRED,
        input_metadata={"validation": True},
        output_metadata={"summary": "validation"},
        provider_code_snapshot=provider.code,
        model_name_snapshot=policy.model_name,
        started_at=timezone.now(),
        completed_at=timezone.now(),
    )
    insight = AIEntityInsight(
        company=company,
        interaction=interaction,
        subject_type="crm.lead",
        subject_public_id=uuid.uuid4(),
        insight_code="CRM_LEAD_INTELLIGENCE",
        source_digest="b" * 64,
        output_payload={"summary": "validation"},
        override_payload={},
        generated_at=timezone.now(),
    )
    insight.full_clean()
