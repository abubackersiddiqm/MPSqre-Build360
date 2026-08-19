from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone

from modules.identity.models import Permission, Role, RolePermission
from modules.tenant.models import Company

CODES = (
    "collaboration.view",
    "collaboration.manage",
    "collaboration.invite",
    "collaboration.grant",
    "collaboration.request",
    "collaboration.submit",
    "collaboration.approve",
    "collaboration.message",
    "collaboration.configure",
    "collaboration.export",
    "collaboration.portal",
)

EXTERNAL_ROLES = {
    "EXTERNAL_COLLABORATOR": ("External Collaborator", ["collaboration.portal", "collaboration.submit", "collaboration.message"]),
    "EXTERNAL_APPROVER": ("External Approver", ["collaboration.portal", "collaboration.submit", "collaboration.message", "collaboration.approve"]),
}


class Command(BaseCommand):
    help = "Reconcile Phase 32 collaboration permissions and external roles for one company."

    def add_arguments(self, parser):
        parser.add_argument("--company", required=True)
        parser.add_argument("--role", default="")

    def handle(self, *args, **options):
        company = Company.objects.filter(code__iexact=options["company"]).first()
        if company is None:
            raise CommandError("Company not found")
        permissions = {item.code: item for item in Permission.objects.filter(code__in=CODES)}
        missing = sorted(set(CODES) - set(permissions))
        if missing:
            raise CommandError(f"Missing permissions: {', '.join(missing)}. Run migrations first.")

        roles = Role.objects.filter(company_public_id=company.public_id, retired_at__isnull=True)
        if options["role"]:
            roles = roles.filter(Q(code__iexact=options["role"]) | Q(name__iexact=options["role"]))
        else:
            roles = roles.filter(Q(code__icontains="ADMIN") | Q(name__icontains="ADMINISTRATOR"))
        if not roles.exists():
            raise CommandError("No matching active administrator role found")

        grants = 0
        for role in roles:
            for permission in permissions.values():
                _, created = RolePermission.objects.get_or_create(role=role, permission=permission)
                grants += int(created)
            self.stdout.write(self.style.SUCCESS(f"{role.name}: {len(CODES)} collaboration permissions reconciled"))

        for code, (name, role_codes) in EXTERNAL_ROLES.items():
            role = Role.objects.filter(
                company_public_id=company.public_id,
                code=code,
                retired_at__isnull=True,
            ).order_by("-version").first()
            if role is None:
                role = Role.objects.create(
                    company_public_id=company.public_id,
                    code=code,
                    name=name,
                    version=1,
                    effective_from=timezone.now(),
                )
            for permission_code in role_codes:
                RolePermission.objects.get_or_create(role=role, permission=permissions[permission_code])
            self.stdout.write(self.style.SUCCESS(f"{role.name}: external portal scope reconciled"))

        self.stdout.write(self.style.SUCCESS(f"Completed with {grants} new administrator grant(s)"))
