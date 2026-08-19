import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from modules.leaseops.application.selectors import property_lease_overview
from modules.leaseops.application.services import (
    create_case,
    create_invoice,
    create_lease,
    create_occupancy,
    create_property,
    create_tenant,
    create_unit,
    seed_defaults,
    transition_case,
    transition_invoice,
    transition_lease,
    transition_occupancy,
)
from modules.tenant.models import Company


class LeaseOpsTests(TestCase):
    """Traceability: P41-PRP-001, P41-LEA-001, P41-BIL-001, P41-EXP-001."""

    def setUp(self):
        self.company = Company.objects.create(
            code="LEASE_TEST",
            legal_name="Lease Test Company",
            display_name="Lease Test",
            timezone="Asia/Kolkata",
            currency="INR",
            locale="en-IN",
            unit_system_code="METRIC",
            fiscal_year_start_month=4,
        )
        self.actor = uuid.uuid4()
        self.approver = uuid.uuid4()
        self.operator = uuid.uuid4()
        self.correlation = uuid.uuid4()
        seed_defaults(self.company)
        self.property = create_property(
            company=self.company,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
            code="TOWER_A",
            name="Tower A",
        )
        self.unit = create_unit(
            company=self.company,
            property=self.property,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
            code="A_101",
            name="Apartment A-101",
            market_rent=Decimal("25000.00"),
        )
        self.tenant = create_tenant(
            company=self.company,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
            account_code="TENANT_001",
            legal_name="Example Tenant Private Limited",
            display_name="Example Tenant",
        )
        self.lease = create_lease(
            company=self.company,
            property=self.property,
            unit=self.unit,
            tenant=self.tenant,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
            lease_number="LEASE_001",
            start_on=date.today(),
            end_on=date.today() + timedelta(days=365),
            base_rent=Decimal("25000.00"),
            security_deposit=Decimal("75000.00"),
        )

    def test_lease_maker_checker_and_unit_status(self):
        self.lease = transition_lease(lease=self.lease, status_code="SUBMITTED", expected_version=self.lease.version, actor_public_id=self.actor, correlation_id=self.correlation)
        with self.assertRaises(ValidationError):
            transition_lease(lease=self.lease, status_code="APPROVED", expected_version=self.lease.version, actor_public_id=self.actor, correlation_id=self.correlation)
        self.lease = transition_lease(lease=self.lease, status_code="APPROVED", expected_version=self.lease.version, actor_public_id=self.approver, correlation_id=self.correlation)
        self.lease = transition_lease(lease=self.lease, status_code="ACTIVE", expected_version=self.lease.version, actor_public_id=self.approver, correlation_id=self.correlation)
        self.unit.refresh_from_db()
        self.assertEqual(self.lease.status_code, "ACTIVE")
        self.assertEqual(self.unit.status_code, "LEASED")
        self.assertEqual(self.lease.lifecycle_events.count(), 3)

    def test_overlapping_lease_is_blocked(self):
        self.lease = transition_lease(lease=self.lease, status_code="SUBMITTED", expected_version=self.lease.version, actor_public_id=self.actor, correlation_id=self.correlation)
        with self.assertRaises(ValidationError):
            create_lease(
                company=self.company,
                property=self.property,
                unit=self.unit,
                tenant=self.tenant,
                actor_public_id=self.actor,
                correlation_id=self.correlation,
                lease_number="LEASE_002",
                start_on=date.today() + timedelta(days=10),
                end_on=date.today() + timedelta(days=300),
                base_rent=Decimal("26000.00"),
            )

    def test_occupancy_maker_checker(self):
        occupancy = create_occupancy(
            company=self.company,
            lease=self.lease,
            unit=self.unit,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
            occupant_reference="Primary occupant",
        )
        occupancy = transition_occupancy(occupancy=occupancy, status_code="SUBMITTED", expected_version=occupancy.version, actor_public_id=self.actor, correlation_id=self.correlation)
        with self.assertRaises(ValidationError):
            transition_occupancy(occupancy=occupancy, status_code="VERIFIED", expected_version=occupancy.version, actor_public_id=self.actor, correlation_id=self.correlation)
        occupancy = transition_occupancy(occupancy=occupancy, status_code="VERIFIED", expected_version=occupancy.version, actor_public_id=self.approver, correlation_id=self.correlation)
        occupancy = transition_occupancy(occupancy=occupancy, status_code="OCCUPIED", expected_version=occupancy.version, actor_public_id=self.operator, correlation_id=self.correlation)
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.status_code, "OCCUPIED")

    def test_invoice_maker_checker_and_payment(self):
        invoice = create_invoice(
            company=self.company,
            lease=self.lease,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
            invoice_number="INV_001",
            period_start=date.today(),
            period_end=date.today() + timedelta(days=29),
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=5),
            gross_amount=Decimal("25000.00"),
            tax_amount=Decimal("4500.00"),
        )
        invoice = transition_invoice(invoice=invoice, status_code="SUBMITTED", expected_version=invoice.version, actor_public_id=self.actor, correlation_id=self.correlation)
        with self.assertRaises(ValidationError):
            transition_invoice(invoice=invoice, status_code="ISSUED", expected_version=invoice.version, actor_public_id=self.actor, correlation_id=self.correlation)
        invoice = transition_invoice(invoice=invoice, status_code="ISSUED", expected_version=invoice.version, actor_public_id=self.approver, correlation_id=self.correlation)
        invoice = transition_invoice(invoice=invoice, status_code="PARTIALLY_PAID", expected_version=invoice.version, actor_public_id=self.operator, correlation_id=self.correlation, paid_amount=Decimal("10000.00"))
        invoice = transition_invoice(invoice=invoice, status_code="PAID", expected_version=invoice.version, actor_public_id=self.operator, correlation_id=self.correlation)
        self.assertEqual(invoice.paid_amount, Decimal("29500.00"))

    def test_tenant_case_sla_and_overview(self):
        case = create_case(
            company=self.company,
            tenant=self.tenant,
            property=self.property,
            unit=self.unit,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
            case_number="CASE_001",
            title="Air conditioning complaint",
            priority_code="HIGH",
        )
        self.assertIsNotNone(case.response_due_at)
        case = transition_case(case=case, status_code="ACKNOWLEDGED", expected_version=case.version, actor_public_id=self.operator, correlation_id=self.correlation)
        case = transition_case(case=case, status_code="IN_PROGRESS", expected_version=case.version, actor_public_id=self.operator, correlation_id=self.correlation)
        case = transition_case(case=case, status_code="RESOLVED", expected_version=case.version, actor_public_id=self.operator, correlation_id=self.correlation)
        case = transition_case(case=case, status_code="CLOSED", expected_version=case.version, actor_public_id=self.operator, correlation_id=self.correlation, satisfaction_score=5)
        payload = property_lease_overview(self.company)
        self.assertEqual(payload["metrics"]["active_properties"], 1)
        self.assertEqual(payload["metrics"]["open_cases"], 0)
