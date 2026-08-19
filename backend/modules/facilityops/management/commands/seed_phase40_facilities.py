from django.core.management.base import BaseCommand, CommandError

from modules.facilityops.application.services import seed_defaults
from modules.tenant.models import Company


class Command(BaseCommand):
    help = "Seed the Phase 40 draft facilities governance policy."

    def add_arguments(self, parser):
        parser.add_argument("--company", default="")

    def handle(self, *args, **options):
        queryset = Company.objects.all().order_by("code")
        if options["company"]:
            queryset = queryset.filter(code=options["company"])
            if not queryset.exists():
                raise CommandError(f"Company not found: {options['company']}")
        created = 0
        for company in queryset.iterator():
            created += seed_defaults(company)["policy"]
        self.stdout.write(self.style.SUCCESS(f"Phase 40 facilities policy reconciliation completed; {created} new policy records."))
