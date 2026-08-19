from __future__ import annotations

import hashlib
import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from modules.configuration.models import ConfigurationDefinition, ConfigurationVersion
from modules.tenant.models import Company, CompanyBrandProfile, Membership, TenantDomain

DEFAULT_STEPS = [
    {"code": "CRM", "label": "Enquiry & CRM", "description": "Customer, contact, lead and opportunity context."},
    {"code": "PRECONSTRUCTION", "label": "Pre-construction", "description": "Project setup and governed pre-construction readiness."},
    {"code": "DESIGN", "label": "Design", "description": "Documents, revisions, reviews and approvals."},
    {"code": "ESTIMATION", "label": "Estimation", "description": "Estimate versions, BOQ approval and baseline."},
    {"code": "CLIENT_APPROVAL", "label": "Client approval", "description": "Approved commercial/design information shared with the client."},
    {"code": "PLANNING", "label": "Planning", "description": "Project baseline, WBS and planned work."},
    {"code": "PROCUREMENT", "label": "Procurement", "description": "Material requests, RFQ, PO and receipt evidence."},
    {"code": "EXECUTION", "label": "Execution", "description": "Tasks and site progress against the plan."},
    {"code": "BILLING", "label": "Billing", "description": "Client invoices, collections and outstanding value."},
    {"code": "HANDOVER", "label": "Handover", "description": "Handover assets and completion evidence."},
]


class Command(BaseCommand):
    help = "Bootstrap white-label branding, platform subdomain and the configurable Project360 lifecycle."

    def add_arguments(self, parser):
        parser.add_argument("--company-code", required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        code = options["company_code"].strip().upper()
        company = Company.objects.filter(code=code).first()
        if company is None:
            raise CommandError(f"Company {code} was not found")
        membership = (
            Membership.objects.select_related("user")
            .filter(
                company=company,
                suspended_at__isnull=True,
                terminated_at__isnull=True,
            )
            .order_by("created_at")
            .first()
        )
        if membership is None:
            raise CommandError("At least one active company membership is required")

        brand, brand_created = CompanyBrandProfile.objects.get_or_create(
            company=company,
            defaults={
                "product_name": company.display_name,
                "tagline": "Construction Operating System",
                "sender_name": company.display_name,
            },
        )

        suffix = getattr(settings, "BUILD360_PLATFORM_DOMAIN_SUFFIX", "").strip().lower().strip(".")
        platform_domain = None
        if suffix:
            host = f"{company.code.lower()}.{suffix}"
            platform_domain = TenantDomain.objects.filter(domain=host).first()
            if platform_domain is not None and platform_domain.company_id != company.id:
                raise CommandError(f"Platform domain {host} is already assigned to another company")
            if platform_domain is None:
                platform_domain = TenantDomain.objects.create(
                    company=company,
                    domain=host,
                    domain_type=TenantDomain.DomainType.PLATFORM_SUBDOMAIN,
                    status=TenantDomain.Status.ACTIVE,
                    is_primary=not TenantDomain.objects.filter(company=company, is_primary=True).exists(),
                    verified_at=timezone.now(),
                    activated_at=timezone.now(),
                    ssl_status=TenantDomain.SslStatus.PENDING,
                )

        definition, _ = ConfigurationDefinition.objects.get_or_create(
            code="PROJECT360_LIFECYCLE",
            defaults={
                "name": "Project360 visual lifecycle",
                "description": "Configurable project journey used by Project360. It references existing domain records; it does not duplicate them.",
                "schema": {
                    "type": "object",
                    "required": ["steps"],
                    "properties": {
                        "steps": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["code", "label"],
                            },
                        }
                    },
                },
                "data_class": "OPERATIONAL_CONFIGURATION",
                "is_secret": False,
                "is_active": True,
            },
        )
        current = ConfigurationVersion.objects.filter(
            company=company,
            definition=definition,
            status=ConfigurationVersion.Status.PUBLISHED,
        ).order_by("-version").first()
        if current is None:
            payload = {"steps": DEFAULT_STEPS}
            checksum = hashlib.sha256(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            ConfigurationVersion.objects.create(
                company=company,
                definition=definition,
                version=1,
                status=ConfigurationVersion.Status.PUBLISHED,
                payload=payload,
                effective_from=timezone.now(),
                created_by_public_id=membership.user.public_id,
                published_at=timezone.now(),
                checksum=checksum,
            )

        self.stdout.write(self.style.SUCCESS("Build360 Experience Foundation bootstrap complete."))
        self.stdout.write(f"Company: {company.code} · {company.display_name}")
        self.stdout.write(f"Brand profile: {'created' if brand_created else 'existing'} v{brand.version}")
        self.stdout.write(f"Platform domain: {platform_domain.domain if platform_domain else 'not configured'}")
        self.stdout.write("Project360 lifecycle: PROJECT360_LIFECYCLE published")
