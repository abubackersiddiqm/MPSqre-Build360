from django.core.management.base import BaseCommand
from django.utils import timezone

from modules.stabilityops.models import PerformanceSample, StabilityPolicyVersion
from modules.tenant.models import Company


class Command(BaseCommand):
    help = "Delete performance telemetry older than each tenant's configured retention window."

    def add_arguments(self, parser):
        parser.add_argument("--company", help="Optional company code")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        companies = Company.objects.all()
        if options.get("company"):
            companies = companies.filter(code__iexact=options["company"])
        total = 0
        for company in companies.iterator():
            policy = (
                StabilityPolicyVersion.objects.filter(company=company, status_code="PUBLISHED").order_by("-version").first()
                or StabilityPolicyVersion.objects.filter(company=company).order_by("-version").first()
            )
            retention_days = policy.telemetry_retention_days if policy else 30
            cutoff = timezone.now() - timezone.timedelta(days=retention_days)
            queryset = PerformanceSample.objects.filter(company=company, observed_at__lt=cutoff)
            count = queryset.count()
            total += count
            if not options["dry_run"] and count:
                queryset.delete()
            self.stdout.write(f"{company.code}: {count} sample(s) {'would be removed' if options['dry_run'] else 'removed'}")
        self.stdout.write(self.style.SUCCESS(f"Telemetry retention processed: {total} sample(s)."))
