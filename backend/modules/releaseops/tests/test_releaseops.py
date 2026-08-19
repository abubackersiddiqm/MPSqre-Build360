import uuid

from django.core.exceptions import ValidationError
from django.test import TestCase

from modules.releaseops.application.services import create_release, create_target, seed_uat_library
from modules.releaseops.models import ReleaseCandidate, ReleaseGate, UATExecution, UATScenario
from modules.tenant.models import Company


class ReleaseOpsModelTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            code="PHASE33_TEST",
            legal_name="Phase 33 Test Company",
            display_name="Phase 33 Test",
            locale="en-IN",
            timezone="Asia/Kolkata",
            currency="INR",
            unit_system_code="METRIC",
            fiscal_year_start_month=4,
        )
        self.actor = uuid.uuid4()
        self.correlation = uuid.uuid4()

    def test_seed_library_is_idempotent(self):
        first = seed_uat_library(self.company)
        second = seed_uat_library(self.company)
        self.assertEqual(first, 28)
        self.assertEqual(second, 0)
        self.assertEqual(UATScenario.objects.filter(company=self.company).count(), 28)

    def test_release_creation_builds_governance_pack(self):
        target = create_target(
            company=self.company,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
            code="PROD",
            name="Production",
            environment_code="PRODUCTION",
            frontend_url="https://app.example.com",
            backend_url="https://api.example.com",
            health_url="https://api.example.com/api/v1/health/ready",
        )
        release = create_release(
            company=self.company,
            target=target,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
            release_code="BUILD360_V1",
            title="Build360 v1",
            version_label="v1.0.0",
        )
        self.assertEqual(ReleaseGate.objects.filter(release=release).count(), 11)
        self.assertEqual(UATExecution.objects.filter(release=release).count(), 28)

    def test_release_target_cannot_cross_company(self):
        other = Company.objects.create(
            code="OTHER_PHASE33",
            legal_name="Other",
            display_name="Other",
            locale="en-IN",
            timezone="Asia/Kolkata",
            currency="INR",
            unit_system_code="METRIC",
            fiscal_year_start_month=4,
        )
        target = create_target(
            company=other,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
            code="PROD",
            name="Production",
            environment_code="PRODUCTION",
            frontend_url="https://other.example.com",
            backend_url="https://other-api.example.com",
        )
        release = ReleaseCandidate(
            company=self.company,
            target=target,
            release_code="INVALID",
            title="Invalid",
            created_by_public_id=self.actor,
        )
        with self.assertRaises(ValidationError):
            release.full_clean()
