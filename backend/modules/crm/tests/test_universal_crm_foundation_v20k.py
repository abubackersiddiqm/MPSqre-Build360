import uuid
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from modules.crm.application.configuration import (
    apply_industry_pack,
    configuration_payload,
    create_custom_field,
    create_pipeline,
    ensure_foundation,
)
from modules.crm.application.services import RequestActor, create_lead, transition_lead
from modules.crm.models import CrmCustomFieldDefinition, PipelineStage

pytestmark = pytest.mark.django_db


def actor(membership, user) -> RequestActor:
    return RequestActor(
        user_public_id=user.public_id,
        membership_public_id=membership.public_id,
        request_id=uuid.uuid4(),
    )


def test_industry_pack_is_tenant_scoped_and_switching_packs_preserves_data_definitions(
    company_factory,
):
    company = company_factory(display_name="Universal CRM Tenant")
    other = company_factory(display_name="Other Tenant")

    apply_industry_pack(company=company, pack_code="financial_services")
    financial = configuration_payload(company)
    untouched = configuration_payload(other)

    assert financial["profile"]["industry_code"] == "financial_services"
    assert financial["profile"]["terminology"]["lead"] == "Applicant"
    assert "requested_amount" in {field["code"] for field in financial["custom_fields"]}
    assert untouched["profile"]["industry_code"] == "general"
    assert "requested_amount" not in {field["code"] for field in untouched["custom_fields"]}

    apply_industry_pack(company=company, pack_code="construction")
    construction = configuration_payload(company)
    active_codes = {field["code"] for field in construction["custom_fields"]}

    assert construction["profile"]["industry_code"] == "construction"
    assert "project_type" in active_codes
    assert "employment_type" not in active_codes
    assert CrmCustomFieldDefinition.objects.filter(
        company=company,
        code="employment_type",
        is_active=False,
    ).exists()


def test_required_custom_field_is_enforced_server_side(
    company_factory,
    user_factory,
    membership_factory,
):
    company = company_factory()
    user = user_factory()
    membership = membership_factory(user, company)
    ensure_foundation(company)
    create_custom_field(
        company=company,
        entity_type="lead",
        code="external_case_id",
        label="External case ID",
        field_type="text",
        is_required=True,
    )

    with pytest.raises(ValidationError, match="external_case_id"):
        create_lead(
            company=company,
            actor=actor(membership, user),
            title="Missing governed field",
        )

    lead = create_lead(
        company=company,
        actor=actor(membership, user),
        title="Complete governed field",
        custom_fields={"external_case_id": "CASE-1001"},
    )
    assert lead.custom_fields == {"external_case_id": "CASE-1001"}


def test_stage_codes_can_repeat_across_pipelines_but_transitions_cannot_cross_them(
    company_factory,
    user_factory,
    membership_factory,
):
    company = company_factory()
    user = user_factory()
    membership = membership_factory(user, company)
    ensure_foundation(company)

    custom_pipeline = create_pipeline(
        company=company,
        entity_type="lead",
        code="partner_sales",
        name="Partner Sales",
    )
    custom_new = PipelineStage.objects.create(
        company=company,
        pipeline=custom_pipeline,
        entity_type=PipelineStage.EntityType.LEAD,
        code="new",
        name="New",
        outcome=PipelineStage.Outcome.OPEN,
        sort_order=10,
        probability_percent=5,
        allowed_next_codes=["qualified"],
        is_initial=True,
        effective_from=timezone.now(),
    )
    custom_qualified = PipelineStage.objects.create(
        company=company,
        pipeline=custom_pipeline,
        entity_type=PipelineStage.EntityType.LEAD,
        code="qualified",
        name="Qualified",
        outcome=PipelineStage.Outcome.QUALIFIED,
        sort_order=20,
        probability_percent=30,
        allowed_next_codes=[],
        effective_from=timezone.now(),
    )
    default_qualified = PipelineStage.objects.get(
        company=company,
        pipeline__is_default=True,
        entity_type=PipelineStage.EntityType.LEAD,
        code="qualified",
    )

    lead = create_lead(
        company=company,
        actor=actor(membership, user),
        title="Partner enquiry",
        pipeline_public_id=custom_pipeline.public_id,
        estimated_value=Decimal("250000"),
    )
    assert lead.stage_id == custom_new.id

    with pytest.raises(ValidationError, match="cannot cross CRM pipelines"):
        transition_lead(
            company=company,
            actor=actor(membership, user),
            lead_public_id=lead.public_id,
            target_stage_public_id=default_qualified.public_id,
            expected_version=1,
        )

    moved = transition_lead(
        company=company,
        actor=actor(membership, user),
        lead_public_id=lead.public_id,
        target_stage_public_id=custom_qualified.public_id,
        expected_version=1,
    )
    assert moved.stage_id == custom_qualified.id
