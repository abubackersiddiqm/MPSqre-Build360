from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from modules.identity.models import Permission, Role, RolePermission
from modules.tenant.models import Company


class Command(BaseCommand):
    help = "Grant all Phase 34 stability permissions to a tenant role."

    def add_arguments(self, parser):
        parser.add_argument("--company", required=True, help="Company code")
        parser.add_argument("--role", default="Company Administrator", help="Role name or code")

    def handle(self, *args, **options):
        company = Company.objects.filter(code__iexact=options["company"]).first()
        if company is None:
            raise CommandError("Company not found.")
        role_value = options["role"]
        roles = Role.objects.filter(company_public_id=company.public_id, retired_at__isnull=True).filter(
            Q(name__iexact=role_value) | Q(code__iexact=role_value)
        )
        if not roles.exists():
            raise CommandError("Role not found for the selected company.")
        permissions = list(Permission.objects.filter(code__startswith="stability."))
        if len(permissions) != 9:
            raise CommandError(f"Expected 9 stability permissions, found {len(permissions)}. Run migrations first.")
        created = 0
        for role in roles:
            for permission in permissions:
                _, was_created = RolePermission.objects.get_or_create(role=role, permission=permission)
                created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f"Granted/reconciled 9 permissions across {roles.count()} role(s); {created} new grants."))
