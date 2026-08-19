from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from modules.employee.models import Employee
from modules.identity.models import User
from modules.tenant.models import Company, Membership
from modules.workops.application.selectors import project_work_overview
from modules.workops.application.services import (
    add_dependency,
    create_checklist_item,
    create_project,
    create_work_item,
    set_checklist_completion,
    transition_project,
    transition_work_item,
)


class WorkOpsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            code="WORKTEST",
            legal_name="Work Test Private Limited",
            display_name="Work Test",
            locale="en-IN",
            timezone="Asia/Kolkata",
            currency="INR",
            unit_system_code="METRIC",
            fiscal_year_start_month=4,
        )
        user = User.objects.create_user(email="manager@example.com", password="StrongPassword123", display_name="Manager")
        membership = Membership.objects.create(company=self.company, user=user, effective_from=timezone.now())
        self.employee = Employee.objects.create(
            company=self.company,
            membership=membership,
            employee_number="E001",
            job_title="Project Manager",
            employment_start=date.today(),
        )
        self.actor = user.public_id
        self.correlation = self.actor
        self.project = create_project(
            company=self.company,
            code="P001",
            name="Test Project",
            start_date=date.today(),
            target_end_date=date.today() + timedelta(days=60),
            manager=self.employee,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
        )

    def test_project_and_work_item_appear_in_overview(self):
        item = create_work_item(
            company=self.company,
            project=self.project,
            code="T001",
            title="Inspect reinforcement",
            due_date=date.today() + timedelta(days=2),
            primary_assignee=self.employee,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
        )
        payload = project_work_overview(self.company)
        self.assertEqual(payload["summary"]["open_work_count"], 1)
        self.assertEqual(payload["work_items"][0]["public_id"], str(item.public_id))

    def test_required_checklist_blocks_completion_until_checked(self):
        item = create_work_item(
            company=self.company,
            project=self.project,
            code="T002",
            title="Pour concrete",
            primary_assignee=self.employee,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
        )
        checklist = create_checklist_item(
            company=self.company,
            work_item=item,
            sequence=1,
            title="Slump test accepted",
            is_required=True,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
        )
        item = transition_work_item(
            company=self.company,
            work_item_public_id=item.public_id,
            status_code="IN_PROGRESS",
            expected_version=item.version,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
        )
        with self.assertRaises(ValidationError):
            transition_work_item(
                company=self.company,
                work_item_public_id=item.public_id,
                status_code="DONE",
                expected_version=item.version,
                actor_public_id=self.actor,
                correlation_id=self.correlation,
            )
        checklist = set_checklist_completion(
            company=self.company,
            checklist_public_id=checklist.public_id,
            is_completed=True,
            expected_version=checklist.version,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
        )
        self.assertTrue(checklist.is_completed)
        item = transition_work_item(
            company=self.company,
            work_item_public_id=item.public_id,
            status_code="DONE",
            expected_version=item.version,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
        )
        self.assertEqual(item.status_code, "DONE")
        self.assertEqual(item.progress_percent, Decimal("100.00"))


    def test_project_completion_requires_closed_work(self):
        project = transition_project(
            company=self.company,
            project_public_id=self.project.public_id,
            status_code="ACTIVE",
            expected_version=self.project.version,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
        )
        create_work_item(
            company=self.company,
            project=project,
            code="T005",
            title="Open construction activity",
            actor_public_id=self.actor,
            correlation_id=self.correlation,
        )
        with self.assertRaises(ValidationError):
            transition_project(
                company=self.company,
                project_public_id=project.public_id,
                status_code="COMPLETED",
                expected_version=project.version,
                actor_public_id=self.actor,
                correlation_id=self.correlation,
            )

    def test_dependency_cycle_is_rejected(self):
        first = create_work_item(
            company=self.company,
            project=self.project,
            code="T003",
            title="First",
            actor_public_id=self.actor,
            correlation_id=self.correlation,
        )
        second = create_work_item(
            company=self.company,
            project=self.project,
            code="T004",
            title="Second",
            actor_public_id=self.actor,
            correlation_id=self.correlation,
        )
        add_dependency(
            company=self.company,
            predecessor=first,
            successor=second,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
        )
        with self.assertRaises(ValidationError):
            add_dependency(
                company=self.company,
                predecessor=second,
                successor=first,
                actor_public_id=self.actor,
                correlation_id=self.correlation,
            )
