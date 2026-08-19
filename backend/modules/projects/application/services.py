from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from modules.crm.application.references import (
    validate_customer_reference,
    validate_opportunity_reference,
)
from modules.platform.actors import RequestActor
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.projects.application.defaults import ensure_default_delivery_stages
from modules.projects.models import (
    DeliveryStage,
    Project,
    ProjectBaseline,
    ProjectStageHistory,
    ProjectTask,
    WbsNode,
)
from modules.tenant.models import Company, Membership


def initial_stage(company: Company, entity_type: str) -> DeliveryStage:
    stage = DeliveryStage.objects.filter(
        company=company,
        entity_type=entity_type,
        is_initial=True,
        is_active=True,
        effective_from__lte=timezone.now(),
    ).filter(
        Q(effective_to__isnull=True) | Q(effective_to__gt=timezone.now())
    ).order_by("sort_order").first()
    if stage is None:
        raise ValidationError(f"No initial {entity_type} stage is configured")
    return stage


def resolve_stage(
    company: Company,
    stage_public_id: uuid.UUID,
    entity_type: str,
) -> DeliveryStage:
    stage = DeliveryStage.objects.filter(
        company=company,
        public_id=stage_public_id,
        entity_type=entity_type,
        is_active=True,
        effective_from__lte=timezone.now(),
    ).filter(
        Q(effective_to__isnull=True) | Q(effective_to__gt=timezone.now())
    ).first()
    if stage is None:
        raise ValidationError("Delivery stage was not found")
    return stage


def available_transitions(stage: DeliveryStage) -> QuerySet[DeliveryStage]:
    return DeliveryStage.objects.filter(
        company=stage.company,
        entity_type=stage.entity_type,
        code__in=stage.allowed_next_codes,
        is_active=True,
        effective_from__lte=timezone.now(),
    ).filter(
        Q(effective_to__isnull=True) | Q(effective_to__gt=timezone.now())
    ).order_by("sort_order")


def _assert_membership(company: Company, membership_public_id: uuid.UUID | None) -> None:
    if membership_public_id is None:
        return
    exists = Membership.objects.filter(
        company=company,
        public_id=membership_public_id,
        suspended_at__isnull=True,
        terminated_at__isnull=True,
    ).exists()
    if not exists:
        raise ValidationError("Membership does not belong to this company")


def _audit(
    *,
    actor: RequestActor,
    company: Company,
    action: str,
    entity_type: str,
    entity_public_id: uuid.UUID,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason_code: str = "",
) -> None:
    append_audit(
        AuditRecord(
            action=action,
            entity_type=entity_type,
            entity_public_id=entity_public_id,
            actor_public_id=actor.user_public_id,
            company_public_id=company.public_id,
            request_id=actor.request_id,
            correlation_id=actor.request_id,
            ip_address=actor.ip_address,
            user_agent=actor.user_agent,
            before=before or {},
            after=after or {},
            reason_code=reason_code,
        )
    )


def _event(
    *,
    actor: RequestActor,
    company: Company,
    event_type: str,
    aggregate_type: str,
    aggregate_public_id: uuid.UUID,
    aggregate_version: int,
    payload: dict[str, Any],
) -> None:
    append_event(
        EventRecord(
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_public_id=aggregate_public_id,
            aggregate_version=aggregate_version,
            company_public_id=company.public_id,
            correlation_id=actor.request_id,
            payload=payload,
        )
    )


@transaction.atomic
def create_project(
    *,
    company: Company,
    actor: RequestActor,
    code: str,
    name: str,
    description: str = "",
    customer_public_id: uuid.UUID | None = None,
    opportunity_public_id: uuid.UUID | None = None,
    manager_membership_public_id: uuid.UUID | None = None,
    location: dict[str, Any] | None = None,
    planned_start_date: Any = None,
    planned_end_date: Any = None,
    currency: str | None = None,
    approved_budget: Decimal = Decimal("0"),
) -> Project:
    ensure_default_delivery_stages(company)
    manager_id = manager_membership_public_id or actor.membership_public_id
    _assert_membership(company, manager_id)
    validate_customer_reference(company, customer_public_id)
    validate_opportunity_reference(company, opportunity_public_id)
    project = Project(
        company=company,
        code=code.strip().upper(),
        name=name.strip(),
        description=description.strip(),
        customer_public_id=customer_public_id,
        opportunity_public_id=opportunity_public_id,
        stage=initial_stage(company, DeliveryStage.EntityType.PROJECT),
        manager_membership_public_id=manager_id,
        location=location or {},
        planned_start_date=planned_start_date,
        planned_end_date=planned_end_date,
        currency=(currency or company.currency).upper(),
        approved_budget=approved_budget,
    )
    project.full_clean()
    project.save()
    ProjectStageHistory.objects.create(
        company=company,
        project=project,
        from_stage_code="",
        to_stage_code=project.stage.code,
        changed_by_public_id=actor.user_public_id,
        changed_at=timezone.now(),
        project_version=project.version,
    )
    _audit(
        actor=actor,
        company=company,
        action="project.created",
        entity_type="project",
        entity_public_id=project.public_id,
        after={"code": project.code, "stage": project.stage.code},
    )
    _event(
        actor=actor,
        company=company,
        event_type="project.created",
        aggregate_type="project",
        aggregate_public_id=project.public_id,
        aggregate_version=project.version,
        payload={"code": project.code, "stage": project.stage.code},
    )
    return project


