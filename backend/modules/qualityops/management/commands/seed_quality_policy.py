from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from modules.qualityops.models import QualityPolicyVersion
from modules.tenant.models import Company


class Command(BaseCommand):
    help = "Create a generic DRAFT quality and QA/QC policy for tenant review."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--company", required=True, help="Tenant company code")
        parser.add_argument("--code", default="QAQC-GENERIC")
        parser.add_argument(
            "--name", default="Generic quality assurance and quality control policy"
        )

    def handle(self, *args, **options) -> None:
        company = Company.objects.filter(code=options["company"]).first()
        if not company:
            raise CommandError(f"Company {options['company']} was not found")
        code = str(options["code"]).strip().upper()
        if QualityPolicyVersion.objects.filter(company=company, code=code).exists():
            raise CommandError(f"Quality policy {code} already exists for {company.code}")

        policy = QualityPolicyVersion(
            company=company,
            code=code,
            name=str(options["name"]).strip(),
            version=1,
            status_code="DRAFT",
            effective_from=timezone.now(),
            configuration={
                "initial_itp_status": "DRAFT",
                "active_itp_statuses": ["APPROVED", "ACTIVE"],
                "initial_request_status": "SUBMITTED",
                "open_request_statuses": [
                    "SUBMITTED",
                    "SCHEDULED",
                    "INSPECTION_PENDING",
                ],
                "initial_inspection_status": "SCHEDULED",
                "completed_inspection_status": "COMPLETED",
                "initial_ncr_status": "OPEN",
                "open_ncr_statuses": [
                    "OPEN",
                    "ROOT_CAUSE_PENDING",
                    "DISPOSITION_PENDING",
                    "ACTION_PENDING",
                ],
                "initial_action_status": "OPEN",
                "open_action_statuses": ["OPEN", "IN_PROGRESS", "COMPLETED"],
                "initial_risk_status": "OPEN",
                "resolved_risk_status": "RESOLVED",
                "critical_severity_codes": ["CRITICAL", "MAJOR"],
                "accepted_inspection_results": ["ACCEPTED", "CONDITIONALLY_ACCEPTED"],
                "accepted_test_results": ["PASSED", "CONDITIONALLY_PASSED"],
                "initial_approval_status": "PENDING",
                "maker_checker_required": True,
                "approval_decisions": {
                    "APPROVE": "APPROVED",
                    "REJECT": "REJECTED",
                },
                "itp_transitions": [
                    {
                        "from": "DRAFT",
                        "to": "APPROVAL_PENDING",
                        "permission": "quality.manage",
                    },
                    {
                        "from": "APPROVAL_PENDING",
                        "to": "APPROVED",
                        "permission": "quality.approve",
                        "milestone": "approved",
                        "required_approvals": [
                            {
                                "step_code": "ITP_APPROVAL",
                                "accepted_statuses": ["APPROVED"],
                            }
                        ],
                    },
                    {
                        "from": "APPROVED",
                        "to": "ACTIVE",
                        "permission": "quality.manage",
                    },
                    {
                        "from": "ACTIVE",
                        "to": "RETIRED",
                        "permission": "quality.approve",
                    },
                ],
                "request_transitions": [
                    {
                        "from": "SUBMITTED",
                        "to": "SCHEDULED",
                        "permission": "quality.inspect",
                    },
                    {
                        "from": "SCHEDULED",
                        "to": "INSPECTION_PENDING",
                        "permission": "quality.inspect",
                    },
                    {
                        "from": "INSPECTION_PENDING",
                        "to": "CLOSED",
                        "permission": "quality.inspect",
                        "milestone": "closed",
                    },
                    {
                        "from": "SUBMITTED",
                        "to": "CANCELLED",
                        "permission": "quality.manage",
                        "milestone": "closed",
                    },
                ],
                "ncr_transitions": [
                    {
                        "from": "OPEN",
                        "to": "ROOT_CAUSE_PENDING",
                        "permission": "quality.ncr",
                    },
                    {
                        "from": "ROOT_CAUSE_PENDING",
                        "to": "DISPOSITION_PENDING",
                        "permission": "quality.ncr",
                    },
                    {
                        "from": "DISPOSITION_PENDING",
                        "to": "ACTION_PENDING",
                        "permission": "quality.ncr",
                    },
                    {
                        "from": "ACTION_PENDING",
                        "to": "CLOSED",
                        "permission": "quality.approve",
                        "milestone": "closed",
                        "required_approvals": [
                            {
                                "step_code": "NCR_CLOSE",
                                "accepted_statuses": ["APPROVED"],
                            }
                        ],
                    },
                ],
                "action_transitions": [
                    {
                        "from": "OPEN",
                        "to": "IN_PROGRESS",
                        "permission": "quality.manage",
                    },
                    {
                        "from": "IN_PROGRESS",
                        "to": "COMPLETED",
                        "permission": "quality.manage",
                        "milestone": "completed",
                    },
                    {
                        "from": "COMPLETED",
                        "to": "VERIFIED",
                        "permission": "quality.approve",
                        "milestone": "verified",
                        "required_approvals": [
                            {
                                "step_code": "ACTION_VERIFY",
                                "accepted_statuses": ["APPROVED"],
                            }
                        ],
                    },
                ],
            },
            change_note=(
                "Generic draft only. Review tenant construction specifications, ITPs, "
                "inspection categories, sampling plans, material standards, laboratory "
                "accreditation, acceptance criteria, NCR dispositions, approvals and "
                "jurisdictional quality obligations before publication."
            ),
        )
        policy.full_clean()
        policy.save()
        self.stdout.write(
            self.style.SUCCESS(
                f"Created DRAFT quality policy {policy.code} v{policy.version} "
                f"for {company.code}."
            )
        )
