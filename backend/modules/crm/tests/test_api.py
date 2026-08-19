import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from modules.crm.models import PipelineStage

pytestmark = pytest.mark.django_db


def configure_lead_stage(company):
    return PipelineStage.objects.create(
        company=company,
        entity_type=PipelineStage.EntityType.LEAD,
        code="new",
        name="New",
        outcome=PipelineStage.Outcome.OPEN,
        sort_order=10,
        allowed_next_codes=[],
        is_initial=True,
        effective_from=timezone.now() - timedelta(minutes=1),
    )


def authorize(client, token_pair, company):
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {token_pair.access_token}",
        HTTP_X_COMPANY_ID=str(company.public_id),
        HTTP_X_REQUEST_ID=str(uuid.uuid4()),
    )


def test_lead_api_never_leaks_cross_tenant_records(
    api_client,
    company_factory,
    user_factory,
    permission_grant_factory,
    token_pair_factory,
):
    company_a = company_factory()
    company_b = company_factory()
    user = user_factory()
    permission_grant_factory(
        user,
        company_a,
        ["crm.lead.read", "crm.lead.manage", "crm.stage.read"],
    )
    configure_lead_stage(company_a)
    configure_lead_stage(company_b)
    token_pair = token_pair_factory(user)
    authorize(api_client, token_pair, company_a)

    response = api_client.post(
        "/api/v1/crm/leads",
        {"title": "Tenant A opportunity", "contact_first_name": "Tenant", "contact_phone": "+919900001111"},
        format="json",
    )
    assert response.status_code == 201
    created_id = response.json()["public_id"]

    api_client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {token_pair.access_token}",
        HTTP_X_COMPANY_ID=str(company_b.public_id),
    )
    denied = api_client.get(f"/api/v1/crm/leads/{created_id}")
    assert denied.status_code in {404, 403}


def test_contact_reveal_requires_privileged_permission(
    api_client,
    company_factory,
    user_factory,
    permission_grant_factory,
    token_pair_factory,
):
    company = company_factory()
    user = user_factory()
    permission_grant_factory(
        user,
        company,
        ["crm.contact.read", "crm.contact.manage"],
    )
    token_pair = token_pair_factory(user)
    authorize(api_client, token_pair, company)
    created = api_client.post(
        "/api/v1/crm/contacts",
        {"first_name": "Ravi", "email": "ravi@example.test"},
        format="json",
    )
    assert created.status_code == 201
    contact_id = created.json()["public_id"]
    assert created.json()["email_masked"].startswith("••••")
    assert "ravi@example.test" not in str(created.json())

    reveal = api_client.post(
        f"/api/v1/crm/contacts/{contact_id}/reveal",
        {"reason_code": "customer-support"},
        format="json",
    )
    assert reveal.status_code == 403


