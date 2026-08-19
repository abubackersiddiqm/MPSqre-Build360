from django.core.management.base import BaseCommand, CommandError

from modules.digitaltwinops.application.services import seed_defaults
from modules.tenant.models import Company


class Command(BaseCommand):
    help = "Create the generic Phase 39 digital twin governance policy."

    def add_arguments(self, parser):
        parser.add_argument("--company", default="")

    def handle(self, *args, **options):
        companies = Company.objects.all()
        if options["company"]:
            companies = companies.filter(code=options["company"])
            if not companies.exists():
                raise CommandError("Company not found.")
        total = 0
        for company in companies.iterator():
            result = seed_defaults(company)
            total += result["policy"]
        self.stdout.write(self.style.SUCCESS(f"Phase 39 policy reconciliation completed; {total} policies created."))
