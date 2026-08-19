import uuid
from collections.abc import Callable

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from modules.identity.models import Permission
from modules.tenant.models import Company
from modules.workflow.application.services import (
    decide_approval,
    publish_workflow_version,
    request_transition,
    start_workflow,
)
from modules.workflow.models import ApprovalTask, WorkflowDefinition, WorkflowVersion


def workflow_document() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    return (
        [
            {"code": "draft", "terminal": False},
            {"code": "approved", "terminal": True},
        ],
        [
            {
                "code": "submit",
                "from": "draft",
                "to": "approved",
                "permission_code": "workflow.execute",
                "requires_approval": True,
                "approval_permission_code": "workflow.approve",
            }
        ],
    )


@pytest.mark.django_db
def test_workflow_uses_frozen_version_and_approval(
    company_factory: Callable[..., Company],
) -> None:
    company = company_factory()
    definition = WorkflowDefinition.objects.create(
        company=company,
        code="test.approval",
        name="Test approval",
    )
    states, transitions = workflow_document()
    version = WorkflowVersion.objects.create(
        definition=definition,
        version=1,
        initial_state_code="draft",
        states=states,
        transitions=transitions,
        created_by_public_id=uuid.uuid4(),
    )
    Permission.objects.bulk_create(
        [
            Permission(code="workflow.execute", description="Execute workflows"),
            Permission(code="workflow.approve", description="Approve workflows"),
        ]
    )
    publish_workflow_version(
        version_public_id=version.public_id,
        company_public_id=company.public_id,
        actor_public_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
    )
    instance = start_workflow(
        definition=definition,
        subject_type="test",
        subject_public_id=uuid.uuid4(),
        actor_public_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
    )
    result = request_transition(
        instance_public_id=instance.public_id,
        company_public_id=company.public_id,
        transition_code="submit",
        expected_version=1,
        actor_public_id=uuid.uuid4(),
        permission_codes={"workflow.execute"},
        correlation_id=uuid.uuid4(),
    )
    assert result.approval_task is not None
    instance.refresh_from_db()
    assert instance.current_state_code == "draft"
    with pytest.raises(ValidationError, match="pending approval"):
        request_transition(
            instance_public_id=instance.public_id,
            company_public_id=company.public_id,
            transition_code="submit",
            expected_version=1,
            actor_public_id=uuid.uuid4(),
            permission_codes={"workflow.execute"},
            correlation_id=uuid.uuid4(),
        )

    assigned_role_public_id = uuid.uuid4()
    result.approval_task.assigned_role_public_id = assigned_role_public_id
    result.approval_task.save(update_fields=["assigned_role_public_id"])
    with pytest.raises(PermissionDenied):
        decide_approval(
            approval_public_id=result.approval_task.public_id,
            company_public_id=company.public_id,
            approved=True,
            actor_public_id=uuid.uuid4(),
            permission_codes={"workflow.approve"},
            role_public_ids=set(),
            correlation_id=uuid.uuid4(),
        )

    decide_approval(
        approval_public_id=result.approval_task.public_id,
        company_public_id=company.public_id,
        approved=True,
        actor_public_id=uuid.uuid4(),
        permission_codes={"workflow.approve"},
        role_public_ids={assigned_role_public_id},
        correlation_id=uuid.uuid4(),
    )
    instance.refresh_from_db()
    assert instance.current_state_code == "approved"
    assert instance.status == instance.Status.COMPLETED
    assert (
        ApprovalTask.objects.get(pk=result.approval_task.pk).status
        == ApprovalTask.Status.APPROVED
    )


@pytest.mark.django_db
def test_workflow_rejects_stale_version_and_missing_permission(
    company_factory: Callable[..., Company],
) -> None:
    company = company_factory()
    definition = WorkflowDefinition.objects.create(
        company=company,
        code="test.direct",
        name="Direct",
    )
    version = WorkflowVersion.objects.create(
        definition=definition,
        version=1,
        initial_state_code="draft",
        states=[{"code": "draft"}, {"code": "done", "terminal": True}],
        transitions=[
            {
                "code": "finish",
                "from": "draft",
                "to": "done",
                "permission_code": "workflow.execute",
            }
        ],
        created_by_public_id=uuid.uuid4(),
    )
    version.status = WorkflowVersion.Status.PUBLISHED
    version.published_at = timezone.now()
    version.save(update_fields=["status", "published_at"])
    instance = start_workflow(
        definition=definition,
        subject_type="test",
        subject_public_id=uuid.uuid4(),
        actor_public_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
    )
    with pytest.raises(PermissionDenied):
        request_transition(
            instance_public_id=instance.public_id,
            company_public_id=company.public_id,
            transition_code="finish",
            expected_version=1,
            actor_public_id=uuid.uuid4(),
            permission_codes=set(),
            correlation_id=uuid.uuid4(),
        )
    with pytest.raises(ValidationError, match="reload"):
        request_transition(
            instance_public_id=instance.public_id,
            company_public_id=company.public_id,
            transition_code="finish",
            expected_version=99,
            actor_public_id=uuid.uuid4(),
            permission_codes={"workflow.execute"},
            correlation_id=uuid.uuid4(),
        )
