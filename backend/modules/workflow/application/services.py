from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.workflow.models import (
    ApprovalTask,
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowTransitionLog,
    WorkflowVersion,
)


@dataclass(frozen=True, slots=True)
class TransitionResult:
    instance: WorkflowInstance
    approval_task: ApprovalTask | None = None


def workflow_checksum(version: WorkflowVersion) -> str:
    document = {
        "initial_state_code": version.initial_state_code,
        "states": version.states,
        "transitions": version.transitions,
    }
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def validate_workflow(version: WorkflowVersion) -> None:
    if not isinstance(version.states, list) or not version.states:
        raise ValidationError("A workflow requires at least one state")
    if not isinstance(version.transitions, list):
        raise ValidationError("Workflow transitions must be a list")
    state_codes: set[str] = set()
    for state in version.states:
        if not isinstance(state, dict) or not isinstance(state.get("code"), str):
            raise ValidationError("Every workflow state requires a code")
        code = state["code"].strip()
        if not code or code in state_codes:
            raise ValidationError("Workflow state codes must be unique and non-empty")
        state_codes.add(code)
    if version.initial_state_code not in state_codes:
        raise ValidationError("The initial workflow state does not exist")
    transition_codes: set[str] = set()
    for transition in version.transitions:
        if not isinstance(transition, dict):
            raise ValidationError("Every transition must be an object")
        code = transition.get("code")
        from_state = transition.get("from")
        to_state = transition.get("to")
        if not all(isinstance(value, str) and value for value in [code, from_state, to_state]):
            raise ValidationError("Every transition requires code, from, and to")
        if code in transition_codes:
            raise ValidationError("Workflow transition codes must be unique")
        if from_state not in state_codes or to_state not in state_codes:
            raise ValidationError("Workflow transitions must reference valid states")
        permission_code = transition.get("permission_code")
        if permission_code is not None and not isinstance(permission_code, str):
            raise ValidationError("Workflow transition permissions must be strings")
        approval_permission = transition.get("approval_permission_code")
        if approval_permission is not None and not isinstance(approval_permission, str):
            raise ValidationError("Workflow approval permissions must be strings")
        assigned_role = transition.get("assigned_role_public_id")
        if assigned_role is not None:
            if not isinstance(assigned_role, str):
                raise ValidationError("Assigned approval roles must be UUID strings")
            try:
                uuid.UUID(assigned_role)
            except ValueError as exc:
                raise ValidationError("Assigned approval roles must be valid UUIDs") from exc
        transition_codes.add(code)


def _transition(version: WorkflowVersion, code: str, from_state: str) -> dict[str, Any]:
    for transition in version.transitions:
        if (
            isinstance(transition, dict)
            and transition.get("code") == code
            and transition.get("from") == from_state
        ):
            return transition
    raise ValidationError("The transition is not available from the current state")


def _state(version: WorkflowVersion, code: str) -> dict[str, Any]:
    for state in version.states:
        if isinstance(state, dict) and state.get("code") == code:
            return state
    raise ValidationError("Workflow state is invalid")


