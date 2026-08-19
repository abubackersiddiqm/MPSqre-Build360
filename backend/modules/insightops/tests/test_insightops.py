import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from modules.insightops.application.selectors import insight_overview
from modules.insightops.application.services import (
    create_action,
    create_board_report,
    create_snapshot,
    record_observation,
    seed_defaults,
    transition_action,
    transition_board_report,
    transition_snapshot,
)
from modules.insightops.models import KPIDefinition
from modules.tenant.models import Company


class InsightOpsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            code="INSIGHT_TEST", legal_name="Insight Test Company", display_name="Insight Test",
            timezone="Asia/Kolkata", currency="INR", locale="en-IN", unit_system_code="METRIC",
            fiscal_year_start_month=4,
        )
        self.actor = uuid.uuid4()
        self.approver = uuid.uuid4()
        self.correlation = uuid.uuid4()
        seed_defaults(self.company)

    def test_kpi_observation_updates_scorecard(self):
        kpi = KPIDefinition.objects.get(company=self.company, code="ON_TIME_MILESTONES")
        record_observation(
            company=self.company, kpi=kpi, actor_public_id=self.actor, correlation_id=self.correlation,
            period_start=date.today().replace(day=1), period_end=date.today(), actual_value=Decimal("95.00"),
        )
        payload = insight_overview(self.company)
        row = next(item for item in payload["kpis"] if item["code"] == "ON_TIME_MILESTONES")
        self.assertEqual(row["status"], "ON_TARGET")

    def test_snapshot_maker_checker(self):
        snapshot = create_snapshot(
            company=self.company, actor_public_id=self.actor, correlation_id=self.correlation,
            code="PORT-001", as_of_date=date.today(), projects_total=2, projects_healthy=2,
        )
        snapshot = transition_snapshot(snapshot=snapshot, status_code="IN_REVIEW", expected_version=snapshot.version, actor_public_id=self.actor, correlation_id=self.correlation)
        with self.assertRaises(ValidationError):
            transition_snapshot(snapshot=snapshot, status_code="APPROVED", expected_version=snapshot.version, actor_public_id=self.actor, correlation_id=self.correlation)
        snapshot = transition_snapshot(snapshot=snapshot, status_code="APPROVED", expected_version=snapshot.version, actor_public_id=self.approver, correlation_id=self.correlation)
        self.assertEqual(snapshot.status_code, "APPROVED")

    def test_board_report_and_action_controls(self):
        report = create_board_report(
            company=self.company, actor_public_id=self.actor, correlation_id=self.correlation,
            code="BOARD-001", title="Monthly portfolio report", period_start=date.today() - timedelta(days=30), period_end=date.today(),
        )
        report = transition_board_report(report=report, status_code="IN_REVIEW", expected_version=report.version, actor_public_id=self.actor, correlation_id=self.correlation)
        with self.assertRaises(ValidationError):
            transition_board_report(report=report, status_code="APPROVED", expected_version=report.version, actor_public_id=self.actor, correlation_id=self.correlation)
        action = create_action(
            company=self.company, actor_public_id=self.actor, correlation_id=self.correlation,
            code="ACT-001", title="Recover delayed package", due_at=timezone.now() + timedelta(days=3),
        )
        action = transition_action(action=action, status_code="IN_PROGRESS", expected_version=action.version, actor_public_id=self.actor, correlation_id=self.correlation)
        with self.assertRaises(ValidationError):
            transition_action(action=action, status_code="COMPLETED", expected_version=action.version, actor_public_id=self.actor, correlation_id=self.correlation)
