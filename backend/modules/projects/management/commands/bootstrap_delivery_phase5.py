from __future__ import annotations

from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from modules.identity.models import Permission, Role, RolePermission, User
from modules.projects.application.defaults import DEFAULT_DELIVERY_STAGES
from modules.projects.models import DeliveryStage
from modules.tenant.models import Company, Membership

STAGES = DEFAULT_DELIVERY_STAGES


class Command(BaseCommand):
    help = "Initialize Phase 5 delivery stages and grant project/design/estimation permissions."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--company-code", required=True)
        parser.add_argument("--admin-email", required=True)

    @transaction.atomic
    def handle(self, *args: object, **options: object) -> None:
        company_code = str(options["company_code"]).strip()
        admin_email = str(options["admin_email"]).strip().lower()
        company = Company.objects.filter(code__iexact=company_code, is_active=True).first()
        if company is None:
            raise CommandError("Active company was not found")
        user = User.objects.filter(email__iexact=admin_email, is_active=True).first()
        if user is None:
            raise CommandError("Active administrator was not found")
        membership = Membership.objects.filter(
            company=company,
            user=user,
            suspended_at__isnull=True,
            terminated_at__isnull=True,
        ).first()
        if membership is None:
            raise CommandError("Administrator does not have an active company membership")
        now = timezone.now()
        stage_count = 0
        for entity_type, definitions in STAGES.items():
            stage_count += self._install_stages(company, entity_type, definitions, now)
        role_ids = membership.role_assignments.filter(effective_from__lte=now).filter(
            Q(effective_to__isnull=True) | Q(effective_to__gt=now)
        ).values_list("role_public_id", flat=True)
        roles = list(
            Role.objects.filter(
                company_public_id=company.public_id,
                public_id__in=role_ids,
                retired_at__isnull=True,
            )
        )
        if not roles:
            raise CommandError("Administrator has no active role assignment")
        permissions = list(
            Permission.objects.filter(
                Q(code__startswith="project.")
                | Q(code__startswith="design.")
                | Q(code__startswith="estimation.")
            )
        )
        if not permissions:
            raise CommandError("Phase 5 permissions are missing; apply migrations first")
        created_grants = 0
        for role in roles:
            for permission in permissions:
                _, created = RolePermission.objects.get_or_create(
                    role=role,
                    permission=permission,
                )
                created_grants += int(created)
        self.stdout.write(self.style.SUCCESS("PHASE 5 DELIVERY INITIALIZATION COMPLETED"))
        self.stdout.write(f"Company: {company.display_name} ({company.code})")
        self.stdout.write(f"Configured stages: {stage_count}")
        self.stdout.write(f"Phase 5 permissions available: {len(permissions)}")
        self.stdout.write(f"New role grants: {created_grants}")

    def _install_stages(
        self,
        company: Company,
        entity_type: str,
        definitions: list[dict[str, object]],
        now: datetime,
    ) -> int:
        DeliveryStage.objects.filter(
            company=company,
            entity_type=entity_type,
            is_initial=True,
        ).update(is_initial=False)
        for definition in definitions:
            DeliveryStage.objects.update_or_create(
                company=company,
                entity_type=entity_type,
                code=definition["code"],
                defaults={
                    "name": definition["name"],
                    "outcome": definition["outcome"],
                    "sort_order": definition["sort_order"],
                    "allowed_next_codes": definition["allowed_next_codes"],
                    "is_initial": bool(definition.get("is_initial", False)),
                    "allows_baseline": bool(definition.get("allows_baseline", False)),
                    "is_active": True,
                    "effective_from": now - timedelta(seconds=1),
                    "effective_to": None,
                },
            )
        return len(definitions)
