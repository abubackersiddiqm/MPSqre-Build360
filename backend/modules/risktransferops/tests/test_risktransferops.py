import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from modules.risktransferops.application.selectors import risk_transfer_overview
from modules.risktransferops.application.services import (
    create_call,
    create_claim,
    create_counterparty,
    create_coverage,
    create_instrument,
    create_loss,
    create_premium,
    create_program,
    seed_defaults,
    transition_call,
    transition_claim,
    transition_counterparty,
    transition_coverage,
    transition_instrument,
    transition_premium,
    transition_program,
)
from modules.tenant.models import Company


class RiskTransferOperationsTests(TestCase):
    """Traceability: P45-INS-001, P45-CLM-001, P45-GRT-001, P45-PRM-001."""

    def setUp(self):
        self.company = Company.objects.create(
            code="RISK_TEST",
            legal_name="Risk Transfer Test Company",
            display_name="Risk Transfer Test",
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
            program_code="RISK_PROGRAM_001",
            name="Construction Risk Program",
            aggregate_exposure=Decimal("100000000.00"),
            starts_on=date.today(),
            ends_on=date.today() + timedelta(days=365),
        )
        self.counterparty = create_counterparty(
            company=self.company,
            actor_public_id=self.creator,
            correlation_id=self.correlation,
            counterparty_code="INSURER_001",
            legal_name="Example Insurance Company",
            counterparty_type_code="INSURER",
            financial_rating_code="A",
        )

    def _verified_counterparty(self):
        with self.assertRaises(ValidationError):
            transition_counterparty(
                counterparty=self.counterparty,
                status_code="VERIFIED",
                expected_version=self.counterparty.version,
                actor_public_id=self.creator,
                correlation_id=self.correlation,
            )
        self.counterparty = transition_counterparty(
            counterparty=self.counterparty,
            status_code="VERIFIED",
            expected_version=self.counterparty.version,
            actor_public_id=self.approver,
            correlation_id=self.correlation,
        )
        return self.counterparty

    def _active_coverage(self):
        party = self._verified_counterparty()
        coverage = create_coverage(
            company=self.company,
            program=self.program,
            counterparty=party,
            actor_public_id=self.creator,
            correlation_id=self.correlation,
            policy_number="POLICY_001",
            coverage_limit=Decimal("100000000.00"),
            annual_premium=Decimal("1000000.00"),
            starts_on=date.today(),
            ends_on=date.today() + timedelta(days=365),
        )
        coverage = transition_coverage(coverage=coverage, status_code="SUBMITTED", expected_version=coverage.version, actor_public_id=self.creator, correlation_id=self.correlation)
        with self.assertRaises(ValidationError):
            transition_coverage(coverage=coverage, status_code="APPROVED", expected_version=coverage.version, actor_public_id=self.creator, correlation_id=self.correlation)
        coverage = transition_coverage(coverage=coverage, status_code="APPROVED", expected_version=coverage.version, actor_public_id=self.approver, correlation_id=self.correlation)
        return transition_coverage(coverage=coverage, status_code="ACTIVE", expected_version=coverage.version, actor_public_id=self.approver, correlation_id=self.correlation)

    def test_program_maker_checker(self):
        program = transition_program(program=self.program, status_code="SUBMITTED", expected_version=self.program.version, actor_public_id=self.creator, correlation_id=self.correlation)
        with self.assertRaises(ValidationError):
            transition_program(program=program, status_code="APPROVED", expected_version=program.version, actor_public_id=self.creator, correlation_id=self.correlation)
        program = transition_program(program=program, status_code="APPROVED", expected_version=program.version, actor_public_id=self.approver, correlation_id=self.correlation)
        self.assertEqual(program.status_code, "APPROVED")

    def test_counterparty_and_coverage_maker_checker(self):
        coverage = self._active_coverage()
        self.assertEqual(self.counterparty.status_code, "VERIFIED")
        self.assertEqual(coverage.status_code, "ACTIVE")

    def test_premium_payment_control(self):
        coverage = self._active_coverage()
        premium = create_premium(
            company=self.company,
            coverage=coverage,
            actor_public_id=self.creator,
            correlation_id=self.correlation,
            installment_number="PREMIUM_001",
            due_on=date.today(),
            amount=Decimal("500000.00"),
        )
        with self.assertRaises(ValidationError):
            transition_premium(premium=premium, status_code="PARTIALLY_PAID", expected_version=premium.version, actor_public_id=self.creator, correlation_id=self.correlation, paid_amount=Decimal("500000.00"))
        premium = transition_premium(premium=premium, status_code="PAID", expected_version=premium.version, actor_public_id=self.creator, correlation_id=self.correlation, payment_reference="PAY-001")
        self.assertEqual(premium.paid_amount, Decimal("500000.00"))

    def test_claim_recovery_cannot_exceed_claim(self):
        coverage = self._active_coverage()
        loss = create_loss(
            company=self.company,
            program=self.program,
            actor_public_id=self.creator,
            correlation_id=self.correlation,
            loss_number="LOSS_001",
            occurrence_on=timezone.now() - timedelta(hours=1),
            reported_on=timezone.now(),
            description="Water ingress damage.",
            estimated_loss=Decimal("1000000.00"),
        )
        claim = create_claim(
            company=self.company,
            loss_event=loss,
            coverage=coverage,
            actor_public_id=self.creator,
            correlation_id=self.correlation,
            claim_number="CLAIM_001",
            notified_on=date.today(),
            claimed_amount=Decimal("900000.00"),
            reserved_amount=Decimal("800000.00"),
        )
        claim = transition_claim(claim=claim, status_code="NOTIFIED", expected_version=claim.version, actor_public_id=self.creator, correlation_id=self.correlation)
        claim = transition_claim(claim=claim, status_code="ADMITTED", expected_version=claim.version, actor_public_id=self.approver, correlation_id=self.correlation)
        with self.assertRaises(ValidationError):
            transition_claim(claim=claim, status_code="SETTLED", expected_version=claim.version, actor_public_id=self.approver, correlation_id=self.correlation, recovered_amount=Decimal("1000000.00"), settlement_reference="SET-001")
        claim = transition_claim(claim=claim, status_code="SETTLED", expected_version=claim.version, actor_public_id=self.approver, correlation_id=self.correlation, recovered_amount=Decimal("750000.00"), settlement_reference="SET-002")
        self.assertEqual(claim.status_code, "SETTLED")

    def test_guarantee_calls_cannot_exceed_instrument(self):
        party = self._verified_counterparty()
        instrument = create_instrument(
            company=self.company,
            program=self.program,
            counterparty=party,
            actor_public_id=self.creator,
            correlation_id=self.correlation,
            instrument_number="BG_001",
            instrument_type_code="PERFORMANCE_BOND",
            beneficiary_name="Project Owner",
            applicant_name="Main Contractor",
            amount=Decimal("1000000.00"),
            issued_on=date.today(),
            expiry_on=date.today() + timedelta(days=180),
        )
        instrument = transition_instrument(instrument=instrument, status_code="SUBMITTED", expected_version=instrument.version, actor_public_id=self.creator, correlation_id=self.correlation)
        instrument = transition_instrument(instrument=instrument, status_code="APPROVED", expected_version=instrument.version, actor_public_id=self.approver, correlation_id=self.correlation)
        instrument = transition_instrument(instrument=instrument, status_code="ACTIVE", expected_version=instrument.version, actor_public_id=self.approver, correlation_id=self.correlation)
        first = create_call(company=self.company, instrument=instrument, actor_public_id=self.creator, correlation_id=self.correlation, call_number="CALL_001", called_on=date.today(), amount=Decimal("700000.00"), reason="Contract default")
        first = transition_call(call=first, status_code="SUBMITTED", expected_version=first.version, actor_public_id=self.creator, correlation_id=self.correlation)
        first = transition_call(call=first, status_code="APPROVED", expected_version=first.version, actor_public_id=self.approver, correlation_id=self.correlation)
        with self.assertRaises(ValidationError):
            create_call(company=self.company, instrument=instrument, actor_public_id=self.creator, correlation_id=self.correlation, call_number="CALL_002", called_on=date.today(), amount=Decimal("400000.00"), reason="Additional default")

    def test_overview_counts_program_without_coverage_as_gap(self):
        program = transition_program(
            program=self.program,
            status_code="SUBMITTED",
            expected_version=self.program.version,
            actor_public_id=self.creator,
            correlation_id=self.correlation,
        )
        transition_program(
            program=program,
            status_code="APPROVED",
            expected_version=program.version,
            actor_public_id=self.approver,
            correlation_id=self.correlation,
        )
        payload = risk_transfer_overview(self.company)
        self.assertEqual(payload["metrics"]["coverage_gaps"], 1)

    def test_overview_contract(self):
        self._active_coverage()
        payload = risk_transfer_overview(self.company)
        self.assertEqual(payload["metrics"]["verified_counterparties"], 1)
        self.assertEqual(payload["metrics"]["active_coverages"], 1)
        self.assertEqual(payload["policy"]["expiry_alert_days"], 45)