def test_preconstruction_project_is_idempotent_and_reused_after_win(
    api_client,
    company_factory,
    user_factory,
    permission_grant_factory,
    token_pair_factory,
):
    from decimal import Decimal

    from modules.crm.models import Customer, Opportunity
    from modules.projects.models import DeliveryStage, Project

    company = company_factory()
    user = user_factory()
    membership = permission_grant_factory(
        user,
        company,
        ["crm.opportunity.manage", "project.project.manage"],
    )
    DeliveryStage.objects.create(
        company=company,
        entity_type=DeliveryStage.EntityType.PROJECT,
        code="preconstruction",
        name="Preconstruction",
        outcome=DeliveryStage.Outcome.OPEN,
        sort_order=10,
        is_initial=True,
        effective_from=timezone.now() - timedelta(minutes=1),
    )
    open_stage = PipelineStage.objects.create(
        company=company,
        entity_type=PipelineStage.EntityType.OPPORTUNITY,
        code="qualified",
        name="Qualified",
        outcome=PipelineStage.Outcome.OPEN,
        sort_order=10,
        is_initial=True,
        effective_from=timezone.now() - timedelta(minutes=1),
    )
    won_stage = PipelineStage.objects.create(
        company=company,
        entity_type=PipelineStage.EntityType.OPPORTUNITY,
        code="won",
        name="Won",
        outcome=PipelineStage.Outcome.WON,
        sort_order=90,
        effective_from=timezone.now() - timedelta(minutes=1),
    )
    customer = Customer.objects.create(
        company=company,
        kind=Customer.Kind.ORGANIZATION,
        display_name="Preconstruction Client",
        normalized_name="preconstruction client",
    )
    opportunity = Opportunity.objects.create(
        company=company,
        name="Residence Design and Build",
        customer=customer,
        stage=open_stage,
        owner_membership_public_id=membership.public_id,
        amount=Decimal("3000000"),
        currency="INR",
        probability_percent=60,
    )
    authorize(api_client, token_pair_factory(user), company)

    first = api_client.post(
        f"/api/v1/crm/opportunities/{opportunity.public_id}/start-preconstruction",
        {},
        format="json",
    )
    second = api_client.post(
        f"/api/v1/crm/opportunities/{opportunity.public_id}/start-preconstruction",
        {},
        format="json",
    )
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["public_id"] == second.json()["public_id"]
    assert Project.objects.filter(company=company, opportunity_public_id=opportunity.public_id).count() == 1

    opportunity.stage = won_stage
    opportunity.save(update_fields=["stage", "updated_at"])
    awarded = api_client.post(
        f"/api/v1/crm/opportunities/{opportunity.public_id}/convert-project",
        {},
        format="json",
    )
    assert awarded.status_code == 200
    assert awarded.json()["public_id"] == first.json()["public_id"]
    assert Project.objects.filter(company=company, opportunity_public_id=opportunity.public_id).count() == 1


def test_crm_core_subscription_override_blocks_api_even_with_permission(
    api_client,
    company_factory,
    user_factory,
    permission_grant_factory,
    token_pair_factory,
):
    from modules.subscription.application.feature_control import append_feature_override

    company = company_factory()
    user = user_factory()
    permission_grant_factory(user, company, ["crm.dashboard.read"])
    append_feature_override(
        company=company,
        code="crm.core",
        enabled=False,
        reason_code="subscription-disabled",
        set_by_public_id=user.public_id,
        correlation_id=uuid.uuid4(),
    )
    authorize(api_client, token_pair_factory(user), company)

    response = api_client.get("/api/v1/crm/summary")
    assert response.status_code == 403


def test_crm_only_subscription_blocks_construction_project_conversion(
    api_client,
    company_factory,
    user_factory,
    permission_grant_factory,
    token_pair_factory,
):
    from modules.crm.models import Customer, Opportunity
    from modules.subscription.application.feature_control import append_feature_override

    company = company_factory()
    user = user_factory()
    membership = permission_grant_factory(
        user,
        company,
        ["crm.opportunity.manage", "project.project.manage"],
    )
    stage = PipelineStage.objects.create(
        company=company,
        entity_type=PipelineStage.EntityType.OPPORTUNITY,
        code="qualified-crm-only",
        name="Qualified",
        outcome=PipelineStage.Outcome.OPEN,
        sort_order=10,
        is_initial=True,
        effective_from=timezone.now() - timedelta(minutes=1),
    )
    customer = Customer.objects.create(
        company=company,
        kind=Customer.Kind.ORGANIZATION,
        display_name="CRM-only customer",
        normalized_name="crm-only customer",
    )
    opportunity = Opportunity.objects.create(
        company=company,
        name="Generic CRM deal",
        customer=customer,
        stage=stage,
        owner_membership_public_id=membership.public_id,
        amount="100000",
        currency="INR",
        probability_percent=50,
    )
    append_feature_override(
        company=company,
        code="module.delivery",
        enabled=False,
        reason_code="crm-only-package",
        set_by_public_id=user.public_id,
        correlation_id=uuid.uuid4(),
    )
    authorize(api_client, token_pair_factory(user), company)

    response = api_client.post(
        f"/api/v1/crm/opportunities/{opportunity.public_id}/start-preconstruction",
        {},
        format="json",
    )
    assert response.status_code == 403
