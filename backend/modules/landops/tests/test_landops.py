import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from modules.landops.application.selectors import land_acquisition_overview
from modules.landops.application.services import (
    create_approval,
    create_diligence,
    create_feasibility,
    create_offer,
    create_opportunity,
    create_ownership,
    create_parcel,
    create_risk,
    seed_defaults,
    transition_approval,
    transition_diligence,
    transition_feasibility,
    transition_offer,
    transition_opportunity,
    transition_risk,
    verify_ownership,
)
from modules.tenant.models import Company


class LandAcquisitionOpsTests(TestCase):
    """Traceability: P43-LND-001, P43-DD-001, P43-FEA-001, P43-ACQ-001."""

    def setUp(self):
        self.company = Company.objects.create(
            code="LAND_TEST",
            legal_name="Land Test Company",
            display_name="Land Test",
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
        self.parcel = create_parcel(
            company=self.company,
            actor_public_id=self.creator,
            correlation_id=self.correlation,
            parcel_code="CHENNAI_001",
            name="Chennai Growth Parcel",
            jurisdiction_code="TN_CHENNAI",
            gross_area=Decimal("10000.000"),
            usable_area=Decimal("8500.000"),
            area_unit_code="SQ_M",
        )

    def _cleared_diligence(self):
        case = create_diligence(
            company=self.company,
            parcel=self.parcel,
            actor_public_id=self.creator,
            correlation_id=self.correlation,
            case_number="DD_TITLE_001",
            category_code="TITLE",
            opened_on=date.today(),
            blockers=[],
        )
        case = transition_diligence(case=case, status_code="IN_REVIEW", expected_version=case.version, actor_public_id=self.creator, correlation_id=self.correlation)
        return transition_diligence(case=case, status_code="CLEARED", expected_version=case.version, actor_public_id=self.approver, correlation_id=self.correlation, note="Title chain verified.")

    def _approved_feasibility(self):
        scenario = create_feasibility(
            company=self.company,
            parcel=self.parcel,
            actor_public_id=self.creator,
            correlation_id=self.correlation,
            scenario_code="BASE_01",
            name="Base development case",
            gross_development_area=Decimal("18000.000"),
            saleable_area=Decimal("15000.000"),
            planned_units=120,
            estimated_revenue=Decimal("100000000.00"),
            land_cost=Decimal("20000000.00"),
            construction_cost=Decimal("50000000.00"),
            soft_cost=Decimal("5000000.00"),
            finance_cost=Decimal("3000000.00"),
            contingency_cost=Decimal("2000000.00"),
        )
        scenario = transition_feasibility(scenario=scenario, status_code="SUBMITTED", expected_version=scenario.version, actor_public_id=self.creator, correlation_id=self.correlation)
        with self.assertRaises(ValidationError):
            transition_feasibility(scenario=scenario, status_code="APPROVED", expected_version=scenario.version, actor_public_id=self.creator, correlation_id=self.correlation)
        return transition_feasibility(scenario=scenario, status_code="APPROVED", expected_version=scenario.version, actor_public_id=self.approver, correlation_id=self.correlation, note="Investment committee approved.")

    def test_ownership_share_and_maker_checker(self):
        ownership = create_ownership(
            company=self.company,
            parcel=self.parcel,
            actor_public_id=self.creator,
            correlation_id=self.correlation,
            owner_name="Example Landowner",
            share_percent=Decimal("75.0000"),
        )
        with self.assertRaises(ValidationError):
            verify_ownership(ownership=ownership, status_code="VERIFIED", expected_version=ownership.version, actor_public_id=self.creator, correlation_id=self.correlation)
        ownership = verify_ownership(ownership=ownership, status_code="VERIFIED", expected_version=ownership.version, actor_public_id=self.approver, correlation_id=self.correlation, note="Registry evidence matched.")
        self.assertEqual(ownership.verification_status_code, "VERIFIED")
        with self.assertRaises(ValidationError):
            create_ownership(
                company=self.company,
                parcel=self.parcel,
                actor_public_id=self.creator,
                correlation_id=self.correlation,
                owner_name="Second Landowner",
                share_percent=Decimal("30.0000"),
            )

    def test_diligence_blocker_prevents_clearance(self):
        case = create_diligence(
            company=self.company,
            parcel=self.parcel,
            actor_public_id=self.creator,
            correlation_id=self.correlation,
            case_number="DD_ENV_001",
            category_code="ENVIRONMENTAL",
            blockers=[{"code": "WETLAND_CONFIRMATION", "severity": "HIGH"}],
        )
        case = transition_diligence(case=case, status_code="IN_REVIEW", expected_version=case.version, actor_public_id=self.creator, correlation_id=self.correlation)
        with self.assertRaises(ValidationError):
            transition_diligence(case=case, status_code="CLEARED", expected_version=case.version, actor_public_id=self.approver, correlation_id=self.correlation)

    def test_feasibility_margin_is_calculated(self):
        scenario = self._approved_feasibility()
        self.assertEqual(scenario.projected_margin_percent, Decimal("20.0000"))
        self.assertEqual(scenario.status_code, "APPROVED")

    def test_acquisition_completion_requires_offer_and_approvals(self):
        self._cleared_diligence()
        scenario = self._approved_feasibility()
        opportunity = create_opportunity(
            company=self.company,
            parcel=self.parcel,
            feasibility=scenario,
            actor_public_id=self.creator,
            correlation_id=self.correlation,
            opportunity_code="ACQ_001",
            seller_name="Example Landowner",
            asking_price=Decimal("23000000.00"),
            target_price=Decimal("21000000.00"),
            probability_percent=Decimal("60.0000"),
            expected_close_on=date.today() + timedelta(days=90),
        )
        for stage in ("SCREENING", "DUE_DILIGENCE", "NEGOTIATION"):
            opportunity = transition_opportunity(opportunity=opportunity, status_code=stage, expected_version=opportunity.version, actor_public_id=self.creator, correlation_id=self.correlation)
        offer = create_offer(
            company=self.company,
            opportunity=opportunity,
            actor_public_id=self.creator,
            correlation_id=self.correlation,
            offer_number="OFFER_001",
            offer_date=date.today(),
            amount=Decimal("21000000.00"),
            validity_until=date.today() + timedelta(days=30),
        )
        offer = transition_offer(offer=offer, status_code="SUBMITTED", expected_version=offer.version, actor_public_id=self.creator, correlation_id=self.correlation)
        with self.assertRaises(ValidationError):
            transition_offer(offer=offer, status_code="APPROVED", expected_version=offer.version, actor_public_id=self.creator, correlation_id=self.correlation)
        offer = transition_offer(offer=offer, status_code="APPROVED", expected_version=offer.version, actor_public_id=self.approver, correlation_id=self.correlation)
        offer = transition_offer(offer=offer, status_code="ISSUED", expected_version=offer.version, actor_public_id=self.approver, correlation_id=self.correlation)
        offer = transition_offer(offer=offer, status_code="ACCEPTED", expected_version=offer.version, actor_public_id=self.approver, correlation_id=self.correlation)
        approval = create_approval(
            company=self.company,
            parcel=self.parcel,
            opportunity=opportunity,
            actor_public_id=self.creator,
            correlation_id=self.correlation,
            approval_code="LAND_USE_001",
            approval_type_code="LAND_USE_CONVERSION",
            authority_name="Planning Authority",
            mandatory_for_acquisition=True,
        )
        approval = transition_approval(approval=approval, status_code="SUBMITTED", expected_version=approval.version, actor_public_id=self.creator, correlation_id=self.correlation)
        approval = transition_approval(approval=approval, status_code="APPROVED", expected_version=approval.version, actor_public_id=self.approver, correlation_id=self.correlation)
        opportunity = transition_opportunity(opportunity=opportunity, status_code="APPROVED", expected_version=opportunity.version, actor_public_id=self.approver, correlation_id=self.correlation)
        opportunity = transition_opportunity(opportunity=opportunity, status_code="ACQUIRED", expected_version=opportunity.version, actor_public_id=self.approver, correlation_id=self.correlation)
        self.parcel.refresh_from_db()
        self.assertEqual(opportunity.stage_code, "ACQUIRED")
        self.assertEqual(self.parcel.status_code, "ACQUIRED")

    def test_critical_risk_blocks_acquisition_approval(self):
        self._cleared_diligence()
        scenario = self._approved_feasibility()
        opportunity = create_opportunity(
            company=self.company,
            parcel=self.parcel,
            feasibility=scenario,
            actor_public_id=self.creator,
            correlation_id=self.correlation,
            opportunity_code="ACQ_RISK_001",
            seller_name="Example Landowner",
        )
        for stage in ("SCREENING", "DUE_DILIGENCE", "NEGOTIATION"):
            opportunity = transition_opportunity(opportunity=opportunity, status_code=stage, expected_version=opportunity.version, actor_public_id=self.creator, correlation_id=self.correlation)
        risk = create_risk(
            company=self.company,
            parcel=self.parcel,
            opportunity=opportunity,
            actor_public_id=self.creator,
            correlation_id=self.correlation,
            risk_number="RISK_001",
            severity_code="CRITICAL",
            title="Unresolved access right",
        )
        with self.assertRaises(ValidationError):
            transition_opportunity(opportunity=opportunity, status_code="APPROVED", expected_version=opportunity.version, actor_public_id=self.approver, correlation_id=self.correlation)
        risk = transition_risk(risk=risk, status_code="ACCEPTED", expected_version=risk.version, actor_public_id=self.approver, correlation_id=self.correlation, note="Board accepted residual risk with legal indemnity.")
        opportunity = transition_opportunity(opportunity=opportunity, status_code="APPROVED", expected_version=opportunity.version, actor_public_id=self.approver, correlation_id=self.correlation)
        self.assertEqual(risk.status_code, "ACCEPTED")
        self.assertEqual(opportunity.stage_code, "APPROVED")

    def test_overview_reports_pipeline_position(self):
        payload = land_acquisition_overview(self.company)
        self.assertEqual(payload["metrics"]["active_parcels"], 1)
        self.assertEqual(payload["metrics"]["pipeline_opportunities"], 0)
        self.assertEqual(payload["policy"]["due_diligence_target_days"], 45)
        self.assertEqual(payload["portfolio"]["area_by_unit"][0]["area_unit_code"], "SQ_M")