@transaction.atomic
def transition_project(
    *,
    company: Company,
    actor: RequestActor,
    project_public_id: uuid.UUID,
    target_stage_public_id: uuid.UUID,
    expected_version: int,
    reason_code: str = "",
) -> Project:
    project = Project.objects.select_for_update().select_related("stage").filter(
        company=company,
        public_id=project_public_id,
    ).first()
    if project is None:
        raise ValidationError("Project was not found")
    if project.version != expected_version:
        raise ValidationError("Project has changed; refresh before retrying")
    target = resolve_stage(company, target_stage_public_id, DeliveryStage.EntityType.PROJECT)
    if target.code not in project.stage.allowed_next_codes:
        raise ValidationError("The requested project transition is not permitted")
    before = {"stage": project.stage.code, "version": project.version}
    old_code = project.stage.code
    project.stage = target
    project.version += 1
    project.full_clean()
    project.save()
    ProjectStageHistory.objects.create(
        company=company,
        project=project,
        from_stage_code=old_code,
        to_stage_code=target.code,
        changed_by_public_id=actor.user_public_id,
        changed_at=timezone.now(),
        reason_code=reason_code.strip(),
        project_version=project.version,
    )
    _audit(
        actor=actor,
        company=company,
        action="project.transitioned",
        entity_type="project",
        entity_public_id=project.public_id,
        before=before,
        after={"stage": target.code, "version": project.version},
        reason_code=reason_code.strip(),
    )
    _event(
        actor=actor,
        company=company,
        event_type="project.transitioned",
        aggregate_type="project",
        aggregate_public_id=project.public_id,
        aggregate_version=project.version,
        payload={"from": old_code, "to": target.code},
    )
    return project


@transaction.atomic
def create_wbs_node(
    *,
    company: Company,
    actor: RequestActor,
    project_public_id: uuid.UUID,
    code: str,
    name: str,
    description: str = "",
    parent_public_id: uuid.UUID | None = None,
    sort_order: int = 100,
) -> WbsNode:
    project = Project.objects.filter(company=company, public_id=project_public_id).first()
    if project is None:
        raise ValidationError("Project was not found")
    parent = None
    if parent_public_id:
        parent = WbsNode.objects.filter(
            company=company,
            project=project,
            public_id=parent_public_id,
        ).first()
        if parent is None:
            raise ValidationError("WBS parent was not found")
    node = WbsNode(
        company=company,
        project=project,
        parent=parent,
        code=code.strip().upper(),
        name=name.strip(),
        description=description.strip(),
        sort_order=sort_order,
    )
    node.full_clean()
    node.save()
    _audit(
        actor=actor,
        company=company,
        action="project.wbs.created",
        entity_type="project_wbs",
        entity_public_id=node.public_id,
        after={"project_public_id": str(project.public_id), "code": node.code},
    )
    return node


@transaction.atomic
def create_task(
    *,
    company: Company,
    actor: RequestActor,
    project_public_id: uuid.UUID,
    code: str,
    title: str,
    description: str = "",
    wbs_node_public_id: uuid.UUID | None = None,
    assignee_membership_public_id: uuid.UUID | None = None,
    planned_start_date: Any = None,
    planned_end_date: Any = None,
) -> ProjectTask:
    project = Project.objects.filter(company=company, public_id=project_public_id).first()
    if project is None:
        raise ValidationError("Project was not found")
    wbs_node = None
    if wbs_node_public_id:
        wbs_node = WbsNode.objects.filter(
            company=company,
            project=project,
            public_id=wbs_node_public_id,
        ).first()
        if wbs_node is None:
            raise ValidationError("WBS node was not found")
    _assert_membership(company, assignee_membership_public_id)
    task = ProjectTask(
        company=company,
        project=project,
        wbs_node=wbs_node,
        code=code.strip().upper(),
        title=title.strip(),
        description=description.strip(),
        stage=initial_stage(company, DeliveryStage.EntityType.TASK),
        assignee_membership_public_id=assignee_membership_public_id,
        planned_start_date=planned_start_date,
        planned_end_date=planned_end_date,
    )
    task.full_clean()
    task.save()
    _audit(
        actor=actor,
        company=company,
        action="project.task.created",
        entity_type="project_task",
        entity_public_id=task.public_id,
        after={"project_public_id": str(project.public_id), "stage": task.stage.code},
    )
    _event(
        actor=actor,
        company=company,
        event_type="project.task_created",
        aggregate_type="project_task",
        aggregate_public_id=task.public_id,
        aggregate_version=task.version,
        payload={"project_public_id": str(project.public_id), "stage": task.stage.code},
    )
    return task


