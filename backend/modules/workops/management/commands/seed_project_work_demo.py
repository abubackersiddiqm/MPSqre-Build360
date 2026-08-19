from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from modules.employee.models import Employee
from modules.tenant.models import Company, Location
from modules.workops.models import (
    ChecklistItem,
    Project,
    ProjectSite,
    WBSNode,
    WorkAssignment,
    WorkItem,
    WorkPackage,
)


class Command(BaseCommand):
    help = "Create generic Phase 30 demonstration project and work records"

    def add_arguments(self, parser):
        parser.add_argument("--company", required=True, help="Tenant company code")

    def handle(self, *args, **options):
        company = Company.objects.filter(code=options["company"]).first()
        if not company:
            raise CommandError("Company not found")
        today = timezone.localdate()
        employees = list(Employee.objects.filter(company=company).select_related("membership", "membership__user").order_by("employee_number")[:2])
        employee = employees[0] if employees else None
        reviewer = employees[1] if len(employees) > 1 else None
        actor_public_id = employee.membership.user.public_id if employee else company.public_id
        location = Location.objects.filter(company=company).order_by("name").first()
        project, _ = Project.objects.get_or_create(
            company=company,
            code="DEMO_PROJECT",
            defaults={
                "name": "Build360 Demonstration Project",
                "description": "Generic non-production project for validating Phase 30 workflows.",
                "project_type_code": "CONSTRUCTION",
                "status_code": "ACTIVE",
                "priority_code": "NORMAL",
                "manager": employee,
                "location": location,
                "start_date": today,
                "target_end_date": today + timedelta(days=180),
                "currency": company.currency,
                "budget": Decimal("1000000.00"),
            },
        )
        site, _ = ProjectSite.objects.get_or_create(
            company=company,
            project=project,
            code="SITE_A",
            defaults={"name": "Demonstration Site A", "location": location, "start_date": today, "target_end_date": today + timedelta(days=180)},
        )
        wbs, _ = WBSNode.objects.get_or_create(
            company=company,
            project=project,
            code="1.0",
            defaults={"name": "Substructure", "sequence": 1, "level": 1},
        )
        package, _ = WorkPackage.objects.get_or_create(
            company=company,
            project=project,
            wbs_node=wbs,
            code="WP_FOUNDATION",
            defaults={
                "name": "Foundation Works",
                "owner": employee,
                "planned_start": today,
                "planned_end": today + timedelta(days=30),
                "status_code": "PLANNED",
                "progress_weight": Decimal("10.00"),
            },
        )
        item, _ = WorkItem.objects.get_or_create(
            company=company,
            project=project,
            code="TASK_EXCAVATION",
            defaults={
                "site": site,
                "work_package": package,
                "title": "Complete foundation excavation",
                "description": "Demonstration work item. Replace with tenant-specific planning data.",
                "status_code": "ASSIGNED" if employee else "BACKLOG",
                "priority_code": "HIGH",
                "planned_start": today,
                "due_date": today + timedelta(days=7),
                "estimated_hours": Decimal("40.00"),
                "primary_assignee": employee,
                "reviewer": reviewer,
                "created_by_public_id": actor_public_id,
            },
        )
        if employee:
            WorkAssignment.objects.get_or_create(
                company=company,
                work_item=item,
                employee=employee,
                assignment_role_code="PRIMARY",
                defaults={
                    "allocation_percent": Decimal("100.00"),
                    "effective_from": today,
                },
            )
        ChecklistItem.objects.get_or_create(
            company=company,
            work_item=item,
            sequence=1,
            defaults={
                "title": "Execution evidence attached and verified",
                "is_required": True,
            },
        )
        self.stdout.write(self.style.SUCCESS(f"Phase 30 demo ready: {project.code} / {item.code}"))
