from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.peopleops.api.serializers import (
    LeaveRequestCreateSerializer,
    LeaveRequestTransitionSerializer,
    PayrollRunCreateSerializer,
    PayrollRunTransitionSerializer,
    TimesheetCreateSerializer,
    TimesheetTransitionSerializer,
)
from modules.peopleops.application.services import (
    create_leave_request,
    create_payroll_run,
    create_timesheet,
    peopleops_portfolio,
    peopleops_summary,
    transition_leave_request,
    transition_payroll_run,
    transition_timesheet,
)
from modules.peopleops.models import LeaveRequest, PayrollRun, Timesheet
from modules.platform.actors import request_actor
from modules.tenant.api.base import TenantScopedAPIView


def _validation(exc: DjangoValidationError) -> ValidationError:
    if hasattr(exc, "message_dict"):
        return ValidationError(exc.message_dict)
    return ValidationError(exc.messages)


def _employee(item) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "user_public_id": str(item.membership.user.public_id),
        "employee_number": item.employee_number,
        "display_name": item.membership.user.display_name,
        "email": item.membership.user.email,
        "job_title": item.job_title,
        "employment_start": item.employment_start,
        "employment_end": item.employment_end,
    }


def _department(item) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "code": item.code,
        "name": item.name,
        "parent_name": item.parent.name if item.parent else None,
        "manager_name": item.manager_employee.membership.user.display_name if item.manager_employee else None,
        "cost_code": item.cost_code,
        "status": item.status,
        "version": item.version,
    }


def _contract(item) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "employee_public_id": str(item.employee.public_id),
        "employee_name": item.employee.membership.user.display_name,
        "department_name": item.department.name,
        "contract_number": item.contract_number,
        "position_title": item.position_title,
        "employment_type": item.employment_type,
        "start_on": item.start_on,
        "end_on": item.end_on,
        "currency": item.currency,
        "annual_compensation": item.annual_compensation,
        "pay_frequency": item.pay_frequency,
        "status": item.status,
        "version": item.version,
    }


def _policy(item) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "code": item.code,
        "name": item.name,
        "leave_type": item.leave_type,
        "annual_days": item.annual_days,
        "carry_forward_days": item.carry_forward_days,
        "requires_approval": item.requires_approval,
        "is_active": item.is_active,
    }


def _balance(item) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "employee_public_id": str(item.employee.public_id),
        "employee_name": item.employee.membership.user.display_name,
        "policy_public_id": str(item.policy.public_id),
        "policy_name": item.policy.name,
        "period_year": item.period_year,
        "opening_days": item.opening_days,
        "accrued_days": item.accrued_days,
        "taken_days": item.taken_days,
        "adjustment_days": item.adjustment_days,
        "available_days": item.available_days,
        "version": item.version,
    }


def _leave(item: LeaveRequest) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "employee_public_id": str(item.employee.public_id),
        "employee_name": item.employee.membership.user.display_name,
        "policy_name": item.policy.name,
        "leave_type": item.policy.leave_type,
        "start_on": item.start_on,
        "end_on": item.end_on,
        "requested_days": item.requested_days,
        "reason": item.reason,
        "status": item.status,
        "approver_name": item.approver_membership.user.display_name if item.approver_membership else None,
        "decision_reason": item.decision_reason,
        "version": item.version,
    }


def _timesheet(item: Timesheet) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "employee_public_id": str(item.employee.public_id),
        "employee_name": item.employee.membership.user.display_name,
        "week_start": item.week_start,
        "total_hours": item.total_hours,
        "status": item.status,
        "approver_name": item.approver_membership.user.display_name if item.approver_membership else None,
        "decision_reason": item.decision_reason,
        "version": item.version,
        "lines": [
            {
                "public_id": str(line.public_id),
                "work_date": line.work_date,
                "project_name": line.project.name if line.project else None,
                "hours": line.hours,
                "description": line.description,
            }
            for line in item.lines.all()
        ],
    }


