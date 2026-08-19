import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from modules.capitalops.application.selectors import capital_overview
from modules.capitalops.application.services import (
    create_commitment,
    create_covenant_test,
    create_debt_facility,
    create_distribution,
    create_drawdown,
    create_investor,
    create_joint_venture,
    create_program,
    seed_defaults,
    transition_commitment,
    transition_covenant_test,
    transition_debt_facility,
    transition_distribution,
    transition_drawdown,
    transition_investor,
    transition_joint_venture,
    transition_program,
)
from modules.tenant.models import Company


class CapitalOperationsTests(TestCase):
    """Traceability: P44-CAP-001, P44-JV-001, P44-DRW-001, P44-COV-001."""

    def setUp(self):
        self.company = Company.objects.create(
            code="CAP_TEST",
            legal_name="Capital Test Company",
            display_name="Capital Test",
            timezone="Asia/Kolkata",
            currency="INR",
            locale="en-IN",
            unit_system_code="METRIC",
            fiscal_year_start_month=4,
        )
        self.creator = uuid.uuid4()
        self.approver = uuid.uuid4()
        self.correlation = uuid.uuid4()
        seed_defaults(self.company)
        self.program = create_program(
            company=self.company,
            actor_public_id=self.creator,
            correlation_id=self.correlation,
            program_code="PROJECT_FUND_001",
            name="Project Funding Program",
            target_capital=Decimal("100000000.00"),
            target_equity=Decimal("40000000.00"),
            target_debt=Decimal("60000000.00"),
            start_on=date.today(),
            target_close_on=date.today() + timedelta(days=120),
        )

    def _approve_program(self):
        program = transition_program(program=self.program, status_code="SUBMITTED", expected_version=self.program.version, actor_public_id=self.creator, correlation_id=self.correlation)
        with self.assertRaises(ValidationError):
            transition_program(program=program, status_code="APPROVED", expected_version=program.version, actor_public_id=self.creator, correlation_id=self.correlation)
        return transition_program(program=program, status_code="APPROVED", expected_version=program.version, actor_public_id=self.approver, correlation_id=self.correlation)

    def _verified_investor(self):
        investor = create_investor(
            company=self.company,
            actor_public_id=self.creator,
            correlation_id=self.correlation,
            investor_code="INV_001",
            legal_name="Example Infrastructure Fund",
            investor_type_code="INSTITUTIONAL",
            accredited_flag=True,
        )
        with self.assertRaises(ValidationError):
            transition_investor(investor=investor, status_code="VERIFIED", expected_version=investor.version, actor_public_id=self.creator, correlation_id=self.correlation)
        return transition_investor(investor=investor, status_code="VERIFIED", expected_version=investor.version, actor_public_id=self.approver, correlation_id=self.correlation)

    def test_program_and_investor_maker_checker(self):
        program = self._approve_program()
        investor = self._verified_investor()
        self.assertEqual(program.status_code, "APPROVED")
        self.assertEqual(investor.kyc_status_code, "VERIFIED")

    def test_joint_venture_ownership_cannot_exceed_100_percent(self):
        first = create_joint_venture(
            company=self.company,
            program=self.program,
            actor_public_id=self.creator,
            correlation_id=self.correlation,
            venture_code="JV_A",
            partner_name="Partner A",
            ownership_percent=Decimal("70.0000"),
            profit_share_percent=Decimal("60.0000"),
        )
        first = transition_joint_venture(joint_venture=first, status_code="SUBMITTED", expected_version=first.version, actor_public_id=self.creator, correlation_id=self.correlation)
        first = transition_joint_venture(joint_venture=first, status_code="APPROVED", expected_version=first.version, actor_public_id=self.approver, correlation_id=self.correlation)
        with self.assertRaises(ValidationError):
            create_joint_venture(
                company=self.company,
                program=self.program,
                actor_public_id=self.creator,
                correlation_id=self.correlation,
                venture_code="JV_B",
                partner_name="Partner B",
                ownership_percent=Decimal("40.0000"),
                profit_share_percent=Decimal("40.0000"),
            )

    def test_drawdown_limit_and_commitment_funding(self):
        investor = self._verified_investor()
        commitment = create_commitment(
            company=self.company,
            program=self.program,
            investor=investor,
            joint_venture=None,
            actor_public_id=self.creator,
            correlation_id=self.correlation,
            commitment_number="COM_001",
            committed_amount=Decimal("10000000.00"),
            committed_on=date.today(),
        )
        commitment = transition_commitment(commitment=commitment, status_code="SUBMITTED", expected_version=commitment.version, actor_public_id=self.creator, correlation_id=self.correlation)
        commitment = transition_commitment(commitment=commitment, status_code="APPROVED", expected_version=commitment.version, actor_public_id=self.approver, correlation_id=self.correlation)
        drawdown = create_drawdown(
            company=self.company,
            program=self.program,
            debt_facility=None,
            commitment=commitment,
            actor_public_id=self.creator,
            correlation_id=self.correlation,
            request_number="CALL_001",
            amount=Decimal("10000000.00"),
            requested_on=date.today(),
        )
        drawdown = transition_drawdown(drawdown=drawdown, status_code="SUBMITTED", expected_version=drawdown.version, actor_public_id=self.creator, correlation_id=self.correlation)
        drawdown = transition_drawdown(drawdown=drawdown, status_code="APPROVED", expected_version=drawdown.version, actor_public_id=self.approver, correlation_id=self.correlation)
        drawdown = transition_drawdown(drawdown=drawdown, status_code="DISBURSED", expected_version=drawdown.version, actor_public_id=self.approver, correlation_id=self.correlation, disbursement_reference="BANK-001")
        commitment.refresh_from_db()
        self.assertEqual(commitment.funded_amount, Decimal("10000000.00"))
        self.assertEqual(commitment.status_code, "FULLY_FUNDED")
        with self.assertRaises(ValidationError):
            create_drawdown(
                company=self.company,
                program=self.program,
                debt_facility=None,
                commitment=commitment,
                actor_public_id=self.creator,
                correlation_id=self.correlation,
                request_number="CALL_002",
                amount=Decimal("1.00"),
                requested_on=date.today(),
            )

    def test_non_compliant_covenant_requires_waiver(self):
        facility = create_debt_facility(
            company=self.company,
            program=self.program,
            actor_public_id=self.creator,
            correlation_id=self.correlation,
            facility_code="DEBT_001",
            lender_name="Example Bank",
            principal_limit=Decimal("60000000.00"),
            interest_rate_percent=Decimal("9.500000"),
        )
        facility = transition_debt_facility(facility=facility, status_code="SUBMITTED", expected_version=facility.version, actor_public_id=self.creator, correlation_id=self.correlation)
        facility = transition_debt_facility(facility=facility, status_code="APPROVED", expected_version=facility.version, actor_public_id=self.approver, correlation_id=self.correlation)
        test = create_covenant_test(
            company=self.company,
            facility=facility,
            actor_public_id=self.creator,
            correlation_id=self.correlation,
            test_number="COV_001",
            covenant_code="LTV",
            tested_on=date.today(),
            metric_value=Decimal("82.000000"),
            threshold_operator="LTE",
            threshold_value=Decimal("75.000000"),
        )
        self.assertFalse(test.compliant)
        test = transition_covenant_test(test=test, status_code="REVIEWED", expected_version=test.version, actor_public_id=self.approver, correlation_id=self.correlation)
        with self.assertRaises(ValidationError):
            transition_covenant_test(test=test, status_code="CLOSED", expected_version=test.version, actor_public_id=self.approver, correlation_id=self.correlation)
        test = transition_covenant_test(test=test, status_code="WAIVED", expected_version=test.version, actor_public_id=self.approver, correlation_id=self.correlation, note="Approved temporary waiver.")
        test = transition_covenant_test(test=test, status_code="CLOSED", expected_version=test.version, actor_public_id=self.approver, correlation_id=self.correlation)
        self.assertEqual(test.status_code, "CLOSED")

    def test_distribution_and_overview(self):
        investor = self._verified_investor()
        distribution = create_distribution(
            company=self.company,
            program=self.program,
            investor=investor,
            joint_venture=None,
            actor_public_id=self.creator,
            correlation_id=self.correlation,
            distribution_number="DIST_001",
            amount=Decimal("250000.00"),
            declared_on=date.today(),
        )
        distribution = transition_distribution(distribution=distribution, status_code="SUBMITTED", expected_version=distribution.version, actor_public_id=self.creator, correlation_id=self.correlation)
        distribution = transition_distribution(distribution=distribution, status_code="APPROVED", expected_version=distribution.version, actor_public_id=self.approver, correlation_id=self.correlation)
        distribution = transition_distribution(distribution=distribution, status_code="PAID", expected_version=distribution.version, actor_public_id=self.approver, correlation_id=self.correlation, payment_reference="PAY-001")
        payload = capital_overview(self.company)
        self.assertEqual(payload["metrics"]["verified_investors"], 1)
        self.assertEqual(payload["distributions"][0]["status_code"], "PAID")
        self.assertEqual(payload["policy"]["covenant_alert_days"], 30)
