from __future__ import annotations

from cryptography.fernet import Fernet
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser

from modules.crm.models import CrmPipeline, PipelineStage
from modules.identity.models import Permission
from modules.subscription.application.feature_control import feature_enabled
from modules.tenant.models import Company

REQUIRED_PERMISSION_CODES = {
    "crm.dashboard.read",
    "crm.customer.read",
    "crm.customer.manage",
    "crm.contact.read",
    "crm.contact.manage",
    "crm.contact.reveal",
    "crm.contact_center.use",
    "crm.lead.read",
    "crm.lead.manage",
    "crm.lead.transition",
    "crm.opportunity.read",
    "crm.opportunity.manage",
    "crm.opportunity.transition",
    "crm.activity.read",
    "crm.activity.manage",
    "crm.stage.read",
    "crm.configuration.read",
    "crm.configuration.manage",
    "crm.automation.read",
    "crm.automation.manage",
}


class Command(BaseCommand):
    help = "Verify CRM production-readiness controls for a tenant without changing data."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--company-code", required=True)
        parser.add_argument(
            "--require-automation",
            action="store_true",
            help="Fail when the crm.automation SaaS add-on is not enabled.",
        )

    def handle(self, *args: object, **options: object) -> None:
        company_code = str(options["company_code"]).strip()
        company = Company.objects.filter(code__iexact=company_code, is_active=True).first()
        if company is None:
            raise CommandError("Active company was not found")

        failures: list[str] = []
        warnings: list[str] = []

        def check(condition: bool, message: str, failure: str | None = None) -> None:
            if condition:
                self.stdout.write(self.style.SUCCESS(f"[PASS] {message}"))
            else:
                text = failure or message
                self.stdout.write(self.style.ERROR(f"[FAIL] {text}"))
                failures.append(text)

        self.stdout.write(f"CRM production-readiness review: {company.display_name} ({company.code})")

        check(
            feature_enabled(company=company, code="crm.core"),
            "CRM Core SaaS entitlement is enabled.",
            "CRM Core SaaS entitlement is disabled.",
        )

        available_permissions = set(
            Permission.objects.filter(code__in=REQUIRED_PERMISSION_CODES).values_list(
                "code", flat=True
            )
        )
        missing_permissions = sorted(REQUIRED_PERMISSION_CODES - available_permissions)
        check(
            not missing_permissions,
            "CRM permission catalogue includes the v20n governance permissions.",
            f"CRM permission catalogue is missing: {', '.join(missing_permissions)}",
        )

        for entity_type, label in (
            (PipelineStage.EntityType.LEAD, "Lead"),
            (PipelineStage.EntityType.OPPORTUNITY, "Opportunity"),
        ):
            default_pipeline = CrmPipeline.objects.filter(
                company=company,
                entity_type=entity_type,
                is_default=True,
                is_active=True,
            ).first()
            check(
                default_pipeline is not None,
                f"{label} default pipeline exists.",
                f"{label} default pipeline is missing.",
            )
            if default_pipeline is not None:
                initial_count = PipelineStage.objects.filter(
                    company=company,
                    pipeline=default_pipeline,
                    entity_type=entity_type,
                    is_active=True,
                    is_initial=True,
                ).count()
                check(
                    initial_count == 1,
                    f"{label} default pipeline has exactly one active initial stage.",
                    f"{label} default pipeline must have exactly one active initial stage; found {initial_count}.",
                )

        keys = list(getattr(settings, "CRM_PROTECTED_DATA_KEYS", []) or [])
        valid_keys = True
        for key in keys:
            try:
                Fernet(str(key).encode("ascii"))
            except (TypeError, ValueError):
                valid_keys = False
                break
        check(bool(keys) and valid_keys, "Protected-contact Fernet key ring is configured and valid.")

        blind_key = str(getattr(settings, "CRM_BLIND_INDEX_KEY", "") or "")
        check(
            len(blind_key) >= 24,
            "Protected-contact blind-index key is configured.",
            "CRM_BLIND_INDEX_KEY must be a strong independent secret (minimum 24 characters for this gate).",
        )

        throttle_rates = settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {})
        check(
            bool(throttle_rates.get("crm_contact_reveal")),
            "Protected contact reveal throttle is configured.",
            "crm_contact_reveal throttle rate is missing.",
        )

        automation_enabled = feature_enabled(company=company, code="crm.automation")
        if options.get("require_automation"):
            check(
                automation_enabled,
                "CRM Automation SaaS add-on is enabled.",
                "CRM Automation was required for this gate but is disabled.",
            )
        elif not automation_enabled:
            warnings.append("CRM Automation is disabled; automation UAT can be skipped for this tenant.")

        for warning in warnings:
            self.stdout.write(self.style.WARNING(f"[INFO] {warning}"))

        if failures:
            raise CommandError(f"CRM production-readiness gate failed with {len(failures)} issue(s).")

        self.stdout.write(self.style.SUCCESS("CRM PRODUCTION-READINESS TECHNICAL GATE PASSED"))
        self.stdout.write("Manual UAT, backup evidence and deployment approval are still required before production release.")
