from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from modules.tenant.models import Company
from modules.workforceops.models import WorkforcePolicyVersion


class Command(BaseCommand):
    help = "Create a generic draft workforce-planning control policy for a company."

    def add_arguments(self, parser):
        parser.add_argument("--company", required=True, help="Tenant company code")

    def handle(self, *args, **options):
        company_code = str(options["company"]).strip()
        company = Company.objects.filter(code=company_code).first()
        if not company:
            raise CommandError(f"Company {company_code!r} was not found")

        policy, created = WorkforcePolicyVersion.objects.get_or_create(
            company=company,
            code="GENERIC-WORKFORCE",
            version=1,
            defaults={
                "name": "Generic workforce planning control policy",
                "status_code": "DRAFT",
                "effective_from": timezone.now(),
                "configuration": {
                    "initial_plan_status": "DRAFT",
                    "immutable_statuses": ["LOCKED"],
                    "maker_checker_required": True,
                    "credential_enforcement": "RISK",
                    "accepted_verification_statuses": ["VERIFIED"],
                    "credential_gap_risk_code": "SKILL_REQUIREMENT_GAP",
                    "credential_gap_severity": "HIGH",
                    "open_risk_status": "OPEN",
                    "filled_demand_status": "FILLED",
                    "approval_decisions": {
                        "APPROVE": "APPROVED",
                        "REJECT": "REJECTED",
                    },
                    "transitions": [
                        {
                            "from": "DRAFT",
                            "to": "SUBMITTED",
                            "permission": "workforce.manage",
                        },
                        {
                            "from": "SUBMITTED",
                            "to": "APPROVED",
                            "permission": "workforce.approve",
                            "milestone": "approved",
                            "required_approvals": [
                                {
                                    "step_code": "WORKFORCE_APPROVAL",
                                    "accepted_statuses": ["APPROVED"],
                                }
                            ],
                        },
                        {
                            "from": "APPROVED",
                            "to": "LOCKED",
                            "permission": "workforce.approve",
                            "milestone": "locked",
                        },
                    ],
                },
                "change_note": (
                    "Generic draft only. Configure company roles, skills, credentials, "
                    "project adapters, regional labour controls and approvals before publishing."
                ),
            },
        )
        if created:
            policy.full_clean()
            policy.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created draft workforce policy {policy.code} v{policy.version}"
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"Draft workforce policy {policy.code} v{policy.version} already exists"
                )
            )
        self.stdout.write(
            "The policy remains DRAFT and is not production-ready until reviewed and published."
        )
