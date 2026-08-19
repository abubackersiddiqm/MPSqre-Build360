from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from modules.safetyops.models import SafetyPolicyVersion
from modules.tenant.models import Company


class Command(BaseCommand):
    help = "Create a generic DRAFT HSE and safety policy for tenant review."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--company", required=True, help="Tenant company code")
        parser.add_argument("--code", default="HSE-GENERIC")
        parser.add_argument("--name", default="Generic HSE and safety operations policy")

    def handle(self, *args, **options) -> None:
        company = Company.objects.filter(code=options["company"]).first()
        if not company:
            raise CommandError(f"Company {options['company']} was not found")
        code = str(options["code"]).strip().upper()
        if SafetyPolicyVersion.objects.filter(company=company, code=code).exists():
            raise CommandError(f"Safety policy {code} already exists for {company.code}")

        policy = SafetyPolicyVersion(
            company=company,
            code=code,
            name=str(options["name"]).strip(),
            version=1,
            status_code="DRAFT",
            effective_from=timezone.now(),
            configuration={
                "initial_observation_status": "OPEN",
                "open_observation_statuses": ["OPEN", "ACTION_REQUIRED"],
                "initial_incident_status": "REPORTED",
                "open_incident_statuses": [
                    "REPORTED",
                    "INVESTIGATING",
                    "ACTION_PENDING",
                ],
                "initial_permit_status": "DRAFT",
                "active_permit_statuses": ["ACTIVE"],
                "initial_action_status": "OPEN",
                "open_action_statuses": ["OPEN", "IN_PROGRESS", "COMPLETED"],
                "initial_risk_status": "OPEN",
                "resolved_risk_status": "RESOLVED",
                "critical_severity_codes": ["CRITICAL", "FATAL"],
                "accepted_inspection_results": ["PASSED", "CONDITIONALLY_PASSED"],
                "critical_incident_risk_code": "CRITICAL_INCIDENT",
                "inspection_failure_action_category": "INSPECTION_NONCONFORMANCE",
                "inspection_failure_action_priority": "HIGH",
                "inspection_failure_due_days": 7,
                "initial_approval_status": "PENDING",
                "maker_checker_required": True,
                "approval_decisions": {
                    "APPROVE": "APPROVED",
                    "REJECT": "REJECTED",
                },
                "observation_transitions": [
                    {
                        "from": "OPEN",
                        "to": "ACTION_REQUIRED",
                        "permission": "safety.manage",
                    },
                    {
                        "from": "OPEN",
                        "to": "CLOSED",
                        "permission": "safety.manage",
                        "milestone": "closed",
                    },
                    {
                        "from": "ACTION_REQUIRED",
                        "to": "CLOSED",
                        "permission": "safety.manage",
                        "milestone": "closed",
                    },
                ],
                "incident_transitions": [
                    {
                        "from": "REPORTED",
                        "to": "INVESTIGATING",
                        "permission": "safety.incident",
                    },
                    {
                        "from": "INVESTIGATING",
                        "to": "ACTION_PENDING",
                        "permission": "safety.incident",
                    },
                    {
                        "from": "ACTION_PENDING",
                        "to": "CLOSED",
                        "permission": "safety.approve",
                        "milestone": "closed",
                        "required_approvals": [
                            {
                                "step_code": "INCIDENT_CLOSE",
                                "accepted_statuses": ["APPROVED"],
                            }
                        ],
                    },
                ],
                "permit_transitions": [
                    {
                        "from": "DRAFT",
                        "to": "APPROVAL_PENDING",
                        "permission": "safety.permit",
                    },
                    {
                        "from": "APPROVAL_PENDING",
                        "to": "ACTIVE",
                        "permission": "safety.approve",
                        "milestone": "approved",
                        "required_approvals": [
                            {
                                "step_code": "PERMIT_ISSUE",
                                "accepted_statuses": ["APPROVED"],
                            }
                        ],
                    },
                    {
                        "from": "ACTIVE",
                        "to": "SUSPENDED",
                        "permission": "safety.permit",
                        "milestone": "suspended",
                    },
                    {
                        "from": "ACTIVE",
                        "to": "CLOSED",
                        "permission": "safety.permit",
                        "milestone": "closed",
                    },
                    {
                        "from": "SUSPENDED",
                        "to": "CLOSED",
                        "permission": "safety.permit",
                        "milestone": "closed",
                    },
                ],
                "action_transitions": [
                    {
                        "from": "OPEN",
                        "to": "IN_PROGRESS",
                        "permission": "safety.manage",
                    },
                    {
                        "from": "IN_PROGRESS",
                        "to": "COMPLETED",
                        "permission": "safety.manage",
                        "milestone": "completed",
                    },
                    {
                        "from": "COMPLETED",
                        "to": "VERIFIED",
                        "permission": "safety.approve",
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
                "Generic draft only. Review jurisdiction-specific HSE obligations, "
                "incident classifications, permit types, severity matrices, competency "
                "rules, regulator reporting, workflows and integrations before publication."
            ),
        )
        policy.full_clean()
        policy.save()
        self.stdout.write(
            self.style.SUCCESS(
                f"Created DRAFT safety policy {policy.code} v{policy.version} "
                f"for {company.code}."
            )
        )
