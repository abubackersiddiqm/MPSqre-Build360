from django.core.management.base import BaseCommand, CommandError

from modules.releaseops.application.services import DEFAULT_GATES, seed_uat_library
from modules.releaseops.models import ReleaseCandidate, ReleaseGate, UATExecution, UATScenario
from modules.tenant.models import Company


class Command(BaseCommand):
    help = "Seed the current Build360 UAT library and attach missing scenarios to open release candidates."

    def add_arguments(self, parser):
        parser.add_argument("--company", required=True, help="Company code")
        parser.add_argument("--release", help="Optional release code to limit synchronization")

    def handle(self, *args, **options):
        company = Company.objects.filter(code=options["company"]).first()
        if company is None:
            raise CommandError("Company not found")

        created_scenarios = seed_uat_library(company)
        releases = ReleaseCandidate.objects.filter(
            company=company,
            status_code__in=["DRAFT", "IN_REVIEW", "READY"],
        )
        if options.get("release"):
            releases = releases.filter(release_code=options["release"].strip().upper())
            if not releases.exists():
                raise CommandError("Open release candidate not found")

        scenarios = list(UATScenario.objects.filter(company=company, status_code="ACTIVE"))
        created_executions = 0
        created_gates = 0
        release_count = 0
        for release in releases:
            release_count += 1
            for code, name, category in DEFAULT_GATES:
                _, created = ReleaseGate.objects.get_or_create(
                    company=company,
                    release=release,
                    code=code,
                    defaults={"name": name, "category_code": category, "is_required": True},
                )
                created_gates += int(created)
            for scenario in scenarios:
                _, created = UATExecution.objects.get_or_create(
                    company=company,
                    release=release,
                    scenario=scenario,
                )
                created_executions += int(created)

        self.stdout.write(
            self.style.SUCCESS(
                "UAT synchronization complete. "
                f"New scenarios: {created_scenarios}; "
                f"open releases updated: {release_count}; "
                f"new gates: {created_gates}; "
                f"new executions: {created_executions}."
            )
        )
