from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from modules.employee.models import Employee
from modules.peopleops.models import (
    Department,
    EmploymentContract,
    LeaveBalance,
    LeavePolicy,
    LeaveRequest,
    PayrollEntry,
    PayrollRun,
    Timesheet,
    TimesheetLine,
    payroll_entry_digest,
)
from modules.platform.actors import RequestActor
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.projects.models import Project
from modules.tenant.models import Company, Membership


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
            reason_code=reason_code[:100],
            before=before or {},
            after=after or {},
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
            correlation_id=actor.request_id,
            company_public_id=company.public_id,
            payload=payload,
        )
    )


def peopleops_summary(company: Company) -> dict[str, Any]:
    today = timezone.localdate()
    employees = Employee.objects.filter(company=company)
    active_contracts = EmploymentContract.objects.filter(
        company=company,
        status=EmploymentContract.Status.ACTIVE,
        start_on__lte=today,
    ).filter(models_end_filter(today))
    leave_requests = LeaveRequest.objects.filter(company=company)
    timesheets = Timesheet.objects.filter(company=company)
    payroll_runs = PayrollRun.objects.filter(company=company)
    latest_payroll = payroll_runs.first()
    pending_leave = leave_requests.filter(status=LeaveRequest.Status.SUBMITTED).count()
    pending_timesheets = timesheets.filter(status=Timesheet.Status.SUBMITTED).count()
    current_year = today.year
    available_leave = sum(
        (item.available_days for item in LeaveBalance.objects.filter(company=company, period_year=current_year)),
        Decimal("0"),
    )
    return {
        "employees": employees.count(),
        "active_contracts": active_contracts.count(),
        "departments": Department.objects.filter(company=company, status=Department.Status.ACTIVE).count(),
        "pending_leave_requests": pending_leave,
        "pending_timesheets": pending_timesheets,
        "available_leave_days": available_leave,
        "payroll_runs": payroll_runs.count(),
        "latest_payroll_status": latest_payroll.status if latest_payroll else "none",
        "latest_payroll_net": latest_payroll.net_total if latest_payroll else Decimal("0"),
        "currency": company.currency,
    }


def models_end_filter(today: date):
    from django.db.models import Q

    return Q(end_on__isnull=True) | Q(end_on__gte=today)


def peopleops_portfolio(company: Company) -> dict[str, Any]:
    return {
        "summary": peopleops_summary(company),
        "departments": Department.objects.filter(company=company).select_related(
            "parent", "manager_employee", "manager_employee__membership__user"
        ),
        "employees": Employee.objects.filter(company=company).select_related("membership__user"),
        "contracts": EmploymentContract.objects.filter(company=company).select_related(
            "employee__membership__user", "department"
        )[:100],
        "leave_policies": LeavePolicy.objects.filter(company=company, is_active=True),
        "leave_balances": LeaveBalance.objects.filter(company=company).select_related(
            "employee__membership__user", "policy"
        )[:100],
        "leave_requests": LeaveRequest.objects.filter(company=company).select_related(
            "employee__membership__user", "policy", "approver_membership__user"
        )[:100],
        "timesheets": Timesheet.objects.filter(company=company).select_related(
            "employee__membership__user", "approver_membership__user"
        ).prefetch_related("lines")[:100],
        "payroll_runs": PayrollRun.objects.filter(company=company).prefetch_related(
            "entries__employee__membership__user"
        )[:50],
    }


def _employee(company: Company, public_id: uuid.UUID) -> Employee:
    item = Employee.objects.select_related("membership__user").filter(
        company=company,
        public_id=public_id,
    ).first()
    if item is None:
        raise ValidationError("Employee was not found")
    return item


def _policy(company: Company, public_id: uuid.UUID) -> LeavePolicy:
    item = LeavePolicy.objects.filter(company=company, public_id=public_id, is_active=True).first()
    if item is None:
        raise ValidationError("Active leave policy was not found")
    return item


