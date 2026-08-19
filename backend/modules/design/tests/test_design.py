import uuid
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from modules.design.application.services import create_document, create_version, request_review
from modules.design.models import DesignIssue
from modules.platform.actors import RequestActor
from modules.projects.application.services import create_project
from modules.projects.models import DeliveryStage

pytestmark = pytest.mark.django_db


def actor(user, membership) -> RequestActor:
    return RequestActor(
        user_public_id=user.public_id,
        membership_public_id=membership.public_id,
        request_id=uuid.uuid4(),
        ip_address="127.0.0.1",
        user_agent="pytest",
    )


def stage(company, entity_type, code, outcome, *, initial=False):
    return DeliveryStage.objects.create(
        company=company,
        entity_type=entity_type,
        code=code,
        name=code.title(),
        outcome=outcome,
        sort_order=10,
        allowed_next_codes=[],
        is_initial=initial,
        effective_from=timezone.now() - timedelta(minutes=1),
    )


def test_review_assignment_requires_review_stage(
    company_factory,
    user_factory,
    membership_factory,
):
    company = company_factory()
    user = user_factory()
    membership = membership_factory(user, company)
    stage(
        company,
        DeliveryStage.EntityType.PROJECT,
        "planning",
        DeliveryStage.Outcome.OPEN,
        initial=True,
    )
    stage(
        company,
        DeliveryStage.EntityType.DESIGN_VERSION,
        "draft",
        DeliveryStage.Outcome.OPEN,
        initial=True,
    )
    project = create_project(
        company=company,
        actor=actor(user, membership),
        code="P-DES",
        name="Design project",
    )
    document = create_document(
        company=company,
        actor=actor(user, membership),
        project_public_id=project.public_id,
        document_number="A-001",
        title="General arrangement",
        discipline_code="ARCH",
        document_type_code="DRAWING",
    )
    version = create_version(
        company=company,
        actor=actor(user, membership),
        document_public_id=document.public_id,
        revision_code="R0",
    )

    with pytest.raises(ValidationError, match="under review"):
        request_review(
            company=company,
            actor=actor(user, membership),
            version_public_id=version.public_id,
            reviewer_membership_public_id=membership.public_id,
        )


def test_design_issue_rejects_cross_company_project(
    company_factory,
    user_factory,
    membership_factory,
):
    company = company_factory()
    other_company = company_factory()
    user = user_factory()
    membership = membership_factory(user, other_company)
    stage(
        other_company,
        DeliveryStage.EntityType.PROJECT,
        "planning",
        DeliveryStage.Outcome.OPEN,
        initial=True,
    )
    project = create_project(
        company=other_company,
        actor=actor(user, membership),
        code="P-OTHER",
        name="Other tenant",
    )
    issue = DesignIssue(
        company=company,
        project=project,
        title="Cross tenant",
        severity=DesignIssue.Severity.HIGH,
        raised_by_public_id=user.public_id,
    )

    with pytest.raises(ValidationError, match="cross companies"):
        issue.full_clean()
