from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from modules.ai.models import AIEntityInsight, AIModelPolicy
from modules.subscription.application.entitlements import effective_entitlements
from modules.tenant.models import Company


class Command(BaseCommand):
    help = "Read-only CRM Lead Intelligence diagnostics."

    def add_arguments(self, parser):
        parser.add_argument("--company-code", required=True)

    def handle(self, *args, **options):
        company = Company.objects.filter(
            code__iexact=options["company_code"].strip(),
            is_active=True,
        ).first()
        if company is None:
            raise CommandError("Active company was not found")

        effective = effective_entitlements(company=company)
        policy = (
            AIModelPolicy.objects.select_related("provider")
            .filter(company=company, code="CRM_LEAD_INTELLIGENCE", is_active=True)
            .order_by("-version")
            .first()
        )
        summary = (
            effective.entitlements.get("crm.ai_summary")
            if "crm.ai_summary" in effective.entitlements
            else effective.entitlements.get("ai", effective.entitlements.get("crm", False))
        )
        recommendation = (
            effective.entitlements.get("crm.ai_recommendation")
            if "crm.ai_recommendation" in effective.entitlements
            else effective.entitlements.get("ai", effective.entitlements.get("crm", False))
        )

        self.stdout.write(f"[COMPANY] {company.code} · {company.display_name}")
        self.stdout.write(f"[SUBSCRIPTION] {effective.subscription_status} · {effective.plan_code or 'NO PLAN'}")
        self.stdout.write(f"[AI SUMMARY] {'ENABLED' if summary else 'DISABLED'}")
        self.stdout.write(f"[AI RECOMMENDATION] {'ENABLED' if recommendation else 'DISABLED'}")
        self.stdout.write(f"[LOCAL ADAPTER] {'ENABLED' if settings.AI_LOCAL_ADAPTER_ENABLED else 'DISABLED'}")
        if policy:
            self.stdout.write(f"[POLICY] {policy.code} v{policy.version} · {policy.provider.code} · {policy.provider.adapter_code}")
            self.stdout.write(f"[MODEL] {policy.model_name}")
            self.stdout.write(
                "[EXECUTION] LOCAL_GROUNDED · external network disabled"
                if policy.provider.adapter_code == "local_grounded"
                else "[EXECUTION] EXTERNAL PROVIDER POLICY"
            )
        else:
            self.stdout.write("[POLICY] MISSING — run Bootstrap-CRM-AI-Lead-Intelligence.bat")
        self.stdout.write(f"[CACHED LEAD INSIGHTS] {AIEntityInsight.objects.filter(company=company, subject_type='crm.lead').count()}")
        self.stdout.write("[DONE] No protected contact endpoint or external AI secret was printed.")