@transaction.atomic
def publish_workflow_version(
    *,
    version_public_id: uuid.UUID,
    company_public_id: uuid.UUID,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> WorkflowVersion:
    version = (
        WorkflowVersion.objects.select_for_update()
        .select_related("definition", "definition__company")
        .filter(public_id=version_public_id, definition__company__public_id=company_public_id)
        .first()
    )
    if not version:
        raise ValidationError("Workflow version was not found")
    if version.status != WorkflowVersion.Status.DRAFT:
        raise ValidationError("Only draft workflow versions can be published")
    validate_workflow(version)
    from modules.identity.models import Permission, Role

    referenced_permissions = {
        str(transition[key])
        for transition in version.transitions
        if isinstance(transition, dict)
        for key in ("permission_code", "approval_permission_code")
        if isinstance(transition.get(key), str)
    }
    known_permissions = set(
        Permission.objects.filter(code__in=referenced_permissions).values_list(
            "code", flat=True
        )
    )
    if known_permissions != referenced_permissions:
        raise ValidationError("Workflow references an unknown permission")
    assigned_role_ids = {
        uuid.UUID(str(transition["assigned_role_public_id"]))
        for transition in version.transitions
        if isinstance(transition, dict)
        and transition.get("assigned_role_public_id") is not None
    }
    known_role_ids = set(
        Role.objects.filter(
            public_id__in=assigned_role_ids,
            company_public_id=company_public_id,
            retired_at__isnull=True,
        ).values_list("public_id", flat=True)
    )
    if known_role_ids != assigned_role_ids:
        raise ValidationError("Workflow references an unavailable approval role")
    version.status = WorkflowVersion.Status.PUBLISHED
    version.published_at = timezone.now()
    version.checksum = workflow_checksum(version)
    version.full_clean()
    version.save(update_fields=["status", "published_at", "checksum", "updated_at"])
    append_audit(
        AuditRecord(
            action="workflow.version.published",
            entity_type="workflow_version",
            entity_public_id=version.public_id,
            actor_public_id=actor_public_id,
            company_public_id=company_public_id,
            request_id=correlation_id,
            correlation_id=correlation_id,
            after={"definition_code": version.definition.code, "version": version.version},
        )
    )
    append_event(
        EventRecord(
            event_type="workflow.version_published",
            aggregate_type="workflow_definition",
            aggregate_public_id=version.definition.public_id,
            aggregate_version=version.version,
            company_public_id=company_public_id,
            correlation_id=correlation_id,
            payload={"workflow_version_public_id": str(version.public_id)},
        )
    )
    return version


@transaction.atomic
def start_workflow(
    *,
    definition: WorkflowDefinition,
    subject_type: str,
    subject_public_id: uuid.UUID,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> WorkflowInstance:
    version = (
        WorkflowVersion.objects.filter(
            definition=definition,
            status=WorkflowVersion.Status.PUBLISHED,
        )
        .order_by("-version")
        .first()
    )
    if not version:
        raise ValidationError("No published workflow version is available")
    instance = WorkflowInstance(
        company=definition.company,
        definition=definition,
        workflow_version=version,
        subject_type=subject_type,
        subject_public_id=subject_public_id,
        current_state_code=version.initial_state_code,
        started_by_public_id=actor_public_id,
        started_at=timezone.now(),
    )
    instance.full_clean()
    instance.save()
    append_audit(
        AuditRecord(
            action="workflow.instance.started",
            entity_type="workflow_instance",
            entity_public_id=instance.public_id,
            actor_public_id=actor_public_id,
            company_public_id=definition.company.public_id,
            request_id=correlation_id,
            correlation_id=correlation_id,
            after={
                "definition_code": definition.code,
                "workflow_version": version.version,
                "state": version.initial_state_code,
            },
        )
    )
    append_event(
        EventRecord(
            event_type="workflow.instance_started",
            aggregate_type="workflow_instance",
            aggregate_public_id=instance.public_id,
            aggregate_version=instance.lock_version,
            company_public_id=definition.company.public_id,
            correlation_id=correlation_id,
            payload={"state": instance.current_state_code},
        )
    )
    return instance


def _apply_transition(
    *,
    instance: WorkflowInstance,
    transition: dict[str, Any],
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    comment: str,
) -> WorkflowInstance:
    from_state = instance.current_state_code
    to_state = str(transition["to"])
    next_version = instance.lock_version + 1
    target_state = _state(instance.workflow_version, to_state)
    instance.current_state_code = to_state
    instance.lock_version = next_version
    if bool(target_state.get("terminal")):
        instance.status = WorkflowInstance.Status.COMPLETED
        instance.completed_at = timezone.now()
    instance.save(
        update_fields=[
            "current_state_code",
            "lock_version",
            "status",
            "completed_at",
            "updated_at",
        ]
    )
    WorkflowTransitionLog.objects.create(
        workflow_instance=instance,
        sequence=next_version - 1,
        transition_code=str(transition["code"]),
        from_state_code=from_state,
        to_state_code=to_state,
        actor_public_id=actor_public_id,
        occurred_at=timezone.now(),
        correlation_id=correlation_id,
        comment=comment[:1000],
    )
    append_audit(
        AuditRecord(
            action="workflow.instance.transitioned",
            entity_type="workflow_instance",
            entity_public_id=instance.public_id,
            actor_public_id=actor_public_id,
            company_public_id=instance.company.public_id,
            request_id=correlation_id,
            correlation_id=correlation_id,
            before={"state": from_state, "lock_version": next_version - 1},
            after={"state": to_state, "lock_version": next_version},
        )
    )
    append_event(
        EventRecord(
            event_type="workflow.instance_transitioned",
            aggregate_type="workflow_instance",
            aggregate_public_id=instance.public_id,
            aggregate_version=next_version,
            company_public_id=instance.company.public_id,
            correlation_id=correlation_id,
            payload={
                "transition_code": transition["code"],
                "from_state": from_state,
                "to_state": to_state,
            },
        )
    )
    return instance


@transaction.atomic
def request_transition(
    *,
    instance_public_id: uuid.UUID,
    company_public_id: uuid.UUID,
    transition_code: str,
    expected_version: int,
    actor_public_id: uuid.UUID,
    permission_codes: set[str],
    correlation_id: uuid.UUID,
    comment: str = "",
) -> TransitionResult:
    instance = (
        WorkflowInstance.objects.select_for_update()
        .select_related("workflow_version", "company")
        .filter(public_id=instance_public_id, company__public_id=company_public_id)
        .first()
    )
    if not instance:
        raise ValidationError("Workflow instance was not found")
    if instance.status != WorkflowInstance.Status.ACTIVE:
        raise ValidationError("Workflow instance is not active")
    if instance.lock_version != expected_version:
        raise ValidationError("Workflow instance changed; reload before retrying")
    transition = _transition(
        instance.workflow_version,
        transition_code,
        instance.current_state_code,
    )
    required_permission = transition.get("permission_code")
    if isinstance(required_permission, str) and required_permission not in permission_codes:
        raise PermissionDenied("Permission denied")
    if bool(transition.get("requires_approval")):
        if ApprovalTask.objects.filter(
            workflow_instance=instance,
            transition_code=transition_code,
            status=ApprovalTask.Status.PENDING,
        ).exists():
            raise ValidationError("This workflow transition already has a pending approval")
        due_hours = transition.get("approval_due_hours", 24)
        if not isinstance(due_hours, int) or due_hours < 1 or due_hours > 2160:
            raise ValidationError("Approval due hours are invalid")
        approval = ApprovalTask.objects.create(
            company=instance.company,
            workflow_instance=instance,
            transition_code=transition_code,
            from_state_code=instance.current_state_code,
            to_state_code=str(transition["to"]),
            approval_permission_code=str(
                transition.get("approval_permission_code", "workflow.approve")
            ),
            requested_by_public_id=actor_public_id,
            due_at=timezone.now() + timedelta(hours=due_hours),
            assigned_role_public_id=(
                uuid.UUID(transition["assigned_role_public_id"])
                if isinstance(transition.get("assigned_role_public_id"), str)
                else None
            ),
        )
        append_audit(
            AuditRecord(
                action="workflow.approval.requested",
                entity_type="approval_task",
                entity_public_id=approval.public_id,
                actor_public_id=actor_public_id,
                company_public_id=instance.company.public_id,
                request_id=correlation_id,
                correlation_id=correlation_id,
                after={
                    "workflow_instance_public_id": str(instance.public_id),
                    "transition_code": transition_code,
                },
            )
        )
        append_event(
            EventRecord(
                event_type="workflow.approval_requested",
                aggregate_type="approval_task",
                aggregate_public_id=approval.public_id,
                aggregate_version=1,
                company_public_id=instance.company.public_id,
                correlation_id=correlation_id,
                payload={"workflow_instance_public_id": str(instance.public_id)},
            )
        )
        return TransitionResult(instance=instance, approval_task=approval)
    return TransitionResult(
        instance=_apply_transition(
            instance=instance,
            transition=transition,
            actor_public_id=actor_public_id,
            correlation_id=correlation_id,
            comment=comment,
        )
    )


@transaction.atomic
def decide_approval(
    *,
    approval_public_id: uuid.UUID,
    company_public_id: uuid.UUID,
    approved: bool,
    actor_public_id: uuid.UUID,
    permission_codes: set[str],
    role_public_ids: set[uuid.UUID],
    correlation_id: uuid.UUID,
    comment: str = "",
) -> ApprovalTask:
    approval = (
        ApprovalTask.objects.select_for_update()
        .select_related("workflow_instance", "workflow_instance__workflow_version", "company")
        .filter(public_id=approval_public_id, company__public_id=company_public_id)
        .first()
    )
    if not approval:
        raise ValidationError("Approval task was not found")
    if approval.status != ApprovalTask.Status.PENDING:
        raise ValidationError("Approval task has already been decided")
    if approval.approval_permission_code not in permission_codes:
        raise PermissionDenied("Permission denied")
    if (
        approval.assigned_user_public_id
        and approval.assigned_user_public_id != actor_public_id
    ):
        raise PermissionDenied("Permission denied")
    if (
        approval.assigned_role_public_id
        and approval.assigned_role_public_id not in role_public_ids
    ):
        raise PermissionDenied("Permission denied")
    instance = WorkflowInstance.objects.select_for_update().get(pk=approval.workflow_instance_id)
    if instance.current_state_code != approval.from_state_code:
        approval.status = ApprovalTask.Status.CANCELLED
        approval.decided_at = timezone.now()
        approval.decided_by_public_id = actor_public_id
        approval.comment = "Cancelled because the workflow state changed."
        approval.save(
            update_fields=["status", "decided_at", "decided_by_public_id", "comment", "updated_at"]
        )
        raise ValidationError("Approval is stale because the workflow state changed")
    approval.status = ApprovalTask.Status.APPROVED if approved else ApprovalTask.Status.REJECTED
    approval.decided_at = timezone.now()
    approval.decided_by_public_id = actor_public_id
    approval.comment = comment[:1000]
    approval.save(
        update_fields=["status", "decided_at", "decided_by_public_id", "comment", "updated_at"]
    )
    if approved:
        transition = _transition(
            instance.workflow_version,
            approval.transition_code,
            instance.current_state_code,
        )
        _apply_transition(
            instance=instance,
            transition=transition,
            actor_public_id=actor_public_id,
            correlation_id=correlation_id,
            comment=comment,
        )
    action = "workflow.approval.approved" if approved else "workflow.approval.rejected"
    append_audit(
        AuditRecord(
            action=action,
            entity_type="approval_task",
            entity_public_id=approval.public_id,
            actor_public_id=actor_public_id,
            company_public_id=approval.company.public_id,
            request_id=correlation_id,
            correlation_id=correlation_id,
            after={"status": approval.status},
        )
    )
    append_event(
        EventRecord(
            event_type=action.replace(".", "_"),
            aggregate_type="approval_task",
            aggregate_public_id=approval.public_id,
            aggregate_version=2,
            company_public_id=approval.company.public_id,
            correlation_id=correlation_id,
            payload={"status": approval.status},
        )
    )
    return approval
