from django.core.management.base import BaseCommand

from modules.supportops.application.services import seed_defaults
from modules.tenant.models import Company


class Command(BaseCommand):
    help = "Seed Phase 36 support policies and service catalog items."

    def add_arguments(self, parser):
        parser.add_argument("--company", dest="company_code")

    def handle(self, *args, **options):
        companies = Company.objects.all()
        if options.get("company_code"):
            companies = companies.filter(code=options["company_code"])
        if not companies.exists():
            self.stderr.write(self.style.ERROR("No matching company found."))
            return
        for company in companies.iterator():
            result = seed_defaults(company)
            self.stdout.write(self.style.SUCCESS(f"{company.code}: {result}"))
