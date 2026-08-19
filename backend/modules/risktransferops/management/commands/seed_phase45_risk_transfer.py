from django.core.management.base import BaseCommand, CommandError

from modules.risktransferops.application.services import seed_defaults
from modules.tenant.models import Company


class Command(BaseCommand):
    help = "Seed generic Phase 45 risk-transfer governance defaults."

    def add_arguments(self, parser):
        parser.add_argument("--company", dest="company_code", default="")

    def handle(self, *args, **options):
        company_code = options["company_code"].strip()
        companies = Company.objects.all()
        if company_code:
            companies = companies.filter(code=company_code)
            if not companies.exists():
                raise CommandError(f"Company not found: {company_code}")
        totals = {"policy": 0}
        for company in companies.iterator():
            result = seed_defaults(company)
            totals["policy"] += result["policy"]
        self.stdout.write(self.style.SUCCESS(f"Phase 45 risk-transfer defaults reconciled: {totals}"))