def _payroll(item: PayrollRun) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "code": item.code,
        "period_start": item.period_start,
        "period_end": item.period_end,
        "currency": item.currency,
        "status": item.status,
        "gross_total": item.gross_total,
        "deduction_total": item.deduction_total,
        "net_total": item.net_total,
        "entry_count": item.entries.count(),
        "evidence_sha256": item.evidence_sha256,
        "version": item.version,
    }


class PeopleopsSummaryView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("people.dashboard.read")
        return Response(peopleops_summary(self.tenant_context.company))


class PeopleopsPortfolioView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("people.dashboard.read")
        data = peopleops_portfolio(self.tenant_context.company)
        return Response(
            {
                "current_user_public_id": str(self.tenant_context.principal.user.public_id),
                "current_membership_public_id": str(self.tenant_context.membership.public_id),
                "summary": data["summary"],
                "employees": [_employee(item) for item in data["employees"]],
                "departments": [_department(item) for item in data["departments"]],
                "contracts": [_contract(item) for item in data["contracts"]],
                "leave_policies": [_policy(item) for item in data["leave_policies"]],
                "leave_balances": [_balance(item) for item in data["leave_balances"]],
                "leave_requests": [_leave(item) for item in data["leave_requests"]],
                "timesheets": [_timesheet(item) for item in data["timesheets"]],
                "payroll_runs": [_payroll(item) for item in data["payroll_runs"]],
            }
        )


class LeaveRequestListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("people.leave.read")
        items = LeaveRequest.objects.filter(company=self.tenant_context.company).select_related(
            "employee__membership__user", "policy", "approver_membership__user"
        )[:100]
        return Response([_leave(item) for item in items])

    def post(self, request: Request) -> Response:
        self.tenant_context.require("people.leave.request")
        serializer = LeaveRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_leave_request(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_leave(item), status=201)


class LeaveRequestTransitionView(TenantScopedAPIView):
    def post(self, request: Request, public_id) -> Response:
        self.tenant_context.require("people.leave.approve")
        serializer = LeaveRequestTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_leave_request(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                approver_membership=self.tenant_context.membership,
                request_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_leave(item))


class TimesheetListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("people.timesheet.read")
        items = Timesheet.objects.filter(company=self.tenant_context.company).select_related(
            "employee__membership__user", "approver_membership__user"
        ).prefetch_related("lines__project")[:100]
        return Response([_timesheet(item) for item in items])

    def post(self, request: Request) -> Response:
        self.tenant_context.require("people.timesheet.create")
        serializer = TimesheetCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_timesheet(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        item = Timesheet.objects.prefetch_related("lines__project").get(pk=item.pk)
        return Response(_timesheet(item), status=201)


class TimesheetTransitionView(TenantScopedAPIView):
    def post(self, request: Request, public_id) -> Response:
        self.tenant_context.require("people.timesheet.approve")
        serializer = TimesheetTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_timesheet(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                approver_membership=self.tenant_context.membership,
                timesheet_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        item = Timesheet.objects.prefetch_related("lines__project").get(pk=item.pk)
        return Response(_timesheet(item))


class PayrollRunListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("people.payroll.read")
        items = PayrollRun.objects.filter(company=self.tenant_context.company).prefetch_related("entries")[:50]
        return Response([_payroll(item) for item in items])

    def post(self, request: Request) -> Response:
        self.tenant_context.require("people.payroll.manage")
        serializer = PayrollRunCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_payroll_run(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_payroll(item), status=201)


class PayrollRunTransitionView(TenantScopedAPIView):
    def post(self, request: Request, public_id) -> Response:
        serializer = PayrollRunTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        permission = {
            PayrollRun.Status.LOCKED: "people.payroll.manage",
            PayrollRun.Status.APPROVED: "people.payroll.approve",
            PayrollRun.Status.POSTED: "people.payroll.post",
            PayrollRun.Status.CANCELLED: "people.payroll.manage",
        }.get(serializer.validated_data["target_status"], "people.payroll.manage")
        self.tenant_context.require(permission)
        try:
            item = transition_payroll_run(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                payroll_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_payroll(item))
