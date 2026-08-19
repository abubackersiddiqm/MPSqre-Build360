from django.core.management.base import BaseCommand, CommandError

from modules.identity.models import Permission, Role, RolePermission
from modules.tenant.models import Company

PERMISSIONS = [
    "support.view", "support.manage", "support.ticket", "support.resolve", "support.sla",
    "support.problem", "support.change", "support.knowledge", "support.improve", "support.export",
]


class Command(BaseCommand):
    help = "Grant Phase 36 support permissions to a company role."

    def add_arguments(self, parser):
        parser.add_argument("--company", required=True)
        parser.add_argument("--role", default="Company Administrator")

    def handle(self, *args, **options):
        company = Company.objects.filter(code=options["company"]).first()
        if not company:
            raise CommandError("Company not found.")
        role = Role.objects.filter(company=company, name=options["role"], retired_at__isnull=True).first()
        if not role:
            raise CommandError("Role not found.")
        permissions = list(Permission.objects.filter(code__in=PERMISSIONS))
        missing = sorted(set(PERMISSIONS) - {item.code for item in permissions})
        if missing:
            raise CommandError(f"Missing permissions: {', '.join(missing)}")
        created = 0
        for permission in permissions:
            _, was_created = RolePermission.objects.get_or_create(role=role, permission=permission)
            created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f"Granted {len(permissions)} permissions ({created} new) to {role.name}."))
