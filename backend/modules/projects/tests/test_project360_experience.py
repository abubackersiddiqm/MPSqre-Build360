from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from modules.configuration.models import ConfigurationDefinition, ConfigurationVersion
from modules.projects.application.experience import project_experience
from modules.projects.models import DeliveryStage, Project

pytestmark = pytest.mark.django_db


def test_project360_uses_published_lifecycle_and_existing_project(company_factory, user_factory, membership_factory):
    company = company_factory()
    user = user_factory()
    membership = membership_factory(user, company)
    stage = DeliveryStage.objects.create(
        company=company,
        entity_type=DeliveryStage.EntityType.PROJECT,
        code="preconstruction",
        name="Pre-construction",
        outcome=DeliveryStage.Outcome.OPEN,
        sort_order=10,
        is_initial=True,
        effective_from=timezone.now() - timedelta(minutes=1),
    )
    project = Project.objects.create(
        company=company,
        code="P360-001",
        name="Visual journey project",
        customer_public_id=user.public_id,
        opportunity_public_id=membership.public_id,
        stage=stage,
        manager_membership_public_id=membership.public_id,
        currency=company.currency,
        approved_budget=Decimal("1000000"),
    )
    definition, _ = ConfigurationDefinition.objects.get_or_create(
        code="PROJECT360_LIFECYCLE",
        defaults={"name": "Project360 lifecycle", "schema": {}, "data_class": "OPERATIONAL_CONFIGURATION"},
    )
    ConfigurationVersion.objects.create(
        company=company,
        definition=definition,
        version=1,
        status=ConfigurationVersion.Status.PUBLISHED,
        payload={"steps": [{"code": "CRM", "label": "CRM"}, {"code": "PRECONSTRUCTION", "label": "Pre-construction"}, {"code": "DESIGN", "label": "Design"}]},
        effective_from=timezone.now() - timedelta(minutes=1),
        created_by_public_id=user.public_id,
        published_at=timezone.now(),
        checksum="test-project360",
    )

    payload = project_experience(company=company, project=project, permission_codes={"project.dashboard.read"})
    assert payload["configured"] is True
    assert payload["project"]["public_id"] == str(project.public_id)
    assert [step["code"] for step in payload["steps"]] == ["CRM", "PRECONSTRUCTION", "DESIGN"]
    assert payload["steps"][0]["status"] == "COMPLETE"
    assert payload["steps"][2]["status"] == "RESTRICTED"
    assert payload["steps"][2]["evidence"] == {"available": False}
