import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from modules.crm.models import Customer, Opportunity, PipelineStage
from modules.projects.models import DeliveryStage, Project
from modules.subscription.application.feature_control import append_feature_override

pytestmark = pytest.mark.django_db


def authorize(client, token_pair, company):
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {token_pair.access_token}",
        HTTP_X_COMPANY_ID=str(company.public_id),
        HTTP_X_REQUEST_ID=str(uuid.uuid4()),
    )


def opportunity_stage(company, code, outcome, *, initial=False):
    return PipelineStage.objects.create(
        company=company,
        entity_type=PipelineStage.EntityType.OPPORTUNITY,
        code=code,
        name=code.replace("_", " ").title(),
        outcome=outcome,
        sort_order=10 if initial else 90,
        is_initial=initial,
        effective_from=timezone.now() - timedelta(minutes=1),
    )


def project_initial_stage(company):
    return DeliveryStage.objects.create(
        company=company,
        entity_type=DeliveryStage.EntityType.PROJECT,
        code="preconstruction",
        name="Preconstruction",
        outcome=DeliveryStage.Outcome.OPEN,
        sort_order=10,
        is_initial=True,
        effective_from=timezone.now() - timedelta(minutes=1),
    )


def test_project_domain_owns_idempotent_crm_preconstruction_handoff(
    api_client,
    company_factory,
    user_factory,
    permission_grant_factory,
    token_pair_factory,
):
    company = company_factory()
    user = user_factory()
    membership = permission_grant_factory(
        user,
        company,
        ["crm.opportunity.manage", "project.project.manage"],
    )
    project_initial_stage(company)
    qualified = opportunity_stage(company, "qualified-v20o", PipelineStage.Outcome.OPEN, initial=True)
    won = opportunity_stage(company, "won-v20o", PipelineStage.Outcome.WON)
    customer = Customer.objects.create(
        company=company,
        kind=Customer.Kind.ORGANIZATION,
        display_name="Guided Handoff Client",
        normalized_name="guided handoff client",
    )
    opportunity = Opportunity.objects.create(
        company=company,
        name="Guided Preconstruction Deal",
        customer=customer,
        stage=qualified,
        owner_membership_public_id=membership.public_id,
        amount=Decimal("2500000"),
        currency="INR",
        probability_percent=65,
    )
    authorize(api_client, token_pair_factory(user), company)

    first = api_client.post(
        f"/api/v1/projects/from-crm-opportunity/{opportunity.public_id}",
        {"mode": "preconstruction"},
        format="json",
    )
    second = api_client.post(
        f"/api/v1/projects/from-crm-opportunity/{opportunity.public_id}",
        {"mode": "preconstruction"},
        format="json",
    )
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["public_id"] == second.json()["public_id"]
    assert Project.objects.filter(company=company, opportunity_public_id=opportunity.public_id).count() == 1

    opportunity.stage = won
    opportunity.save(update_fields=["stage", "updated_at"])
    awarded = api_client.post(
        f"/api/v1/projects/from-crm-opportunity/{opportunity.public_id}",
        {"mode": "award"},
        format="json",
    )
    assert awarded.status_code == 200
    assert awarded.json()["public_id"] == first.json()["public_id"]
    assert awarded.json()["created"] is False


