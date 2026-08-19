from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from modules.equipmentops.models import EquipmentPolicyVersion
from modules.tenant.models import Company


class Command(BaseCommand):
    help = "Create a generic DRAFT equipment policy for controlled tenant configuration."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--company", required=True, help="Tenant company code")
        parser.add_argument("--code", default="EQUIPMENT-GENERIC")
        parser.add_argument("--name", default="Generic equipment operations policy")

    def handle(self, *args, **options) -> None:
        company = Company.objects.filter(code=options["company"]).first()
        if not company:
            raise CommandError(f"Company {options['company']} was not found")
        code = str(options["code"]).strip()
        if EquipmentPolicyVersion.objects.filter(company=company, code=code).exists():
            raise CommandError(
                f"Equipment policy {code} already exists for {company.code}"
            )
        policy = EquipmentPolicyVersion(
            company=company,
            code=code,
            name=str(options["name"]).strip(),
            version=1,
            status_code="DRAFT",
            effective_from=timezone.now(),
            configuration={
                "initial_asset_status": "REGISTERED",
                "immutable_asset_statuses": ["RETIRED", "DECOMMISSIONED"],
                "initial_deployment_status": "PLANNED",
                "active_deployment_statuses": ["ACTIVE", "DEPLOYED"],
                "deployed_asset_status": "DEPLOYED",
                "initial_work_order_status": "OPEN",
                "open_work_order_statuses": [
                    "OPEN",
                    "APPROVAL_PENDING",
                    "PLANNED",
                    "IN_PROGRESS",
                ],
                "meter_regression_action": "BLOCK",
                "accepted_inspection_results": ["PASSED", "CONDITIONALLY_PASSED"],
                "inspection_failure_risk_code": "INSPECTION_NOT_ACCEPTED",
                "inspection_failure_severity": "HIGH",
                "open_risk_status": "OPEN",
                "maker_checker_required": True,
                "maintenance_hold_priorities": ["CRITICAL"],
                "maintenance_hold_asset_status": "MAINTENANCE_HOLD",
                "approval_decisions": {
                    "APPROVE": "APPROVED",
                    "REJECT": "REJECTED",
                },
                "asset_status_by_work_order_status": {
                    "IN_PROGRESS": "MAINTENANCE_HOLD",
                    "COMPLETED": "AVAILABLE",
                    "CLOSED": "AVAILABLE",
                },
                "work_order_transitions": [
                    {
                        "from": "OPEN",
                        "to": "APPROVAL_PENDING",
                        "permission": "equipment.maintain",
                    },
                    {
                        "from": "APPROVAL_PENDING",
                        "to": "PLANNED",
                        "permission": "equipment.approve",
                        "milestone": "approved",
                        "required_approvals": [
                            {
                                "step_code": "MAINTENANCE_APPROVAL",
                                "accepted_statuses": ["APPROVED"],
                            }
                        ],
                    },
                    {
                        "from": "OPEN",
                        "to": "PLANNED",
                        "permission": "equipment.maintain",
                    },
                    {
                        "from": "PLANNED",
                        "to": "IN_PROGRESS",
                        "permission": "equipment.maintain",
                    },
                    {
                        "from": "IN_PROGRESS",
                        "to": "COMPLETED",
                        "permission": "equipment.maintain",
                        "milestone": "completed",
                    },
                    {
                        "from": "COMPLETED",
                        "to": "CLOSED",
                        "permission": "equipment.maintain",
                        "milestone": "closed",
                    },
                ],
            },
            change_note=(
                "Generic draft only. Review asset taxonomy, maintenance controls, "
                "inspection rules, approvals, providers, jurisdictions and adapters "
                "before publication."
            ),
        )
        policy.full_clean()
        policy.save()
        self.stdout.write(
            self.style.SUCCESS(
                f"Created DRAFT equipment policy {policy.code} v{policy.version} "
                f"for {company.code}."
            )
        )
