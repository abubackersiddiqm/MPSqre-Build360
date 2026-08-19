from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Prefetch, Q, Sum
from django.utils import timezone

from modules.employee.models import Employee, ReportingLine
from modules.myworkops.models import OfflineDraft, PersonalNotification, WorkActivity
from modules.tenant.models import Company, Membership
from modules.workops.models import (
    ChecklistItem,
    TimesheetEntry,
    WorkApproval,
    WorkAssignment,
    WorkItem,
)

OPEN_STATUSES = {"BACKLOG", "READY", "ASSIGNED", "IN_PROGRESS", "BLOCKED", "REVIEW", "APPROVED"}
EMPLOYEE_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "READY": ("IN_PROGRESS", "BLOCKED"),
    "ASSIGNED": ("IN_PROGRESS", "BLOCKED"),
    "IN_PROGRESS": ("BLOCKED", "REVIEW"),
    "BLOCKED": ("IN_PROGRESS",),
    "APPROVED": ("DONE",),
}


def _iso(value: Any) -> str | None:
    return value.isoformat() if value else None


def employee_for_membership(company: Company, membership: Membership) -> Employee | None:
    return (
        Employee.objects.filter(company=company, membership=membership)
        .select_related(
            "membership",
            "membership__user",
            "organization_profile",
            "organization_profile__department",
            "organization_profile__designation",
            "organization_profile__work_calendar",
        )
        .first()
    )


def assigned_work_queryset(company: Company, employee: Employee):
    today = timezone.localdate()
    assignment_ids = WorkAssignment.objects.filter(
        company=company,
        employee=employee,
        status_code="ACTIVE",
        effective_from__lte=today,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today)).values_list("work_item_id", flat=True)
    return (
        WorkItem.objects.filter(company=company)
        .filter(Q(primary_assignee=employee) | Q(id__in=assignment_ids))
        .select_related(
            "project",
            "site",
            "work_package",
            "primary_assignee",
            "reviewer",
            "reviewer__membership",
            "reviewer__membership__user",
        )
        .prefetch_related(
            Prefetch("checklist_items", queryset=ChecklistItem.objects.order_by("sequence")),
            "predecessor_links__predecessor",
        )
        .distinct()
    )


def _work_payload(item: WorkItem, today) -> dict[str, Any]:
    checklist = list(item.checklist_items.all())
    blocked_by = [
        link.predecessor
        for link in item.predecessor_links.all()
        if link.predecessor.status_code not in {"DONE", "CANCELLED"}
    ]
    if item.due_date and item.due_date < today and item.status_code in OPEN_STATUSES:
        bucket = "OVERDUE"
    elif item.status_code == "BLOCKED":
        bucket = "BLOCKED"
    elif item.due_date == today or (
        item.planned_start and item.planned_start <= today and item.status_code in OPEN_STATUSES
    ):
        bucket = "TODAY"
    elif item.due_date and today < item.due_date <= today + timedelta(days=14):
        bucket = "UPCOMING"
    elif item.status_code in {"DONE", "CANCELLED"}:
        bucket = "COMPLETED"
    else:
        bucket = "QUEUE"
    return {
        "public_id": str(item.public_id),
        "project_public_id": str(item.project.public_id),
        "project_code": item.project.code,
        "project_name": item.project.name,
        "site_name": item.site.name if item.site else None,
        "work_package_name": item.work_package.name if item.work_package else None,
        "code": item.code,
        "title": item.title,
        "description": item.description,
        "work_type_code": item.work_type_code,
        "status_code": item.status_code,
        "priority_code": item.priority_code,
        "planned_start": _iso(item.planned_start),
        "due_date": _iso(item.due_date),
        "progress_percent": str(item.progress_percent),
        "estimated_hours": str(item.estimated_hours) if item.estimated_hours is not None else None,
        "reviewer_name": item.reviewer.membership.user.display_name if item.reviewer else None,
        "reviewer_public_id": str(item.reviewer.public_id) if item.reviewer else None,
        "bucket": bucket,
        "is_overdue": bucket == "OVERDUE",
        "allowed_transitions": list(EMPLOYEE_TRANSITIONS.get(item.status_code, ())),
        "blocked_by": [
            {"public_id": str(value.public_id), "code": value.code, "title": value.title, "status_code": value.status_code}
            for value in blocked_by
        ],
        "checklist": [
            {
                "public_id": str(row.public_id),
                "sequence": row.sequence,
                "title": row.title,
                "is_required": row.is_required,
                "is_completed": row.is_completed,
                "version": row.version,
            }
            for row in checklist
        ],
        "version": item.version,
    }



