from django.core.management.base import BaseCommand, CommandError

from modules.identity.models import Permission, Role, RolePermission
from modules.tenant.models import Company


class Command(BaseCommand):
    help = "Grant Phase 42 development sales permissions to a tenant role."

    def add_arguments(self, parser):
        parser.add_argument("--company", required=True)
        parser.add_argument("--role", default="Company Administrator")

    def handle(self, *args, **options):
        company = Company.objects.filter(code=options["company"]).first()
        if company is None:
            raise CommandError("Company not found.")
        role = Role.objects.filter(company_public_id=company.public_id, name=options["role"], retired_at__isnull=True).first()
        if role is None:
            role = Role.objects.filter(company_public_id=company.public_id, code=options["role"], retired_at__isnull=True).first()
        if role is None:
            raise CommandError("Role not found.")
        permissions = Permission.objects.filter(code__startswith="sales.")
        created = 0
        for permission in permissions:
            _, was_created = RolePermission.objects.get_or_create(role=role, permission=permission)
            created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f"Reconciled {permissions.count()} sales permissions for {role.name}; created {created} grants."))
