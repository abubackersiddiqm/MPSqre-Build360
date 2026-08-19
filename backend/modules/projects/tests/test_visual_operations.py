from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from modules.design.models import DesignDocument, DesignIssue, DesignReview, DesignVersion
from modules.projects.application.visual_operations import project_design_board
from modules.projects.models import DeliveryStage, Project

pytestmark = pytest.mark.django_db


def _stage(company, *, entity_type, code, name, outcome, sort_order=10, initial=False):
    return DeliveryStage.objects.create(
        company=company,
        entity_type=entity_type,
        code=code,
        name=name,
        outcome=outcome,
        sort_order=sort_order,
        is_initial=initial,
        effective_from=timezone.now() - timedelta(minutes=1),
    )


def test_design_board_projects_existing_design_records_without_shadow_tables(
    company_factory,
    user_factory,
    membership_factory,
):
    company = company_factory()
    user = user_factory()
    membership = membership_factory(user, company)
    project_stage = _stage(
        company,
        entity_type=DeliveryStage.EntityType.PROJECT,
        code="preconstruction",
        name="Pre-construction",
        outcome=DeliveryStage.Outcome.OPEN,
        initial=True,
    )
    design_stage = _stage(
        company,
        entity_type=DeliveryStage.EntityType.DESIGN_VERSION,
        code="review",
        name="Under review",
        outcome=DeliveryStage.Outcome.REVIEW,
        initial=True,
    )
    project = Project.objects.create(
        company=company,
        code="VIS-001",
        name="Visual residence",
        stage=project_stage,
        manager_membership_public_id=membership.public_id,
        currency=company.currency,
        approved_budget=Decimal("1000000"),
    )
    document = DesignDocument.objects.create(
        company=company,
        project=project,
        document_number="A-101",
        title="Living room elevation",
        discipline_code="ARCH",
        document_type_code="ELEVATION",
        created_by_public_id=user.public_id,
    )
    version = DesignVersion.objects.create(
        company=company,
        document=document,
        version_number=1,
        revision_code="R01",
        stage=design_stage,
        created_by_public_id=user.public_id,
    )
    DesignReview.objects.create(
        company=company,
        design_version=version,
        reviewer_membership_public_id=membership.public_id,
        requested_by_public_id=user.public_id,
        requested_at=timezone.now(),
    )
    DesignIssue.objects.create(
        company=company,
        project=project,
        design_version=version,
        title="Dimension confirmation",
        severity=DesignIssue.Severity.MEDIUM,
        raised_by_public_id=user.public_id,
    )

    payload = project_design_board(
        company=company,
        project=project,
        permission_codes={"design.document.read", "files.download"},
    )

    assert payload["available"] is True
    assert payload["summary"]["documents"] == 1
    assert payload["summary"]["pending_reviews"] == 1
    assert payload["summary"]["open_issues"] == 1
    assert payload["permissions"]["can_download_files"] is True
    assert payload["documents"][0]["document_number"] == "A-101"
    assert payload["documents"][0]["latest_version"]["revision_code"] == "R01"


def test_design_board_does_not_disclose_documents_without_permission(
    company_factory,
    user_factory,
    membership_factory,
):
    company = company_factory()
    user = user_factory()
    membership = membership_factory(user, company)
    project_stage = _stage(
        company,
        entity_type=DeliveryStage.EntityType.PROJECT,
        code="open",
        name="Open",
        outcome=DeliveryStage.Outcome.OPEN,
        initial=True,
    )
    project = Project.objects.create(
        company=company,
        code="VIS-002",
        name="Restricted design",
        stage=project_stage,
        manager_membership_public_id=membership.public_id,
        currency=company.currency,
    )

    payload = project_design_board(
        company=company,
        project=project,
        permission_codes={"project.dashboard.read"},
    )

    assert payload["available"] is False
    assert payload["documents"] == []