@transaction.atomic
def create_leave_request(
    *,
    company: Company,
    actor: RequestActor,
    employee_public_id: uuid.UUID,
    policy_public_id: uuid.UUID,
    start_on: date,
    end_on: date,
    requested_days: Decimal,
    reason: str = "",
) -> LeaveRequest:
    employee = _employee(company, employee_public_id)
    if employee.membership.user.public_id != actor.user_public_id:
        raise ValidationError("Employees may create leave requests only for themselves")
    policy = _policy(company, policy_public_id)
    overlapping = LeaveRequest.objects.filter(
        company=company,
        employee=employee,
        status__in=[LeaveRequest.Status.SUBMITTED, LeaveRequest.Status.APPROVED],
        start_on__lte=end_on,
        end_on__gte=start_on,
    ).exists()
    if overlapping:
        raise ValidationError("Leave request overlaps an existing submitted or approved request")
    item = LeaveRequest(
        company=company,
        employee=employee,
        policy=policy,
        start_on=start_on,
        end_on=end_on,
        requested_days=requested_days,
        reason=reason.strip(),
        status=LeaveRequest.Status.SUBMITTED if policy.requires_approval else LeaveRequest.Status.APPROVED,
        requester_user_public_id=actor.user_public_id,
        decided_at=None if policy.requires_approval else timezone.now(),
    )
    item.full_clean()
    item.save()
    if not policy.requires_approval:
        _consume_leave_balance(company=company, request=item)
    _audit(
        actor=actor,
        company=company,
        action="peopleops.leave.created",
        entity_type="leave_request",
        entity_public_id=item.public_id,
        after={"status": item.status, "requested_days": str(item.requested_days)},
    )
    _event(
        actor=actor,
        company=company,
        event_type="peopleops.leave.created",
        aggregate_type="leave_request",
        aggregate_public_id=item.public_id,
        aggregate_version=item.version,
        payload={"status": item.status, "leave_type": item.policy.leave_type},
    )
    return item


def _consume_leave_balance(*, company: Company, request: LeaveRequest) -> LeaveBalance:
    balance = LeaveBalance.objects.select_for_update().filter(
        company=company,
        employee=request.employee,
        policy=request.policy,
        period_year=request.start_on.year,
    ).first()
    if balance is None:
        raise ValidationError("Leave balance is not configured for the requested period")
    if balance.available_days < request.requested_days:
        raise ValidationError("Insufficient leave balance")
    balance.taken_days += request.requested_days
    balance.version += 1
    balance.full_clean()
    balance.save()
    return balance


_ALLOWED_LEAVE_TRANSITIONS = {
    LeaveRequest.Status.DRAFT: {LeaveRequest.Status.SUBMITTED, LeaveRequest.Status.CANCELLED},
    LeaveRequest.Status.SUBMITTED: {LeaveRequest.Status.APPROVED, LeaveRequest.Status.REJECTED, LeaveRequest.Status.CANCELLED},
    LeaveRequest.Status.APPROVED: {LeaveRequest.Status.CANCELLED},
    LeaveRequest.Status.REJECTED: set(),
    LeaveRequest.Status.CANCELLED: set(),
}


@transaction.atomic
def transition_leave_request(
    *,
    company: Company,
    actor: RequestActor,
    approver_membership: Membership,
    request_public_id: uuid.UUID,
    target_status: str,
    expected_version: int,
    decision_reason: str = "",
) -> LeaveRequest:
    item = LeaveRequest.objects.select_for_update().select_related("employee", "policy").filter(
        company=company,
        public_id=request_public_id,
    ).first()
    if item is None:
        raise ValidationError("Leave request was not found")
    if item.version != expected_version:
        raise ValidationError("Leave request changed; refresh before retrying")
    if target_status not in _ALLOWED_LEAVE_TRANSITIONS[item.status]:
        raise ValidationError(f"Transition from {item.status} to {target_status} is not allowed")
    if target_status in {LeaveRequest.Status.APPROVED, LeaveRequest.Status.REJECTED}:
        if item.requester_user_public_id == actor.user_public_id:
            raise ValidationError("Leave requester cannot approve or reject their own request")
        item.approver_membership = approver_membership
        item.decided_at = timezone.now()
        item.decision_reason = decision_reason.strip()
    if target_status == LeaveRequest.Status.APPROVED:
        _consume_leave_balance(company=company, request=item)
    if target_status == LeaveRequest.Status.CANCELLED and item.status == LeaveRequest.Status.APPROVED:
        balance = LeaveBalance.objects.select_for_update().get(
            company=company,
            employee=item.employee,
            policy=item.policy,
            period_year=item.start_on.year,
        )
        balance.taken_days -= item.requested_days
        balance.version += 1
        balance.full_clean()
        balance.save()
    before = {"status": item.status, "version": item.version}
    item.status = target_status
    item.version += 1
    item.full_clean()
    item.save()
    _audit(
        actor=actor,
        company=company,
        action="peopleops.leave.transitioned",
        entity_type="leave_request",
        entity_public_id=item.public_id,
        before=before,
        after={"status": item.status, "version": item.version},
        reason_code=decision_reason,
    )
    _event(
        actor=actor,
        company=company,
        event_type="peopleops.leave.transitioned",
        aggregate_type="leave_request",
        aggregate_public_id=item.public_id,
        aggregate_version=item.version,
        payload={"status": item.status},
    )
    return item


