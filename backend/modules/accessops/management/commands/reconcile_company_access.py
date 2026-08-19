from __future__ import annotations

import uuid
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db.models import Q
from django.utils import timezone

from modules.accessops.application.services import reconcile_standard_company_access
from modules.accessops.models import PlatformOperator
from modules.identity.application.permissions import effective_permission_codes
from modules.identity.models import Role
from modules.tenant.models import Company, Membership


EXPECTED_DATABASES = {
    "demo": "build360_demo",
    "testing": "build360_testing",
    "production": "build360_production",
}


class Command(BaseCommand):
    help = (
        "Reconcile standard COMPANY_ADMIN/COMPANY_USER roles for one existing company. "
        "This is governance repair, not seed data creation."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--company-code", required=True)
        parser.add_argument(
            "--confirm-production",
            action="store_true",
            help="Required when BUILD360_ENVIRONMENT=production.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        environment = str(
            getattr(settings, "BUILD360_ENVIRONMENT", "") or ""
        ).strip().lower()
        database_name = str(
            settings.DATABASES["default"].get("NAME", "") or ""
        ).strip()

        expected_database = EXPECTED_DATABASES.get(environment)
        if expected_database is None:
            raise CommandError(
                f"Unsupported Build360 environment: {environment or 'UNKNOWN'}."
            )
        if database_name != expected_database:
            raise CommandError(
                f"Environment {environment.upper()} requires database "
                f"'{expected_database}', got '{database_name}'."
            )
        if environment == "production" and not options["confirm_production"]:
            raise CommandError(
                "Production reconciliation requires --confirm-production."
            )

        company_code = str(options["company_code"]).strip().upper()
        company = Company.objects.filter(code=company_code).first()
        if company is None:
            raise CommandError(f"Company '{company_code}' was not found.")

        roots = list(
            PlatformOperator.objects.select_related("user")
            .filter(
                operator_type_code="ROOT_OPERATOR",
                is_active=True,
                user__is_active=True,
            )
            .order_by("created_at")
        )
        if len(roots) != 1:
            raise CommandError(
                "Exactly one active ROOT_OPERATOR is required for governed reconciliation; "
                f"found {len(roots)}."
            )
        actor = roots[0].user

        self.stdout.write("=" * 72)
        self.stdout.write("Build360 Standard Company Access Reconciliation")
        self.stdout.write(f"Environment : {environment.upper()}")
        self.stdout.write(f"Database    : {database_name}")
        self.stdout.write(f"Company     : {company.display_name} ({company.code})")
        self.stdout.write("Seed data   : NONE")
        self.stdout.write("=" * 72)

        self._print_memberships(company=company, title="BEFORE")

        summary = reconcile_standard_company_access(
            company=company,
            actor_public_id=actor.public_id,
            correlation_id=uuid.uuid4(),
        )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("RECONCILIATION APPLIED"))
        for key, value in summary.items():
            self.stdout.write(f"  {key}: {value}")

        self._print_memberships(company=company, title="AFTER")

    def _print_memberships(self, *, company: Company, title: str) -> None:
        now = timezone.now()
        memberships = list(
            Membership.objects.select_related("user")
            .filter(
                company=company,
                effective_from__lte=now,
                suspended_at__isnull=True,
                terminated_at__isnull=True,
                user__is_active=True,
            )
            .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now))
            .order_by("user__email")
        )

        self.stdout.write("")
        self.stdout.write(f"{title} EFFECTIVE ACCESS")
        if not memberships:
            self.stdout.write("  No active memberships.")
            return

        for membership in memberships:
            role_ids = list(
                membership.role_assignments.filter(effective_from__lte=now)
                .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now))
                .values_list("role_public_id", flat=True)
            )
            active_roles = list(
                Role.objects.filter(
                    public_id__in=role_ids,
                    company_public_id=company.public_id,
                    retired_at__isnull=True,
                    effective_from__lte=now,
                )
                .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now))
                .order_by("code")
            )
            active_role_ids = [role.public_id for role in active_roles]
            permissions = effective_permission_codes(
                company_public_id=company.public_id,
                role_public_ids=active_role_ids,
            )
            role_codes = ", ".join(role.code for role in active_roles) or "NONE"
            self.stdout.write(
                f"  {membership.user.email}: "
                f"roles=[{role_codes}] effective_permissions={len(permissions)}"
            )
