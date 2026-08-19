from django.core.management.base import BaseCommand, CommandError

from modules.goliveops.application.services import seed_defaults
from modules.tenant.models import Company


class Command(BaseCommand):
    help = "Reconcile Phase 35 go-live policies and readiness gates."

    def add_arguments(self, parser):
        parser.add_argument("--company", dest="company_code", default="")

    def handle(self, *args, **options):
        company_code = options["company_code"].strip()
        companies = Company.objects.all().order_by("code")
        if company_code:
            companies = companies.filter(code=company_code)
            if not companies.exists():
                raise CommandError(f"Company not found: {company_code}")
        total = 0
        for company in companies.iterator():
            result = seed_defaults(company)
            total += 1
            self.stdout.write(f"{company.code}: policy={result['policy_version']} new_gates={result['gates']}")
        self.stdout.write(self.style.SUCCESS(f"Phase 35 defaults reconciled for {total} company record(s)."))
