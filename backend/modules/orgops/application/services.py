from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

from modules.accessops.application.services import create_invitation
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
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.tenant.models import Company, Location, Membership


def _code(value: str) -> str:
    return value.strip().upper().replace(" ", "_")


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


def _same_company(instance: Any, company: Company, label: str) -> None:
    if instance is not None and instance.company_id != company.id:
        raise ValidationError(f"{label} cannot cross companies")


@transaction.atomic
def create_department(
    *,
    company: Company,
    code: str,
    name: str,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    parent: Department | None = None,
    location: Location | None = None,
    cost_center_code: str = "",
) -> Department:
    normalized = _code(code)
    if not normalized:
        raise ValidationError({"code": "Department code is required"})
    _same_company(parent, company, "Department parent")
    _same_company(location, company, "Department location")
    department = Department(
        company=company,
        code=normalized,
        name=name.strip(),
        parent=parent,
        location=location,
        cost_center_code=cost_center_code.strip(),
    )
    department.full_clean()
    department.save()
    _audit_event(
        action="peopleorg.department.created",
        event_type="peopleorg.department_created",
        entity_type="department",
        entity_public_id=department.public_id,
        actor_public_id=actor_public_id,
        company=company,
        correlation_id=correlation_id,
        version=department.version,
        after={"code": department.code, "name": department.name},
    )
    return department


@transaction.atomic
def create_designation(
    *,
    company: Company,
    code: str,
    name: str,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    level_code: str = "",
    description: str = "",
) -> Designation:
    designation = Designation(
        company=company,
        code=_code(code),
        name=name.strip(),
        level_code=_code(level_code) if level_code else "",
        description=description.strip(),
    )
    designation.full_clean()
    designation.save()
    _audit_event(
        action="peopleorg.designation.created",
        event_type="peopleorg.designation_created",
        entity_type="designation",
        entity_public_id=designation.public_id,
        actor_public_id=actor_public_id,
        company=company,
        correlation_id=correlation_id,
        version=designation.version,
        after={"code": designation.code, "name": designation.name},
    )
    return designation


@transaction.atomic
def create_work_calendar(
    *,
    company: Company,
    code: str,
    name: str,
    timezone_name: str,
    working_days: list[int],
    standard_hours_per_day: Decimal,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> WorkCalendar:
    normalized_days = sorted(set(int(day) for day in working_days))
    if any(day < 1 or day > 7 for day in normalized_days):
        raise ValidationError({"working_days": "Working days must use ISO weekday values 1 through 7"})
    calendar = WorkCalendar(
        company=company,
        code=_code(code),
        name=name.strip(),
        timezone=timezone_name.strip(),
        working_days=normalized_days,
        standard_hours_per_day=standard_hours_per_day,
    )
    calendar.full_clean()
    calendar.save()
    _audit_event(
        action="peopleorg.calendar.created",
        event_type="peopleorg.calendar_created",
        entity_type="work_calendar",
        entity_public_id=calendar.public_id,
        actor_public_id=actor_public_id,
        company=company,
        correlation_id=correlation_id,
        version=calendar.version,
        after={
            "code": calendar.code,
            "name": calendar.name,
            "working_days": calendar.working_days,
        },
    )
    return calendar


@transaction.atomic
def update_employee_profile(
    *,
    company: Company,
    employee: Employee,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    job_title: str,
    department: Department | None,
    designation: Designation | None,
    work_calendar: WorkCalendar | None,
    employment_type_code: str,
    worker_category_code: str,
    mobile: str,
    status_code: str,
    probation_end: date | None,
    confirmation_date: date | None,
) -> EmployeeOrganizationProfile:
    _same_company(employee, company, "Employee")
    _same_company(department, company, "Department")
    _same_company(designation, company, "Designation")
    _same_company(work_calendar, company, "Work calendar")
    locked_employee = Employee.objects.select_for_update().get(pk=employee.pk)
    locked_employee.job_title = job_title.strip() or locked_employee.job_title
    locked_employee.full_clean()
    locked_employee.save(update_fields=["job_title", "updated_at"])
    profile, created = EmployeeOrganizationProfile.objects.select_for_update().get_or_create(
        company=company,
        employee=locked_employee,
        defaults={
            "department": department,
            "designation": designation,
            "work_calendar": work_calendar,
            "employment_type_code": _code(employment_type_code) or "FULL_TIME",
            "worker_category_code": _code(worker_category_code) if worker_category_code else "",
            "mobile": mobile.strip(),
            "status_code": _code(status_code) or "ACTIVE",
            "probation_end": probation_end,
            "confirmation_date": confirmation_date,
        },
    )
    before = {} if created else {
        "department_public_id": str(profile.department.public_id) if profile.department else None,
        "designation_public_id": str(profile.designation.public_id) if profile.designation else None,
        "status_code": profile.status_code,
    }
    if not created:
        profile.department = department
        profile.designation = designation
        profile.work_calendar = work_calendar
        profile.employment_type_code = _code(employment_type_code) or profile.employment_type_code
        profile.worker_category_code = _code(worker_category_code) if worker_category_code else ""
        profile.mobile = mobile.strip()
        profile.status_code = _code(status_code) or profile.status_code
        profile.probation_end = probation_end
        profile.confirmation_date = confirmation_date
        profile.version += 1
        profile.full_clean()
        profile.save()
    _audit_event(
        action="peopleorg.employee_profile.updated",
        event_type="peopleorg.employee_profile_updated",
        entity_type="employee_organization_profile",
        entity_public_id=profile.public_id,
        actor_public_id=actor_public_id,
        company=company,
        correlation_id=correlation_id,
        version=profile.version,
        before=before,
        after={
            "employee_public_id": str(employee.public_id),
            "department_public_id": str(department.public_id) if department else None,
            "designation_public_id": str(designation.public_id) if designation else None,
            "status_code": profile.status_code,
        },
    )
    return profile


def _current_manager(employee: Employee, as_of: date) -> Employee | None:
    line = (
        ReportingLine.objects.filter(
            company=employee.company,
            employee=employee,
            effective_from__lte=as_of,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=as_of))
        .select_related("manager")
        .order_by("-effective_from", "-created_at")
        .first()
    )
    return line.manager if line else None


