from __future__ import annotations

import uuid
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from modules.stabilityops.application.selectors import stability_overview
from modules.stabilityops.application.services import record_performance_sample, seed_defaults
from modules.stabilityops.models import PerformanceSample, ServiceEndpoint
from modules.tenant.models import Company


class StabilityOverviewTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            code="PH34",
            legal_name="Phase 34 Test Company",
            display_name="Phase 34 Test Company",
            locale="en-IN",
            timezone="Asia/Kolkata",
            currency="INR",
            unit_system_code="METRIC",
            fiscal_year_start_month=4,
        )
        seed_defaults(self.company)

    def test_overview_handles_multiple_samples_without_queryset_reuse_without_queryset_reuse(self):
        endpoint = ServiceEndpoint.objects.filter(company=self.company).first()
        assert endpoint is not None
        observed_at = timezone.now() - timedelta(minutes=1)
        PerformanceSample.objects.bulk_create(
            [
                PerformanceSample(
                    company=self.company,
                    endpoint=endpoint,
                    source_code="PROBE",
                    route_label=endpoint.route_pattern,
                    method_code="GET",
                    http_status=200,
                    duration_ms=(index % 900) + 1,
                    observed_at=observed_at,
                )
                for index in range(60)
            ],
            batch_size=500,
        )
        payload = stability_overview(self.company)
        self.assertEqual(payload["metrics"]["samples_24h"], 60)
        self.assertGreater(payload["metrics"]["api_p95_ms"], 0)

    def test_record_sample_rejects_cross_tenant_endpoint(self):
        other = Company.objects.create(
            code="OTHER34",
            legal_name="Other Company",
            display_name="Other Company",
            locale="en-IN",
            timezone="Asia/Kolkata",
            currency="INR",
            unit_system_code="METRIC",
            fiscal_year_start_month=4,
        )
        endpoint = ServiceEndpoint.objects.filter(company=self.company).first()
        assert endpoint is not None
        with self.assertRaisesMessage(Exception, "cannot cross companies"):
            record_performance_sample(
                company=other,
                endpoint=endpoint,
                source_code="PROBE",
                route_label=endpoint.route_pattern,
                method_code="GET",
                http_status=200,
                duration_ms=10,
                observed_at=timezone.now(),
                request_id=uuid.uuid4(),
                session_fingerprint="",
                metadata={},
            )
