from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from modules.collabops.application.selectors import internal_overview
from modules.collabops.application.services import create_collaboration_item, create_partner
from modules.collabops.models import PartnerContact, ProjectAccessGrant
from modules.identity.models import User
from modules.tenant.models import Company, Membership
from modules.workops.models import Project


class CollaborationOpsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            code="COLLABTEST",
            legal_name="Collaboration Test Private Limited",
            display_name="Collaboration Test",
            locale="en-IN",
            timezone="Asia/Kolkata",
            currency="INR",
            unit_system_code="METRIC",
            fiscal_year_start_month=4,
        )
        self.user = User.objects.create_user(
            email="admin@example.com",
            password="StrongPassword123",
            display_name="Company Administrator",
        )
        self.membership = Membership.objects.create(company=self.company, user=self.user, effective_from=timezone.now())
        self.project = Project.objects.create(
            company=self.company,
            code="P001",
            name="Tower Project",
            start_date=date.today(),
            target_end_date=date.today() + timedelta(days=120),
            currency="INR",
        )
        self.partner = create_partner(
            company=self.company,
            code="V001",
            legal_name="Vendor One Private Limited",
            display_name="Vendor One",
            organization_type_code="VENDOR",
            actor_public_id=self.user.public_id,
            correlation_id=self.user.public_id,
        )

    def test_internal_overview_reports_partner_and_item(self):
        create_collaboration_item(
            company=self.company,
            organization=self.partner,
            project=self.project,
            site=None,
            assigned_contact=None,
            reference="RFQ-001",
            item_type_code="RFQ",
            title="Structural steel quotation",
            status_code="ISSUED",
            actor_public_id=self.user.public_id,
            correlation_id=self.user.public_id,
        )
        payload = internal_overview(self.company)
        self.assertEqual(payload["metrics"]["active_partners"], 1)
        self.assertEqual(payload["metrics"]["open_items"], 1)

    def test_project_grant_rejects_cross_tenant_contact(self):
        other = Company.objects.create(
            code="OTHER",
            legal_name="Other Company",
            display_name="Other",
            locale="en-IN",
            timezone="Asia/Kolkata",
            currency="INR",
            unit_system_code="METRIC",
            fiscal_year_start_month=4,
        )
        foreign_partner = self.partner.__class__.objects.create(
            company=other,
            code="OTHER-V",
            legal_name="Other Vendor",
            display_name="Other Vendor",
        )
        contact = PartnerContact.objects.create(
            company=other,
            organization=foreign_partner,
            full_name="Foreign Contact",
            email="foreign@example.com",
        )
        grant = ProjectAccessGrant(
            company=self.company,
            contact=contact,
            project=self.project,
            scopes=["SUBMIT"],
            effective_from=timezone.now(),
            granted_by_public_id=self.user.public_id,
        )
        with self.assertRaises(ValidationError):
            grant.full_clean()
