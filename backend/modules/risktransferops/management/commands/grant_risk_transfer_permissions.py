from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone

from modules.identity.models import Permission, Role, RolePermission
from modules.tenant.models import Company

PERMISSIONS = [
    "risktransfer.view", "risktransfer.manage", "risktransfer.counterparty", "risktransfer.program",
    "risktransfer.coverage", "risktransfer.premium", "risktransfer.loss", "risktransfer.claim",
    "risktransfer.instrument", "risktransfer.call", "risktransfer.approve", "risktransfer.export",
]


class Command(BaseCommand):
    help = "Grant Phase 45 risk-transfer permissions to eligible roles."

    def add_arguments(self, parser):
        parser.add_argument("--company", required=True)
        parser.add_argument("--role", required=False, default="")

    def handle(self, *args, **options):
        company = Company.objects.filter(code=options["company"].strip().upper()).first()
        if company is None:
            raise CommandError("Company not found.")
        permissions = list(Permission.objects.filter(code__in=PERMISSIONS))
        if len(permissions) != len(PERMISSIONS):
            raise CommandError("Phase 45 permission inventory is incomplete. Apply migrations first.")
        roles = Role.objects.filter(company_public_id=company.public_id, retired_at__isnull=True).filter(
            Q(effective_to__isnull=True) | Q(effective_to__gt=timezone.now())
        )
        if options["role"]:
            roles = roles.filter(Q(code__iexact=options["role"]) | Q(name__iexact=options["role"]))
        else:
            roles = roles.filter(Q(code__icontains="ADMIN") | Q(name__icontains="ADMINISTRATOR"))
        if not roles.exists():
            raise CommandError("No matching active role found.")
        grants = 0
        for role in roles:
            for permission in permissions:
                _, created = RolePermission.objects.get_or_create(role=role, permission=permission)
                grants += int(created)
        self.stdout.write(self.style.SUCCESS(f"Risk-transfer permissions reconciled. New grants: {grants}"))
