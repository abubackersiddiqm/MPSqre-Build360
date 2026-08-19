from django.core.management.base import BaseCommand, CommandError

from modules.identity.models import Permission, Role, RolePermission
from modules.tenant.models import Company

CODES = [
    "digitaltwin.view",
    "digitaltwin.manage",
    "digitaltwin.model",
    "digitaltwin.coordinate",
    "digitaltwin.issue",
    "digitaltwin.device",
    "digitaltwin.telemetry",
    "digitaltwin.alert",
    "digitaltwin.handover",
    "digitaltwin.approve",
    "digitaltwin.export",
]


class Command(BaseCommand):
    help = "Grant all Phase 39 digital twin permissions to a tenant role."

    def add_arguments(self, parser):
        parser.add_argument("--company", required=True)
        parser.add_argument("--role", default="Company Administrator")

    def handle(self, *args, **options):
        company = Company.objects.filter(code=options["company"]).first()
        if company is None:
            raise CommandError(f"Company not found: {options['company']}")
        role = Role.objects.filter(
            company_public_id=company.public_id,
            name=options["role"],
            retired_at__isnull=True,
        ).first()
        if role is None:
            role = Role.objects.filter(
                company_public_id=company.public_id,
                code=options["role"],
                retired_at__isnull=True,
            ).first()
        if role is None:
            raise CommandError(f"Active role not found: {options['role']}")
        permissions = Permission.objects.filter(code__in=CODES)
        missing = sorted(set(CODES) - set(permissions.values_list("code", flat=True)))
        if missing:
            raise CommandError(f"Missing permissions: {', '.join(missing)}")
        created = 0
        for permission in permissions:
            _, was_created = RolePermission.objects.get_or_create(role=role, permission=permission)
            created += int(was_created)
        self.stdout.write(
            self.style.SUCCESS(
                f"Granted/reconciled {permissions.count()} digital twin permissions; {created} new assignments."
            )
        )
