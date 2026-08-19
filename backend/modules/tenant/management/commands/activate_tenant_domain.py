from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import models, transaction
from django.utils import timezone

from modules.tenant.models import Company, TenantDomain


class Command(BaseCommand):
    help = "Activate a custom tenant domain after deployment/DNS verification has been completed outside the application."

    def add_arguments(self, parser):
        parser.add_argument("--company-code", required=True)
        parser.add_argument("--domain", required=True)
        parser.add_argument("--dns-verified", action="store_true")
        parser.add_argument("--make-primary", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        if not options["dns_verified"]:
            raise CommandError("Refusing activation without --dns-verified evidence acknowledgement")
        company = Company.objects.filter(code=options["company_code"].strip().upper()).first()
        if company is None:
            raise CommandError("Company not found")
        domain = options["domain"].strip().lower().rstrip(".")
        item = TenantDomain.objects.select_for_update().filter(company=company, domain=domain).first()
        if item is None:
            raise CommandError("Domain registration not found")
        if item.domain_type != TenantDomain.DomainType.CUSTOM_DOMAIN:
            raise CommandError("This command is only required for custom domains")
        if options["make_primary"]:
            TenantDomain.objects.filter(company=company, is_primary=True).update(is_primary=False, version=models.F("version") + 1)
            item.is_primary = True
        item.status = TenantDomain.Status.ACTIVE
        item.verified_at = item.verified_at or timezone.now()
        item.activated_at = item.activated_at or timezone.now()
        item.ssl_status = TenantDomain.SslStatus.PENDING
        item.version += 1
        item.full_clean()
        item.save()
        self.stdout.write(self.style.SUCCESS(f"Activated tenant mapping for {item.domain}."))
        self.stdout.write("SSL status remains PENDING until the hosting/edge platform proves certificate provisioning.")
