from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from modules.employee.models import Employee, ReportingLine
from modules.myworkops.models import OfflineDraft, PersonalNotification, WorkActivity
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.tenant.models import Company, Membership
from modules.workops.application.services import (
    create_timesheet,
    record_daily_progress,
    review_timesheet,
    review_work_approval,
    set_checklist_completion,
    submit_timesheet,
    transition_work_item,
)
from modules.workops.models import (
    ChecklistItem,
    Project,
    TimesheetEntry,
    WorkApproval,
    WorkAssignment,
    WorkItem,
)

EMPLOYEE_TRANSITIONS: dict[str, set[str]] = {
    "READY": {"IN_PROGRESS", "BLOCKED"},
    "ASSIGNED": {"IN_PROGRESS", "BLOCKED"},
    "IN_PROGRESS": {"BLOCKED", "REVIEW"},
    "BLOCKED": {"IN_PROGRESS"},
    "APPROVED": {"DONE"},
}


def _code(value: str) -> str:
    return value.strip().upper().replace(" ", "_")


def current_employee(company: Company, membership: Membership) -> Employee:
    employee = Employee.objects.filter(company=company, membership=membership).first()
    if employee is None:
        raise ValidationError(
            {"employee_profile": "Complete the employee profile in People and Organization before using My Work."}
        )
    return employee


def _is_assigned(company: Company, employee: Employee, item: WorkItem) -> bool:
    if item.company_id != company.id:
        return False
    if item.primary_assignee_id == employee.id:
        return True
    today = timezone.localdate()
    return WorkAssignment.objects.filter(
        company=company,
        employee=employee,
        work_item=item,
        status_code="ACTIVE",
        effective_from__lte=today,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today)).exists()


def _require_assigned(company: Company, employee: Employee, item: WorkItem) -> None:
    if not _is_assigned(company, employee, item):
        raise ValidationError("The work item is not assigned to this employee")


def _require_direct_report(company: Company, manager: Employee, employee: Employee) -> None:
    today = timezone.localdate()
    allowed = ReportingLine.objects.filter(
        company=company,
        manager=manager,
        employee=employee,
        effective_from__lte=today,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today)).exists()
    if not allowed:
        raise ValidationError("The timesheet does not belong to a current direct report")


def _activity(
    *,
    company: Company,
    employee: Employee,
    actor_public_id: uuid.UUID,
    activity_type_code: str,
    summary: str,
    work_item: WorkItem | None = None,
    metadata: dict[str, Any] | None = None,
) -> WorkActivity:
    return WorkActivity.objects.create(
        company=company,
        employee=employee,
        work_item=work_item,
        activity_type_code=_code(activity_type_code),
        summary=summary[:500],
        actor_public_id=actor_public_id,
        metadata=metadata or {},
    )


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


