from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from modules.employee.models import Employee
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.tenant.models import Company, Location
from modules.workops.models import (
    ChecklistItem,
    DailyProgress,
    Milestone,
    Project,
    ProjectSite,
    TimesheetEntry,
    WBSNode,
    WorkApproval,
    WorkAssignment,
    WorkDependency,
    WorkItem,
    WorkPackage,
)

PROJECT_TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"ACTIVE", "CANCELLED"},
    "ACTIVE": {"ON_HOLD", "COMPLETED", "CANCELLED"},
    "ON_HOLD": {"ACTIVE", "CANCELLED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}

WORK_TRANSITIONS: dict[str, set[str]] = {
    "BACKLOG": {"READY", "ASSIGNED", "CANCELLED"},
    "READY": {"ASSIGNED", "IN_PROGRESS", "BLOCKED", "CANCELLED"},
    "ASSIGNED": {"IN_PROGRESS", "BLOCKED", "CANCELLED"},
    "IN_PROGRESS": {"BLOCKED", "REVIEW", "DONE", "CANCELLED"},
    "BLOCKED": {"READY", "ASSIGNED", "IN_PROGRESS", "CANCELLED"},
    "REVIEW": {"IN_PROGRESS", "CANCELLED"},
    "APPROVED": {"DONE", "IN_PROGRESS"},
    "DONE": set(),
    "CANCELLED": set(),
}


def _code(value: str) -> str:
    return value.strip().upper().replace(" ", "_")


def _same_company(instance: Any, company: Company, label: str) -> None:
    if instance is not None and instance.company_id != company.id:
        raise ValidationError(f"{label} cannot cross companies")


def _audit_event(
    *,
    action: str,
    event_type: str,
    entity_type: str,
    entity_public_id: uuid.UUID,
    actor_public_id: uuid.UUID,
    company: Company,
    correlation_id: uuid.UUID,
    version: int,
    after: dict[str, Any],
    before: dict[str, Any] | None = None,
) -> None:
    append_audit(
        AuditRecord(
            action=action,
            entity_type=entity_type,
            entity_public_id=entity_public_id,
            actor_public_id=actor_public_id,
            company_public_id=company.public_id,
            request_id=correlation_id,
            correlation_id=correlation_id,
            before=before or {},
            after=after,
        )
    )
    append_event(
        EventRecord(
            event_type=event_type,
            aggregate_type=entity_type,
            aggregate_public_id=entity_public_id,
            aggregate_version=version,
            company_public_id=company.public_id,
            correlation_id=correlation_id,
            payload=after,
        )
    )


def _locked(model: type[Any], *, company: Company, public_id: uuid.UUID) -> Any:
    item = model.objects.select_for_update().filter(company=company, public_id=public_id).first()
    if item is None:
        raise ValidationError("Record not found")
    return item


def _check_version(instance: Any, expected_version: int) -> None:
    if instance.version != expected_version:
        raise ValidationError(
            {"expected_version": f"Record changed. Current version is {instance.version}. Refresh and retry."}
        )


@transaction.atomic
def create_project(
    *,
    company: Company,
    code: str,
    name: str,
    start_date: date,
    target_end_date: date,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    project_type_code: str = "CONSTRUCTION",
    description: str = "",
    priority_code: str = "NORMAL",
    manager: Employee | None = None,
    location: Location | None = None,
    currency: str | None = None,
    budget: Decimal | None = None,
) -> Project:
    _same_company(manager, company, "Project manager")
    _same_company(location, company, "Project location")
    project = Project(
        company=company,
        code=_code(code),
        name=name.strip(),
        description=description.strip(),
        project_type_code=_code(project_type_code),
        priority_code=_code(priority_code),
        manager=manager,
        location=location,
        start_date=start_date,
        target_end_date=target_end_date,
        currency=(currency or company.currency).strip().upper(),
        budget=budget,
    )
    project.full_clean()
    project.save()
    _audit_event(
        action="work.project.created",
        event_type="work.project_created",
        entity_type="project",
        entity_public_id=project.public_id,
        actor_public_id=actor_public_id,
        company=company,
        correlation_id=correlation_id,
        version=project.version,
        after={"code": project.code, "name": project.name, "status_code": project.status_code},
    )
    return project


@transaction.atomic
def transition_project(
    *,
    company: Company,
    project_public_id: uuid.UUID,
    status_code: str,
    expected_version: int,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> Project:
    project: Project = _locked(Project, company=company, public_id=project_public_id)
    _check_version(project, expected_version)
    target = _code(status_code)
    if target not in PROJECT_TRANSITIONS.get(project.status_code, set()):
        raise ValidationError({"status_code": f"Cannot move project from {project.status_code} to {target}"})
    if target == "COMPLETED" and project.work_items.exclude(status_code__in=["DONE", "CANCELLED"]).exists():
        raise ValidationError("All project work items must be done or cancelled before project completion")
    before = {"status_code": project.status_code, "version": project.version}
    project.status_code = target
    if target == "COMPLETED":
        project.actual_end_date = timezone.localdate()
    project.version += 1
    project.full_clean()
    project.save(update_fields=["status_code", "actual_end_date", "version", "updated_at"])
    _audit_event(
        action="work.project.status_changed",
        event_type="work.project_status_changed",
        entity_type="project",
        entity_public_id=project.public_id,
        actor_public_id=actor_public_id,
        company=company,
        correlation_id=correlation_id,
        version=project.version,
        before=before,
        after={"status_code": project.status_code, "version": project.version},
    )
    return project


@transaction.atomic
def create_site(
    *,
    company: Company,
    project: Project,
    code: str,
    name: str,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    location: Location | None = None,
    address: dict[str, Any] | None = None,
    start_date: date | None = None,
    target_end_date: date | None = None,
) -> ProjectSite:
    _same_company(project, company, "Project")
    _same_company(location, company, "Site location")
    site = ProjectSite(
        company=company,
        project=project,
        code=_code(code),
        name=name.strip(),
        location=location,
        address=address or {},
        start_date=start_date,
        target_end_date=target_end_date,
    )
    site.full_clean()
    site.save()
    _audit_event(
        action="work.site.created",
        event_type="work.site_created",
        entity_type="project_site",
        entity_public_id=site.public_id,
        actor_public_id=actor_public_id,
        company=company,
        correlation_id=correlation_id,
        version=site.version,
        after={"project_code": project.code, "code": site.code, "name": site.name},
    )
    return site


@transaction.atomic
def create_wbs_node(
    *,
    company: Company,
    project: Project,
    code: str,
    name: str,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    parent: WBSNode | None = None,
    sequence: int = 1,
) -> WBSNode:
    _same_company(project, company, "Project")
    _same_company(parent, company, "WBS parent")
    if parent and parent.project_id != project.id:
        raise ValidationError({"parent_public_id": "WBS parent must belong to the same project"})
    node = WBSNode(
        company=company,
        project=project,
        code=_code(code),
        name=name.strip(),
        parent=parent,
        sequence=sequence,
        level=(parent.level + 1 if parent else 1),
    )
    node.full_clean()
    node.save()
    _audit_event(
        action="work.wbs.created",
        event_type="work.wbs_created",
        entity_type="wbs_node",
        entity_public_id=node.public_id,
        actor_public_id=actor_public_id,
        company=company,
        correlation_id=correlation_id,
        version=node.version,
        after={"project_code": project.code, "code": node.code, "name": node.name},
    )
    return node


@transaction.atomic
def create_work_package(
    *,
    company: Company,
    project: Project,
    wbs_node: WBSNode,
    code: str,
    name: str,
    planned_start: date,
    planned_end: date,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    owner: Employee | None = None,
    description: str = "",
    progress_weight: Decimal = Decimal("1.00"),
) -> WorkPackage:
    _same_company(project, company, "Project")
    _same_company(wbs_node, company, "WBS node")
    _same_company(owner, company, "Work package owner")
    if wbs_node.project_id != project.id:
        raise ValidationError({"wbs_node_public_id": "WBS node must belong to the selected project"})
    package = WorkPackage(
        company=company,
        project=project,
        wbs_node=wbs_node,
        code=_code(code),
        name=name.strip(),
        description=description.strip(),
        owner=owner,
        planned_start=planned_start,
        planned_end=planned_end,
        progress_weight=progress_weight,
    )
    package.full_clean()
    package.save()
    _audit_event(
        action="work.package.created",
        event_type="work.package_created",
        entity_type="work_package",
        entity_public_id=package.public_id,
        actor_public_id=actor_public_id,
        company=company,
        correlation_id=correlation_id,
        version=package.version,
        after={"project_code": project.code, "code": package.code, "name": package.name},
    )
    return package


@transaction.atomic
def create_milestone(
    *,
    company: Company,
    project: Project,
    code: str,
    name: str,
    target_date: date,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    owner: Employee | None = None,
) -> Milestone:
    _same_company(project, company, "Project")
    _same_company(owner, company, "Milestone owner")
    milestone = Milestone(
        company=company,
        project=project,
        code=_code(code),
        name=name.strip(),
        target_date=target_date,
        owner=owner,
    )
    milestone.full_clean()
    milestone.save()
    _audit_event(
        action="work.milestone.created",
        event_type="work.milestone_created",
        entity_type="milestone",
        entity_public_id=milestone.public_id,
        actor_public_id=actor_public_id,
        company=company,
        correlation_id=correlation_id,
        version=milestone.version,
        after={"project_code": project.code, "code": milestone.code, "target_date": target_date.isoformat()},
    )
    return milestone


@transaction.atomic
def create_work_item(
    *,
    company: Company,
    project: Project,
    code: str,
    title: str,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    site: ProjectSite | None = None,
    work_package: WorkPackage | None = None,
    description: str = "",
    work_type_code: str = "TASK",
    priority_code: str = "NORMAL",
    planned_start: date | None = None,
    due_date: date | None = None,
    estimated_hours: Decimal | None = None,
    primary_assignee: Employee | None = None,
    reviewer: Employee | None = None,
) -> WorkItem:
    _same_company(project, company, "Project")
    _same_company(site, company, "Project site")
    _same_company(work_package, company, "Work package")
    _same_company(primary_assignee, company, "Assignee")
    _same_company(reviewer, company, "Reviewer")
    if site and site.project_id != project.id:
        raise ValidationError({"site_public_id": "Site must belong to the selected project"})
    if work_package and work_package.project_id != project.id:
        raise ValidationError({"work_package_public_id": "Work package must belong to the selected project"})
    status = "ASSIGNED" if primary_assignee else "BACKLOG"
    item = WorkItem(
        company=company,
        project=project,
        site=site,
        work_package=work_package,
        code=_code(code),
        title=title.strip(),
        description=description.strip(),
        work_type_code=_code(work_type_code),
        status_code=status,
        priority_code=_code(priority_code),
        planned_start=planned_start,
        due_date=due_date,
        estimated_hours=estimated_hours,
        primary_assignee=primary_assignee,
        reviewer=reviewer,
        created_by_public_id=actor_public_id,
    )
    item.full_clean()
    item.save()
    if primary_assignee:
        WorkAssignment.objects.create(
            company=company,
            work_item=item,
            employee=primary_assignee,
            assignment_role_code="PRIMARY",
            allocation_percent=Decimal("100.00"),
            effective_from=timezone.localdate(),
        )
    _audit_event(
        action="work.item.created",
        event_type="work.item_created",
        entity_type="work_item",
        entity_public_id=item.public_id,
        actor_public_id=actor_public_id,
        company=company,
        correlation_id=correlation_id,
        version=item.version,
        after={"project_code": project.code, "code": item.code, "title": item.title, "status_code": item.status_code},
    )
    return item


@transaction.atomic
def assign_work_item(
    *,
    company: Company,
    work_item_public_id: uuid.UUID,
    employee: Employee,
    assignment_role_code: str,
    allocation_percent: Decimal,
    effective_from: date,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    effective_to: date | None = None,
    make_primary: bool = False,
) -> WorkAssignment:
    item: WorkItem = _locked(WorkItem, company=company, public_id=work_item_public_id)
    _same_company(employee, company, "Assigned employee")
    assignment = WorkAssignment(
        company=company,
        work_item=item,
        employee=employee,
        assignment_role_code=_code(assignment_role_code),
        allocation_percent=allocation_percent,
        effective_from=effective_from,
        effective_to=effective_to,
    )
    assignment.full_clean()
    assignment.save()
    if make_primary:
        item.primary_assignee = employee
        if item.status_code in {"BACKLOG", "READY"}:
            item.status_code = "ASSIGNED"
        item.version += 1
        item.save(update_fields=["primary_assignee", "status_code", "version", "updated_at"])
    _audit_event(
        action="work.assignment.created",
        event_type="work.assignment_created",
        entity_type="work_assignment",
        entity_public_id=assignment.public_id,
        actor_public_id=actor_public_id,
        company=company,
        correlation_id=correlation_id,
        version=assignment.version,
        after={
            "work_item_code": item.code,
            "employee_number": employee.employee_number,
            "role": assignment.assignment_role_code,
            "make_primary": make_primary,
        },
    )
    return assignment


def _dependency_reaches(*, company: Company, start_id: int, target_id: int) -> bool:
    edges = list(
        WorkDependency.objects.filter(company=company).values_list("predecessor_id", "successor_id")
    )
    graph: dict[int, set[int]] = {}
    for predecessor_id, successor_id in edges:
        graph.setdefault(predecessor_id, set()).add(successor_id)
    stack = [start_id]
    visited: set[int] = set()
    while stack:
        current = stack.pop()
        if current == target_id:
            return True
        if current in visited:
            continue
        visited.add(current)
        stack.extend(graph.get(current, set()))
    return False


@transaction.atomic
def add_dependency(
    *,
    company: Company,
    predecessor: WorkItem,
    successor: WorkItem,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    dependency_type_code: str = "FINISH_TO_START",
    lag_days: int = 0,
) -> WorkDependency:
    _same_company(predecessor, company, "Predecessor")
    _same_company(successor, company, "Successor")
    if predecessor.id == successor.id:
        raise ValidationError("A work item cannot depend on itself")
    if predecessor.project_id != successor.project_id:
        raise ValidationError("Dependencies cannot cross projects")
    if _dependency_reaches(company=company, start_id=successor.id, target_id=predecessor.id):
        raise ValidationError("Dependency would create a cycle")
    dependency = WorkDependency(
        company=company,
        predecessor=predecessor,
        successor=successor,
        dependency_type_code=_code(dependency_type_code),
        lag_days=lag_days,
    )
    dependency.full_clean()
    dependency.save()
    _audit_event(
        action="work.dependency.created",
        event_type="work.dependency_created",
        entity_type="work_dependency",
        entity_public_id=dependency.public_id,
        actor_public_id=actor_public_id,
        company=company,
        correlation_id=correlation_id,
        version=dependency.version,
        after={"predecessor": predecessor.code, "successor": successor.code, "type": dependency.dependency_type_code},
    )
    return dependency


@transaction.atomic
def create_checklist_item(
    *,
    company: Company,
    work_item: WorkItem,
    sequence: int,
    title: str,
    is_required: bool,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> ChecklistItem:
    _same_company(work_item, company, "Work item")
    item = ChecklistItem(
        company=company,
        work_item=work_item,
        sequence=sequence,
        title=title.strip(),
        is_required=is_required,
    )
    item.full_clean()
    item.save()
    _audit_event(
        action="work.checklist.created",
        event_type="work.checklist_created",
        entity_type="checklist_item",
        entity_public_id=item.public_id,
        actor_public_id=actor_public_id,
        company=company,
        correlation_id=correlation_id,
        version=item.version,
        after={"work_item_code": work_item.code, "sequence": sequence, "title": item.title},
    )
    return item


@transaction.atomic
def set_checklist_completion(
    *,
    company: Company,
    checklist_public_id: uuid.UUID,
    is_completed: bool,
    expected_version: int,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> ChecklistItem:
    item: ChecklistItem = _locked(ChecklistItem, company=company, public_id=checklist_public_id)
    _check_version(item, expected_version)
    before = {"is_completed": item.is_completed, "version": item.version}
    item.is_completed = is_completed
    item.completed_by_public_id = actor_public_id if is_completed else None
    item.completed_at = timezone.now() if is_completed else None
    item.version += 1
    item.save(
        update_fields=["is_completed", "completed_by_public_id", "completed_at", "version", "updated_at"]
    )
    _audit_event(
        action="work.checklist.completion_changed",
        event_type="work.checklist_completion_changed",
        entity_type="checklist_item",
        entity_public_id=item.public_id,
        actor_public_id=actor_public_id,
        company=company,
        correlation_id=correlation_id,
        version=item.version,
        before=before,
        after={"is_completed": item.is_completed, "version": item.version},
    )
    return item


@transaction.atomic
def transition_work_item(
    *,
    company: Company,
    work_item_public_id: uuid.UUID,
    status_code: str,
    expected_version: int,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> WorkItem:
    item: WorkItem = _locked(WorkItem, company=company, public_id=work_item_public_id)
    _check_version(item, expected_version)
    target = _code(status_code)
    if target not in WORK_TRANSITIONS.get(item.status_code, set()):
        raise ValidationError({"status_code": f"Cannot move work item from {item.status_code} to {target}"})
    if target in {"REVIEW", "APPROVED", "DONE"} and item.checklist_items.filter(
        is_required=True, is_completed=False
    ).exists():
        raise ValidationError("Complete all required checklist items before review or completion")
    if target == "IN_PROGRESS":
        blocked_predecessors = item.predecessor_links.exclude(predecessor__status_code__in=["DONE", "CANCELLED"])
        if blocked_predecessors.exists():
            raise ValidationError("A predecessor is not complete")
    if target == "DONE" and item.reviewer_id and not item.approvals.filter(status_code="APPROVED").exists():
        raise ValidationError("An approved work approval is required before completion")
    before = {"status_code": item.status_code, "progress_percent": str(item.progress_percent), "version": item.version}
    item.status_code = target
    if target == "IN_PROGRESS" and not item.actual_start:
        item.actual_start = timezone.now()
    if target == "DONE":
        item.completed_at = timezone.now()
        item.progress_percent = Decimal("100.00")
    item.version += 1
    item.full_clean()
    item.save(
        update_fields=["status_code", "actual_start", "completed_at", "progress_percent", "version", "updated_at"]
    )
    _audit_event(
        action="work.item.status_changed",
        event_type="work.item_status_changed",
        entity_type="work_item",
        entity_public_id=item.public_id,
        actor_public_id=actor_public_id,
        company=company,
        correlation_id=correlation_id,
        version=item.version,
        before=before,
        after={"status_code": item.status_code, "progress_percent": str(item.progress_percent), "version": item.version},
    )
    return item


@transaction.atomic
def record_daily_progress(
    *,
    company: Company,
    project: Project,
    progress_date: date,
    quantity_completed: Decimal,
    hours_worked: Decimal,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    site: ProjectSite | None = None,
    work_item: WorkItem | None = None,
    recorded_by: Employee | None = None,
    unit_code: str = "",
    progress_percent: Decimal | None = None,
    note: str = "",
    blockers: str = "",
) -> DailyProgress:
    for instance, label in (
        (project, "Project"),
        (site, "Project site"),
        (work_item, "Work item"),
        (recorded_by, "Progress recorder"),
    ):
        _same_company(instance, company, label)
    if site and site.project_id != project.id:
        raise ValidationError("Progress site must belong to the selected project")
    if work_item and work_item.project_id != project.id:
        raise ValidationError("Progress work item must belong to the selected project")
    entry = DailyProgress(
        company=company,
        project=project,
        site=site,
        work_item=work_item,
        progress_date=progress_date,
        quantity_completed=quantity_completed,
        unit_code=_code(unit_code) if unit_code else "",
        progress_percent=progress_percent,
        hours_worked=hours_worked,
        note=note.strip(),
        blockers=blockers.strip(),
        recorded_by=recorded_by,
    )
    entry.full_clean()
    entry.save()
    if work_item and progress_percent is not None and progress_percent > work_item.progress_percent:
        WorkItem.objects.filter(pk=work_item.pk, progress_percent__lt=progress_percent).update(
            progress_percent=progress_percent,
            version=work_item.version + 1,
            updated_at=timezone.now(),
        )
    _audit_event(
        action="work.progress.recorded",
        event_type="work.progress_recorded",
        entity_type="daily_progress",
        entity_public_id=entry.public_id,
        actor_public_id=actor_public_id,
        company=company,
        correlation_id=correlation_id,
        version=entry.version,
        after={
            "project_code": project.code,
            "work_item_code": work_item.code if work_item else None,
            "progress_date": progress_date.isoformat(),
            "progress_percent": str(progress_percent) if progress_percent is not None else None,
        },
    )
    return entry


@transaction.atomic
def create_timesheet(
    *,
    company: Company,
    employee: Employee,
    project: Project,
    work_date: date,
    hours: Decimal,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    work_item: WorkItem | None = None,
    description: str = "",
    submit_now: bool = False,
) -> TimesheetEntry:
    _same_company(employee, company, "Timesheet employee")
    _same_company(project, company, "Timesheet project")
    _same_company(work_item, company, "Timesheet work item")
    if work_item and work_item.project_id != project.id:
        raise ValidationError("Timesheet work item must belong to the selected project")
    existing_hours = (
        TimesheetEntry.objects.filter(company=company, employee=employee, work_date=work_date)
        .exclude(status_code="REJECTED")
        .aggregate(total=Sum("hours"))["total"]
        or Decimal("0.00")
    )
    if existing_hours + hours > Decimal("24.00"):
        raise ValidationError({"hours": "Total timesheet hours for one employee cannot exceed 24 per day"})
    entry = TimesheetEntry(
        company=company,
        employee=employee,
        project=project,
        work_item=work_item,
        work_date=work_date,
        hours=hours,
        description=description.strip(),
        status_code="SUBMITTED" if submit_now else "DRAFT",
        submitted_at=timezone.now() if submit_now else None,
    )
    entry.full_clean()
    entry.save()
    _audit_event(
        action="work.timesheet.created",
        event_type="work.timesheet_created",
        entity_type="timesheet_entry",
        entity_public_id=entry.public_id,
        actor_public_id=actor_public_id,
        company=company,
        correlation_id=correlation_id,
        version=entry.version,
        after={
            "employee_number": employee.employee_number,
            "project_code": project.code,
            "work_date": work_date.isoformat(),
            "hours": str(hours),
            "status_code": entry.status_code,
        },
    )
    return entry


@transaction.atomic
def submit_timesheet(
    *,
    company: Company,
    timesheet_public_id: uuid.UUID,
    expected_version: int,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> TimesheetEntry:
    entry: TimesheetEntry = _locked(TimesheetEntry, company=company, public_id=timesheet_public_id)
    _check_version(entry, expected_version)
    if entry.status_code not in {"DRAFT", "REJECTED"}:
        raise ValidationError("Only draft or rejected timesheets can be submitted")
    before = {"status_code": entry.status_code, "version": entry.version}
    entry.status_code = "SUBMITTED"
    entry.submitted_at = timezone.now()
    entry.reviewed_by_public_id = None
    entry.reviewed_at = None
    entry.review_note = ""
    entry.version += 1
    entry.save(
        update_fields=[
            "status_code",
            "submitted_at",
            "reviewed_by_public_id",
            "reviewed_at",
            "review_note",
            "version",
            "updated_at",
        ]
    )
    _audit_event(
        action="work.timesheet.submitted",
        event_type="work.timesheet_submitted",
        entity_type="timesheet_entry",
        entity_public_id=entry.public_id,
        actor_public_id=actor_public_id,
        company=company,
        correlation_id=correlation_id,
        version=entry.version,
        before=before,
        after={"status_code": entry.status_code, "version": entry.version},
    )
    return entry


@transaction.atomic
def review_timesheet(
    *,
    company: Company,
    timesheet_public_id: uuid.UUID,
    decision_code: str,
    expected_version: int,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    review_note: str = "",
) -> TimesheetEntry:
    entry: TimesheetEntry = _locked(TimesheetEntry, company=company, public_id=timesheet_public_id)
    _check_version(entry, expected_version)
    if entry.status_code != "SUBMITTED":
        raise ValidationError("Only submitted timesheets can be reviewed")
    if entry.employee.membership.user.public_id == actor_public_id:
        raise ValidationError("A person cannot approve their own timesheet")
    decision = _code(decision_code)
    if decision not in {"APPROVED", "REJECTED"}:
        raise ValidationError({"decision_code": "Decision must be APPROVED or REJECTED"})
    before = {"status_code": entry.status_code, "version": entry.version}
    entry.status_code = decision
    entry.reviewed_by_public_id = actor_public_id
    entry.reviewed_at = timezone.now()
    entry.review_note = review_note.strip()
    entry.version += 1
    entry.save(
        update_fields=["status_code", "reviewed_by_public_id", "reviewed_at", "review_note", "version", "updated_at"]
    )
    _audit_event(
        action="work.timesheet.reviewed",
        event_type="work.timesheet_reviewed",
        entity_type="timesheet_entry",
        entity_public_id=entry.public_id,
        actor_public_id=actor_public_id,
        company=company,
        correlation_id=correlation_id,
        version=entry.version,
        before=before,
        after={"status_code": entry.status_code, "review_note": entry.review_note, "version": entry.version},
    )
    return entry


@transaction.atomic
def request_work_approval(
    *,
    company: Company,
    work_item: WorkItem,
    reviewer: Employee,
    approval_type_code: str,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    request_note: str = "",
) -> WorkApproval:
    _same_company(work_item, company, "Work item")
    _same_company(reviewer, company, "Approval reviewer")
    if reviewer.membership.user.public_id == actor_public_id:
        raise ValidationError("Maker-checker control requires a different reviewer")
    if work_item.status_code not in {"IN_PROGRESS", "REVIEW"}:
        raise ValidationError("Work must be in progress or review before approval is requested")
    if work_item.checklist_items.filter(is_required=True, is_completed=False).exists():
        raise ValidationError("Complete all required checklist items before requesting approval")
    if WorkApproval.objects.filter(
        company=company,
        work_item=work_item,
        approval_type_code=_code(approval_type_code),
        status_code="PENDING",
    ).exists():
        raise ValidationError("A pending approval of this type already exists for the work item")
    approval = WorkApproval(
        company=company,
        work_item=work_item,
        approval_type_code=_code(approval_type_code),
        requested_by_public_id=actor_public_id,
        reviewer=reviewer,
        status_code="PENDING",
        request_note=request_note.strip(),
        requested_at=timezone.now(),
    )
    approval.full_clean()
    approval.save()
    if work_item.status_code == "IN_PROGRESS":
        work_item.status_code = "REVIEW"
        work_item.version += 1
        work_item.save(update_fields=["status_code", "version", "updated_at"])
    _audit_event(
        action="work.approval.requested",
        event_type="work.approval_requested",
        entity_type="work_approval",
        entity_public_id=approval.public_id,
        actor_public_id=actor_public_id,
        company=company,
        correlation_id=correlation_id,
        version=approval.version,
        after={
            "work_item_code": work_item.code,
            "approval_type_code": approval.approval_type_code,
            "reviewer_employee_number": reviewer.employee_number,
        },
    )
    return approval


@transaction.atomic
def review_work_approval(
    *,
    company: Company,
    approval_public_id: uuid.UUID,
    decision_code: str,
    expected_version: int,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    decision_note: str = "",
) -> WorkApproval:
    approval: WorkApproval = _locked(WorkApproval, company=company, public_id=approval_public_id)
    _check_version(approval, expected_version)
    if approval.status_code != "PENDING":
        raise ValidationError("Only pending approvals can be decided")
    if approval.requested_by_public_id == actor_public_id:
        raise ValidationError("A requester cannot decide their own approval")
    if approval.reviewer.membership.user.public_id != actor_public_id:
        raise ValidationError("Only the assigned reviewer can decide this approval")
    decision = _code(decision_code)
    if decision not in {"APPROVED", "REJECTED"}:
        raise ValidationError({"decision_code": "Decision must be APPROVED or REJECTED"})
    before = {"status_code": approval.status_code, "version": approval.version}
    approval.status_code = decision
    approval.decision_note = decision_note.strip()
    approval.decided_at = timezone.now()
    approval.decided_by_public_id = actor_public_id
    approval.version += 1
    approval.save(
        update_fields=["status_code", "decision_note", "decided_at", "decided_by_public_id", "version", "updated_at"]
    )
    item = WorkItem.objects.select_for_update().get(pk=approval.work_item_id)
    if decision == "APPROVED" and item.status_code == "REVIEW":
        item.status_code = "APPROVED"
        item.version += 1
        item.save(update_fields=["status_code", "version", "updated_at"])
    elif decision == "REJECTED" and item.status_code == "REVIEW":
        item.status_code = "IN_PROGRESS"
        item.version += 1
        item.save(update_fields=["status_code", "version", "updated_at"])
    _audit_event(
        action="work.approval.reviewed",
        event_type="work.approval_reviewed",
        entity_type="work_approval",
        entity_public_id=approval.public_id,
        actor_public_id=actor_public_id,
        company=company,
        correlation_id=correlation_id,
        version=approval.version,
        before=before,
        after={"status_code": approval.status_code, "decision_note": approval.decision_note, "version": approval.version},
    )
    return approval