@transaction.atomic
def create_timesheet(
    *,
    company: Company,
    actor: RequestActor,
    employee_public_id: uuid.UUID,
    week_start: date,
    lines: list[dict[str, Any]],
) -> Timesheet:
    employee = _employee(company, employee_public_id)
    if employee.membership.user.public_id != actor.user_public_id:
        raise ValidationError("Employees may create timesheets only for themselves")
    if Timesheet.objects.filter(company=company, employee=employee, week_start=week_start).exists():
        raise ValidationError("A timesheet already exists for this employee and week")
    item = Timesheet(company=company, employee=employee, week_start=week_start, status=Timesheet.Status.SUBMITTED, submitted_at=timezone.now())
    item.full_clean()
    item.save()
    total = Decimal("0")
    for row in lines:
        project = None
        project_public_id = row.get("project_public_id")
        if project_public_id:
            project = Project.objects.filter(company=company, public_id=project_public_id).first()
            if project is None:
                raise ValidationError("Timesheet project was not found")
        line = TimesheetLine(
            company=company,
            timesheet=item,
            work_date=row["work_date"],
            project=project,
            hours=row["hours"],
            description=str(row.get("description", "")).strip(),
        )
        line.full_clean()
        line.save()
        total += line.hours
    item.total_hours = total
    item.full_clean()
    item.save(update_fields=["total_hours", "updated_at"])
    _audit(
        actor=actor,
        company=company,
        action="peopleops.timesheet.created",
        entity_type="timesheet",
        entity_public_id=item.public_id,
        after={"week_start": str(item.week_start), "total_hours": str(item.total_hours)},
    )
    _event(
        actor=actor,
        company=company,
        event_type="peopleops.timesheet.created",
        aggregate_type="timesheet",
        aggregate_public_id=item.public_id,
        aggregate_version=item.version,
        payload={"week_start": str(item.week_start), "total_hours": str(item.total_hours)},
    )
    return item


_ALLOWED_TIMESHEET_TRANSITIONS = {
    Timesheet.Status.DRAFT: {Timesheet.Status.SUBMITTED},
    Timesheet.Status.SUBMITTED: {Timesheet.Status.APPROVED, Timesheet.Status.REJECTED},
    Timesheet.Status.REJECTED: {Timesheet.Status.SUBMITTED},
    Timesheet.Status.APPROVED: set(),
}


@transaction.atomic
def transition_timesheet(
    *,
    company: Company,
    actor: RequestActor,
    approver_membership: Membership,
    timesheet_public_id: uuid.UUID,
    target_status: str,
    expected_version: int,
    decision_reason: str = "",
) -> Timesheet:
    item = Timesheet.objects.select_for_update().select_related("employee__membership__user").filter(
        company=company,
        public_id=timesheet_public_id,
    ).first()
    if item is None:
        raise ValidationError("Timesheet was not found")
    if item.version != expected_version:
        raise ValidationError("Timesheet changed; refresh before retrying")
    if target_status not in _ALLOWED_TIMESHEET_TRANSITIONS[item.status]:
        raise ValidationError(f"Transition from {item.status} to {target_status} is not allowed")
    if target_status in {Timesheet.Status.APPROVED, Timesheet.Status.REJECTED}:
        if item.employee.membership.user.public_id == actor.user_public_id:
            raise ValidationError("Timesheet submitter cannot approve their own timesheet")
        item.approver_membership = approver_membership
        item.decided_at = timezone.now()
        item.decision_reason = decision_reason.strip()
    if target_status == Timesheet.Status.SUBMITTED:
        item.submitted_at = timezone.now()
        item.decided_at = None
        item.approver_membership = None
    before = {"status": item.status, "version": item.version}
    item.status = target_status
    item.version += 1
    item.full_clean()
    item.save()
    _audit(
        actor=actor,
        company=company,
        action="peopleops.timesheet.transitioned",
        entity_type="timesheet",
        entity_public_id=item.public_id,
        before=before,
        after={"status": item.status, "version": item.version},
        reason_code=decision_reason,
    )
    _event(
        actor=actor,
        company=company,
        event_type="peopleops.timesheet.transitioned",
        aggregate_type="timesheet",
        aggregate_public_id=item.public_id,
        aggregate_version=item.version,
        payload={"status": item.status},
    )
    return item