def test_crm_only_tenant_cannot_call_delivery_handoff_endpoint(
    api_client,
    company_factory,
    user_factory,
    permission_grant_factory,
    token_pair_factory,
):
    company = company_factory()
    user = user_factory()
    membership = permission_grant_factory(
        user,
        company,
        ["crm.opportunity.manage", "project.project.manage"],
    )
    stage = opportunity_stage(company, "qualified-crm-only-v20o", PipelineStage.Outcome.OPEN, initial=True)
    customer = Customer.objects.create(
        company=company,
        kind=Customer.Kind.ORGANIZATION,
        display_name="CRM Only Client",
        normalized_name="crm only client",
    )
    opportunity = Opportunity.objects.create(
        company=company,
        name="CRM-only generic deal",
        customer=customer,
        stage=stage,
        owner_membership_public_id=membership.public_id,
        amount=Decimal("100000"),
        currency="INR",
        probability_percent=50,
    )
    append_feature_override(
        company=company,
        code="module.delivery",
        enabled=False,
        reason_code="crm-only-v20o",
        set_by_public_id=user.public_id,
        correlation_id=uuid.uuid4(),
    )
    authorize(api_client, token_pair_factory(user), company)

    response = api_client.post(
        f"/api/v1/projects/from-crm-opportunity/{opportunity.public_id}",
        {"mode": "preconstruction"},
        format="json",
    )
    assert response.status_code == 403


def test_won_opportunity_handoff_bootstraps_fresh_delivery_workflow(
    api_client,
    company_factory,
    user_factory,
    permission_grant_factory,
    token_pair_factory,
):
    company = company_factory()
    user = user_factory()
    membership = permission_grant_factory(
        user,
        company,
        ["crm.opportunity.manage", "project.project.manage"],
    )
    won = opportunity_stage(company, "won-v20o1", PipelineStage.Outcome.WON, initial=True)
    customer = Customer.objects.create(
        company=company,
        kind=Customer.Kind.ORGANIZATION,
        display_name="Fresh Delivery Client",
        normalized_name="fresh delivery client",
    )
    opportunity = Opportunity.objects.create(
        company=company,
        name="Fresh Awarded Deal",
        customer=customer,
        stage=won,
        owner_membership_public_id=membership.public_id,
        amount=Decimal("200000"),
        currency="INR",
        probability_percent=100,
    )
    assert DeliveryStage.objects.filter(company=company).count() == 0
    authorize(api_client, token_pair_factory(user), company)

    response = api_client.post(
        f"/api/v1/projects/from-crm-opportunity/{opportunity.public_id}",
        {"mode": "award"},
        format="json",
    )

    assert response.status_code == 201
    created = Project.objects.get(company=company, opportunity_public_id=opportunity.public_id)
    assert created.location == {}
    for entity_type in DeliveryStage.EntityType.values:
        assert DeliveryStage.objects.filter(
            company=company,
            entity_type=entity_type,
            is_initial=True,
            is_active=True,
        ).exists()


def test_manual_project_create_bootstraps_defaults_without_replacing_custom_project_stage(
    api_client,
    company_factory,
    user_factory,
    permission_grant_factory,
    token_pair_factory,
):
    company = company_factory()
    user = user_factory()
    membership = permission_grant_factory(user, company, ["project.project.manage"])
    custom_stage = DeliveryStage.objects.create(
        company=company,
        entity_type=DeliveryStage.EntityType.PROJECT,
        code="intake-custom-v20o1",
        name="Custom Intake",
        outcome=DeliveryStage.Outcome.OPEN,
        sort_order=5,
        is_initial=True,
        effective_from=timezone.now() - timedelta(minutes=1),
    )
    authorize(api_client, token_pair_factory(user), company)

    response = api_client.post(
        "/api/v1/projects/items",
        {
            "code": "MANUAL-V20O1",
            "name": "Manual Project",
            "manager_membership_public_id": str(membership.public_id),
            "approved_budget": "150000",
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["location"] == {}
    assert response.json()["stage"]["code"] == custom_stage.code
    assert DeliveryStage.objects.filter(
        company=company,
        entity_type=DeliveryStage.EntityType.PROJECT,
    ).count() == 1
    for entity_type in [
        DeliveryStage.EntityType.TASK,
        DeliveryStage.EntityType.DESIGN_VERSION,
        DeliveryStage.EntityType.ESTIMATE_VERSION,
    ]:
        assert DeliveryStage.objects.filter(
            company=company,
            entity_type=entity_type,
            is_initial=True,
            is_active=True,
        ).exists()
