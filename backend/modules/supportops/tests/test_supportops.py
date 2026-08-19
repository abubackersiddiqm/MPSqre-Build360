import uuid

from django.core.exceptions import ValidationError
from django.test import TestCase

from modules.supportops.application.selectors import support_overview
from modules.supportops.application.services import (
    create_article,
    create_change,
    create_ticket,
    seed_defaults,
    transition_article,
    transition_change,
    transition_ticket,
)
from modules.supportops.models import ServiceCatalogItem
from modules.tenant.models import Company


class SupportOpsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(

            code="SUPPORT_TEST",

            legal_name="Support Test Company",

            display_name="Support Test",

            timezone="Asia/Kolkata",

            locale="en-IN",

            currency="INR",

            unit_system_code="METRIC",

            fiscal_year_start_month=4,

        )
        self.actor = uuid.uuid4()
        self.other_actor = uuid.uuid4()
        self.correlation = uuid.uuid4()
        seed_defaults(self.company)

    def test_ticket_deadlines_and_overview(self):
        catalog = ServiceCatalogItem.objects.get(company=self.company, code="APPLICATION_SUPPORT")
        ticket = create_ticket(
            company=self.company,
            catalog_item=catalog,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
            code="SUP-001",
            title="Application test issue",
            requester_name="Test User",
            requester_email="test@example.com",
        )
        self.assertEqual(ticket.status_code, "NEW")
        self.assertGreater(ticket.resolution_due_at, ticket.response_due_at)
        payload = support_overview(self.company)
        self.assertEqual(payload["metrics"]["open_tickets"], 1)

    def test_ticket_requires_resolution_summary(self):
        ticket = create_ticket(
            company=self.company,
            actor_public_id=self.actor,
            correlation_id=self.correlation,
            code="SUP-002",
            title="Resolution control",
            requester_name="Test User",
        )
        ticket = transition_ticket(
            ticket=ticket, status_code="IN_PROGRESS", expected_version=ticket.version,
            actor_public_id=self.actor, correlation_id=self.correlation,
        )
        with self.assertRaises(ValidationError):
            transition_ticket(
                ticket=ticket, status_code="RESOLVED", expected_version=ticket.version,
                actor_public_id=self.actor, correlation_id=self.correlation,
            )

    def test_change_and_article_maker_checker(self):
        change = create_change(
            company=self.company, actor_public_id=self.actor, correlation_id=self.correlation,
            code="CHG-001", title="Controlled change", rollback_plan="Restore previous deployment."
        )
        change = transition_change(
            change=change, status_code="ASSESSMENT", expected_version=change.version,
            actor_public_id=self.actor, correlation_id=self.correlation,
        )
        change = transition_change(
            change=change, status_code="PENDING_APPROVAL", expected_version=change.version,
            actor_public_id=self.actor, correlation_id=self.correlation,
        )
        with self.assertRaises(ValidationError):
            transition_change(
                change=change, status_code="APPROVED", expected_version=change.version,
                actor_public_id=self.actor, correlation_id=self.correlation,
            )
        article = create_article(
            company=self.company, actor_public_id=self.actor, correlation_id=self.correlation,
            code="KB-001", title="Support guide", content="Resolution instructions."
        )
        article = transition_article(
            article=article, status_code="IN_REVIEW", expected_version=article.version,
            actor_public_id=self.actor, correlation_id=self.correlation,
        )
        with self.assertRaises(ValidationError):
            transition_article(
                article=article, status_code="PUBLISHED", expected_version=article.version,
                actor_public_id=self.actor, correlation_id=self.correlation,
            )