def _period_gross(contract: EmploymentContract) -> Decimal:
    divisor = {
        EmploymentContract.PayFrequency.MONTHLY: Decimal("12"),
        EmploymentContract.PayFrequency.BIWEEKLY: Decimal("26"),
        EmploymentContract.PayFrequency.WEEKLY: Decimal("52"),
    }[contract.pay_frequency]
    return (contract.annual_compensation / divisor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@transaction.atomic
def create_payroll_run(
    *,
    company: Company,
    actor: RequestActor,
    code: str,
    period_start: date,
    period_end: date,
    currency: str,
) -> PayrollRun:
    normalized_currency = currency.strip().upper()
    item = PayrollRun(
        company=company,
        code=code.strip().upper(),
        period_start=period_start,
        period_end=period_end,
        currency=normalized_currency,
        created_by_user_public_id=actor.user_public_id,
    )
    item.full_clean()
    item.save()
    contracts = EmploymentContract.objects.filter(
        company=company,
        status=EmploymentContract.Status.ACTIVE,
        currency=normalized_currency,
        start_on__lte=period_end,
    ).filter(models_end_filter(period_start)).select_related("employee")
    gross_total = Decimal("0")
    for contract in contracts:
        gross = _period_gross(contract)
        deductions = Decimal("0")
        entry = PayrollEntry(
            company=company,
            payroll_run=item,
            employee=contract.employee,
            gross_amount=gross,
            deduction_amount=deductions,
            net_amount=gross - deductions,
            components={"base": str(gross), "statutory_calculation": "not_configured"},
            evidence_sha256=payroll_entry_digest(
                run_code=item.code,
                employee_number=contract.employee.employee_number,
                gross=gross,
                deductions=deductions,
            ),
        )
        entry.full_clean()
        entry.save()
        gross_total += gross
    item.gross_total = gross_total
    item.net_total = gross_total
    item.full_clean()
    item.save(update_fields=["gross_total", "net_total", "updated_at"])
    _audit(
        actor=actor,
        company=company,
        action="peopleops.payroll.created",
        entity_type="payroll_run",
        entity_public_id=item.public_id,
        after={"code": item.code, "entries": item.entries.count(), "gross_total": str(item.gross_total)},
    )
    _event(
        actor=actor,
        company=company,
        event_type="peopleops.payroll.created",
        aggregate_type="payroll_run",
        aggregate_public_id=item.public_id,
        aggregate_version=item.version,
        payload={"code": item.code, "currency": item.currency},
    )
    return item


_ALLOWED_PAYROLL_TRANSITIONS = {
    PayrollRun.Status.DRAFT: {PayrollRun.Status.LOCKED, PayrollRun.Status.CANCELLED},
    PayrollRun.Status.LOCKED: {PayrollRun.Status.APPROVED, PayrollRun.Status.CANCELLED},
    PayrollRun.Status.APPROVED: {PayrollRun.Status.POSTED, PayrollRun.Status.CANCELLED},
    PayrollRun.Status.POSTED: set(),
    PayrollRun.Status.CANCELLED: set(),
}


@transaction.atomic
def transition_payroll_run(
    *,
    company: Company,
    actor: RequestActor,
    payroll_public_id: uuid.UUID,
    target_status: str,
    expected_version: int,
) -> PayrollRun:
    item = PayrollRun.objects.select_for_update().filter(company=company, public_id=payroll_public_id).first()
    if item is None:
        raise ValidationError("Payroll run was not found")
    if item.version != expected_version:
        raise ValidationError("Payroll run changed; refresh before retrying")
    if target_status not in _ALLOWED_PAYROLL_TRANSITIONS[item.status]:
        raise ValidationError(f"Transition from {item.status} to {target_status} is not allowed")
    if target_status == PayrollRun.Status.APPROVED:
        if item.created_by_user_public_id == actor.user_public_id:
            raise ValidationError("Payroll maker cannot approve the same payroll run")
        item.approved_by_user_public_id = actor.user_public_id
        item.approved_at = timezone.now()
    if target_status == PayrollRun.Status.POSTED:
        item.posted_at = timezone.now()
        evidence = {
            "code": item.code,
            "gross": str(item.gross_total),
            "deductions": str(item.deduction_total),
            "net": str(item.net_total),
            "entries": item.entries.count(),
        }
        item.evidence_sha256 = hashlib.sha256(
            json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
    before = {"status": item.status, "version": item.version}
    item.status = target_status
    item.version += 1
    item.full_clean()
    item.save()
    _audit(
        actor=actor,
        company=company,
        action="peopleops.payroll.transitioned",
        entity_type="payroll_run",
        entity_public_id=item.public_id,
        before=before,
        after={"status": item.status, "version": item.version},
    )
    _event(
        actor=actor,
        company=company,
        event_type="peopleops.payroll.transitioned",
        aggregate_type="payroll_run",
        aggregate_public_id=item.public_id,
        aggregate_version=item.version,
        payload={"code": item.code, "status": item.status},
    )
    return item
