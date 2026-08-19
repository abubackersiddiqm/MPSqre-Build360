from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from modules.commercialops.models import CommercialPolicyVersion
from modules.tenant.models import Company

DEFAULT_CONFIGURATION = {
    "initial_contract_status": "DRAFT",
    "initial_milestone_status": "PLANNED",
    "initial_variation_status": "DRAFT",
    "initial_payment_status": "DRAFT",
    "initial_claim_status": "NOTICE",
    "initial_eot_status": "DRAFT",
    "initial_approval_status": "PENDING",
    "initial_risk_status": "OPEN",
    "resolved_risk_status": "RESOLVED",
    "active_contract_statuses": ["ACTIVE", "UNDER_EXECUTION"],
    "open_milestone_statuses": ["PLANNED", "IN_PROGRESS"],
    "open_variation_statuses": ["DRAFT", "SUBMITTED", "UNDER_REVIEW"],
    "open_payment_statuses": ["DRAFT", "SUBMITTED", "UNDER_CERTIFICATION"],
    "open_claim_statuses": ["NOTICE", "SUBMITTED", "UNDER_ASSESSMENT"],
    "open_eot_statuses": ["DRAFT", "SUBMITTED", "UNDER_ASSESSMENT"],
    "critical_claim_priority_codes": ["CRITICAL", "URGENT"],
    "critical_risk_severity_codes": ["CRITICAL", "HIGH"],
    "contract_transitions": [
        {"from": "DRAFT", "to": "ACTIVE", "permission": "commercial.approve"},
        {"from": "ACTIVE", "to": "UNDER_EXECUTION", "permission": "commercial.contract"},
        {"from": "UNDER_EXECUTION", "to": "COMPLETED", "permission": "commercial.approve", "milestone": "closed"},
        {"from": "COMPLETED", "to": "CLOSED", "permission": "commercial.approve", "milestone": "closed"},
    ],
    "milestone_transitions": [
        {"from": "PLANNED", "to": "IN_PROGRESS", "permission": "commercial.contract"},
        {"from": "IN_PROGRESS", "to": "ACHIEVED", "permission": "commercial.approve", "milestone": "achieved"},
    ],
    "variation_transitions": [
        {"from": "DRAFT", "to": "SUBMITTED", "permission": "commercial.change", "milestone": "submitted"},
        {"from": "SUBMITTED", "to": "UNDER_REVIEW", "permission": "commercial.change"},
        {"from": "UNDER_REVIEW", "to": "APPROVED", "permission": "commercial.approve", "milestone": "approved", "required_approvals": [{"step_code": "COMMERCIAL_REVIEW", "accepted_statuses": ["APPROVED"]}]},
        {"from": "UNDER_REVIEW", "to": "REJECTED", "permission": "commercial.approve", "milestone": "rejected"},
    ],
    "payment_transitions": [
        {"from": "DRAFT", "to": "SUBMITTED", "permission": "commercial.payment", "milestone": "submitted"},
        {"from": "SUBMITTED", "to": "UNDER_CERTIFICATION", "permission": "commercial.payment"},
        {"from": "UNDER_CERTIFICATION", "to": "CERTIFIED", "permission": "commercial.approve", "milestone": "certified"},
        {"from": "CERTIFIED", "to": "PAID", "permission": "commercial.payment"},
    ],
    "claim_transitions": [
        {"from": "NOTICE", "to": "SUBMITTED", "permission": "commercial.claim"},
        {"from": "SUBMITTED", "to": "UNDER_ASSESSMENT", "permission": "commercial.claim"},
        {"from": "UNDER_ASSESSMENT", "to": "SETTLED", "permission": "commercial.approve", "milestone": "resolved"},
        {"from": "UNDER_ASSESSMENT", "to": "REJECTED", "permission": "commercial.approve", "milestone": "resolved"},
    ],
    "eot_transitions": [
        {"from": "DRAFT", "to": "SUBMITTED", "permission": "commercial.claim"},
        {"from": "SUBMITTED", "to": "UNDER_ASSESSMENT", "permission": "commercial.claim"},
        {"from": "UNDER_ASSESSMENT", "to": "APPROVED", "permission": "commercial.approve", "milestone": "approved"},
        {"from": "UNDER_ASSESSMENT", "to": "REJECTED", "permission": "commercial.approve", "milestone": "rejected"},
    ],
    "approval_decisions": {"APPROVE": "APPROVED", "REJECT": "REJECTED"},
}


class Command(BaseCommand):
    help = "Create a generic draft Phase 27 commercial policy for one company."

    def add_arguments(self, parser):
        parser.add_argument("--company", required=True, help="Company code")
        parser.add_argument("--code", default="COMMERCIAL_DEFAULT")

    def handle(self, *args, **options):
        company = Company.objects.filter(code=options["company"]).first()
        if not company:
            raise CommandError("Company was not found")
        code = options["code"].strip().upper()
        next_version = (
            CommercialPolicyVersion.objects.filter(company=company, code=code)
            .order_by("-version")
            .values_list("version", flat=True)
            .first()
            or 0
        ) + 1
        item = CommercialPolicyVersion(
            company=company,
            code=code,
            name="Generic Commercial Operations Policy",
            version=next_version,
            status_code="DRAFT",
            effective_from=timezone.now(),
            configuration=DEFAULT_CONFIGURATION,
            change_note="Generic draft only. Review contract, claims, payment and jurisdiction controls before publishing.",
        )
        item.full_clean()
        item.save()
        self.stdout.write(
            self.style.SUCCESS(
                f"Created DRAFT commercial policy {item.code} v{item.version} for {company.code}"
            )
        )
