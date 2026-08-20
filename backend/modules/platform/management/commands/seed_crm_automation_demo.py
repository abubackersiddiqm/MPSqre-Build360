from __future__ import annotations

import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from modules.crm.application.automation import validate_actions, validate_condition_tree
from modules.crm.models import CrmAutomationRule
from modules.subscription.application.feature_control import feature_enabled
from modules.tenant.models import Company

DEMO_COMPANY_CODES = ("DEMOCRM", "DEMOCORE", "DEMO360")

DEMO_AUTOMATION_RULES: tuple[dict[str, object], ...] = (
    {
        "code": "website-lead-follow-up",
        "name": "Website lead follow-up",
        "description": "Create a high-priority follow-up task when a new website enquiry becomes a CRM lead.",
        "trigger_code": "lead.created",
        "condition_tree": {
            "mode": "all",
            "items": [{"field": "source_code", "operator": "eq", "value": "website"}],
        },
        "actions": [
            {
                "type": "create_task",
                "subject": "Call website enquiry",
                "notes": "Review the new website enquiry, confirm requirement, budget and preferred next step.",
                "due_in_hours": 4,
                "priority": "high",
            }
        ],
        "priority": 10,
        "stop_on_match": False,
    },
    {
        "code": "high-value-lead-review",
        "name": "High-value lead fast review",
        "description": "Escalate large-value enquiries for an early commercial review.",
        "trigger_code": "lead.created",
        "condition_tree": {
            "mode": "all",
            "items": [{"field": "estimated_value", "operator": "gte", "value": 10000000}],
        },
        "actions": [
            {
                "type": "create_task",
                "subject": "Review high-value enquiry",
                "notes": "Validate scope, decision makers, commercial fit and the next customer conversation.",
                "due_in_hours": 2,
                "priority": "urgent",
            }
        ],
        "priority": 20,
        "stop_on_match": False,
    },
    {
        "code": "qualified-lead-proposal",
        "name": "Qualified lead proposal preparation",
        "description": "Prepare the proposal workflow when a lead reaches the qualified stage.",
        "trigger_code": "lead.stage_changed",
        "condition_tree": {
            "mode": "all",
            "items": [{"field": "stage.code", "operator": "eq", "value": "qualified"}],
        },
        "actions": [
            {
                "type": "create_task",
                "subject": "Prepare proposal and estimate",
                "notes": "Prepare the proposal, estimate and customer-facing commercial discussion points.",
                "due_in_hours": 8,
                "priority": "high",
            }
        ],
        "priority": 30,
        "stop_on_match": False,
    },
    {
        "code": "callback-requested-follow-up",
        "name": "Callback requested follow-up",
        "description": "Schedule the next customer touchpoint when a completed interaction records a callback request.",
        "trigger_code": "activity.completed",
        "condition_tree": {
            "mode": "all",
            "items": [{"field": "outcome_code", "operator": "eq", "value": "callback_requested"}],
        },
        "actions": [
            {
                "type": "schedule_follow_up",
                "subject": "Return requested callback",
                "notes": "Customer requested a callback. Reconnect and record the outcome in Relationship 360.",
                "due_in_hours": 2,
                "priority": "high",
            }
        ],
        "priority": 40,
        "stop_on_match": False,
    },
)


class Command(BaseCommand):
    help = "Seed idempotent CRM automation demo rules for governed Build360 DEMO tenants only."

    @transaction.atomic
    def handle(self, *args: object, **options: object) -> None:
        self._require_demo_database()

        companies = {
            company.code: company
            for company in Company.objects.filter(code__in=DEMO_COMPANY_CODES, is_active=True)
        }
        missing = [code for code in DEMO_COMPANY_CODES if code not in companies]
        if missing:
            raise CommandError(
                "Demo companies are missing. Run seed_build360_demo first: " + ", ".join(missing)
            )

        total_created = 0
        total_updated = 0
        total_unchanged = 0
        total_skipped = 0

        for company_code in DEMO_COMPANY_CODES:
            company = companies[company_code]
            if not feature_enabled(company=company, code="crm.automation"):
                total_skipped += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"{company.code}: crm.automation is disabled; automation demo rules skipped."
                    )
                )
                continue

            company_created = 0
            company_updated = 0
            company_unchanged = 0
            for definition in DEMO_AUTOMATION_RULES:
                result = self._upsert_rule(company=company, definition=definition)
                if result == "created":
                    company_created += 1
                    total_created += 1
                elif result == "updated":
                    company_updated += 1
                    total_updated += 1
                else:
                    company_unchanged += 1
                    total_unchanged += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f"{company.code}: 4 automation rules ready "
                    f"(created {company_created}, updated {company_updated}, unchanged {company_unchanged})."
                )
            )

        self.stdout.write(self.style.SUCCESS("BUILD360 CRM AUTOMATION DEMO DATA READY"))
        self.stdout.write(
            f"Created {total_created} | Updated {total_updated} | "
            f"Unchanged {total_unchanged} | Companies skipped {total_skipped}"
        )

    def _require_demo_database(self) -> None:
        if settings.BUILD360_ENVIRONMENT != "demo":
            raise CommandError("CRM automation demo seeding is blocked outside BUILD360_ENVIRONMENT=demo.")
        database_name = str(settings.DATABASES["default"].get("NAME", ""))
        guard = os.getenv("BUILD360_DATABASE_NAME_GUARD", "").strip()
        if not guard or database_name != guard:
            raise CommandError(
                "Demo database name guard is missing or does not match DATABASE_URL."
            )

    def _upsert_rule(self, *, company: Company, definition: dict[str, object]) -> str:
        code = str(definition["code"])
        condition_tree = validate_condition_tree(definition["condition_tree"])
        actions = validate_actions(definition["actions"])
        desired = {
            "name": str(definition["name"]),
            "description": str(definition["description"]),
            "trigger_code": str(definition["trigger_code"]),
            "condition_tree": condition_tree,
            "actions": actions,
            "priority": int(definition["priority"]),
            "stop_on_match": bool(definition["stop_on_match"]),
            "is_active": True,
        }

        rule = CrmAutomationRule.objects.filter(company=company, code=code).first()
        if rule is None:
            rule = CrmAutomationRule(company=company, code=code, **desired)
            rule.full_clean()
            rule.save()
            return "created"

        changed_fields: list[str] = []
        for field, value in desired.items():
            if getattr(rule, field) != value:
                setattr(rule, field, value)
                changed_fields.append(field)
        if not changed_fields:
            return "unchanged"

        rule.version += 1
        rule.full_clean()
        rule.save(update_fields=[*changed_fields, "version", "updated_at"])
        return "updated"
