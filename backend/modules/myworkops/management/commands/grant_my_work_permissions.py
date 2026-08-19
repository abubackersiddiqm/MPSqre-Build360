from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from modules.identity.models import Permission, Role, RolePermission
from modules.tenant.models import Company

CODES = (
    "mywork.view",
    "mywork.execute",
    "mywork.time",
    "mywork.approve",
    "mywork.offline",
    "mywork.configure",
    "mywork.export",
)


class Command(BaseCommand):
    help = "Reconcile Phase 31 My Work permissions for one company role or all administrator roles."

    def add_arguments(self, parser):
        parser.add_argument("--company", required=True)
        parser.add_argument("--role", default="")

    def handle(self, *args, **options):
        company = Company.objects.filter(code__iexact=options["company"]).first()
        if company is None:
            raise CommandError("Company not found")
        permissions = list(Permission.objects.filter(code__in=CODES))
        if len(permissions) != len(CODES):
            missing = sorted(set(CODES) - {item.code for item in permissions})
            raise CommandError(f"Missing permissions: {', '.join(missing)}. Run migrations first.")
        roles = Role.objects.filter(company_public_id=company.public_id, retired_at__isnull=True)
        if options["role"]:
            roles = roles.filter(Q(code__iexact=options["role"]) | Q(name__iexact=options["role"]))
        else:
            roles = roles.filter(Q(code__icontains="ADMIN") | Q(name__icontains="ADMINISTRATOR"))
        if not roles.exists():
            raise CommandError("No matching active role found")
        grants = 0
        for role in roles:
            for permission in permissions:
                _, created = RolePermission.objects.get_or_create(role=role, permission=permission)
                grants += int(created)
            self.stdout.write(self.style.SUCCESS(f"{role.name}: {len(permissions)} My Work permissions reconciled"))
        self.stdout.write(self.style.SUCCESS(f"Completed with {grants} new grant(s)"))
