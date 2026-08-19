import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from modules.facilityops.application.selectors import facility_overview
from modules.facilityops.application.services import (
    create_asset,
    create_facility,
    create_inspection,
    create_plan,
    create_service_request,
    create_warranty_claim,
    create_work_order,
    seed_defaults,
    transition_asset,
    transition_inspection,
    transition_service_request,
    transition_warranty_claim,
    transition_work_order,
)
from modules.tenant.models import Company


class FacilityOpsTests(TestCase):
    """Traceability: P40-FAC-001, P40-AST-001, P40-MNT-001, P40-WAR-001."""

    def setUp(self):
        self.company = Company.objects.create(
            code="FAC_TEST",
            legal_name="Facilities Test Company",
            display_name="Facilities Test",
            timezone="Asia/Kolkata",
            currency="INR",
            locale="en-IN",
            unit_system_code="METRIC",
            fiscal_year_start_month=4,
        )
        self.actor = uuid.uuid4()
        self.approver = uuid.uuid4()
        self.technician = uuid.uuid4()
        self.correlation = uuid.uuid4()
        seed_defaults(self.company)
        self.facility = create_facility(
            company=self.company,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
            code="HQ_01",
            name="Head office",
        )
        self.asset = create_asset(
            company=self.company,
            facility=self.facility,
            space=None,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
            asset_tag="AHU_001",
            asset_name="Air handling unit",
            classification_code="HVAC",
            commissioned_on=date.today(),
            warranty_start_on=date.today(),
            warranty_end_on=date.today() + timedelta(days=365),
            service_interval_days=90,
        )

    def test_asset_maker_checker_and_lifecycle(self):
        with self.assertRaises(ValidationError):
            transition_asset(
                asset=self.asset,
                status_code="VERIFIED",
                expected_version=self.asset.version,
                actor_public_id=self.actor,
                correlation_id=self.correlation,
            )
        self.asset = transition_asset(
            asset=self.asset,
            status_code="VERIFIED",
            expected_version=self.asset.version,
            actor_public_id=self.approver,
            correlation_id=self.correlation,
        )
        self.asset = transition_asset(
            asset=self.asset,
            status_code="IN_SERVICE",
            expected_version=self.asset.version,
            actor_public_id=self.approver,
            correlation_id=self.correlation,
        )
        self.assertEqual(self.asset.operation_status_code, "IN_SERVICE")
        self.assertEqual(self.asset.lifecycle_events.count(), 2)

    def test_service_request_sla_and_resolution(self):
        request_item = create_service_request(
            company=self.company,
            facility=self.facility,
            space=None,
            asset=self.asset,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
            request_number="SR_001",
            title="Cooling unavailable",
            priority_code="HIGH",
        )
        self.assertIsNotNone(request_item.response_due_at)
        request_item = transition_service_request(
            request_item=request_item,
            status_code="ACKNOWLEDGED",
            expected_version=request_item.version,
            actor_public_id=self.technician,
            correlation_id=self.correlation,
        )
        request_item = transition_service_request(
            request_item=request_item,
            status_code="IN_PROGRESS",
            expected_version=request_item.version,
            actor_public_id=self.technician,
            correlation_id=self.correlation,
        )
        request_item = transition_service_request(
            request_item=request_item,
            status_code="RESOLVED",
            expected_version=request_item.version,
            actor_public_id=self.technician,
            correlation_id=self.correlation,
        )
        self.assertEqual(request_item.status_code, "RESOLVED")

    def test_work_order_maker_checker_and_service_dates(self):
        plan = create_plan(
            company=self.company,
            asset=self.asset,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
            code="PM_AHU_90",
            name="Quarterly AHU service",
            frequency_days=90,
            next_due_date=date.today(),
        )
        work_order = create_work_order(
            company=self.company,
            asset=self.asset,
            plan=plan,
            service_request=None,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
            work_order_number="WO_001",
            title="Quarterly preventive maintenance",
            assigned_to_public_id=self.technician,
            due_date=date.today(),
        )
        work_order = transition_work_order(work_order=work_order, status_code="SUBMITTED", expected_version=work_order.version, actor_public_id=self.actor, correlation_id=self.correlation)
        with self.assertRaises(ValidationError):
            transition_work_order(work_order=work_order, status_code="APPROVED", expected_version=work_order.version, actor_public_id=self.actor, correlation_id=self.correlation)
        work_order = transition_work_order(work_order=work_order, status_code="APPROVED", expected_version=work_order.version, actor_public_id=self.approver, correlation_id=self.correlation)
        work_order = transition_work_order(work_order=work_order, status_code="IN_PROGRESS", expected_version=work_order.version, actor_public_id=self.technician, correlation_id=self.correlation)
        work_order = transition_work_order(work_order=work_order, status_code="COMPLETED", expected_version=work_order.version, actor_public_id=self.technician, correlation_id=self.correlation, completion_evidence={"checklist": "complete"})
        with self.assertRaises(ValidationError):
            transition_work_order(work_order=work_order, status_code="VERIFIED", expected_version=work_order.version, actor_public_id=self.technician, correlation_id=self.correlation)
        work_order = transition_work_order(work_order=work_order, status_code="VERIFIED", expected_version=work_order.version, actor_public_id=self.approver, correlation_id=self.correlation)
        work_order = transition_work_order(work_order=work_order, status_code="CLOSED", expected_version=work_order.version, actor_public_id=self.approver, correlation_id=self.correlation)
        self.asset.refresh_from_db()
        plan.refresh_from_db()
        self.assertEqual(self.asset.last_service_on, date.today())
        self.assertEqual(plan.next_due_date, date.today() + timedelta(days=90))

    def test_warranty_and_inspection_maker_checker(self):
        claim = create_warranty_claim(
            company=self.company,
            asset=self.asset,
            work_order=None,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
            claim_number="WC_001",
            reported_on=date.today(),
            issue_description="Compressor failure",
            claimed_amount=Decimal("25000.00"),
        )
        claim = transition_warranty_claim(claim=claim, status_code="FILED", expected_version=claim.version, actor_public_id=self.actor, correlation_id=self.correlation)
        claim = transition_warranty_claim(claim=claim, status_code="UNDER_REVIEW", expected_version=claim.version, actor_public_id=self.approver, correlation_id=self.correlation)
        with self.assertRaises(ValidationError):
            transition_warranty_claim(claim=claim, status_code="APPROVED", expected_version=claim.version, actor_public_id=self.actor, correlation_id=self.correlation)
        claim = transition_warranty_claim(claim=claim, status_code="APPROVED", expected_version=claim.version, actor_public_id=self.approver, correlation_id=self.correlation, approved_amount=Decimal("20000.00"))
        self.assertEqual(claim.status_code, "APPROVED")

        inspection = create_inspection(
            company=self.company,
            facility=self.facility,
            space=None,
            asset=self.asset,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
            inspection_number="CI_001",
            inspected_on=date.today(),
            condition_code="FAIR",
            score=Decimal("65.00"),
        )
        inspection = transition_inspection(inspection=inspection, status_code="SUBMITTED", expected_version=inspection.version, actor_public_id=self.actor, correlation_id=self.correlation)
        with self.assertRaises(ValidationError):
            transition_inspection(inspection=inspection, status_code="VERIFIED", expected_version=inspection.version, actor_public_id=self.actor, correlation_id=self.correlation)
        inspection = transition_inspection(inspection=inspection, status_code="VERIFIED", expected_version=inspection.version, actor_public_id=self.approver, correlation_id=self.correlation)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.condition_code, "FAIR")
        payload = facility_overview(self.company)
        self.assertEqual(payload["metrics"]["active_facilities"], 1)
