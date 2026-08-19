from __future__ import annotations

import os

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count

from modules.integration.application.meta_leads import META_PROVIDER_CODE
from modules.integration.models import ConnectorProfile, DataMappingProfile, MetaLeadReceipt
from modules.subscription.application.entitlements import effective_entitlements
from modules.tenant.models import Company, Membership


class Command(BaseCommand):
    help = "Read-only diagnostics for Build360 Meta Lead Ads ingestion."

    def add_arguments(self, parser):
        parser.add_argument("--company-code", required=True)

    def handle(self, *args, **options):
        company = Company.objects.filter(code__iexact=options["company_code"].strip()).first()
        if company is None:
            raise CommandError("Company was not found")

        effective = effective_entitlements(company=company)
        if "crm.meta_ads" in effective.entitlements:
            entitled = effective.entitlements["crm.meta_ads"]
            entitlement_source = "crm.meta_ads"
        else:
            entitled = effective.entitlements.get("crm", False)
            entitlement_source = "crm fallback"

        self.stdout.write(f"[COMPANY] {company.code} · {company.display_name}")
        self.stdout.write(f"[SUBSCRIPTION] {effective.subscription_status} · {effective.plan_code or 'NO PLAN'}")
        self.stdout.write(
            f"[META ENTITLEMENT] {'ENABLED' if entitled else 'DISABLED'} via {entitlement_source}"
        )

        connectors = ConnectorProfile.objects.filter(
            company=company,
            provider_code=META_PROVIDER_CODE,
        ).order_by("code")
        self.stdout.write(f"[CONNECTORS] {connectors.count()}")
        for connector in connectors:
            cfg = connector.public_config or {}
            secret_ref = connector.secret_ref
            env_available = False
            if secret_ref.startswith("env://"):
                env_available = bool(os.getenv(secret_ref.removeprefix("env://"), "").strip())
            owner_ok = Membership.objects.filter(
                company=company,
                public_id=cfg.get("default_owner_membership_public_id"),
                suspended_at__isnull=True,
                terminated_at__isnull=True,
                user__is_active=True,
            ).exists()
            mapping_ok = DataMappingProfile.objects.filter(
                connector=connector,
                code=cfg.get("mapping_code") or "META_LEAD_DEFAULT",
                status=DataMappingProfile.Status.PUBLISHED,
            ).exists()
            receipt_counts = {
                row["status"]: row["count"]
                for row in MetaLeadReceipt.objects.filter(connector=connector)
                .values("status")
                .annotate(count=Count("id"))
            }
            self.stdout.write("")
            self.stdout.write(f"  [CONNECTOR] {connector.code} · {connector.status}")
            self.stdout.write(f"  [PAGE] {cfg.get('page_id') or 'MISSING'}")
            self.stdout.write(f"  [FORMS] {', '.join(cfg.get('lead_form_ids') or []) or 'ALL CONFIGURED PAGE FORMS'}")
            self.stdout.write(f"  [GRAPH VERSION] {cfg.get('graph_api_version') or 'MISSING'}")
            self.stdout.write(f"  [OWNER] {'OK' if owner_ok else 'MISSING/INACTIVE'}")
            self.stdout.write(f"  [MAPPING] {'PUBLISHED' if mapping_ok else 'MISSING'}")
            self.stdout.write(
                f"  [SECRET REF] {'CONFIGURED' if secret_ref else 'MISSING'} · "
                f"backend value {'AVAILABLE' if env_available else 'NOT AVAILABLE'}"
            )
            self.stdout.write(
                f"  [VERIFY TOKEN] {'CONFIGURED' if cfg.get('webhook_verify_token_digest') else 'MISSING'}"
            )
            self.stdout.write(f"  [RECEIPTS] {receipt_counts or {}}")

        if not connectors.exists():
            self.stdout.write("")
            self.stdout.write("[NEXT] Open /crm/meta-leads and create the first connector.")
        elif not entitled:
            self.stdout.write("")
            self.stdout.write("[BLOCKED] Enable crm.meta_ads (or the legacy broad crm entitlement) through governed subscription administration.")
        else:
            self.stdout.write("")
            self.stdout.write("[DONE] Diagnostic completed without revealing any raw Meta secret.")
