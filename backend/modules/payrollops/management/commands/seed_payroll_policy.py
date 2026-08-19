from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from modules.payrollops.models import PayrollPolicyVersion
from modules.tenant.models import Company


class Command(BaseCommand):
    help = (
        "Create an optional generic draft payroll policy. It contains no country-specific "
        "tax or statutory formula and is never published automatically."
    )

    def add_arguments(self, parser):
        parser.add_argument("--company", required=True, help="Company code")
        parser.add_argument("--policy-code", default="GENERIC_PAYROLL")
        parser.add_argument("--currency", default="")

    def handle(self, *args, **options):
        company = Company.objects.filter(code=options["company"].strip().upper()).first()
        if not company:
            raise CommandError("Company was not found")
        currency = options["currency"].strip().upper() or company.currency
        code = options["policy_code"].strip().upper()
        configuration = {
            "initial_run_status": "DRAFT",
            "immutable_statuses": ["LOCKED"],
            "run_creation_period_statuses": ["OPEN"],
            "run_types": ["REGULAR", "OFF_CYCLE", "FINAL_SETTLEMENT"],
            "approval_assignment_required": True,
            "approval_segregation_of_duties": True,
            "approval_reason_required": False,
            "approval_decisions": {
                "APPROVE": "APPROVED",
                "REJECT": "REJECTED",
            },
            "statutory_adapter": None,
            "calculation_adapter": None,
            "transitions": [
                {
                    "from": "DRAFT",
                    "to": "CALCULATED",
                    "permission": "payroll.manage",
                    "milestone": "calculated",
                    "event_type": "payroll.run.calculated",
                },
                {
                    "from": "CALCULATED",
                    "to": "PENDING_APPROVAL",
                    "permission": "payroll.manage",
                    "event_type": "payroll.run.approval_requested",
                },
                {
                    "from": "PENDING_APPROVAL",
                    "to": "APPROVED",
                    "permission": "payroll.approve",
                    "segregation_of_duties": True,
                    "required_approvals": [
                        {
                            "step_code": "PAYROLL_APPROVAL",
                            "accepted_statuses": ["APPROVED"],
                        }
                    ],
                    "milestone": "approved",
                    "event_type": "payroll.run.approved",
                },
                {
                    "from": "APPROVED",
                    "to": "LOCKED",
                    "permission": "payroll.approve",
                    "segregation_of_duties": True,
                    "milestone": "locked",
                    "event_type": "payroll.run.locked",
                },
            ],
        }
        policy, created = PayrollPolicyVersion.objects.get_or_create(
            company=company,
            code=code,
            version=1,
            defaults={
                "name": "Generic Payroll Control Policy",
                "status_code": "DRAFT",
                "locale_code": company.locale,
                "currency": currency,
                "effective_from": timezone.now(),
                "configuration": configuration,
                "change_note": (
                    "Non-statutory starter template. Validate and publish through an approved "
                    "configuration process before creating payroll runs."
                ),
            },
        )
        if not created:
            self.stdout.write(self.style.WARNING(f"Policy already exists: {policy.public_id}"))
            return
        policy.full_clean()
        policy.save()
        self.stdout.write(self.style.SUCCESS(f"Draft policy created: {policy.public_id}"))
        self.stdout.write(
            "The policy remains DRAFT and unpublished. Country-specific rules were not added."
        )
