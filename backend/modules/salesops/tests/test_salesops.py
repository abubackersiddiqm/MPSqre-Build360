import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from modules.salesops.application.selectors import development_sales_overview
from modules.salesops.application.services import (
    create_booking,
    create_buyer,
    create_handover,
    create_inventory,
    create_milestone,
    create_receipt,
    create_reservation,
    create_unit,
    seed_defaults,
    transition_booking,
    transition_handover,
    transition_receipt,
)
from modules.tenant.models import Company


class DevelopmentSalesOpsTests(TestCase):
    """Traceability: P42-INV-001, P42-BKG-001, P42-COL-001, P42-HND-001."""

    def setUp(self):
        self.company = Company.objects.create(
            code="SALES_TEST",
            legal_name="Sales Test Company",
            display_name="Sales Test",
            timezone="Asia/Kolkata",
            currency="INR",
            locale="en-IN",
            unit_system_code="METRIC",
            fiscal_year_start_month=4,
        )
        self.creator = uuid.uuid4()
        self.approver = uuid.uuid4()
        self.collector = uuid.uuid4()
        self.correlation = uuid.uuid4()
        seed_defaults(self.company)
        self.inventory = create_inventory(
            company=self.company,
            actor_public_id=self.creator,
            correlation_id=self.correlation,
            code="GREEN_RESIDENCES",
            name="Green Residences",
            status_code="LAUNCHED",
        )
        self.unit = create_unit(
            company=self.company,
            inventory=self.inventory,
            actor_public_id=self.creator,
            correlation_id=self.correlation,
            code="A_101",
            name="Apartment A-101",
            list_price=Decimal("5000000.00"),
            status_code="AVAILABLE",
        )
        self.buyer = create_buyer(
            company=self.company,
            actor_public_id=self.creator,
            correlation_id=self.correlation,
            account_code="BUYER_001",
            legal_name="Example Buyer",
            display_name="Example Buyer",
        )
        self.reservation = create_reservation(
            company=self.company,
            unit=self.unit,
            buyer=self.buyer,
            actor_public_id=self.creator,
            correlation_id=self.correlation,
            reservation_number="RES_001",
            token_amount=Decimal("100000.00"),
        )
        self.booking = create_booking(
            company=self.company,
            unit=self.unit,
            buyer=self.buyer,
            reservation=self.reservation,
            actor_public_id=self.creator,
            correlation_id=self.correlation,
            booking_number="BOOK_001",
            booking_date=date.today(),
            base_price=Decimal("5000000.00"),
            discount_amount=Decimal("100000.00"),
            tax_amount=Decimal("250000.00"),
            other_charges=Decimal("50000.00"),
            total_consideration=Decimal("5200000.00"),
        )

    def test_booking_maker_checker_and_inventory_status(self):
        self.booking = transition_booking(booking=self.booking, status_code="SUBMITTED", expected_version=self.booking.version, actor_public_id=self.creator, correlation_id=self.correlation)
        with self.assertRaises(ValidationError):
            transition_booking(booking=self.booking, status_code="APPROVED", expected_version=self.booking.version, actor_public_id=self.creator, correlation_id=self.correlation)
        self.booking = transition_booking(booking=self.booking, status_code="APPROVED", expected_version=self.booking.version, actor_public_id=self.approver, correlation_id=self.correlation)
        self.unit.refresh_from_db()
        self.reservation.refresh_from_db()
        self.assertEqual(self.unit.status_code, "BOOKED")
        self.assertEqual(self.reservation.status_code, "CONVERTED")

    def test_overlapping_reservation_is_blocked(self):
        self.unit.status_code = "AVAILABLE"
        self.unit.save(update_fields=["status_code"])
        with self.assertRaises(ValidationError):
            create_reservation(
                company=self.company,
                unit=self.unit,
                buyer=self.buyer,
                actor_public_id=self.creator,
                correlation_id=self.correlation,
                reservation_number="RES_002",
            )

    def test_receipt_confirmation_updates_milestone(self):
        self.booking = transition_booking(booking=self.booking, status_code="SUBMITTED", expected_version=self.booking.version, actor_public_id=self.creator, correlation_id=self.correlation)
        self.booking = transition_booking(booking=self.booking, status_code="APPROVED", expected_version=self.booking.version, actor_public_id=self.approver, correlation_id=self.correlation)
        milestone = create_milestone(
            company=self.company,
            booking=self.booking,
            actor_public_id=self.creator,
            correlation_id=self.correlation,
            sequence=1,
            milestone_code="BOOKING",
            description="Booking milestone",
            due_on=date.today(),
            amount=Decimal("1000000.00"),
            tax_amount=Decimal("50000.00"),
        )
        receipt = create_receipt(
            company=self.company,
            booking=self.booking,
            milestone=milestone,
            actor_public_id=self.collector,
            correlation_id=self.correlation,
            receipt_number="RCT_001",
            receipt_date=date.today(),
            amount=Decimal("1050000.00"),
        )
        receipt = transition_receipt(receipt=receipt, status_code="SUBMITTED", expected_version=receipt.version, actor_public_id=self.collector, correlation_id=self.correlation)
        with self.assertRaises(ValidationError):
            transition_receipt(receipt=receipt, status_code="CONFIRMED", expected_version=receipt.version, actor_public_id=self.collector, correlation_id=self.correlation)
        receipt = transition_receipt(receipt=receipt, status_code="CONFIRMED", expected_version=receipt.version, actor_public_id=self.approver, correlation_id=self.correlation)
        milestone.refresh_from_db()
        self.assertEqual(milestone.status_code, "PAID")
        self.assertEqual(milestone.paid_amount, Decimal("1050000.00"))

    def test_handover_maker_checker(self):
        self.booking = transition_booking(booking=self.booking, status_code="SUBMITTED", expected_version=self.booking.version, actor_public_id=self.creator, correlation_id=self.correlation)
        self.booking = transition_booking(booking=self.booking, status_code="APPROVED", expected_version=self.booking.version, actor_public_id=self.approver, correlation_id=self.correlation)
        self.booking = transition_booking(booking=self.booking, status_code="ACTIVE", expected_version=self.booking.version, actor_public_id=self.approver, correlation_id=self.correlation)
        handover = create_handover(
            company=self.company,
            booking=self.booking,
            unit=self.unit,
            actor_public_id=self.creator,
            correlation_id=self.correlation,
            planned_on=date.today() + timedelta(days=30),
            open_defect_count=0,
        )
        handover = transition_handover(handover=handover, status_code="READINESS_REVIEW", expected_version=handover.version, actor_public_id=self.creator, correlation_id=self.correlation)
        with self.assertRaises(ValidationError):
            transition_handover(handover=handover, status_code="READY", expected_version=handover.version, actor_public_id=self.creator, correlation_id=self.correlation)
        handover = transition_handover(handover=handover, status_code="READY", expected_version=handover.version, actor_public_id=self.approver, correlation_id=self.correlation)
        handover = transition_handover(handover=handover, status_code="OFFERED", expected_version=handover.version, actor_public_id=self.approver, correlation_id=self.correlation)
        handover = transition_handover(handover=handover, status_code="POSSESSED", expected_version=handover.version, actor_public_id=self.approver, correlation_id=self.correlation)
        self.booking.refresh_from_db()
        self.unit.refresh_from_db()
        self.assertEqual(self.booking.status_code, "HANDED_OVER")
        self.assertEqual(self.unit.status_code, "HANDED_OVER")

    def test_overview_reports_commercial_position(self):
        payload = development_sales_overview(self.company)
        self.assertEqual(payload["metrics"]["active_developments"], 1)
        self.assertEqual(payload["metrics"]["reserved_units"], 1)
        self.assertEqual(payload["metrics"]["booking_value"], "0")
        self.assertEqual(payload["policy"]["reservation_expiry_hours"], 72)
