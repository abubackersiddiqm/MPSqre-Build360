from django.core.management.base import BaseCommand, CommandError

from modules.salesops.application.services import seed_defaults
from modules.tenant.models import Company


class Command(BaseCommand):
    help = "Create generic Phase 42 development sales governance defaults."

    def add_arguments(self, parser):
        parser.add_argument("--company", default="")

    def handle(self, *args, **options):
        code = options["company"].strip()
        companies = Company.objects.filter(code=code) if code else Company.objects.all()
        if code and not companies.exists():
            raise CommandError(f"Company not found: {code}")
        count = 0
        for company in companies.iterator():
            result = seed_defaults(company)
            count += result["policy"]
        self.stdout.write(self.style.SUCCESS(f"Phase 42 development sales defaults reconciled. Created policies: {count}"))
