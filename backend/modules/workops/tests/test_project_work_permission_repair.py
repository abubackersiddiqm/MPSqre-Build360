from __future__ import annotations

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from modules.identity.models import Permission, Role, RolePermission
from modules.tenant.models import Company

WORK_PERMISSION_CODES = (
    "work.view",
    "work.project.manage",
    "work.plan.manage",
    "work.assign",
    "work.progress",
    "work.time.manage",
    "work.approve",
    "work.configure",
    "work.export",
)


class ProjectWorkPermissionRepairTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            code="REPAIR_TEST",
            legal_name="Repair Test Company",
            display_name="Repair Test Company",
            locale="en-IN",
            timezone="Asia/Kolkata",
            currency="INR",
            unit_system_code="METRIC",
            fiscal_year_start_month=4,
        )
        self.role = Role.objects.create(
            company_public_id=self.company.public_id,
            code="COMPANY_ADMINISTRATOR",
            name="Company Administrator",
            version=1,
            effective_from=timezone.now(),
        )
        for code in WORK_PERMISSION_CODES:
            Permission.objects.update_or_create(
                code=code,
                defaults={
                    "description": code,
                    "data_class": "PROJECT_WORK_MANAGEMENT",
                },
            )

    def test_command_grants_all_work_permissions_to_admin_role(self):
        call_command(
            "grant_project_work_permissions",
            company=self.company.code,
        )
        granted = set(
            RolePermission.objects.filter(role=self.role).values_list(
                "permission__code",
                flat=True,
            )
        )
        self.assertTrue(set(WORK_PERMISSION_CODES).issubset(granted))