def _ensure_no_reporting_cycle(employee: Employee, manager: Employee, as_of: date) -> None:
    current = manager
    visited: set[int] = set()
    while current is not None:
        if current.pk == employee.pk:
            raise ValidationError("Reporting line would create a management cycle")
        if current.pk in visited:
            raise ValidationError("Existing reporting hierarchy contains a cycle")
        visited.add(current.pk)
        current = _current_manager(current, as_of)


@transaction.atomic
def set_employee_manager(
    *,
    company: Company,
    employee: Employee,
    manager: Employee,
    effective_from: date,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> ReportingLine:
    _same_company(employee, company, "Employee")
    _same_company(manager, company, "Manager")
    if employee.pk == manager.pk:
        raise ValidationError("An employee cannot report to themselves")
    _ensure_no_reporting_cycle(employee, manager, effective_from)
    active_lines = ReportingLine.objects.select_for_update().filter(
        company=company,
        employee=employee,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=effective_from))
    active_lines.update(effective_to=effective_from)
    line = ReportingLine(
        company=company,
        employee=employee,
        manager=manager,
        effective_from=effective_from,
    )
    line.full_clean()
    line.save()
    _audit_event(
        action="peopleorg.reporting_line.changed",
        event_type="peopleorg.reporting_line_changed",
        entity_type="reporting_line",
        entity_public_id=line.public_id,
        actor_public_id=actor_public_id,
        company=company,
        correlation_id=correlation_id,
        version=int(timezone.now().timestamp() * 1_000_000),
        after={
            "employee_public_id": str(employee.public_id),
            "manager_public_id": str(manager.public_id),
            "effective_from": effective_from.isoformat(),
        },
    )
    return line


@transaction.atomic
def create_assignment(
    *,
    company: Company,
    employee: Employee,
    assignment_type_code: str,
    project_code: str,
    site_code: str,
    location: Location | None,
    work_package_code: str,
    allocation_percent: Decimal,
    effective_from: date,
    effective_to: date | None,
    is_primary: bool,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> OrganizationAssignment:
    _same_company(employee, company, "Employee")
    _same_company(location, company, "Location")
    if is_primary:
        OrganizationAssignment.objects.select_for_update().filter(
            company=company,
            employee=employee,
            is_primary=True,
        ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=effective_from)).update(
            effective_to=effective_from,
            version=models.F("version") + 1,
        )
    assignment = OrganizationAssignment(
        company=company,
        employee=employee,
        assignment_type_code=_code(assignment_type_code) or "PRIMARY",
        project_code=_code(project_code) if project_code else "",
        site_code=_code(site_code) if site_code else "",
        location=location,
        work_package_code=_code(work_package_code) if work_package_code else "",
        allocation_percent=allocation_percent,
        effective_from=effective_from,
        effective_to=effective_to,
        is_primary=is_primary,
    )
    assignment.full_clean()
    assignment.save()
    _audit_event(
        action="peopleorg.assignment.created",
        event_type="peopleorg.assignment_created",
        entity_type="organization_assignment",
        entity_public_id=assignment.public_id,
        actor_public_id=actor_public_id,
        company=company,
        correlation_id=correlation_id,
        version=assignment.version,
        after={
            "employee_public_id": str(employee.public_id),
            "project_code": assignment.project_code,
            "site_code": assignment.site_code,
            "allocation_percent": str(assignment.allocation_percent),
        },
    )
    return assignment


