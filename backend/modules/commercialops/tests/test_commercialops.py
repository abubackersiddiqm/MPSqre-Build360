from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from modules.commercialops.application.selectors import commercial_overview
from modules.commercialops.models import CommercialContract, CommercialPolicyVersion
from modules.tenant.models import Company

CONFIGURATION = {
    "initial_contract_status": "DRAFT",
    "initial_milestone_status": "PLANNED",
    "initial_variation_status": "DRAFT",
    "initial_payment_status": "DRAFT",
    "initial_claim_status": "NOTICE",
    "initial_eot_status": "DRAFT",
    "initial_approval_status": "PENDING",
    "initial_risk_status": "OPEN",
    "resolved_risk_status": "RESOLVED",
    "active_contract_statuses": ["ACTIVE"],
    "open_milestone_statuses": ["PLANNED"],
    "open_variation_statuses": ["SUBMITTED"],
    "open_payment_statuses": ["SUBMITTED"],
    "open_claim_statuses": ["NOTICE"],
    "open_eot_statuses": ["SUBMITTED"],
    "critical_claim_priority_codes": ["CRITICAL"],
    "critical_risk_severity_codes": ["CRITICAL"],
    "contract_transitions": [],
    "milestone_transitions": [],
    "variation_transitions": [],
    "payment_transitions": [],
    "claim_transitions": [],
    "eot_transitions": [],
    "approval_decisions": {"APPROVE": "APPROVED"},
}


def company(code: str) -> Company:
    return Company.objects.create(
        code=code,
        legal_name=f"{code} Legal",
        display_name=code,
        locale="en-IN",
        timezone="Asia/Kolkata",
        currency="INR",
        unit_system_code="metric",
        fiscal_year_start_month=4,
    )


class CommercialOpsTests(TestCase):
    def setUp(self):
        self.company = company("COPS_A")
        self.other_company = company("COPS_B")
        now = timezone.now()
        self.policy = CommercialPolicyVersion.objects.create(
            company=self.company,
            code="DEFAULT",
            name="Default",
            version=1,
            status_code="PUBLISHED",
            effective_from=now - timedelta(days=1),
            published_at=now - timedelta(days=1),
            configuration=CONFIGURATION,
        )
        self.other_policy = CommercialPolicyVersion.objects.create(
            company=self.other_company,
            code="DEFAULT",
            name="Default",
            version=1,
            status_code="PUBLISHED",
            effective_from=now - timedelta(days=1),
            published_at=now - timedelta(days=1),
            configuration=CONFIGURATION,
        )

    def test_empty_overview_does_not_defer_selected_relations(self):
        overview = commercial_overview(self.company)
        self.assertEqual(overview["summary"]["active_contract_count"], 0)
        self.assertEqual(overview["financial_exposure"], [])

    def test_contract_rejects_cross_tenant_policy(self):
        item = CommercialContract(
            company=self.company,
            policy=self.other_policy,
            contract_number="CON-001",
            counterparty_name="Vendor",
            contract_type_code="MAIN",
            title="Main works",
            status_code="ACTIVE",
            currency_code="INR",
            original_value=Decimal("1000"),
            current_contract_value=Decimal("1000"),
            start_date=date.today(),
            planned_completion_date=date.today() + timedelta(days=30),
        )
        with self.assertRaises(ValidationError):
            item.full_clean()

    def test_overview_is_tenant_isolated_and_currency_safe(self):
        CommercialContract.objects.create(
            company=self.company,
            policy=self.policy,
            contract_number="CON-001",
            counterparty_name="Vendor A",
            contract_type_code="MAIN",
            title="Main works",
            status_code="ACTIVE",
            currency_code="INR",
            original_value=Decimal("1000"),
            current_contract_value=Decimal("1000"),
            start_date=date.today(),
            planned_completion_date=date.today() + timedelta(days=30),
        )
        CommercialContract.objects.create(
            company=self.other_company,
            policy=self.other_policy,
            contract_number="CON-002",
            counterparty_name="Vendor B",
            contract_type_code="MAIN",
            title="Other works",
            status_code="ACTIVE",
            currency_code="USD",
            original_value=Decimal("500"),
            current_contract_value=Decimal("500"),
            start_date=date.today(),
            planned_completion_date=date.today() + timedelta(days=30),
        )
        overview = commercial_overview(self.company)
        self.assertEqual(overview["summary"]["active_contract_count"], 1)
        self.assertEqual(overview["financial_exposure"][0]["currency_code"], "INR")
        self.assertEqual(overview["financial_exposure"][0]["contract_value"], "1000.00")

    def test_all_tables_use_commercialops_namespace(self):
        tables = {
            model._meta.db_table
            for model in self.policy._meta.apps.get_app_config("commercialops").get_models()
        }
        self.assertTrue(tables)
        self.assertTrue(all(name.startswith("commercialops_") for name in tables))
