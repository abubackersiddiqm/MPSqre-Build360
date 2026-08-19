from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from modules.ai.models import AIModelPolicy, AIProviderProfile
from modules.tenant.models import Company


class Command(BaseCommand):
    help = "Bootstrap the governed CRM Lead Intelligence policy for one company."

    def add_arguments(self, parser):
        parser.add_argument("--company-code", required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        company = Company.objects.filter(
            code__iexact=options["company_code"].strip(),
            is_active=True,
        ).first()
        if company is None:
            raise CommandError("Active company was not found")

        provider, _ = AIProviderProfile.objects.update_or_create(
            company=company,
            code="LOCAL_GROUNDED",
            defaults={
                "display_name": "Build360 local governed adapter",
                "adapter_code": "local_grounded",
                "secret_reference": "",
                "data_residency": "tenant-database",
                "configuration": {
                    "network_access": False,
                    "persists_raw_prompts": False,
                    "executes_actions": False,
                    "crm_lead_intelligence": True,
                },
                "supports_citations": True,
                "supports_extraction": True,
                "supports_tools": False,
                "is_active": True,
            },
        )

        existing = (
            AIModelPolicy.objects.filter(
                company=company,
                code="CRM_LEAD_INTELLIGENCE",
                is_active=True,
            )
            .order_by("-version")
            .first()
        )
        if existing:
            self.stdout.write(self.style.SUCCESS(
                f"CRM Lead Intelligence policy already active: v{existing.version}"
            ))
            return

        latest = (
            AIModelPolicy.objects.filter(
                company=company,
                code="CRM_LEAD_INTELLIGENCE",
            )
            .order_by("-version")
            .first()
        )
        policy = AIModelPolicy(
            company=company,
            provider=provider,
            code="CRM_LEAD_INTELLIGENCE",
            name="CRM Sales Copilot",
            model_name="build360-local-grounded-crm-v2",
            purpose=AIModelPolicy.Purpose.ASSISTANT,
            system_instruction=(
                "Summarize the selected CRM lead and authorized relationship history. "
                "Recommend one advisory next action, prepare next-call talking points, and create "
                "English plus practical Roman-Tamil Tanglish drafts using cited evidence only. "
                "Do not change lead stage, send communications, reveal protected contact fields, "
                "or execute business actions."
            ),
            allowed_source_types=["crm.lead", "crm.activity", "crm.stage_history"],
            allowed_data_classifications=["internal", "confidential"],
            allowed_tool_codes=[],
            max_context_records=30,
            max_output_characters=4000,
            human_review_required=False,
            citations_required=True,
            retention_days=90,
            effective_from=timezone.now(),
            is_active=True,
            version=(latest.version + 1) if latest else 1,
        )
        policy.full_clean()
        policy.save()
        self.stdout.write(self.style.SUCCESS(
            f"CRM Lead Intelligence policy created: v{policy.version}"
        ))
        self.stdout.write("Provider: LOCAL_GROUNDED")
        self.stdout.write("External network execution: disabled")
