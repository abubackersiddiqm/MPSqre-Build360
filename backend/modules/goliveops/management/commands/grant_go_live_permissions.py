from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from modules.identity.models import Permission, Role, RolePermission

PERMISSION_CODES = [
    "golive.view",
    "golive.manage",
    "golive.migration",
    "golive.training",
    "golive.cutover",
    "golive.approve",
    "golive.hypercare",
    "golive.configure",
    "golive.export",
]


class Command(BaseCommand):
    help = "Grant Phase 35 permissions to a configurable company role."

    def add_arguments(self, parser):
        parser.add_argument("--company", required=True)
        parser.add_argument("--role", required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        company_code = options["company"].strip()
        role_name = options["role"].strip()
        role = Role.objects.filter(company__code=company_code, retired_at__isnull=True).filter(name=role_name).first()
        if role is None:
            role = Role.objects.filter(company__code=company_code, retired_at__isnull=True, code=role_name).first()
        if role is None:
            raise CommandError(f"Role not found for {company_code}: {role_name}")
        permissions = list(Permission.objects.filter(code__in=PERMISSION_CODES))
        missing = sorted(set(PERMISSION_CODES) - {permission.code for permission in permissions})
        if missing:
            raise CommandError(f"Permissions are missing: {', '.join(missing)}")
        created = 0
        for permission in permissions:
            _, was_created = RolePermission.objects.get_or_create(role=role, permission=permission)
            created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f"Granted/reconciled {len(permissions)} permissions for {role.name}; new links={created}."))
