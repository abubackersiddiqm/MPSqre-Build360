from __future__ import annotations

import uuid
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from modules.releaseops.application.selectors import release_overview
from modules.releaseops.models import ReadinessRun
from modules.tenant.models import Company


class ReleaseOverviewRegressionTests(TestCase):
    def setUp(self) -> None:
        self.company = Company.objects.create(
            code="PHASE33_OVERVIEW_TEST",
            legal_name="Phase 33 Overview Test Company",
            display_name="Phase 33 Overview Test",
            locale="en-IN",
            timezone="Asia/Kolkata",
            currency="INR",
            unit_system_code="METRIC",
            fiscal_year_start_month=4,
        )

    def test_overview_counts_failed_runs_without_filtering_a_slice(self) -> None:
        now = timezone.now()
        failed_count = 0
        for index in range(30):
            checks_failed = 1 if index % 3 == 0 else 0
            failed_count += checks_failed
            ReadinessRun.objects.create(
                company=self.company,
                status_code="FAILED" if checks_failed else "PASSED",
                checks_total=1,
                checks_passed=0 if checks_failed else 1,
                checks_failed=checks_failed,
                results=[],
                started_at=now - timedelta(minutes=index),
                completed_at=now - timedelta(minutes=index),
                executed_by_public_id=uuid.uuid4(),
            )

        payload = release_overview(self.company)

        self.assertEqual(payload["metrics"]["failed_readiness_checks"], failed_count)
        self.assertEqual(len(payload["readiness_runs"]), 25)
