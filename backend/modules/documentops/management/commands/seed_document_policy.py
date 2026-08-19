from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from modules.documentops.models import DocumentControlPolicyVersion
from modules.tenant.models import Company

DRAFT_CONFIGURATION = {
    "initial_document_status": "DRAFT",
    "initial_revision_status": "DRAFT",
    "initial_transmittal_status": "DRAFT",
    "initial_rfi_status": "OPEN",
    "initial_submittal_status": "DRAFT",
    "initial_approval_status": "PENDING",
    "initial_distribution_status": "DISTRIBUTED",
    "acknowledged_distribution_status": "ACKNOWLEDGED",
    "initial_risk_status": "OPEN",
    "resolved_risk_status": "RESOLVED",
    "active_document_statuses": ["ACTIVE", "ISSUED"],
    "review_revision_statuses": ["SUBMITTED", "UNDER_REVIEW"],
    "open_transmittal_statuses": ["DRAFT", "ISSUED", "ACKNOWLEDGEMENT_PENDING"],
    "open_rfi_statuses": ["OPEN", "ASSIGNED", "RESPONSE_PENDING"],
    "open_submittal_statuses": ["DRAFT", "SUBMITTED", "UNDER_REVIEW", "REVISION_REQUIRED"],
    "critical_priority_codes": ["CRITICAL", "URGENT"],
    "approved_submittal_decisions": ["APPROVED", "APPROVED_WITH_COMMENTS"],
    "document_transitions": [
        {"from": "DRAFT", "to": "ACTIVE", "permission": "document.manage"},
        {"from": "ACTIVE", "to": "ARCHIVED", "permission": "document.manage"},
    ],
    "revision_transitions": [
        {"from": "DRAFT", "to": "SUBMITTED", "permission": "document.manage", "milestone": "submitted"},
        {"from": "SUBMITTED", "to": "UNDER_REVIEW", "permission": "document.issue"},
        {"from": "UNDER_REVIEW", "to": "ISSUED", "permission": "document.issue", "milestone": "issued"},
        {"from": "ISSUED", "to": "SUPERSEDED", "permission": "document.issue", "milestone": "superseded"},
    ],
    "transmittal_transitions": [
        {"from": "DRAFT", "to": "ISSUED", "permission": "document.issue", "milestone": "issued"},
        {"from": "ISSUED", "to": "ACKNOWLEDGED", "permission": "document.issue", "milestone": "acknowledged"},
        {"from": "ACKNOWLEDGED", "to": "CLOSED", "permission": "document.issue", "milestone": "closed"},
    ],
    "rfi_transitions": [
        {"from": "OPEN", "to": "ASSIGNED", "permission": "document.rfi"},
        {"from": "ASSIGNED", "to": "RESPONDED", "permission": "document.rfi", "milestone": "responded"},
        {"from": "RESPONDED", "to": "CLOSED", "permission": "document.rfi", "milestone": "closed"},
    ],
    "submittal_transitions": [
        {"from": "DRAFT", "to": "SUBMITTED", "permission": "document.submittal", "milestone": "submitted"},
        {"from": "SUBMITTED", "to": "UNDER_REVIEW", "permission": "document.submittal"},
        {"from": "UNDER_REVIEW", "to": "CLOSED", "permission": "document.submittal", "milestone": "reviewed"},
    ],
    "approval_decisions": {
        "APPROVE": "APPROVED",
        "REJECT": "REJECTED",
        "RETURN": "RETURNED",
    },
}


class Command(BaseCommand):
    help = "Create a generic draft document-control policy for a company"

    def add_arguments(self, parser):
        parser.add_argument("--company", required=True, help="Tenant company code")
        parser.add_argument("--code", default="DOC_CONTROL", help="Policy code")

    def handle(self, *args, **options):
        company_code = str(options["company"]).strip().upper()
        policy_code = str(options["code"]).strip().upper()
        company = Company.objects.filter(code=company_code).first()
        if not company:
            raise CommandError(f"Company not found: {company_code}")
        if DocumentControlPolicyVersion.objects.filter(
            company=company, code=policy_code, version=1
        ).exists():
            self.stdout.write(
                self.style.WARNING(
                    f"Draft document-control policy already exists: {company_code}/{policy_code}/1"
                )
            )
            return
        policy = DocumentControlPolicyVersion(
            company=company,
            code=policy_code,
            name="Generic Document Control and Engineering Policy",
            version=1,
            status_code="DRAFT",
            effective_from=timezone.now(),
            configuration=DRAFT_CONFIGURATION,
            change_note=(
                "Generic non-statutory draft. Review document numbering, revision, "
                "RFI, transmittal, submittal, approval and retention workflows before publication."
            ),
        )
        policy.full_clean()
        policy.save()
        self.stdout.write(
            self.style.SUCCESS(
                f"Created DRAFT document-control policy {company_code}/{policy_code}/1"
            )
        )
