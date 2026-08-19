import hashlib
import uuid

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from modules.ai.application.services import (
    create_extraction_job,
    create_grounded_interaction,
    decide_tool_action,
    propose_tool_action,
    run_evaluation,
)
from modules.ai.models import AICitation, AIModelPolicy, AIProviderProfile, AIToolAction
from modules.platform.actors import RequestActor
from modules.reporting.models import MetricDefinition


@pytest.fixture
def ai_context(company_factory, user_factory, membership_factory):
    company = company_factory()
    requester = user_factory()
    reviewer = user_factory()
    membership = membership_factory(requester, company)
    reviewer_membership = membership_factory(reviewer, company)
    provider = AIProviderProfile.objects.create(
        company=company,
        code="LOCAL_GROUNDED",
        display_name="Local governed",
        adapter_code="local_grounded",
        supports_citations=True,
        supports_extraction=True,
        supports_tools=True,
        is_active=True,
    )
    assistant = AIModelPolicy.objects.create(
        company=company,
        code="BUILD360_ASSISTANT",
        name="Assistant",
        provider=provider,
        model_name="local-v1",
        purpose=AIModelPolicy.Purpose.ASSISTANT,
        allowed_source_types=["reporting.metric"],
        allowed_data_classifications=["internal"],
        allowed_tool_codes=["notification.draft"],
        human_review_required=True,
        citations_required=True,
        effective_from=timezone.now(),
    )
    extraction = AIModelPolicy.objects.create(
        company=company,
        code="BUILD360_EXTRACTION",
        name="Extraction",
        provider=provider,
        model_name="local-v1",
        purpose=AIModelPolicy.Purpose.EXTRACTION,
        allowed_source_types=["document.text"],
        allowed_data_classifications=["internal"],
        human_review_required=True,
        citations_required=False,
        effective_from=timezone.now(),
    )
    return {
        "company": company,
        "requester": RequestActor(
            user_public_id=requester.public_id,
            membership_public_id=membership.public_id,
            request_id=uuid.uuid4(),
            ip_address="127.0.0.1",
            user_agent="pytest",
        ),
        "reviewer": RequestActor(
            user_public_id=reviewer.public_id,
            membership_public_id=reviewer_membership.public_id,
            request_id=uuid.uuid4(),
            ip_address="127.0.0.1",
            user_agent="pytest",
        ),
        "assistant": assistant,
        "extraction": extraction,
    }


@pytest.mark.django_db
def test_grounded_interaction_is_cited_and_idempotent(ai_context):
    company = ai_context["company"]
    actor = ai_context["requester"]
    MetricDefinition.objects.create(
        company=company,
        code="PROJECTS_ACTIVE",
        name="Active projects",
        domain_code="projects",
        calculation_code="projects.active",
        unit_code="count",
        data_classification="internal",
    )
    interaction = create_grounded_interaction(
        company=company,
        actor=actor,
        permission_codes={"project.dashboard.read", "ai.interaction.create"},
        policy_code="BUILD360_ASSISTANT",
        prompt="Summarize active projects",
        metric_codes=["PROJECTS_ACTIVE"],
        idempotency_key="grounded-1",
    )
    duplicate = create_grounded_interaction(
        company=company,
        actor=actor,
        permission_codes={"project.dashboard.read", "ai.interaction.create"},
        policy_code="BUILD360_ASSISTANT",
        prompt="Summarize active projects",
        metric_codes=["PROJECTS_ACTIVE"],
        idempotency_key="grounded-1",
    )
    assert duplicate.public_id == interaction.public_id
    assert interaction.prompt_digest == hashlib.sha256(b"Summarize active projects").hexdigest()
    assert "[1] Active projects" in interaction.response_text
    assert AICitation.objects.filter(interaction=interaction).count() == 1


@pytest.mark.django_db
def test_extraction_does_not_persist_raw_source(ai_context):
    source = "contract_number: CNT-100\nvendor_name: Example Vendor"
    job = create_extraction_job(
        company=ai_context["company"],
        actor=ai_context["requester"],
        policy_code="BUILD360_EXTRACTION",
        source_type="document.text",
        source_public_id=None,
        source_text=source,
        schema_code="CONTRACT_HEADER",
        requested_fields=["contract_number", "vendor_name"],
        idempotency_key="extract-1",
    )
    assert job.extracted_payload["contract_number"] == "CNT-100"
    assert job.source_digest == hashlib.sha256(source.encode()).hexdigest()
    assert source not in str(job.__dict__)


@pytest.mark.django_db
def test_tool_action_requires_independent_confirmation(ai_context):
    company = ai_context["company"]
    requester = ai_context["requester"]
    MetricDefinition.objects.create(
        company=company,
        code="PROJECTS_ACTIVE",
        name="Active projects",
        domain_code="projects",
        calculation_code="projects.active",
        unit_code="count",
        data_classification="internal",
    )
    interaction = create_grounded_interaction(
        company=company,
        actor=requester,
        permission_codes={"project.dashboard.read"},
        policy_code="BUILD360_ASSISTANT",
        prompt="Prepare a draft notice",
        metric_codes=["PROJECTS_ACTIVE"],
        idempotency_key="grounded-action",
    )
    action = propose_tool_action(
        company=company,
        actor=requester,
        interaction_public_id=interaction.public_id,
        action_code="notification.draft",
        target_type="project",
        target_public_id=None,
        proposed_payload={"title": "Draft only"},
        idempotency_key="action-1",
    )
    with pytest.raises(ValidationError, match="independent"):
        decide_tool_action(
            company=company,
            actor=requester,
            action_public_id=action.public_id,
            decision="confirm",
            reason="self approval",
        )
    confirmed = decide_tool_action(
        company=company,
        actor=ai_context["reviewer"],
        action_public_id=action.public_id,
        decision="confirm",
        reason="reviewed",
    )
    assert confirmed.status == AIToolAction.Status.CONFIRMED


@pytest.mark.django_db
def test_guardrail_evaluation_records_evidence(ai_context):
    run = run_evaluation(
        company=ai_context["company"],
        actor=ai_context["requester"],
        policy_code="BUILD360_ASSISTANT",
    )
    assert run.status == "completed"
    assert run.passed_count == run.scenario_count

@pytest.mark.django_db
def test_extraction_policy_evaluation_accepts_review_gated_provenance(ai_context):
    run = run_evaluation(
        company=ai_context["company"],
        actor=ai_context["requester"],
        policy_code="BUILD360_EXTRACTION",
    )
    assert run.status == "completed"
    assert run.passed_count == run.scenario_count

