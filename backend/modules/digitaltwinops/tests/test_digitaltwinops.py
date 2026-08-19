import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from modules.digitaltwinops.application.selectors import digital_twin_overview
from modules.digitaltwinops.application.services import (
    create_asset,
    create_clash,
    create_device,
    create_federation,
    create_model,
    create_revision,
    record_telemetry,
    seed_defaults,
    transition_asset,
    transition_clash,
    transition_revision,
)
from modules.tenant.models import Company


class DigitalTwinOpsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            code="TWIN_TEST",
            legal_name="Digital Twin Test Company",
            display_name="Digital Twin Test",
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
        self.model = create_model(
            company=self.company,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
            code="ARC_MAIN",
            name="Architectural authoring model",
            discipline_code="ARCHITECTURE",
            file_format_code="IFC",
        )

    def test_revision_maker_checker_and_publish(self):
        revision = create_revision(
            company=self.company,
            model=self.model,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
            revision_code="P01",
            file_reference="models/arc-p01.ifc",
        )
        revision = transition_revision(
            revision=revision,
            status_code="SUBMITTED",
            expected_version=revision.version,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
        )
        with self.assertRaises(ValidationError):
            transition_revision(
                revision=revision,
                status_code="APPROVED",
                expected_version=revision.version,
                actor_public_id=self.actor,
                correlation_id=self.correlation,
            )
        revision = transition_revision(
            revision=revision,
            status_code="APPROVED",
            expected_version=revision.version,
            actor_public_id=self.approver,
            correlation_id=self.correlation,
        )
        revision = transition_revision(
            revision=revision,
            status_code="PUBLISHED",
            expected_version=revision.version,
            actor_public_id=self.approver,
            correlation_id=self.correlation,
        )
        self.model.refresh_from_db()
        self.assertEqual(self.model.current_revision_code, "P01")
        self.assertEqual(self.model.status_code, "PUBLISHED")

    def test_clash_lifecycle(self):
        federation = create_federation(
            company=self.company,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
            code="FED_001",
            name="Coordination federation",
            model_public_ids=[self.model.public_id],
        )
        clash = create_clash(
            company=self.company,
            federation=federation,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
            clash_number="CL_001",
            discipline_a_code="ARCHITECTURE",
            discipline_b_code="MEP",
            title="Duct intersects beam",
        )
        clash = transition_clash(
            clash=clash,
            status_code="IN_PROGRESS",
            expected_version=clash.version,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
        )
        clash = transition_clash(
            clash=clash,
            status_code="RESOLVED",
            expected_version=clash.version,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
            resolution_note="Duct rerouted.",
        )
        self.assertEqual(clash.status_code, "RESOLVED")

    def test_telemetry_threshold_creates_alert(self):
        device = create_device(
            company=self.company,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
            code="TEMP_01",
            name="Concrete curing temperature",
            device_type_code="TEMPERATURE_SENSOR",
            metric_code="TEMPERATURE",
            unit_code="CELSIUS",
            threshold_configuration={"min": 10, "max": 35, "severity": "HIGH"},
        )
        reading, alert = record_telemetry(
            company=self.company,
            device=device,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
            observed_at=timezone.now(),
            numeric_value=Decimal("42.000000"),
            metric_code="TEMPERATURE",
            unit_code="CELSIUS",
        )
        self.assertIsNotNone(alert)
        payload = digital_twin_overview(self.company)
        self.assertEqual(payload["metrics"]["open_alerts"], 1)
        self.assertEqual(payload["metrics"]["telemetry_readings_24h"], 1)

    def test_handover_asset_maker_checker(self):
        asset = create_asset(
            company=self.company,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
            asset_tag="AHU_001",
            asset_name="Air handling unit",
            classification_code="HVAC",
            model=self.model,
            commissioned_on=date.today(),
            warranty_end_on=date.today() + timedelta(days=365),
        )
        with self.assertRaises(ValidationError):
            transition_asset(
                asset=asset,
                status_code="VERIFIED",
                expected_version=asset.version,
                actor_public_id=self.actor,
                correlation_id=self.correlation,
            )
        asset = transition_asset(
            asset=asset,
            status_code="VERIFIED",
            expected_version=asset.version,
            actor_public_id=self.approver,
            correlation_id=self.correlation,
        )
        self.assertEqual(asset.operation_status_code, "VERIFIED")
