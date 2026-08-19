from __future__ import annotations

from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone

from modules.employee.models import Employee
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


def _iso(value):
    return value.isoformat() if value else None


def project_work_overview(company: Company) -> dict[str, object]:
    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())

    projects = list(
        Project.objects.filter(company=company)
        .select_related("manager", "manager__membership", "manager__membership__user", "location")
        .order_by("code")[:1000]
    )
    sites = list(
        ProjectSite.objects.filter(company=company)
        .select_related("project", "location")
        .order_by("project__code", "code")[:2000]
    )
    wbs_nodes = list(
        WBSNode.objects.filter(company=company)
        .select_related("project", "parent")
        .order_by("project__code", "level", "sequence", "code")[:3000]
    )
    packages = list(
        WorkPackage.objects.filter(company=company)
        .select_related("project", "wbs_node", "owner", "owner__membership", "owner__membership__user")
        .order_by("project__code", "code")[:3000]
    )
    milestones = list(
        Milestone.objects.filter(company=company)
        .select_related("project", "owner", "owner__membership", "owner__membership__user")
        .order_by("target_date", "project__code")[:2000]
    )
    work_items = list(
        WorkItem.objects.filter(company=company)
        .select_related(
            "project",
            "site",
            "work_package",
            "primary_assignee",
            "primary_assignee__membership",
            "primary_assignee__membership__user",
            "reviewer",
            "reviewer__membership",
            "reviewer__membership__user",
        )
        .order_by("due_date", "project__code", "code")[:5000]
    )
    work_item_ids = [item.id for item in work_items]

    checklist_rows = list(
        ChecklistItem.objects.filter(company=company, work_item_id__in=work_item_ids)
        .select_related("work_item")
        .order_by("work_item__code", "sequence")[:10000]
    )
    checklists_by_item: dict[int, list[ChecklistItem]] = {}
    for row in checklist_rows:
        checklists_by_item.setdefault(row.work_item_id, []).append(row)

    assignments = list(
        WorkAssignment.objects.filter(company=company)
        .select_related("work_item", "employee", "employee__membership", "employee__membership__user")
        .order_by("work_item__code", "employee__employee_number")[:5000]
    )
    dependencies = list(
        WorkDependency.objects.filter(company=company)
        .select_related("predecessor", "successor")
        .order_by("successor__code", "predecessor__code")[:5000]
    )
    progress_entries = list(
        DailyProgress.objects.filter(company=company)
        .select_related("project", "site", "work_item", "recorded_by", "recorded_by__membership", "recorded_by__membership__user")
        .order_by("-progress_date", "-created_at")[:500]
    )
    timesheets = list(
        TimesheetEntry.objects.filter(company=company)
        .select_related("employee", "employee__membership", "employee__membership__user", "project", "work_item")
        .order_by("-work_date", "-created_at")[:1000]
    )
    approvals = list(
        WorkApproval.objects.filter(company=company)
        .select_related("work_item", "work_item__project", "reviewer", "reviewer__membership", "reviewer__membership__user")
        .order_by("status_code", "requested_at")[:1000]
    )
    people = list(
        Employee.objects.filter(company=company, membership__suspended_at__isnull=True, membership__terminated_at__isnull=True)
        .select_related("membership", "membership__user")
        .order_by("employee_number")[:3000]
    )
    locations = list(Location.objects.filter(company=company).order_by("name")[:2000])

    open_statuses = ["BACKLOG", "READY", "ASSIGNED", "IN_PROGRESS", "BLOCKED", "REVIEW", "APPROVED"]
    overdue = sum(1 for item in work_items if item.status_code in open_statuses and item.due_date and item.due_date < today)
    approved_hours = (
        TimesheetEntry.objects.filter(
            company=company,
            status_code="APPROVED",
            work_date__gte=week_start,
            work_date__lte=today,
        ).aggregate(total=Sum("hours"))["total"]
        or 0
    )

    return {
        "generated_at": timezone.now().isoformat(),
        "company": {
            "public_id": str(company.public_id),
            "code": company.code,
            "display_name": company.display_name,
            "timezone": company.timezone,
            "currency": company.currency,
            "locale": company.locale,
        },
        "summary": {
            "active_project_count": sum(1 for item in projects if item.status_code == "ACTIVE"),
            "open_work_count": sum(1 for item in work_items if item.status_code in open_statuses),
            "overdue_work_count": overdue,
            "blocked_work_count": sum(1 for item in work_items if item.status_code == "BLOCKED"),
            "pending_approval_count": sum(1 for item in approvals if item.status_code == "PENDING"),
            "submitted_timesheet_count": sum(1 for item in timesheets if item.status_code == "SUBMITTED"),
            "approved_hours_this_week": str(approved_hours),
            "milestones_due_30_days": sum(
                1
                for item in milestones
                if item.status_code not in {"ACHIEVED", "CANCELLED"}
                and today <= item.target_date <= today + timedelta(days=30)
            ),
        },
        "projects": [
            {
                "public_id": str(item.public_id),
                "code": item.code,
                "name": item.name,
                "description": item.description,
                "project_type_code": item.project_type_code,
                "status_code": item.status_code,
                "priority_code": item.priority_code,
                "manager_public_id": str(item.manager.public_id) if item.manager else None,
                "manager_name": item.manager.membership.user.display_name if item.manager else None,
                "location_public_id": str(item.location.public_id) if item.location else None,
                "location_name": item.location.name if item.location else None,
                "start_date": item.start_date.isoformat(),
                "target_end_date": item.target_end_date.isoformat(),
                "actual_end_date": _iso(item.actual_end_date),
                "currency": item.currency,
                "budget": str(item.budget) if item.budget is not None else None,
                "version": item.version,
            }
            for item in projects
        ],
        "sites": [
            {
                "public_id": str(item.public_id),
                "project_public_id": str(item.project.public_id),
                "project_code": item.project.code,
                "code": item.code,
                "name": item.name,
                "location_public_id": str(item.location.public_id) if item.location else None,
                "location_name": item.location.name if item.location else None,
                "status_code": item.status_code,
                "start_date": _iso(item.start_date),
                "target_end_date": _iso(item.target_end_date),
                "version": item.version,
            }
            for item in sites
        ],
        "wbs_nodes": [
            {
                "public_id": str(item.public_id),
                "project_public_id": str(item.project.public_id),
                "project_code": item.project.code,
                "code": item.code,
                "name": item.name,
                "parent_public_id": str(item.parent.public_id) if item.parent else None,
                "parent_name": item.parent.name if item.parent else None,
                "sequence": item.sequence,
                "level": item.level,
                "status_code": item.status_code,
                "version": item.version,
            }
            for item in wbs_nodes
        ],
        "work_packages": [
            {
                "public_id": str(item.public_id),
                "project_public_id": str(item.project.public_id),
                "project_code": item.project.code,
                "wbs_node_public_id": str(item.wbs_node.public_id),
                "wbs_name": item.wbs_node.name,
                "code": item.code,
                "name": item.name,
                "description": item.description,
                "owner_public_id": str(item.owner.public_id) if item.owner else None,
                "owner_name": item.owner.membership.user.display_name if item.owner else None,
                "planned_start": item.planned_start.isoformat(),
                "planned_end": item.planned_end.isoformat(),
                "status_code": item.status_code,
                "progress_weight": str(item.progress_weight),
                "version": item.version,
            }
            for item in packages
        ],
        "milestones": [
            {
                "public_id": str(item.public_id),
                "project_public_id": str(item.project.public_id),
                "project_code": item.project.code,
                "code": item.code,
                "name": item.name,
                "target_date": item.target_date.isoformat(),
                "owner_name": item.owner.membership.user.display_name if item.owner else None,
                "status_code": item.status_code,
                "achieved_at": _iso(item.achieved_at),
                "version": item.version,
            }
            for item in milestones
        ],
        "work_items": [
            {
                "public_id": str(item.public_id),
                "project_public_id": str(item.project.public_id),
                "project_code": item.project.code,
                "site_public_id": str(item.site.public_id) if item.site else None,
                "site_name": item.site.name if item.site else None,
                "work_package_public_id": str(item.work_package.public_id) if item.work_package else None,
                "work_package_name": item.work_package.name if item.work_package else None,
                "code": item.code,
                "title": item.title,
                "description": item.description,
                "work_type_code": item.work_type_code,
                "status_code": item.status_code,
                "priority_code": item.priority_code,
                "planned_start": _iso(item.planned_start),
                "due_date": _iso(item.due_date),
                "actual_start": _iso(item.actual_start),
                "completed_at": _iso(item.completed_at),
                "progress_percent": str(item.progress_percent),
                "estimated_hours": str(item.estimated_hours) if item.estimated_hours is not None else None,
                "primary_assignee_public_id": str(item.primary_assignee.public_id) if item.primary_assignee else None,
                "primary_assignee_name": item.primary_assignee.membership.user.display_name if item.primary_assignee else None,
                "reviewer_public_id": str(item.reviewer.public_id) if item.reviewer else None,
                "reviewer_name": item.reviewer.membership.user.display_name if item.reviewer else None,
                "is_overdue": bool(item.status_code in open_statuses and item.due_date and item.due_date < today),
                "version": item.version,
                "checklist": [
                    {
                        "public_id": str(row.public_id),
                        "sequence": row.sequence,
                        "title": row.title,
                        "is_required": row.is_required,
                        "is_completed": row.is_completed,
                        "version": row.version,
                    }
                    for row in checklists_by_item.get(item.id, [])
                ],
            }
            for item in work_items
        ],
        "assignments": [
            {
                "public_id": str(item.public_id),
                "work_item_public_id": str(item.work_item.public_id),
                "work_item_code": item.work_item.code,
                "employee_public_id": str(item.employee.public_id),
                "employee_number": item.employee.employee_number,
                "employee_name": item.employee.membership.user.display_name,
                "assignment_role_code": item.assignment_role_code,
                "allocation_percent": str(item.allocation_percent),
                "effective_from": item.effective_from.isoformat(),
                "effective_to": _iso(item.effective_to),
                "status_code": item.status_code,
                "version": item.version,
            }
            for item in assignments
        ],
        "dependencies": [
            {
                "public_id": str(item.public_id),
                "predecessor_public_id": str(item.predecessor.public_id),
                "predecessor_code": item.predecessor.code,
                "successor_public_id": str(item.successor.public_id),
                "successor_code": item.successor.code,
                "dependency_type_code": item.dependency_type_code,
                "lag_days": item.lag_days,
                "version": item.version,
            }
            for item in dependencies
        ],
        "progress_entries": [
            {
                "public_id": str(item.public_id),
                "project_public_id": str(item.project.public_id),
                "project_code": item.project.code,
                "site_name": item.site.name if item.site else None,
                "work_item_public_id": str(item.work_item.public_id) if item.work_item else None,
                "work_item_code": item.work_item.code if item.work_item else None,
                "progress_date": item.progress_date.isoformat(),
                "quantity_completed": str(item.quantity_completed),
                "unit_code": item.unit_code,
                "progress_percent": str(item.progress_percent) if item.progress_percent is not None else None,
                "hours_worked": str(item.hours_worked),
                "note": item.note,
                "blockers": item.blockers,
                "recorded_by_name": item.recorded_by.membership.user.display_name if item.recorded_by else None,
                "version": item.version,
            }
            for item in progress_entries
        ],
        "timesheets": [
            {
                "public_id": str(item.public_id),
                "employee_public_id": str(item.employee.public_id),
                "employee_number": item.employee.employee_number,
                "employee_name": item.employee.membership.user.display_name,
                "project_public_id": str(item.project.public_id),
                "project_code": item.project.code,
                "work_item_public_id": str(item.work_item.public_id) if item.work_item else None,
                "work_item_code": item.work_item.code if item.work_item else None,
                "work_date": item.work_date.isoformat(),
                "hours": str(item.hours),
                "description": item.description,
                "status_code": item.status_code,
                "review_note": item.review_note,
                "version": item.version,
            }
            for item in timesheets
        ],
        "approvals": [
            {
                "public_id": str(item.public_id),
                "work_item_public_id": str(item.work_item.public_id),
                "work_item_code": item.work_item.code,
                "work_item_title": item.work_item.title,
                "project_code": item.work_item.project.code,
                "approval_type_code": item.approval_type_code,
                "reviewer_public_id": str(item.reviewer.public_id),
                "reviewer_name": item.reviewer.membership.user.display_name,
                "status_code": item.status_code,
                "request_note": item.request_note,
                "decision_note": item.decision_note,
                "requested_at": item.requested_at.isoformat(),
                "decided_at": _iso(item.decided_at),
                "version": item.version,
            }
            for item in approvals
        ],
        "people": [
            {
                "public_id": str(item.public_id),
                "employee_number": item.employee_number,
                "display_name": item.membership.user.display_name,
                "email": item.membership.user.email,
                "job_title": item.job_title,
            }
            for item in people
        ],
        "locations": [
            {
                "public_id": str(item.public_id),
                "code": item.code,
                "name": item.name,
                "location_type_code": item.location_type_code,
            }
            for item in locations
        ],
    }
