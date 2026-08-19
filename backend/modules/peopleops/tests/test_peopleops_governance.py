import uuid
from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from modules.employee.models import Employee
from modules.peopleops.models import LeaveBalance, PayrollRun, Timesheet


def _employee(company_factory, user_factory, membership_factory):
    company = company_factory()
    user = user_factory()
    membership = membership_factory(user, company)
    employee = Employee.objects.create(
        company=company,
        membership=membership,
        employee_number="EMP-T",
        job_title="Engineer",
        employment_start=date(2026, 1, 1),
    )
    return company, employee


def test_timesheet_week_must_start_on_monday(company_factory, user_factory, membership_factory):
    company, employee = _employee(company_factory, user_factory, membership_factory)
    item = Timesheet(
        company=company,
        employee=employee,
        week_start=date(2026, 8, 4),
    )
    with pytest.raises(ValidationError, match="Monday"):
        item.clean()


def test_leave_balance_cannot_be_negative(company_factory, user_factory, membership_factory):
    company, employee = _employee(company_factory, user_factory, membership_factory)
    from modules.peopleops.models import LeavePolicy

    policy = LeavePolicy(
        company=company,
        code="A",
        name="Annual",
        leave_type=LeavePolicy.LeaveType.ANNUAL,
        annual_days=Decimal("1"),
    )
    balance = LeaveBalance(
        company=company,
        employee=employee,
        policy=policy,
        period_year=2026,
        accrued_days=Decimal("1"),
        taken_days=Decimal("2"),
    )
    with pytest.raises(ValidationError, match="negative"):
        balance.clean()


def test_payroll_requires_independent_approval(company_factory):
    company = company_factory()
    maker = uuid.uuid4()
    item = PayrollRun(
        company=company,
        code="PAY-1",
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31),
        currency="INR",
        gross_total=Decimal("10"),
        deduction_total=Decimal("0"),
        net_total=Decimal("10"),
        created_by_user_public_id=maker,
        approved_by_user_public_id=maker,
    )
    with pytest.raises(ValidationError, match="different users"):
        item.clean()