@transaction.atomic
def transition_own_work_item(
    *,
    company: Company,
    employee: Employee,
    work_item_public_id: uuid.UUID,
    status_code: str,
    expected_version: int,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> WorkItem:
    item = WorkItem.objects.select_related("project").filter(company=company, public_id=work_item_public_id).first()
    if item is None:
        raise ValidationError("Work item not found")
    _require_assigned(company, employee, item)
    target = _code(status_code)
    if target not in EMPLOYEE_TRANSITIONS.get(item.status_code, set()):
        raise ValidationError({"status_code": f"Employees cannot move work from {item.status_code} to {target}"})
    result = transition_work_item(
        company=company,
        work_item_public_id=item.public_id,
        status_code=target,
        expected_version=expected_version,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
    )
    _activity(
        company=company,
        employee=employee,
        work_item=result,
        actor_public_id=actor_public_id,
        activity_type_code="WORK_STATUS_CHANGED",
        summary=f"Moved {result.code} to {result.status_code.replace('_', ' ').title()}",
        metadata={"status_code": result.status_code, "version": result.version},
    )
    return result


@transaction.atomic
def complete_own_checklist(
    *,
    company: Company,
    employee: Employee,
    checklist_public_id: uuid.UUID,
    is_completed: bool,
    expected_version: int,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> ChecklistItem:
    item = ChecklistItem.objects.select_related("work_item").filter(company=company, public_id=checklist_public_id).first()
    if item is None:
        raise ValidationError("Checklist item not found")
    _require_assigned(company, employee, item.work_item)
    result = set_checklist_completion(
        company=company,
        checklist_public_id=item.public_id,
        is_completed=is_completed,
        expected_version=expected_version,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
    )
    _activity(
        company=company,
        employee=employee,
        work_item=result.work_item,
        actor_public_id=actor_public_id,
        activity_type_code="CHECKLIST_UPDATED",
        summary=f"{'Completed' if result.is_completed else 'Reopened'} checklist: {result.title}",
        metadata={"checklist_public_id": str(result.public_id), "is_completed": result.is_completed},
    )
    return result


@transaction.atomic
def record_own_progress(
    *,
    company: Company,
    employee: Employee,
    work_item: WorkItem,
    progress_date: date,
    quantity_completed: Decimal,
    hours_worked: Decimal,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    unit_code: str = "",
    progress_percent: Decimal | None = None,
    note: str = "",
    blockers: str = "",
):
    _require_assigned(company, employee, work_item)
    result = record_daily_progress(
        company=company,
        project=work_item.project,
        site=work_item.site,
        work_item=work_item,
        recorded_by=employee,
        progress_date=progress_date,
        quantity_completed=quantity_completed,
        hours_worked=hours_worked,
        unit_code=unit_code,
        progress_percent=progress_percent,
        note=note,
        blockers=blockers,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
    )
    _activity(
        company=company,
        employee=employee,
        work_item=work_item,
        actor_public_id=actor_public_id,
        activity_type_code="PROGRESS_RECORDED",
        summary=f"Recorded progress for {work_item.code}",
        metadata={
            "progress_date": progress_date.isoformat(),
            "progress_percent": str(progress_percent) if progress_percent is not None else None,
            "hours_worked": str(hours_worked),
            "has_blocker": bool(blockers.strip()),
        },
    )
    return result


def _project_available(company: Company, employee: Employee, project: Project) -> bool:
    if project.company_id != company.id:
        return False
    return WorkItem.objects.filter(company=company, project=project).filter(
        Q(primary_assignee=employee) | Q(assignments__employee=employee, assignments__status_code="ACTIVE")
    ).exists()


@transaction.atomic
def create_own_timesheet(
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
    if work_item is not None:
        _require_assigned(company, employee, work_item)
        if work_item.project_id != project.id:
            raise ValidationError("Timesheet work item must belong to the selected project")
    elif not _project_available(company, employee, project):
        raise ValidationError("The project is not available in this employee's assigned work")
    result = create_timesheet(
        company=company,
        employee=employee,
        project=project,
        work_item=work_item,
        work_date=work_date,
        hours=hours,
        description=description,
        submit_now=submit_now,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
    )
    _activity(
        company=company,
        employee=employee,
        work_item=work_item,
        actor_public_id=actor_public_id,
        activity_type_code="TIMESHEET_CREATED",
        summary=f"Logged {hours} hours for {project.code}",
        metadata={"timesheet_public_id": str(result.public_id), "status_code": result.status_code},
    )
    return result


@transaction.atomic
def submit_own_timesheet(
    *,
    company: Company,
    employee: Employee,
    timesheet_public_id: uuid.UUID,
    expected_version: int,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> TimesheetEntry:
    entry = TimesheetEntry.objects.filter(company=company, public_id=timesheet_public_id).first()
    if entry is None:
        raise ValidationError("Timesheet not found")
    if entry.employee_id != employee.id:
        raise ValidationError("Employees can submit only their own timesheets")
    result = submit_timesheet(
        company=company,
        timesheet_public_id=entry.public_id,
        expected_version=expected_version,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
    )
    _activity(
        company=company,
        employee=employee,
        work_item=result.work_item,
        actor_public_id=actor_public_id,
        activity_type_code="TIMESHEET_SUBMITTED",
        summary=f"Submitted {result.hours} hours for review",
        metadata={"timesheet_public_id": str(result.public_id)},
    )
    return result


@transaction.atomic
def decide_own_approval(
    *,
    company: Company,
    employee: Employee,
    approval_public_id: uuid.UUID,
    decision_code: str,
    expected_version: int,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    decision_note: str = "",
) -> WorkApproval:
    approval = WorkApproval.objects.select_related("work_item").filter(company=company, public_id=approval_public_id).first()
    if approval is None:
        raise ValidationError("Approval not found")
    if approval.reviewer_id != employee.id:
        raise ValidationError("This approval is assigned to another reviewer")
    result = review_work_approval(
        company=company,
        approval_public_id=approval.public_id,
        decision_code=decision_code,
        expected_version=expected_version,
        decision_note=decision_note,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
    )
    _activity(
        company=company,
        employee=employee,
        work_item=result.work_item,
        actor_public_id=actor_public_id,
        activity_type_code="APPROVAL_DECIDED",
        summary=f"{result.status_code.title()} {result.work_item.code}",
        metadata={"approval_public_id": str(result.public_id), "decision_note": result.decision_note},
    )
    return result


@transaction.atomic
def decide_team_timesheet(
    *,
    company: Company,
    manager: Employee,
    timesheet_public_id: uuid.UUID,
    decision_code: str,
    expected_version: int,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    review_note: str = "",
) -> TimesheetEntry:
    entry = TimesheetEntry.objects.select_related("employee", "work_item").filter(
        company=company, public_id=timesheet_public_id
    ).first()
    if entry is None:
        raise ValidationError("Timesheet not found")
    _require_direct_report(company, manager, entry.employee)
    result = review_timesheet(
        company=company,
        timesheet_public_id=entry.public_id,
        decision_code=decision_code,
        expected_version=expected_version,
        review_note=review_note,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
    )
    _activity(
        company=company,
        employee=manager,
        work_item=result.work_item,
        actor_public_id=actor_public_id,
        activity_type_code="TEAM_TIMESHEET_DECIDED",
        summary=f"{result.status_code.title()} team timesheet",
        metadata={"timesheet_public_id": str(result.public_id), "employee_public_id": str(result.employee.public_id)},
    )
    return result


@transaction.atomic
def upsert_offline_draft(
    *,
    company: Company,
    employee: Employee,
    client_draft_id: uuid.UUID,
    device_id: uuid.UUID,
    draft_type_code: str,
    payload: dict[str, Any],
    client_updated_at,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    work_item: WorkItem | None = None,
) -> OfflineDraft:
    if work_item is not None:
        _require_assigned(company, employee, work_item)
    draft_type = _code(draft_type_code)
    if draft_type not in {"PROGRESS", "TIMESHEET", "NOTE"}:
        raise ValidationError({"draft_type_code": "Supported draft types are PROGRESS, TIMESHEET and NOTE"})
    existing = OfflineDraft.objects.select_for_update().filter(
        company=company,
        employee=employee,
        client_draft_id=client_draft_id,
    ).first()
    if existing and client_updated_at < existing.client_updated_at:
        existing.status_code = "CONFLICT"
        existing.conflict_reason = "A newer draft is already stored on the server"
        existing.version += 1
        existing.save(update_fields=["status_code", "conflict_reason", "version", "updated_at"])
        return existing
    before = {"status_code": existing.status_code, "version": existing.version} if existing else {}
    if existing is None:
        existing = OfflineDraft(
            company=company,
            employee=employee,
            client_draft_id=client_draft_id,
            device_id=device_id,
            draft_type_code=draft_type,
            payload=payload,
            client_updated_at=client_updated_at,
            work_item=work_item,
        )
    else:
        existing.device_id = device_id
        existing.draft_type_code = draft_type
        existing.payload = payload
        existing.client_updated_at = client_updated_at
        existing.work_item = work_item
        existing.status_code = "DRAFT"
        existing.synced_at = None
        existing.conflict_reason = ""
        existing.version += 1
    existing.full_clean()
    existing.save()
    _audit_event(
        action="mywork.offline_draft.saved",
        event_type="mywork.offline_draft_saved",
        entity_type="offline_draft",
        entity_public_id=existing.public_id,
        actor_public_id=actor_public_id,
        company=company,
        correlation_id=correlation_id,
        version=existing.version,
        before=before,
        after={"draft_type_code": existing.draft_type_code, "status_code": existing.status_code},
    )
    return existing


@transaction.atomic
def sync_offline_draft(
    *,
    company: Company,
    employee: Employee,
    draft_public_id: uuid.UUID,
    expected_version: int,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> OfflineDraft:
    draft = OfflineDraft.objects.select_for_update().select_related("work_item", "work_item__project", "work_item__site").filter(
        company=company,
        employee=employee,
        public_id=draft_public_id,
    ).first()
    if draft is None:
        raise ValidationError("Offline draft not found")
    if draft.version != expected_version:
        raise ValidationError({"expected_version": f"Draft changed. Current version is {draft.version}."})
    if draft.status_code == "SYNCED":
        return draft
    payload = draft.payload
    try:
        if draft.draft_type_code == "PROGRESS":
            if draft.work_item is None:
                raise ValidationError("A progress draft requires a work item")
            expected_work_version = payload.get("work_item_version")
            if expected_work_version is not None and int(expected_work_version) != draft.work_item.version:
                raise ValidationError("The work item changed after this draft was created")
            record_own_progress(
                company=company,
                employee=employee,
                work_item=draft.work_item,
                progress_date=date.fromisoformat(str(payload["progress_date"])),
                quantity_completed=Decimal(str(payload.get("quantity_completed", "0"))),
                hours_worked=Decimal(str(payload.get("hours_worked", "0"))),
                unit_code=str(payload.get("unit_code", "")),
                progress_percent=(
                    Decimal(str(payload["progress_percent"]))
                    if payload.get("progress_percent") not in {None, ""}
                    else None
                ),
                note=str(payload.get("note", "")),
                blockers=str(payload.get("blockers", "")),
                actor_public_id=actor_public_id,
                correlation_id=correlation_id,
            )
        elif draft.draft_type_code == "TIMESHEET":
            project = Project.objects.filter(company=company, public_id=payload.get("project_public_id")).first()
            if project is None:
                raise ValidationError("Timesheet project not found")
            work_item = draft.work_item
            create_own_timesheet(
                company=company,
                employee=employee,
                project=project,
                work_item=work_item,
                work_date=date.fromisoformat(str(payload["work_date"])),
                hours=Decimal(str(payload["hours"])),
                description=str(payload.get("description", "")),
                submit_now=bool(payload.get("submit_now", False)),
                actor_public_id=actor_public_id,
                correlation_id=correlation_id,
            )
        elif draft.draft_type_code == "NOTE":
            _activity(
                company=company,
                employee=employee,
                work_item=draft.work_item,
                actor_public_id=actor_public_id,
                activity_type_code="OFFLINE_NOTE_SYNCED",
                summary=str(payload.get("summary", "Offline note synchronized")),
                metadata={"note": str(payload.get("note", ""))[:2000]},
            )
        else:
            raise ValidationError("Unsupported offline draft type")
    except (ValidationError, KeyError, ValueError, ArithmeticError) as error:
        draft.status_code = "CONFLICT"
        if isinstance(error, ValidationError):
            draft.conflict_reason = "; ".join(error.messages)
        else:
            draft.conflict_reason = str(error)
        draft.version += 1
        draft.save(update_fields=["status_code", "conflict_reason", "version", "updated_at"])
        return draft

    before = {"status_code": draft.status_code, "version": draft.version}
    draft.status_code = "SYNCED"
    draft.synced_at = timezone.now()
    draft.conflict_reason = ""
    draft.version += 1
    draft.save(update_fields=["status_code", "synced_at", "conflict_reason", "version", "updated_at"])
    _audit_event(
        action="mywork.offline_draft.synced",
        event_type="mywork.offline_draft_synced",
        entity_type="offline_draft",
        entity_public_id=draft.public_id,
        actor_public_id=actor_public_id,
        company=company,
        correlation_id=correlation_id,
        version=draft.version,
        before=before,
        after={"draft_type_code": draft.draft_type_code, "status_code": draft.status_code},
    )
    return draft


@transaction.atomic
def discard_offline_draft(
    *,
    company: Company,
    employee: Employee,
    draft_public_id: uuid.UUID,
    expected_version: int,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> OfflineDraft:
    draft = OfflineDraft.objects.select_for_update().filter(
        company=company, employee=employee, public_id=draft_public_id
    ).first()
    if draft is None:
        raise ValidationError("Offline draft not found")
    if draft.version != expected_version:
        raise ValidationError({"expected_version": f"Draft changed. Current version is {draft.version}."})
    before = {"status_code": draft.status_code, "version": draft.version}
    draft.status_code = "DISCARDED"
    draft.version += 1
    draft.save(update_fields=["status_code", "version", "updated_at"])
    _audit_event(
        action="mywork.offline_draft.discarded",
        event_type="mywork.offline_draft_discarded",
        entity_type="offline_draft",
        entity_public_id=draft.public_id,
        actor_public_id=actor_public_id,
        company=company,
        correlation_id=correlation_id,
        version=draft.version,
        before=before,
        after={"status_code": draft.status_code},
    )
    return draft


@transaction.atomic
def update_notification_state(
    *,
    company: Company,
    employee: Employee,
    notification_public_id: uuid.UUID,
    action: str,
    expected_version: int,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> PersonalNotification:
    notification = PersonalNotification.objects.select_for_update().filter(
        company=company, employee=employee, public_id=notification_public_id
    ).first()
    if notification is None:
        raise ValidationError("Notification not found")
    if notification.version != expected_version:
        raise ValidationError(
            {"expected_version": f"Notification changed. Current version is {notification.version}."}
        )
    command = _code(action)
    before = {
        "read_at": notification.read_at.isoformat() if notification.read_at else None,
        "dismissed_at": notification.dismissed_at.isoformat() if notification.dismissed_at else None,
        "version": notification.version,
    }
    if command == "READ":
        notification.read_at = notification.read_at or timezone.now()
    elif command == "UNREAD":
        notification.read_at = None
    elif command == "DISMISS":
        notification.dismissed_at = timezone.now()
        notification.read_at = notification.read_at or timezone.now()
    else:
        raise ValidationError({"action": "Action must be READ, UNREAD or DISMISS"})
    notification.version += 1
    notification.save(update_fields=["read_at", "dismissed_at", "version", "updated_at"])
    _audit_event(
        action="mywork.notification.state_changed",
        event_type="mywork.notification_state_changed",
        entity_type="personal_notification",
        entity_public_id=notification.public_id,
        actor_public_id=actor_public_id,
        company=company,
        correlation_id=correlation_id,
        version=notification.version,
        before=before,
        after={"action": command, "version": notification.version},
    )
    return notification
