from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

from modules.employee.models import Employee, ReportingLine
from modules.orgops.models import (
    AttendanceEntry,
    Department,
    Designation,
    EmployeeOrganizationProfile,
    LeaveRequest,
    LeaveType,
    OrganizationAssignment,
    PeopleImportJob,
    WorkCalendar,
)
from modules.tenant.models import Company, Location


def _iso(value: object | None) -> str | None:
    return value.isoformat() if value is not None and hasattr(value, "isoformat") else None


def organization_overview(company: Company) -> dict[str, object]:
    today = timezone.localdate()
    employees = list(
        Employee.objects.filter(company=company)
        .select_related("membership", "membership__user")
        .order_by("employee_number")[:2000]
    )
    employee_ids = [employee.id for employee in employees]
    profiles = {
        profile.employee_id: profile
        for profile in EmployeeOrganizationProfile.objects.filter(
            company=company, employee_id__in=employee_ids
        ).select_related("department", "designation", "work_calendar")
    }
    current_lines = (
        ReportingLine.objects.filter(
            company=company,
            employee_id__in=employee_ids,
            effective_from__lte=today,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today))
        .select_related("manager", "manager__membership", "manager__membership__user")
        .order_by("employee_id", "-effective_from", "-created_at")
    )
    managers: dict[int, Employee] = {}
    for line in current_lines:
        managers.setdefault(line.employee_id, line.manager)

    active_assignments = list(
        OrganizationAssignment.objects.filter(
            company=company,
            effective_from__lte=today,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today))
        .select_related("employee", "employee__membership", "employee__membership__user", "location")
        .order_by("-is_primary", "employee__employee_number", "-effective_from")[:3000]
    )
    assigned_employee_ids = {assignment.employee_id for assignment in active_assignments}
    attendance_today = AttendanceEntry.objects.filter(company=company, work_date=today)
    pending_leave = LeaveRequest.objects.filter(company=company, status_code="SUBMITTED")

    return {
        "generated_at": timezone.now().isoformat(),
        "company": {
            "public_id": str(company.public_id),
            "code": company.code,
            "display_name": company.display_name,
            "locale": company.locale,
            "timezone": company.timezone,
            "currency": company.currency,
        },
        "summary": {
            "employee_count": len(employees),
            "active_profile_count": sum(
                1
                for employee in employees
                if profiles.get(employee.id) is not None
                and profiles[employee.id].status_code == "ACTIVE"
            ),
            "department_count": Department.objects.filter(company=company, is_active=True).count(),
            "unassigned_employee_count": sum(
                1 for employee in employees if employee.id not in assigned_employee_ids
            ),
            "pending_leave_count": pending_leave.count(),
            "attendance_recorded_today": attendance_today.count(),
        },
        "departments": [
            {
                "public_id": str(item.public_id),
                "code": item.code,
                "name": item.name,
                "parent_public_id": str(item.parent.public_id) if item.parent else None,
                "parent_name": item.parent.name if item.parent else None,
                "location_public_id": str(item.location.public_id) if item.location else None,
                "location_name": item.location.name if item.location else None,
                "cost_center_code": item.cost_center_code,
                "is_active": item.is_active,
                "version": item.version,
            }
            for item in Department.objects.filter(company=company)
            .select_related("parent", "location")
            .order_by("name")[:1000]
        ],
        "designations": [
            {
                "public_id": str(item.public_id),
                "code": item.code,
                "name": item.name,
                "level_code": item.level_code,
                "description": item.description,
                "is_active": item.is_active,
                "version": item.version,
            }
            for item in Designation.objects.filter(company=company).order_by("name")[:1000]
        ],
        "work_calendars": [
            {
                "public_id": str(item.public_id),
                "code": item.code,
                "name": item.name,
                "timezone": item.timezone,
                "working_days": item.working_days,
                "standard_hours_per_day": str(item.standard_hours_per_day),
                "is_active": item.is_active,
                "version": item.version,
            }
            for item in WorkCalendar.objects.filter(company=company).order_by("name")[:500]
        ],
        "locations": [
            {
                "public_id": str(item.public_id),
                "code": item.code,
                "name": item.name,
                "location_type_code": item.location_type_code,
            }
            for item in Location.objects.filter(company=company).order_by("name")[:1000]
        ],
        "people": [
            {
                "employee_public_id": str(employee.public_id),
                "membership_public_id": str(employee.membership.public_id),
                "user_public_id": str(employee.membership.user.public_id),
                "employee_number": employee.employee_number,
                "display_name": employee.membership.user.display_name,
                "email": employee.membership.user.email,
                "job_title": employee.job_title,
                "employment_start": employee.employment_start.isoformat(),
                "employment_end": _iso(employee.employment_end),
                "membership_suspended_at": _iso(employee.membership.suspended_at),
                "membership_terminated_at": _iso(employee.membership.terminated_at),
                "profile": (
                    {
                        "public_id": str(profiles[employee.id].public_id),
                        "department_public_id": (
                            str(profiles[employee.id].department.public_id)
                            if profiles[employee.id].department
                            else None
                        ),
                        "department_name": (
                            profiles[employee.id].department.name
                            if profiles[employee.id].department
                            else None
                        ),
                        "designation_public_id": (
                            str(profiles[employee.id].designation.public_id)
                            if profiles[employee.id].designation
                            else None
                        ),
                        "designation_name": (
                            profiles[employee.id].designation.name
                            if profiles[employee.id].designation
                            else None
                        ),
                        "work_calendar_public_id": (
                            str(profiles[employee.id].work_calendar.public_id)
                            if profiles[employee.id].work_calendar
                            else None
                        ),
                        "employment_type_code": profiles[employee.id].employment_type_code,
                        "worker_category_code": profiles[employee.id].worker_category_code,
                        "mobile": profiles[employee.id].mobile,
                        "status_code": profiles[employee.id].status_code,
                        "probation_end": _iso(profiles[employee.id].probation_end),
                        "confirmation_date": _iso(profiles[employee.id].confirmation_date),
                        "version": profiles[employee.id].version,
                    }
                    if employee.id in profiles
                    else None
                ),
                "manager": (
                    {
                        "employee_public_id": str(managers[employee.id].public_id),
                        "employee_number": managers[employee.id].employee_number,
                        "display_name": managers[employee.id].membership.user.display_name,
                    }
                    if employee.id in managers
                    else None
                ),
            }
            for employee in employees
        ],
        "assignments": [
            {
                "public_id": str(item.public_id),
                "employee_public_id": str(item.employee.public_id),
                "employee_number": item.employee.employee_number,
                "employee_name": item.employee.membership.user.display_name,
                "assignment_type_code": item.assignment_type_code,
                "project_code": item.project_code,
                "site_code": item.site_code,
                "location_public_id": str(item.location.public_id) if item.location else None,
                "location_name": item.location.name if item.location else None,
                "work_package_code": item.work_package_code,
                "allocation_percent": str(item.allocation_percent),
                "effective_from": item.effective_from.isoformat(),
                "effective_to": _iso(item.effective_to),
                "is_primary": item.is_primary,
                "version": item.version,
            }
            for item in active_assignments
        ],
        "leave_types": [
            {
                "public_id": str(item.public_id),
                "code": item.code,
                "name": item.name,
                "unit_code": item.unit_code,
                "requires_approval": item.requires_approval,
                "is_paid": item.is_paid,
                "annual_entitlement": (
                    str(item.annual_entitlement) if item.annual_entitlement is not None else None
                ),
                "is_active": item.is_active,
                "version": item.version,
            }
            for item in LeaveType.objects.filter(company=company).order_by("name")[:500]
        ],
        "leave_requests": [
            {
                "public_id": str(item.public_id),
                "employee_public_id": str(item.employee.public_id),
                "employee_number": item.employee.employee_number,
                "employee_name": item.employee.membership.user.display_name,
                "leave_type_public_id": str(item.leave_type.public_id),
                "leave_type_name": item.leave_type.name,
                "start_date": item.start_date.isoformat(),
                "end_date": item.end_date.isoformat(),
                "quantity": str(item.quantity),
                "reason": item.reason,
                "status_code": item.status_code,
                "review_note": item.review_note,
                "version": item.version,
            }
            for item in LeaveRequest.objects.filter(company=company)
            .select_related("employee", "employee__membership", "employee__membership__user", "leave_type")
            .order_by("-created_at")[:1000]
        ],
        "attendance_entries": [
            {
                "public_id": str(item.public_id),
                "employee_public_id": str(item.employee.public_id),
                "employee_number": item.employee.employee_number,
                "employee_name": item.employee.membership.user.display_name,
                "work_date": item.work_date.isoformat(),
                "status_code": item.status_code,
                "hours_worked": str(item.hours_worked),
                "source_code": item.source_code,
                "notes": item.notes,
                "version": item.version,
            }
            for item in AttendanceEntry.objects.filter(company=company)
            .select_related("employee", "employee__membership", "employee__membership__user")
            .order_by("-work_date", "employee__employee_number")[:1000]
        ],
        "import_jobs": [
            {
                "public_id": str(item.public_id),
                "source_name": item.source_name,
                "status_code": item.status_code,
                "total_rows": item.total_rows,
                "success_rows": item.success_rows,
                "failed_rows": item.failed_rows,
                "error_rows": item.error_rows,
                "completed_at": _iso(item.completed_at),
                "created_at": item.created_at.isoformat(),
            }
            for item in PeopleImportJob.objects.filter(company=company).order_by("-created_at")[:100]
        ],
    }
