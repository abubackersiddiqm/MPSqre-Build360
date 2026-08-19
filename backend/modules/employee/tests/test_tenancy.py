from collections.abc import Callable
from datetime import date

import pytest
from django.core.exceptions import ValidationError

from modules.employee.models import Employee
from modules.identity.models import User
from modules.tenant.models import Company, Membership


@pytest.mark.django_db
def test_employee_rejects_cross_company_membership(
    company_factory: Callable[..., Company],
    user_factory: Callable[..., User],
    membership_factory: Callable[[User, Company], Membership],
) -> None:
    user = user_factory()
    membership = membership_factory(user, company_factory())
    employee = Employee(
        company=company_factory(),
        membership=membership,
        employee_number="EMP-1",
        job_title="Engineer",
        employment_start=date.today(),
    )

    with pytest.raises(ValidationError, match="same company"):
        employee.full_clean()