def _refresh_operational_notifications(
    *,
    company: Company,
    employee: Employee,
    work_rows: list[WorkItem],
    approvals: list[WorkApproval],
    team_timesheets: list[TimesheetEntry],
    today,
) -> None:
    active_keys: set[str] = set()

    def upsert(*, source_key: str, notification_type_code: str, severity_code: str, title: str, message: str, work_item: WorkItem | None = None) -> None:
        active_keys.add(source_key)
        PersonalNotification.objects.update_or_create(
            company=company,
            employee=employee,
            source_key=source_key,
            defaults={
                "work_item": work_item,
                "notification_type_code": notification_type_code,
                "severity_code": severity_code,
                "title": title,
                "message": message,
                "action_url": "/platform/my-work",
            },
        )

    for item in work_rows:
        if item.status_code not in OPEN_STATUSES:
            continue
        if item.due_date and item.due_date < today:
            upsert(
                source_key=f"work:{item.public_id}:overdue",
                notification_type_code="WORK_OVERDUE",
                severity_code="CRITICAL",
                title=f"{item.code} is overdue",
                message=f"{item.title} was due on {item.due_date.isoformat()}.",
                work_item=item,
            )
        if item.status_code == "BLOCKED":
            upsert(
                source_key=f"work:{item.public_id}:blocked",
                notification_type_code="WORK_BLOCKED",
                severity_code="WARNING",
                title=f"{item.code} is blocked",
                message="Review the blocker and escalate the constraint when support is required.",
                work_item=item,
            )
        if item.due_date == today:
            upsert(
                source_key=f"work:{item.public_id}:due_today",
                notification_type_code="WORK_DUE_TODAY",
                severity_code="INFO",
                title=f"{item.code} is due today",
                message=item.title,
                work_item=item,
            )

    for approval in approvals:
        if approval.status_code == "PENDING":
            upsert(
                source_key=f"approval:{approval.public_id}:pending",
                notification_type_code="APPROVAL_PENDING",
                severity_code="WARNING",
                title=f"Approval required for {approval.work_item.code}",
                message=approval.work_item.title,
                work_item=approval.work_item,
            )

    for timesheet in team_timesheets:
        upsert(
            source_key=f"timesheet:{timesheet.public_id}:pending",
            notification_type_code="TIMESHEET_PENDING",
            severity_code="INFO",
            title=f"Timesheet awaiting review: {timesheet.employee.employee_number}",
            message=f"{timesheet.hours} hours on {timesheet.work_date.isoformat()}.",
            work_item=timesheet.work_item,
        )

    generated = PersonalNotification.objects.filter(
        company=company,
        employee=employee,
        dismissed_at__isnull=True,
    ).filter(
        Q(source_key__startswith="work:")
        | Q(source_key__startswith="approval:")
        | Q(source_key__startswith="timesheet:")
    )
    if active_keys:
        generated.exclude(source_key__in=active_keys).update(dismissed_at=timezone.now())
    else:
        generated.update(dismissed_at=timezone.now())