@transaction.atomic
def create_leave_type(
    *,
    company: Company,
    code: str,
    name: str,
    unit_code: str,
    requires_approval: bool,
    is_paid: bool,
    annual_entitlement: Decimal | None,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> LeaveType:
    leave_type = LeaveType(
        company=company,
        code=_code(code),
        name=name.strip(),
        unit_code=_code(unit_code) or "DAYS",
        requires_approval=requires_approval,
        is_paid=is_paid,
        annual_entitlement=annual_entitlement,
    )
    leave_type.full_clean()
    leave_type.save()
    _audit_event(
        action="peopleorg.leave_type.created",
        event_type="peopleorg.leave_type_created",
        entity_type="leave_type",
        entity_public_id=leave_type.public_id,
        actor_public_id=actor_public_id,
        company=company,
        correlation_id=correlation_id,
        version=leave_type.version,
        after={"code": leave_type.code, "name": leave_type.name},
    )
    return leave_type


@transaction.atomic
def submit_leave_request(
    *,
    company: Company,
    employee: Employee,
    leave_type: LeaveType,
    start_date: date,
    end_date: date,
    quantity: Decimal,
    reason: str,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> LeaveRequest:
    _same_company(employee, company, "Employee")
    _same_company(leave_type, company, "Leave type")
    status = "SUBMITTED" if leave_type.requires_approval else "APPROVED"
    request = LeaveRequest(
        company=company,
        employee=employee,
        leave_type=leave_type,
        start_date=start_date,
        end_date=end_date,
        quantity=quantity,
        reason=reason.strip(),
        status_code=status,
        requested_by_public_id=actor_public_id,
        reviewed_by_public_id=actor_public_id if status == "APPROVED" else None,
        reviewed_at=timezone.now() if status == "APPROVED" else None,
    )
    request.full_clean()
    request.save()
    _audit_event(
        action="peopleorg.leave.submitted",
        event_type="peopleorg.leave_submitted",
        entity_type="leave_request",
        entity_public_id=request.public_id,
        actor_public_id=actor_public_id,
        company=company,
        correlation_id=correlation_id,
        version=request.version,
        after={
            "employee_public_id": str(employee.public_id),
            "leave_type_code": leave_type.code,
            "status_code": request.status_code,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
    )
    return request


@transaction.atomic
def review_leave_request(
    *,
    company: Company,
    leave_request: LeaveRequest,
    decision_code: str,
    review_note: str,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    expected_version: int,
) -> LeaveRequest:
    locked = LeaveRequest.objects.select_for_update().get(pk=leave_request.pk, company=company)
    if locked.version != expected_version:
        raise ValidationError("Leave request changed. Refresh before reviewing it")
    if locked.status_code != "SUBMITTED":
        raise ValidationError("Only submitted leave requests can be reviewed")
    decision = _code(decision_code)
    if decision not in {"APPROVED", "REJECTED"}:
        raise ValidationError("Decision must be APPROVED or REJECTED")
    before = {"status_code": locked.status_code}
    locked.status_code = decision
    locked.review_note = review_note.strip()
    locked.reviewed_by_public_id = actor_public_id
    locked.reviewed_at = timezone.now()
    locked.version += 1
    locked.save()
    _audit_event(
        action="peopleorg.leave.reviewed",
        event_type="peopleorg.leave_reviewed",
        entity_type="leave_request",
        entity_public_id=locked.public_id,
        actor_public_id=actor_public_id,
        company=company,
        correlation_id=correlation_id,
        version=locked.version,
        before=before,
        after={"status_code": locked.status_code, "review_note": locked.review_note},
    )
    return locked


@transaction.atomic
def upsert_attendance(
    *,
    company: Company,
    employee: Employee,
    work_date: date,
    status_code: str,
    hours_worked: Decimal,
    source_code: str,
    notes: str,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> AttendanceEntry:
    _same_company(employee, company, "Employee")
    entry, created = AttendanceEntry.objects.select_for_update().get_or_create(
        company=company,
        employee=employee,
        work_date=work_date,
        defaults={
            "status_code": _code(status_code),
            "hours_worked": hours_worked,
            "source_code": _code(source_code),
            "notes": notes.strip(),
            "recorded_by_public_id": actor_public_id,
        },
    )
    before = {} if created else {
        "status_code": entry.status_code,
        "hours_worked": str(entry.hours_worked),
    }
    if not created:
        entry.status_code = _code(status_code)
        entry.hours_worked = hours_worked
        entry.source_code = _code(source_code)
        entry.notes = notes.strip()
        entry.recorded_by_public_id = actor_public_id
        entry.version += 1
    entry.full_clean()
    entry.save()
    _audit_event(
        action="peopleorg.attendance.recorded",
        event_type="peopleorg.attendance_recorded",
        entity_type="attendance_entry",
        entity_public_id=entry.public_id,
        actor_public_id=actor_public_id,
        company=company,
        correlation_id=correlation_id,
        version=entry.version,
        before=before,
        after={
            "employee_public_id": str(employee.public_id),
            "work_date": work_date.isoformat(),
            "status_code": entry.status_code,
            "hours_worked": str(entry.hours_worked),
        },
    )
    return entry


@transaction.atomic
def bulk_import_people(
    *,
    company: Company,
    source_name: str,
    rows: list[dict[str, Any]],
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> tuple[PeopleImportJob, list[dict[str, Any]]]:
    job = PeopleImportJob.objects.create(
        company=company,
        source_name=source_name.strip() or "people-import",
        total_rows=len(rows),
        created_by_public_id=actor_public_id,
    )
    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    success_count = 0
    for index, row in enumerate(rows, start=1):
        try:
            email = str(row.get("email", "")).strip().lower()
            employee_number = str(row.get("employee_number", "")).strip()
            if not email or not employee_number:
                raise ValidationError("email and employee_number are required")
            membership = Membership.objects.filter(
                company=company,
                user__email__iexact=email,
            ).select_related("user").first()
            if membership and hasattr(membership, "employee"):
                employee = membership.employee
                department = Department.objects.filter(
                    company=company,
                    code__iexact=str(row.get("department_code", "")).strip(),
                ).first() if row.get("department_code") else None
                designation = Designation.objects.filter(
                    company=company,
                    code__iexact=str(row.get("designation_code", "")).strip(),
                ).first() if row.get("designation_code") else None
                profile = update_employee_profile(
                    company=company,
                    employee=employee,
                    actor_public_id=actor_public_id,
                    correlation_id=correlation_id,
                    job_title=str(row.get("job_title", employee.job_title)),
                    department=department,
                    designation=designation,
                    work_calendar=None,
                    employment_type_code=str(row.get("employment_type_code", "FULL_TIME")),
                    worker_category_code=str(row.get("worker_category_code", "")),
                    mobile=str(row.get("mobile", "")),
                    status_code=str(row.get("status_code", "ACTIVE")),
                    probation_end=None,
                    confirmation_date=None,
                )
                results.append({
                    "row": index,
                    "status": "UPDATED",
                    "employee_public_id": str(employee.public_id),
                    "profile_public_id": str(profile.public_id),
                })
            else:
                role_ids = [uuid.UUID(str(value)) for value in row.get("role_public_ids", [])]
                if not role_ids:
                    raise ValidationError("role_public_ids are required for a new person")
                invitation, raw_token = create_invitation(
                    company=company,
                    email=email,
                    display_name=str(row.get("display_name", email)).strip(),
                    invitation_type_code="EMPLOYEE",
                    role_public_ids=role_ids,
                    employee_number=employee_number,
                    job_title=str(row.get("job_title", "Team member")).strip(),
                    invited_by_public_id=actor_public_id,
                    correlation_id=correlation_id,
                )
                results.append({
                    "row": index,
                    "status": "INVITED",
                    "invitation_public_id": str(invitation.public_id),
                    "acceptance_token": raw_token,
                })
            success_count += 1
        except Exception as error:  # row isolation is intentional for import reporting
            message = "; ".join(getattr(error, "messages", [])) or str(error)
            errors.append({"row": index, "message": message[:500]})
            results.append({"row": index, "status": "FAILED", "message": message[:500]})
    job.success_rows = success_count
    job.failed_rows = len(errors)
    job.error_rows = errors
    job.status_code = "COMPLETED_WITH_ERRORS" if errors else "COMPLETED"
    job.completed_at = timezone.now()
    job.version += 1
    job.save()
    _audit_event(
        action="peopleorg.import.completed",
        event_type="peopleorg.import_completed",
        entity_type="people_import_job",
        entity_public_id=job.public_id,
        actor_public_id=actor_public_id,
        company=company,
        correlation_id=correlation_id,
        version=job.version,
        after={
            "total_rows": job.total_rows,
            "success_rows": job.success_rows,
            "failed_rows": job.failed_rows,
            "status_code": job.status_code,
        },
    )
    return job, results
