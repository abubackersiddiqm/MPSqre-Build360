from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.utils import timezone

from modules.design.models import DesignDocument, DesignReview, DesignVersion
from modules.projects.models import DeliveryStage, Project
from modules.workflow.application.approval_center import approval_center_items
from modules.workflow.models import (
    ApprovalTask,
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowVersion,
)

pytestmark = pytest.mark.django_db


def _delivery_stage(company, entity_type, code, name, outcome, *, initial=False):
    return DeliveryStage.objects.create(
        company=company,
        entity_type=entity_type,
        code=code,
        name=name,
        outcome=outcome,
        sort_order=10,
        is_initial=initial,
        effective_from=timezone.now() - timedelta(minutes=1),
    )


def test_approval_center_unifies_actionable_workflow_and_design_review(
    company_factory,
    user_factory,
    membership_factory,
):
    company = company_factory()
    user = user_factory()
    membership = membership_factory(user, company)

    definition = WorkflowDefinition.objects.create(
        company=company,
        code="po.approval",
        name="Purchase order approval",
    )
    workflow_version = WorkflowVersion.objects.create(
        definition=definition,
        version=1,
        status=WorkflowVersion.Status.PUBLISHED,
        initial_state_code="draft",
        states=[{"code": "draft"}, {"code": "approved", "terminal": True}],
        transitions=[],
        created_by_public_id=user.public_id,
        published_at=timezone.now(),
    )
    instance = WorkflowInstance.objects.create(
        company=company,
        definition=definition,
        workflow_version=workflow_version,
        subject_type="purchase_order",
        subject_public_id=uuid.uuid4(),
        current_state_code="draft",
        started_by_public_id=user.public_id,
        started_at=timezone.now(),
    )
    approval = ApprovalTask.objects.create(
        company=company,
        workflow_instance=instance,
        transition_code="approve",
        from_state_code="draft",
        to_state_code="approved",
        approval_permission_code="workflow.approve",
        requested_by_public_id=user.public_id,
        due_at=timezone.now() - timedelta(hours=1),
    )

    project_stage = _delivery_stage(
        company,
        DeliveryStage.EntityType.PROJECT,
        "preconstruction",
        "Pre-construction",
        DeliveryStage.Outcome.OPEN,
        initial=True,
    )
    design_stage = _delivery_stage(
        company,
        DeliveryStage.EntityType.DESIGN_VERSION,
        "review",
        "Under review",
        DeliveryStage.Outcome.REVIEW,
        initial=True,
    )
    project = Project.objects.create(
        company=company,
        code="APR-001",
        name="Approval residence",
        stage=project_stage,
        manager_membership_public_id=membership.public_id,
        currency=company.currency,
        approved_budget=Decimal("1000000"),
    )
    document = DesignDocument.objects.create(
        company=company,
        project=project,
        document_number="A-201",
        title="Kitchen elevation",
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
    review = DesignReview.objects.create(
        company=company,
        design_version=version,
        reviewer_membership_public_id=membership.public_id,
        requested_by_public_id=user.public_id,
        requested_at=timezone.now(),
    )

    context = SimpleNamespace(
        company=company,
        membership=membership,
        principal=SimpleNamespace(user=user),
        permission_codes=lambda: {"workflow.approve", "design.review.decide"},
        role_public_ids=lambda: set(),
    )
    payload = approval_center_items(tenant_context=context)

    assert payload["summary"] == {
        "pending": 2,
        "overdue": 1,
        "workflow": 1,
        "design_reviews": 1,
    }
    assert payload["items"][0]["public_id"] == str(approval.public_id)
    design_item = next(item for item in payload["items"] if item["kind"] == "DESIGN_REVIEW")
    assert design_item["public_id"] == str(review.public_id)
    assert design_item["record_version"] == 1
    assert design_item["detail_href"].startswith("/project360/design?project=")
