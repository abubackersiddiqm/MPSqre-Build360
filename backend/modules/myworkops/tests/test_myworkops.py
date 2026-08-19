from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from modules.employee.models import Employee
from modules.identity.models import User
from modules.myworkops.application.selectors import my_work_overview
from modules.myworkops.application.services import transition_own_work_item
from modules.tenant.models import Company, Membership
from modules.workops.application.services import create_project, create_work_item


class MyWorkOpsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            code="MYWORKTEST",
            legal_name="My Work Test Private Limited",
            display_name="My Work Test",
            locale="en-IN",
            timezone="Asia/Kolkata",
            currency="INR",
            unit_system_code="METRIC",
            fiscal_year_start_month=4,
        )
        self.user = User.objects.create_user(
            email="employee@example.com",
            password="StrongPassword123",
            display_name="Site Engineer",
        )
        self.membership = Membership.objects.create(
            company=self.company,
            user=self.user,
            effective_from=timezone.now(),
        )
        self.employee = Employee.objects.create(
            company=self.company,
            membership=self.membership,
            employee_number="E001",
            job_title="Site Engineer",
            employment_start=date.today(),
        )
        self.project = create_project(
            company=self.company,
            code="P001",
            name="Tower Project",
            start_date=date.today(),
            target_end_date=date.today() + timedelta(days=90),
            actor_public_id=self.user.public_id,
            correlation_id=self.user.public_id,
        )

    def test_assigned_work_is_personalized(self):
        item = create_work_item(
            company=self.company,
            project=self.project,
            code="W001",
            title="Inspect reinforcement",
            primary_assignee=self.employee,
            due_date=date.today(),
            actor_public_id=self.user.public_id,
            correlation_id=self.user.public_id,
        )
        payload = my_work_overview(self.company, self.membership)
        self.assertEqual(payload["profile_state"], "ACTIVE")
        self.assertEqual(payload["summary"]["due_today_count"], 1)
        self.assertEqual(payload["work_items"][0]["public_id"], str(item.public_id))

    def test_missing_employee_profile_returns_guided_state(self):
        user = User.objects.create_user(
            email="operator@example.com",
            password="StrongPassword123",
            display_name="Platform Operator",
        )
        membership = Membership.objects.create(
            company=self.company,
            user=user,
            effective_from=timezone.now(),
        )
        payload = my_work_overview(self.company, membership)
        self.assertEqual(payload["profile_state"], "EMPLOYEE_PROFILE_REQUIRED")
        self.assertEqual(payload["summary"]["open_count"], 0)

    def test_employee_cannot_update_unassigned_work(self):
        item = create_work_item(
            company=self.company,
            project=self.project,
            code="W002",
            title="Unassigned task",
            actor_public_id=self.user.public_id,
            correlation_id=self.user.public_id,
        )
        with self.assertRaises(ValidationError):
            transition_own_work_item(
                company=self.company,
                employee=self.employee,
                work_item_public_id=item.public_id,
                status_code="IN_PROGRESS",
                expected_version=item.version,
                actor_public_id=self.user.public_id,
                correlation_id=self.user.public_id,
            )
