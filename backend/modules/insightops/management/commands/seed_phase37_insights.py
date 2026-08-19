from django.core.management.base import BaseCommand, CommandError

from modules.insightops.application.services import seed_defaults
from modules.tenant.models import Company


class Command(BaseCommand):
    help = "Seed or reconcile Phase 37 executive intelligence policy and baseline KPI definitions."

    def add_arguments(self, parser):
        parser.add_argument("--company", required=False, default="", help="Company code; omit to seed all companies")

    def handle(self, *args, **options):
        company_code = options["company"]
        companies = Company.objects.filter(code=company_code) if company_code else Company.objects.all()
        if not companies.exists():
            raise CommandError(f"Company not found: {company_code}" if company_code else "No companies are available.")
        for company in companies.iterator():
            result = seed_defaults(company)
            self.stdout.write(self.style.SUCCESS(f"Phase 37 defaults reconciled for {company.code}: {result}"))