def my_work_overview(company: Company, membership: Membership) -> dict[str, Any]:
    now = timezone.now()
    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    employee = employee_for_membership(company, membership)
    company_payload = {
        "public_id": str(company.public_id),
        "code": company.code,
        "display_name": company.display_name,
        "timezone": company.timezone,
        "currency": company.currency,
        "locale": company.locale,
    }
    if employee is None:
        return {
            "generated_at": now.isoformat(),
            "company": company_payload,
            "profile_state": "EMPLOYEE_PROFILE_REQUIRED",
            "employee": None,
            "summary": {
                "due_today_count": 0,
                "overdue_count": 0,
                "blocked_count": 0,
                "open_count": 0,
                "pending_approval_count": 0,
                "submitted_team_timesheet_count": 0,
                "hours_this_week": "0",
                "unread_notification_count": 0,
                "offline_draft_count": 0,
            },
            "work_items": [],
            "timesheets": [],
            "approval_inbox": [],
            "team_timesheets": [],
            "notifications": [],
            "offline_drafts": [],
            "activity": [],
        }

    try:
        org = employee.organization_profile
    except ObjectDoesNotExist:
        org = None

    work_rows = list(assigned_work_queryset(company, employee).order_by("due_date", "priority_code", "code")[:2000])
    work_payload = [_work_payload(item, today) for item in work_rows]

    own_timesheets = list(
        TimesheetEntry.objects.filter(company=company, employee=employee)
        .select_related("project", "work_item")
        .order_by("-work_date", "-created_at")[:500]
    )
    approvals = list(
        WorkApproval.objects.filter(company=company, reviewer=employee)
        .select_related("work_item", "work_item__project")
        .order_by("status_code", "requested_at")[:500]
    )

    direct_report_ids = ReportingLine.objects.filter(
        company=company,
        manager=employee,
        effective_from__lte=today,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today)).values_list("employee_id", flat=True)
    team_timesheets = list(
        TimesheetEntry.objects.filter(company=company, employee_id__in=direct_report_ids, status_code="SUBMITTED")
        .select_related("employee", "employee__membership", "employee__membership__user", "project", "work_item")
        .order_by("work_date", "employee__employee_number")[:500]
    )

    _refresh_operational_notifications(
        company=company,
        employee=employee,
        work_rows=work_rows,
        approvals=approvals,
        team_timesheets=team_timesheets,
        today=today,
    )
    notifications = list(
        PersonalNotification.objects.filter(company=company, employee=employee, dismissed_at__isnull=True)
        .select_related("work_item")
        .order_by("read_at", "-created_at")[:200]
    )
    drafts = list(
        OfflineDraft.objects.filter(company=company, employee=employee)
        .exclude(status_code="DISCARDED")
        .select_related("work_item")
        .order_by("status_code", "-client_updated_at")[:200]
    )
    activity = list(
        WorkActivity.objects.filter(company=company, employee=employee)
        .select_related("work_item", "work_item__project")
        .order_by("-occurred_at")[:200]
    )
    approved_hours = (
        TimesheetEntry.objects.filter(
            company=company,
            employee=employee,
            status_code="APPROVED",
            work_date__gte=week_start,
            work_date__lte=today,
        ).aggregate(total=Sum("hours"))["total"]
        or Decimal("0")
    )

    return {
        "generated_at": now.isoformat(),
        "company": company_payload,
        "profile_state": "ACTIVE",
        "employee": {
            "public_id": str(employee.public_id),
            "employee_number": employee.employee_number,
            "display_name": employee.membership.user.display_name,
            "email": employee.membership.user.email,
            "job_title": employee.job_title,
            "department_name": org.department.name if org and org.department else None,
            "designation_name": org.designation.name if org and org.designation else None,
            "work_calendar_name": org.work_calendar.name if org and org.work_calendar else None,
        },
        "summary": {
            "due_today_count": sum(1 for item in work_payload if item["bucket"] == "TODAY"),
            "overdue_count": sum(1 for item in work_payload if item["bucket"] == "OVERDUE"),
            "blocked_count": sum(1 for item in work_payload if item["status_code"] == "BLOCKED"),
            "open_count": sum(1 for item in work_payload if item["status_code"] in OPEN_STATUSES),
            "pending_approval_count": sum(1 for item in approvals if item.status_code == "PENDING"),
            "submitted_team_timesheet_count": len(team_timesheets),
            "hours_this_week": str(approved_hours),
            "unread_notification_count": sum(1 for item in notifications if item.read_at is None),
            "offline_draft_count": sum(1 for item in drafts if item.status_code in {"DRAFT", "CONFLICT"}),
        },
        "work_items": work_payload,
        "timesheets": [
            {
                "public_id": str(item.public_id),
                "project_public_id": str(item.project.public_id),
                "project_code": item.project.code,
                "project_name": item.project.name,
                "work_item_public_id": str(item.work_item.public_id) if item.work_item else None,
                "work_item_code": item.work_item.code if item.work_item else None,
                "work_date": item.work_date.isoformat(),
                "hours": str(item.hours),
                "description": item.description,
                "status_code": item.status_code,
                "review_note": item.review_note,
                "version": item.version,
            }
            for item in own_timesheets
        ],
        "approval_inbox": [
            {
                "public_id": str(item.public_id),
                "work_item_public_id": str(item.work_item.public_id),
                "work_item_code": item.work_item.code,
                "work_item_title": item.work_item.title,
                "project_code": item.work_item.project.code,
                "approval_type_code": item.approval_type_code,
                "status_code": item.status_code,
                "request_note": item.request_note,
                "decision_note": item.decision_note,
                "requested_at": item.requested_at.isoformat(),
                "version": item.version,
            }
            for item in approvals
        ],
        "team_timesheets": [
            {
                "public_id": str(item.public_id),
                "employee_name": item.employee.membership.user.display_name,
                "employee_number": item.employee.employee_number,
                "project_code": item.project.code,
                "work_item_code": item.work_item.code if item.work_item else None,
                "work_date": item.work_date.isoformat(),
                "hours": str(item.hours),
                "description": item.description,
                "status_code": item.status_code,
                "version": item.version,
            }
            for item in team_timesheets
        ],
        "notifications": [
            {
                "public_id": str(item.public_id),
                "notification_type_code": item.notification_type_code,
                "severity_code": item.severity_code,
                "title": item.title,
                "message": item.message,
                "action_url": item.action_url,
                "work_item_public_id": str(item.work_item.public_id) if item.work_item else None,
                "read_at": _iso(item.read_at),
                "created_at": item.created_at.isoformat(),
                "version": item.version,
            }
            for item in notifications
        ],
        "offline_drafts": [
            {
                "public_id": str(item.public_id),
                "client_draft_id": str(item.client_draft_id),
                "device_id": str(item.device_id),
                "draft_type_code": item.draft_type_code,
                "work_item_public_id": str(item.work_item.public_id) if item.work_item else None,
                "work_item_code": item.work_item.code if item.work_item else None,
                "payload": item.payload,
                "status_code": item.status_code,
                "client_updated_at": item.client_updated_at.isoformat(),
                "synced_at": _iso(item.synced_at),
                "conflict_reason": item.conflict_reason,
                "version": item.version,
            }
            for item in drafts
        ],
        "activity": [
            {
                "public_id": str(item.public_id),
                "activity_type_code": item.activity_type_code,
                "summary": item.summary,
                "work_item_public_id": str(item.work_item.public_id) if item.work_item else None,
                "work_item_code": item.work_item.code if item.work_item else None,
                "project_code": item.work_item.project.code if item.work_item else None,
                "occurred_at": item.occurred_at.isoformat(),
                "metadata": item.metadata,
            }
            for item in activity
        ],
    }
