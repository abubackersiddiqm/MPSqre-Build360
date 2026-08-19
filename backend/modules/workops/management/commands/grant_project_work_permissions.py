from __future__ import annotations

import uuid

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from modules.identity.models import Permission, Role, RolePermission
from modules.tenant.models import Company

WORK_PERMISSION_CODES = (
    "work.view",
    "work.project.manage",
    "work.plan.manage",
    "work.assign",
    "work.progress",
    "work.time.manage",
    "work.approve",
    "work.configure",
    "work.export",
)


class Command(BaseCommand):
    help = (
        "Grant Phase 30 Project and Work permissions to active company "
        "administrator roles. The operation is idempotent."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--company",
            default="",
            help="Optional company code or public UUID.",
        )
        parser.add_argument(
            "--role",
            default="",
            help="Optional exact role code or role name.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report intended grants without changing data.",
        )

    def handle(self, *args, **options):
        permissions = list(
            Permission.objects.filter(code__in=WORK_PERMISSION_CODES).order_by("code")
        )
        if len(permissions) != len(WORK_PERMISSION_CODES):
            found = {permission.code for permission in permissions}
            missing = sorted(set(WORK_PERMISSION_CODES) - found)
            raise CommandError(
                "Phase 30 permissions are missing: " + ", ".join(missing)
            )

        roles = Role.objects.filter(retired_at__isnull=True)
        company_value = options["company"].strip()
        if company_value:
            company = Company.objects.filter(code__iexact=company_value).first()
            if company is None:
                try:
                    company_public_id = uuid.UUID(company_value)
                except ValueError:
                    company_public_id = None
                if company_public_id is not None:
                    company = Company.objects.filter(public_id=company_public_id).first()
            if company is None:
                raise CommandError(f"Company not found: {company_value}")
            roles = roles.filter(company_public_id=company.public_id)

        role_value = options["role"].strip()
        if role_value:
            roles = roles.filter(
                Q(code__iexact=role_value) | Q(name__iexact=role_value)
            )
        else:
            roles = roles.filter(
                Q(code__icontains="ADMIN") | Q(name__icontains="ADMINISTRATOR")
            )

        selected_roles = list(roles.order_by("company_public_id", "code", "-version"))
        if not selected_roles:
            raise CommandError("No matching active administrator roles were found.")

        planned = 0
        created = 0
        with transaction.atomic():
            for role in selected_roles:
                for permission in permissions:
                    planned += 1
                    if options["dry_run"]:
                        continue
                    _, was_created = RolePermission.objects.get_or_create(
                        role=role,
                        permission=permission,
                    )
                    created += int(was_created)
            if options["dry_run"]:
                transaction.set_rollback(True)

        mode = "DRY RUN" if options["dry_run"] else "APPLIED"
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode}: {len(selected_roles)} role(s), "
                f"{planned} evaluated grant(s), {created} new grant(s)."
            )
        )
        for role in selected_roles:
            self.stdout.write(
                f"- {role.company_public_id} | {role.code} | {role.name} | v{role.version}"
            )
