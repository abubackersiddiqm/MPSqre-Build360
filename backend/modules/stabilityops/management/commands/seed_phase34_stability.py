from django.core.management.base import BaseCommand, CommandError

from modules.stabilityops.application.services import seed_defaults
from modules.tenant.models import Company


class Command(BaseCommand):
    help = "Seed generic Phase 34 stability policy, endpoint registry and stabilization gates."

    def add_arguments(self, parser):
        parser.add_argument("--company", help="Company code. Omit to seed every active company.")

    def handle(self, *args, **options):
        company_code = options.get("company")
        companies = Company.objects.filter(is_active=True)
        if company_code:
            companies = companies.filter(code__iexact=company_code)
        if not companies.exists():
            raise CommandError("No matching active company was found.")
        for company in companies:
            result = seed_defaults(company)
            self.stdout.write(
                self.style.SUCCESS(
                    f"{company.code}: policy={result['policy']} endpoints={result['endpoints']} gates={result['gates']}"
                )
            )