@transaction.atomic
def transition_task(
    *,
    company: Company,
    actor: RequestActor,
    task_public_id: uuid.UUID,
    target_stage_public_id: uuid.UUID,
    expected_version: int,
    progress_percent: int | None = None,
) -> ProjectTask:
    task = ProjectTask.objects.select_for_update().select_related("stage", "project").filter(
        company=company,
        public_id=task_public_id,
    ).first()
    if task is None:
        raise ValidationError("Task was not found")
    if task.version != expected_version:
        raise ValidationError("Task has changed; refresh before retrying")
    target = resolve_stage(company, target_stage_public_id, DeliveryStage.EntityType.TASK)
    if target.code not in task.stage.allowed_next_codes:
        raise ValidationError("The requested task transition is not permitted")
    old_code = task.stage.code
    task.stage = target
    task.progress_percent = (
        100
        if target.outcome == DeliveryStage.Outcome.COMPLETE
        else task.progress_percent if progress_percent is None else progress_percent
    )
    task.version += 1
    task.full_clean()
    task.save()
    _audit(
        actor=actor,
        company=company,
        action="project.task.transitioned",
        entity_type="project_task",
        entity_public_id=task.public_id,
        before={"stage": old_code, "version": expected_version},
        after={"stage": target.code, "version": task.version},
    )
    _event(
        actor=actor,
        company=company,
        event_type="project.task_transitioned",
        aggregate_type="project_task",
        aggregate_public_id=task.public_id,
        aggregate_version=task.version,
        payload={"from": old_code, "to": target.code},
    )
    return task


@transaction.atomic
def baseline_project(
    *,
    company: Company,
    actor: RequestActor,
    project_public_id: uuid.UUID,
    expected_version: int,
) -> ProjectBaseline:
    project = Project.objects.select_for_update().select_related("stage").filter(
        company=company,
        public_id=project_public_id,
    ).first()
    if project is None:
        raise ValidationError("Project was not found")
    if project.version != expected_version:
        raise ValidationError("Project has changed; refresh before retrying")
    if not project.stage.allows_baseline:
        raise ValidationError("The current project stage does not allow baselining")
    nodes = list(
        WbsNode.objects.filter(company=company, project=project)
        .order_by("sort_order", "code")
        .values("public_id", "parent__public_id", "code", "name", "sort_order", "version")
    )
    tasks = list(
        ProjectTask.objects.filter(company=company, project=project)
        .select_related("stage")
        .order_by("code")
        .values(
            "public_id",
            "wbs_node__public_id",
            "code",
            "title",
            "stage__code",
            "planned_start_date",
            "planned_end_date",
            "progress_percent",
            "version",
        )
    )
    baseline_number = project.baseline_version + 1
    baseline = ProjectBaseline.objects.create(
        company=company,
        project=project,
        baseline_number=baseline_number,
        source_project_version=project.version,
        snapshot={
            "project": {
                "public_id": str(project.public_id),
                "code": project.code,
                "name": project.name,
                "stage": project.stage.code,
                "planned_start_date": (
                    project.planned_start_date.isoformat()
                    if project.planned_start_date
                    else None
                ),
                "planned_end_date": (
                    project.planned_end_date.isoformat()
                    if project.planned_end_date
                    else None
                ),
                "approved_budget": str(project.approved_budget),
                "currency": project.currency,
            },
            "wbs": [
                {
                    **row,
                    "public_id": str(row["public_id"]),
                    "parent__public_id": (
                        str(row["parent__public_id"])
                        if row["parent__public_id"]
                        else None
                    ),
                }
                for row in nodes
            ],
            "tasks": [
                {
                    **row,
                    "public_id": str(row["public_id"]),
                    "wbs_node__public_id": (
                        str(row["wbs_node__public_id"])
                        if row["wbs_node__public_id"]
                        else None
                    ),
                    "planned_start_date": (
                        row["planned_start_date"].isoformat()
                        if row["planned_start_date"]
                        else None
                    ),
                    "planned_end_date": (
                        row["planned_end_date"].isoformat()
                        if row["planned_end_date"]
                        else None
                    ),
                }
                for row in tasks
            ],
        },
        created_by_public_id=actor.user_public_id,
    )
    project.baseline_version = baseline_number
    project.baselined_at = timezone.now()
    project.version += 1
    project.save(update_fields=["baseline_version", "baselined_at", "version", "updated_at"])
    _audit(
        actor=actor,
        company=company,
        action="project.baselined",
        entity_type="project",
        entity_public_id=project.public_id,
        after={"baseline_number": baseline_number, "version": project.version},
    )
    _event(
        actor=actor,
        company=company,
        event_type="project.baselined",
        aggregate_type="project",
        aggregate_public_id=project.public_id,
        aggregate_version=project.version,
        payload={"baseline_number": baseline_number},
    )
    return baseline
