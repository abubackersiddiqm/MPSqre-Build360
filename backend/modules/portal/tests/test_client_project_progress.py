from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from modules.identity.models import User
from modules.portal.api.views import _recipient_share
from modules.portal.models import PortalAccessGrant, PortalScopeType, PortalShare, PortalType
from modules.projects.models import DeliveryStage, Project, ProjectTask
from modules.tenant.models import Company, Membership


class ClientProjectProgressShareTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(

            code="PORTALP",

            legal_name="Portal Progress Pvt Ltd",

            display_name="Portal Progress",

            timezone="Asia/Kolkata",

            locale="en-IN",

            currency="INR",

            unit_system_code="METRIC",

            fiscal_year_start_month=4,

        )
        self.user = User.objects.create(email="client-progress@example.com")
        self.membership = Membership.objects.create(
            company=self.company,
            user=self.user,
            effective_from=timezone.now() - timedelta(minutes=1),
        )
        self.stage = DeliveryStage.objects.create(
            company=self.company,
            entity_type=DeliveryStage.EntityType.PROJECT,
            code="active",
            name="Active",
            outcome=DeliveryStage.Outcome.OPEN,
            sort_order=10,
            is_initial=True,
            effective_from=timezone.now() - timedelta(minutes=1),
        )
        self.task_stage = DeliveryStage.objects.create(
            company=self.company,
            entity_type=DeliveryStage.EntityType.TASK,
            code="task-open",
            name="Task Open",
            outcome=DeliveryStage.Outcome.OPEN,
            sort_order=10,
            is_initial=True,
            effective_from=timezone.now() - timedelta(minutes=1),
        )
        self.project = Project.objects.create(
            company=self.company,
            code="PRJ-PORTAL-1",
            name="Client Residence",
            stage=self.stage,
            manager_membership_public_id=self.membership.public_id,
            currency="INR",
        )
        ProjectTask.objects.create(
            company=self.company,
            project=self.project,
            code="TASK-001",
            title="Internal task title must not be returned",
            stage=self.task_stage,
            progress_percent=50,
        )
        self.grant = PortalAccessGrant.objects.create(
            company=self.company,
            user_public_id=self.user.public_id,
            portal_type=PortalType.CLIENT,
            scope_type=PortalScopeType.PROJECT,
            scope_public_id=self.project.public_id,
            permission_codes=["portal.dashboard.view", "portal.project.view"],
            effective_from=timezone.now() - timedelta(minutes=1),
            granted_by_public_id=self.user.public_id,
        )
        self.share = PortalShare.objects.create(
            company=self.company,
            grant=self.grant,
            entity_type="project",
            entity_public_id=self.project.public_id,
            access_level=PortalShare.AccessLevel.VIEW,
            created_by_public_id=self.user.public_id,
        )

    def test_project_progress_share_returns_aggregate_client_safe_progress(self):
        payload = _recipient_share(self.share)
        entity = payload["entity"]
        self.assertEqual(entity["type"], "project")
        self.assertEqual(entity["project_code"], "PRJ-PORTAL-1")
        self.assertEqual(entity["progress_percent"], 50)
        self.assertEqual(entity["task_count"], 1)
        self.assertNotIn("tasks", entity)
        self.assertNotIn("approved_budget", entity)
        self.assertNotIn("Internal task title", str(entity))

    def test_project_share_requires_project_permission(self):
        self.grant.permission_codes = ["portal.dashboard.view"]
        self.grant.save(update_fields=["permission_codes", "updated_at"])
        self.assertIsNone(_recipient_share(self.share)["entity"])
