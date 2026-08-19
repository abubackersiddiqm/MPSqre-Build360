import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from modules.sustainabilityops.application.selectors import sustainability_overview
from modules.sustainabilityops.application.services import (
    create_assessment,
    create_factor,
    create_inventory,
    create_target,
    record_activity,
    record_resource,
    seed_defaults,
    transition_activity,
    transition_assessment,
    transition_inventory,
    transition_target,
)
from modules.tenant.models import Company


class SustainabilityOpsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            code="SUS_TEST",
            legal_name="Sustainability Test Company",
            display_name="Sustainability Test",
            timezone="Asia/Kolkata",
            currency="INR",
            locale="en-IN",
            unit_system_code="METRIC",
            fiscal_year_start_month=4,
        )
        self.actor = uuid.uuid4()
        self.approver = uuid.uuid4()
        self.correlation = uuid.uuid4()
        seed_defaults(self.company)
        self.factor = create_factor(
            company=self.company,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
            code="TEST_DIESEL",
            name="Test diesel factor",
            category_code="MOBILE_COMBUSTION",
            scope_code="SCOPE_1",
            activity_unit_code="LITRE",
            factor_kg_co2e_per_unit=Decimal("2.50000000"),
            source_name="Test source",
            valid_from=date.today() - timedelta(days=30),
        )

    def test_activity_calculation_and_maker_checker(self):
        activity = record_activity(
            company=self.company,
            factor=self.factor,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
            activity_date=date.today(),
            quantity=Decimal("10.0000"),
            activity_unit_code="LITRE",
        )
        self.assertEqual(activity.calculated_kg_co2e, Decimal("25.0000"))
        with self.assertRaises(ValidationError):
            transition_activity(
                activity=activity,
                status_code="VERIFIED",
                expected_version=activity.version,
                actor_public_id=self.actor,
                correlation_id=self.correlation,
            )
        activity = transition_activity(
            activity=activity,
            status_code="VERIFIED",
            expected_version=activity.version,
            actor_public_id=self.approver,
            correlation_id=self.correlation,
        )
        self.assertEqual(activity.status_code, "VERIFIED")

    def test_inventory_aggregates_verified_activities(self):
        activity = record_activity(
            company=self.company,
            factor=self.factor,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
            activity_date=date.today(),
            quantity=Decimal("4.0000"),
            activity_unit_code="LITRE",
        )
        activity = transition_activity(
            activity=activity,
            status_code="VERIFIED",
            expected_version=activity.version,
            actor_public_id=self.approver,
            correlation_id=self.correlation,
        )
        inventory = create_inventory(
            company=self.company,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
            code="INV-001",
            period_start=date.today() - timedelta(days=1),
            period_end=date.today(),
            offsets_kg_co2e=Decimal("1.0000"),
        )
        self.assertEqual(inventory.scope1_kg_co2e, Decimal("10.0000"))
        self.assertEqual(inventory.net_kg_co2e, Decimal("9.0000"))
        inventory = transition_inventory(
            inventory=inventory,
            status_code="IN_REVIEW",
            expected_version=inventory.version,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
        )
        with self.assertRaises(ValidationError):
            transition_inventory(
                inventory=inventory,
                status_code="APPROVED",
                expected_version=inventory.version,
                actor_public_id=self.actor,
                correlation_id=self.correlation,
            )


    def test_renewable_energy_is_quantity_weighted(self):
        record_resource(
            company=self.company,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
            resource_type_code="ENERGY",
            resource_subtype_code="GRID",
            period_start=date.today(),
            period_end=date.today(),
            quantity=Decimal("100.0000"),
            unit_code="KWH",
            renewable_percent=Decimal("25.00"),
            cost_amount=Decimal("0.00"),
            currency="INR",
        )
        record_resource(
            company=self.company,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
            resource_type_code="ENERGY",
            resource_subtype_code="SOLAR",
            period_start=date.today(),
            period_end=date.today(),
            quantity=Decimal("50.0000"),
            unit_code="KWH",
            renewable_percent=Decimal("100.00"),
            cost_amount=Decimal("0.00"),
            currency="INR",
        )
        payload = sustainability_overview(self.company)
        self.assertEqual(payload["metrics"]["energy_kwh"], "150.00")
        self.assertEqual(payload["metrics"]["renewable_energy_percent"], "50.00")

    def test_target_and_assurance_controls(self):
        target = create_target(
            company=self.company,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
            code="CARBON-2030",
            name="Reduce operational carbon",
            category_code="CARBON",
            metric_unit_code="TCO2E",
            direction_code="REDUCE",
            baseline_value=Decimal("100.0000"),
            target_value=Decimal("70.0000"),
            start_date=date.today(),
            target_date=date.today() + timedelta(days=365),
        )
        target = transition_target(
            target=target,
            status_code="ACTIVE",
            expected_version=target.version,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
            latest_value=Decimal("90.0000"),
            progress_percent=Decimal("33.33"),
        )
        self.assertEqual(target.status_code, "ACTIVE")
        assessment = create_assessment(
            company=self.company,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
            code="ASSURE-001",
            assessment_type_code="INTERNAL_AUDIT",
            framework_code="GHG_PROTOCOL",
            period_start=date.today() - timedelta(days=30),
            period_end=date.today(),
            findings_total=1,
            major_findings=1,
        )
        assessment = transition_assessment(
            assessment=assessment,
            status_code="IN_REVIEW",
            expected_version=assessment.version,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
        )
        with self.assertRaises(ValidationError):
            transition_assessment(
                assessment=assessment,
                status_code="APPROVED",
                expected_version=assessment.version,
                actor_public_id=self.actor,
                correlation_id=self.correlation,
            )
        payload = sustainability_overview(self.company)
        self.assertEqual(payload["metrics"]["active_targets"], 1)
