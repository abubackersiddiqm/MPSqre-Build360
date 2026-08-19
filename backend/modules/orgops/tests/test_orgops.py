import uuid
from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from modules.employee.models import Employee
from modules.identity.models import User
from modules.orgops.application.services import (
    create_assignment,
    create_department,
    create_designation,
    create_leave_type,
    review_leave_request,
    set_employee_manager,
    submit_leave_request,
    update_employee_profile,
    upsert_attendance,
)
from modules.orgops.models import AttendanceEntry, EmployeeOrganizationProfile
from modules.tenant.models import Company, Membership

pytestmark = pytest.mark.django_db


def company(code: str) -> Company:
    return Company.objects.create(
        code=code,
        legal_name=code,
        display_name=code,
        locale="en-IN",
        timezone="Asia/Kolkata",
        currency="INR",
        unit_system_code="METRIC",
        fiscal_year_start_month=4,
    )


def employee(company_obj: Company, number: str, name: str) -> Employee:
    user = User.objects.create_user(
        email=f"{number.lower()}@example.test",
        password="StrongPassword123",
        display_name=name,
    )
    membership = Membership.objects.create(
        company=company_obj,
        user=user,
        effective_from=timezone.now(),
    )
    return Employee.objects.create(
        company=company_obj,
        membership=membership,
        employee_number=number,
        job_title="Team member",
        employment_start=date(2026, 1, 1),
    )


def test_employee_profile_and_assignment_complete_people_setup():
    tenant = company("P29")
    person = employee(tenant, "EMP-001", "Employee One")
    actor = person.membership.user.public_id
    department = create_department(
        company=tenant,
        code="DELIVERY",
        name="Project Delivery",
        actor_public_id=actor,
        correlation_id=uuid.uuid4(),
    )
    designation = create_designation(
        company=tenant,
        code="SITE_ENGINEER",
        name="Site Engineer",
        actor_public_id=actor,
        correlation_id=uuid.uuid4(),
    )
    profile = update_employee_profile(
        company=tenant,
        employee=person,
        actor_public_id=actor,
        correlation_id=uuid.uuid4(),
        job_title="Site Engineer",
        department=department,
        designation=designation,
        work_calendar=None,
        employment_type_code="FULL_TIME",
        worker_category_code="ENGINEERING",
        mobile="9999999999",
        status_code="ACTIVE",
        probation_end=None,
        confirmation_date=None,
    )
    assignment = create_assignment(
        company=tenant,
        employee=person,
        assignment_type_code="PRIMARY",
        project_code="PRJ-001",
        site_code="SITE-A",
        location=None,
        work_package_code="STRUCTURE",
        allocation_percent=Decimal("100.00"),
        effective_from=date(2026, 8, 1),
        effective_to=None,
        is_primary=True,
        actor_public_id=actor,
        correlation_id=uuid.uuid4(),
    )
    assert profile.department == department
    assert profile.designation == designation
    assert assignment.project_code == "PRJ-001"


def test_reporting_line_rejects_cycle():
    tenant = company("CYCLE")
    first = employee(tenant, "EMP-001", "First")
    second = employee(tenant, "EMP-002", "Second")
    actor = first.membership.user.public_id
    set_employee_manager(
        company=tenant,
        employee=second,
        manager=first,
        effective_from=date(2026, 8, 1),
        actor_public_id=actor,
        correlation_id=uuid.uuid4(),
    )
    with pytest.raises(ValidationError):
        set_employee_manager(
            company=tenant,
            employee=first,
            manager=second,
            effective_from=date(2026, 8, 2),
            actor_public_id=actor,
            correlation_id=uuid.uuid4(),
        )


def test_leave_review_uses_optimistic_version():
    tenant = company("LEAVE")
    person = employee(tenant, "EMP-001", "Employee")
    actor = person.membership.user.public_id
    leave_type = create_leave_type(
        company=tenant,
        code="GENERAL",
        name="General Leave",
        unit_code="DAYS",
        requires_approval=True,
        is_paid=True,
        annual_entitlement=Decimal("12.00"),
        actor_public_id=actor,
        correlation_id=uuid.uuid4(),
    )
    request = submit_leave_request(
        company=tenant,
        employee=person,
        leave_type=leave_type,
        start_date=date(2026, 8, 10),
        end_date=date(2026, 8, 10),
        quantity=Decimal("1.00"),
        reason="Personal",
        actor_public_id=actor,
        correlation_id=uuid.uuid4(),
    )
    reviewed = review_leave_request(
        company=tenant,
        leave_request=request,
        decision_code="APPROVED",
        review_note="Approved",
        actor_public_id=actor,
        correlation_id=uuid.uuid4(),
        expected_version=1,
    )
    assert reviewed.status_code == "APPROVED"
    with pytest.raises(ValidationError):
        review_leave_request(
            company=tenant,
            leave_request=reviewed,
            decision_code="REJECTED",
            review_note="Stale",
            actor_public_id=actor,
            correlation_id=uuid.uuid4(),
            expected_version=1,
        )


def test_attendance_is_idempotently_upserted_for_day():
    tenant = company("ATT")
    person = employee(tenant, "EMP-001", "Employee")
    actor = person.membership.user.public_id
    first = upsert_attendance(
        company=tenant,
        employee=person,
        work_date=date(2026, 8, 3),
        status_code="PRESENT",
        hours_worked=Decimal("8.00"),
        source_code="MANUAL",
        notes="",
        actor_public_id=actor,
        correlation_id=uuid.uuid4(),
    )
    second = upsert_attendance(
        company=tenant,
        employee=person,
        work_date=date(2026, 8, 3),
        status_code="PRESENT",
        hours_worked=Decimal("9.00"),
        source_code="MANUAL",
        notes="Corrected",
        actor_public_id=actor,
        correlation_id=uuid.uuid4(),
    )
    assert first.pk == second.pk
    assert AttendanceEntry.objects.filter(company=tenant, employee=person).count() == 1
    assert second.version == 2


def test_profile_rejects_cross_tenant_department():
    first_company = company("A")
    second_company = company("B")
    person = employee(first_company, "EMP-001", "Employee")
    actor = person.membership.user.public_id
    foreign_department = create_department(
        company=second_company,
        code="FOREIGN",
        name="Foreign",
        actor_public_id=actor,
        correlation_id=uuid.uuid4(),
    )
    with pytest.raises(ValidationError):
        update_employee_profile(
            company=first_company,
            employee=person,
            actor_public_id=actor,
            correlation_id=uuid.uuid4(),
            job_title="Engineer",
            department=foreign_department,
            designation=None,
            work_calendar=None,
            employment_type_code="FULL_TIME",
            worker_category_code="",
            mobile="",
            status_code="ACTIVE",
            probation_end=None,
            confirmation_date=None,
        )
    assert not EmployeeOrganizationProfile.objects.filter(employee=person).exists()
