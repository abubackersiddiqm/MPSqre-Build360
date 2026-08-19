from __future__ import annotations

import uuid
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from modules.goliveops.application.selectors import go_live_overview
from modules.goliveops.application.services import (
    create_go_live_wave,
    create_migration_issue,
    seed_defaults,
    transition_go_live_wave,
)
from modules.goliveops.models import GoLiveGate, MigrationBatch
from modules.tenant.models import Company


class GoLiveOperationsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            code="PH35",
            legal_name="Phase 35 Test Company",
            display_name="Phase 35 Test Company",
            locale="en-IN",
            timezone="Asia/Kolkata",
            currency="INR",
            unit_system_code="METRIC",
            fiscal_year_start_month=4,
        )
        seed_defaults(self.company)

    def test_overview_handles_more_than_page_size_without_queryset_reuse(self):
        actor = uuid.uuid4()
        MigrationBatch.objects.bulk_create([
            MigrationBatch(
                company=self.company,
                code=f"BATCH_{index:03d}",
                entity_code="EMPLOYEE",
                source_file_name=f"employees-{index}.csv",
                dry_run=True,
                total_rows=10,
                valid_rows=10,
                invalid_rows=0,
                warning_rows=0,
                created_by_public_id=actor,
            )
            for index in range(40)
        ])
        payload = go_live_overview(self.company)
        self.assertEqual(payload["metrics"]["migration_batches"], 40)
        self.assertEqual(len(payload["migration_batches"]), 20)
        self.assertEqual(payload["metrics"]["migration_pass_percent"], 100.0)

    def test_migration_issue_rejects_cross_tenant_batch(self):
        other = Company.objects.create(
            code="OTHER35",
            legal_name="Other Company",
            display_name="Other Company",
            locale="en-IN",
            timezone="Asia/Kolkata",
            currency="INR",
            unit_system_code="METRIC",
            fiscal_year_start_month=4,
        )
        batch = MigrationBatch.objects.create(
            company=self.company,
            code="EMPLOYEE_01",
            entity_code="EMPLOYEE",
            source_file_name="employees.csv",
            total_rows=1,
            created_by_public_id=uuid.uuid4(),
        )
        with self.assertRaisesMessage(ValidationError, "cannot cross companies"):
            create_migration_issue(
                company=other,
                batch=batch,
                actor_public_id=uuid.uuid4(),
                correlation_id=uuid.uuid4(),
                row_number=1,
                field_name="email",
                severity_code="ERROR",
                issue_code="INVALID_EMAIL",
                message="Invalid email",
                raw_value="bad",
            )

    def test_wave_requires_independent_approval(self):
        creator = uuid.uuid4()
        wave = create_go_live_wave(
            company=self.company,
            plan=None,
            actor_public_id=creator,
            correlation_id=uuid.uuid4(),
            code="WAVE_1",
            name="First production wave",
            scope={"companies": ["PH35"]},
            planned_at=timezone.now() + timedelta(days=1),
        )
        wave.status_code = "READY"
        wave.version += 1
        wave.save(update_fields=["status_code", "version", "updated_at"])
        GoLiveGate.objects.filter(company=self.company).update(status_code="PASSED")
        with self.assertRaisesMessage(ValidationError, "creator cannot approve"):
            transition_go_live_wave(
                wave=wave,
                status_code="APPROVED",
                expected_version=wave.version,
                actor_public_id=creator,
                correlation_id=uuid.uuid4(),
            )
