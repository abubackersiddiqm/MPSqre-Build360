from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError

from modules.orgops.models import Department, Designation, LeaveType, WorkCalendar
from modules.tenant.models import Company


class Command(BaseCommand):
    help = "Create optional generic Phase 29 demonstration organization data"

    def add_arguments(self, parser):
        parser.add_argument("--company", required=True, help="Tenant company code")

    def handle(self, *args, **options):
        company = Company.objects.filter(code__iexact=options["company"]).first()
        if not company:
            raise CommandError("Company was not found")
        calendar, _ = WorkCalendar.objects.get_or_create(
            company=company,
            code="STANDARD",
            defaults={
                "name": "Standard work calendar",
                "timezone": company.timezone,
                "working_days": [1, 2, 3, 4, 5, 6],
                "standard_hours_per_day": Decimal("8.00"),
            },
        )
        department, _ = Department.objects.get_or_create(
            company=company,
            code="PROJECT_DELIVERY",
            defaults={"name": "Project Delivery"},
        )
        designation, _ = Designation.objects.get_or_create(
            company=company,
            code="SITE_ENGINEER",
            defaults={"name": "Site Engineer", "level_code": "DELIVERY"},
        )
        leave_type, _ = LeaveType.objects.get_or_create(
            company=company,
            code="GENERAL_LEAVE",
            defaults={
                "name": "General Leave",
                "unit_code": "DAYS",
                "requires_approval": True,
                "is_paid": True,
            },
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Demo organization data ready: {calendar.code}, {department.code}, "
                f"{designation.code}, {leave_type.code}"
            )
        )
