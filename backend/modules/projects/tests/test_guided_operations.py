from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from modules.crm.models import Customer
from modules.procurement.models import PurchaseRequest
from modules.projects.application.guided_operations import (
    project_procurement_flow,
    universal_search,
)
from modules.projects.models import DeliveryStage, Project
from modules.vendor.models import SupplyStage

pytestmark = pytest.mark.django_db


def _project_stage(company):
    return DeliveryStage.objects.create(
        company=company,
        entity_type=DeliveryStage.EntityType.PROJECT,
        code="open",
        name="Open",
        outcome=DeliveryStage.Outcome.OPEN,
        sort_order=10,
        is_initial=True,
        effective_from=timezone.now() - timedelta(minutes=1),
    )


def test_universal_search_is_permission_scoped(company_factory, user_factory, membership_factory):
    company = company_factory()
    user = user_factory()
    membership = membership_factory(user, company)
    project = Project.objects.create(
        company=company,
        code="SRCH-001",
        name="Searchable Residence",
        stage=_project_stage(company),
        manager_membership_public_id=membership.public_id,
        currency=company.currency,
    )
    Customer.objects.create(
        company=company,
        kind=Customer.Kind.ORGANIZATION,
        display_name="Private Customer",
        normalized_name="private customer",
    )

    project_only = universal_search(
        company=company,
        query="Search",
        permission_codes={"project.dashboard.read"},
    )
    assert [item["kind"] for item in project_only["items"]] == ["PROJECT"]
    assert project_only["items"][0]["public_id"] == str(project.public_id)

    crm_only = universal_search(
        company=company,
        query="Private",
        permission_codes={"crm.dashboard.read"},
    )
    assert [item["kind"] for item in crm_only["items"]] == ["CUSTOMER"]


def test_procurement_flow_projects_existing_request_without_shadow_record(
    company_factory,
    user_factory,
    membership_factory,
):
    company = company_factory()
    user = user_factory()
    membership = membership_factory(user, company)
    project = Project.objects.create(
        company=company,
        code="PROC-001",
        name="Procurement Residence",
        stage=_project_stage(company),
        manager_membership_public_id=membership.public_id,
        currency=company.currency,
        approved_budget=Decimal("500000"),
    )
    stage = SupplyStage.objects.create(
        company=company,
        entity_type=SupplyStage.EntityType.PURCHASE_REQUEST,
        code="draft",
        name="Draft",
        outcome=SupplyStage.Outcome.OPEN,
        sort_order=10,
        is_initial=True,
        effective_from=timezone.now() - timedelta(minutes=1),
    )
    request = PurchaseRequest.objects.create(
        company=company,
        request_number="PR-001",
        title="Cement requirement",
        project=project,
        stage=stage,
        requester_membership_public_id=membership.public_id,
        currency=company.currency,
        estimated_total=Decimal("25000"),
    )

    payload = project_procurement_flow(company=company, project=project)

    assert payload["summary"]["requests"] == 1
    assert payload["requests"][0]["public_id"] == str(request.public_id)
    assert payload["requests"][0]["current_step"] == "RFQ"
    assert payload["requests"][0]["status"] == "ACTION"


def test_executive_portfolio_uses_existing_project_tasks(company_factory, user_factory, membership_factory):
    from modules.projects.application.guided_operations import executive_portfolio
    from modules.projects.models import ProjectTask

    company = company_factory()
    user = user_factory()
    membership = membership_factory(user, company)
    project = Project.objects.create(
        company=company,
        code="EXEC-001",
        name="Executive Residence",
        stage=_project_stage(company),
        manager_membership_public_id=membership.public_id,
        currency=company.currency,
        approved_budget=Decimal("1000000"),
    )
    task_stage = DeliveryStage.objects.create(
        company=company,
        entity_type=DeliveryStage.EntityType.TASK,
        code="doing",
        name="Doing",
        outcome=DeliveryStage.Outcome.OPEN,
        sort_order=10,
        is_initial=True,
        effective_from=timezone.now() - timedelta(minutes=1),
    )
    ProjectTask.objects.create(
        company=company,
        project=project,
        code="T-001",
        title="Late task",
        stage=task_stage,
        assignee_membership_public_id=membership.public_id,
        planned_end_date=timezone.localdate() - timedelta(days=1),
        progress_percent=30,
    )

    payload = executive_portfolio(company=company, permission_codes={"project.dashboard.read"})

    assert payload["summary"]["active_projects"] == 1
    assert payload["projects"][0]["overdue_tasks"] == 1
    assert payload["projects"][0]["health"] in {"ATTENTION", "CRITICAL"}
    assert payload["finance"] is None


def test_executive_portfolio_history_requires_insights_permission(company_factory):
    from modules.insightops.models import PortfolioSnapshot
    from modules.projects.application.guided_operations import executive_portfolio

    company = company_factory()
    PortfolioSnapshot.objects.create(
        company=company,
        code="PORTFOLIO-2026-08",
        as_of_date=timezone.localdate(),
        status_code="PUBLISHED",
        projects_total=3,
        projects_healthy=2,
        projects_at_risk=1,
        projects_critical=0,
        schedule_performance_percent=Decimal("88.00"),
        cost_performance_percent=Decimal("94.00"),
        portfolio_value=Decimal("1000000"),
        currency=company.currency,
        created_by_public_id=company.public_id,
        published_at=timezone.now(),
    )

    restricted = executive_portfolio(
        company=company,
        permission_codes={"project.dashboard.read"},
    )
    assert restricted["history_available"] is False
    assert restricted["history"] == []

    permitted = executive_portfolio(
        company=company,
        permission_codes={"project.dashboard.read", "insights.view"},
    )
    assert permitted["history_available"] is True
    assert len(permitted["history"]) == 1
    assert permitted["history"][0]["code"] == "PORTFOLIO-2026-08"
