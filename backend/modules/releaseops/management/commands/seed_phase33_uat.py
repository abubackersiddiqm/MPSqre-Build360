from django.core.management.base import BaseCommand, CommandError

from modules.releaseops.application.services import seed_uat_library
from modules.tenant.models import Company


class Command(BaseCommand):
    help = "Seed the current Build360 end-to-end UAT scenario library for one company."

    def add_arguments(self, parser):
        parser.add_argument("--company", required=True, help="Company code")

    def handle(self, *args, **options):
        company = Company.objects.filter(code=options["company"]).first()
        if company is None:
            raise CommandError("Company not found")
        created = seed_uat_library(company)
        self.stdout.write(self.style.SUCCESS(f"Build360 UAT library ready. New scenarios: {created}"))
