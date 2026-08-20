from __future__ import annotations

import uuid
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from modules.accessops.application.services import (
    STANDARD_COMPANY_ADMIN_ROLE_CODE,
    STANDARD_COMPANY_USER_ROLE_CODE,
    assign_membership_role,
    transfer_primary_company_admin,
)
from modules.accessops.models import CompanyAccessProfile
from modules.identity.models import Role, User
from modules.tenant.models import Company, Membership


class PrimaryAdminTransferTests(TestCase):
    def setUp(self) -> None:
        now = timezone.now()
        self.company = Company.objects.create(
            code="ADMTR",
            legal_name="Admin Transfer Test Pvt Ltd",
            display_name="Admin Transfer Test",
            locale="en-IN",
            timezone="Asia/Kolkata",
            currency="INR",
            unit_system_code="METRIC",
            fiscal_year_start_month=4,
            is_active=True,
        )
        self.old_user = User.objects.create_user(
            email="old.admin@example.com",
            password="OldAdmin@2026",
            display_name="Old Admin",
        )
        self.new_user = User.objects.create_user(
            email="new.admin@example.com",
            password="NewAdmin@2026",
            display_name="New Admin",
        )
        self.old_membership = Membership.objects.create(
            company=self.company,
            user=self.old_user,
            effective_from=now - timedelta(days=10),
        )
        self.new_membership = Membership.objects.create(
            company=self.company,
            user=self.new_user,
            effective_from=now - timedelta(days=5),
        )
        self.admin_role = Role.objects.create(
            company_public_id=self.company.public_id,
            code=STANDARD_COMPANY_ADMIN_ROLE_CODE,
            name="Company Administrator",
            version=1,
            effective_from=now - timedelta(days=10),
        )
        self.user_role = Role.objects.create(
            company_public_id=self.company.public_id,
            code=STANDARD_COMPANY_USER_ROLE_CODE,
            name="Company User",
            version=1,
            effective_from=now - timedelta(days=10),
        )
        CompanyAccessProfile.objects.create(
            company=self.company,
            plan_code="CRM_ONLY",
            onboarding_status_code="ADMIN_ACTIVE",
            primary_admin_email=self.old_user.email,
            created_by_public_id=self.old_user.public_id,
            activated_at=now - timedelta(days=9),
        )
        assign_membership_role(
            membership=self.old_membership,
            role=self.admin_role,
            assigned_by_public_id=self.old_user.public_id,
            correlation_id=uuid.uuid4(),
        )
        assign_membership_role(
            membership=self.old_membership,
            role=self.user_role,
            assigned_by_public_id=self.old_user.public_id,
            correlation_id=uuid.uuid4(),
        )
        assign_membership_role(
            membership=self.new_membership,
            role=self.user_role,
            assigned_by_public_id=self.old_user.public_id,
            correlation_id=uuid.uuid4(),
        )

    def test_transfer_promotes_target_and_demotes_previous_primary_only(self) -> None:
        result = transfer_primary_company_admin(
            company=self.company,
            membership=self.new_membership,
            actor_public_id=self.old_user.public_id,
            correlation_id=uuid.uuid4(),
            reason_code="support-request",
        )
        self.assertTrue(result["changed"])
        profile = CompanyAccessProfile.objects.get(company=self.company)
        self.assertEqual(profile.primary_admin_email, self.new_user.email)
        self.assertTrue(
            self.new_membership.role_assignments.filter(
                role_public_id=self.admin_role.public_id,
                effective_to__isnull=True,
            ).exists()
        )
        self.assertFalse(
            self.old_membership.role_assignments.filter(
                role_public_id=self.admin_role.public_id,
                effective_to__isnull=True,
            ).exists()
        )
        self.assertTrue(
            self.old_membership.role_assignments.filter(
                role_public_id=self.user_role.public_id,
                effective_to__isnull=True,
            ).exists()
        )

    def test_transfer_to_current_primary_is_idempotent(self) -> None:
        result = transfer_primary_company_admin(
            company=self.company,
            membership=self.old_membership,
            actor_public_id=self.old_user.public_id,
            correlation_id=uuid.uuid4(),
            reason_code="no-change",
        )
        self.assertFalse(result["changed"])
