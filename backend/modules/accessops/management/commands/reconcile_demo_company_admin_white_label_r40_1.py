from __future__ import annotations

import uuid

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from modules.accessops.application.services import (
    COMPANY_ADMIN_PERMISSION_CODES,
    STANDARD_COMPANY_ADMIN_ROLE_CODE,
    create_role,
)
from modules.accessops.models import PlatformOperator
from modules.identity.models import Role
from modules.tenant.models import Company


class Command(BaseCommand):
    help = (
        "Reconcile DEMO Company Administrator roles with the governed tenant "
        "branding/domain permissions required by White Label."
    )

    def handle(self, *args, **options):
        environment = str(getattr(settings, "BUILD360_ENVIRONMENT", "")).lower()
        database_name = str(settings.DATABASES["default"]["NAME"])
        if environment != "demo":
            raise CommandError("R40.1 access repair is DEMO-only and requires BUILD360_ENVIRONMENT=demo")
        if database_name != "build360_demo":
            raise CommandError(
                f"R40.1 access repair refuses database {database_name!r}; expected 'build360_demo'"
            )

        operator = (
            PlatformOperator.objects.select_related("user")
            .filter(is_active=True, operator_type_code="ROOT_OPERATOR", user__is_active=True)
            .order_by("id")
            .first()
        )
        if operator is None:
            raise CommandError("Active ROOT_OPERATOR not found. Apply/validate R37.3 first.")

        desired = set(COMPANY_ADMIN_PERMISSION_CODES)
        changed = 0
        unchanged = 0
        for company in Company.objects.filter(is_active=True).order_by("code"):
            current = (
                Role.objects.filter(
                    company_public_id=company.public_id,
                    code=STANDARD_COMPANY_ADMIN_ROLE_CODE,
                    retired_at__isnull=True,
                )
                .order_by("-version")
                .first()
            )
            current_codes = set()
            if current is not None:
                current_codes = set(
                    current.permission_grants.values_list("permission__code", flat=True)
                )
            if current is not None and current_codes == desired:
                self.stdout.write(
                    f"[OK] {company.code}: COMPANY_ADMIN v{current.version} already governed"
                )
                unchanged += 1
                continue

            role = create_role(
                company=company,
                code=STANDARD_COMPANY_ADMIN_ROLE_CODE,
                name="Company Administrator",
                permission_codes=list(COMPANY_ADMIN_PERMISSION_CODES),
                actor_public_id=operator.user.public_id,
                correlation_id=uuid.uuid4(),
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"[UPDATED] {company.code}: COMPANY_ADMIN -> v{role.version} "
                    f"({len(desired)} tenant-admin permissions)"
                )
            )
            changed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"R40.1 Company Admin access reconciliation complete: changed={changed}, unchanged={unchanged}"
            )
        )
