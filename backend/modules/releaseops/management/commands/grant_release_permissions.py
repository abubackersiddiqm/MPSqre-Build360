from django.core.management.base import BaseCommand, CommandError

from modules.identity.models import Permission, Role, RolePermission
from modules.tenant.models import Company


class Command(BaseCommand):
    help = "Grant all release.* permissions to a selected active role."

    def add_arguments(self, parser):
        parser.add_argument("--company", required=True, help="Company code")
        parser.add_argument("--role", default="Company Administrator", help="Role name or code")

    def handle(self, *args, **options):
        company = Company.objects.filter(code=options["company"]).first()
        if company is None:
            raise CommandError("Company not found")
        role_value = options["role"]
        role = Role.objects.filter(company_public_id=company.public_id, retired_at__isnull=True).filter(
            name__iexact=role_value
        ).order_by("-version").first()
        if role is None:
            role = Role.objects.filter(company_public_id=company.public_id, retired_at__isnull=True, code__iexact=role_value).order_by("-version").first()
        if role is None:
            raise CommandError("Role not found")
        permissions = list(Permission.objects.filter(code__startswith="release."))
        for permission in permissions:
            RolePermission.objects.get_or_create(role=role, permission=permission)
        self.stdout.write(self.style.SUCCESS(f"Granted {len(permissions)} release permissions to {role.name}."))
