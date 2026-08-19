from __future__ import annotations

from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from modules.crm.application.configuration import default_pipeline
from modules.crm.models import PipelineStage
from modules.identity.models import Permission, Role, RolePermission, User
from modules.tenant.models import Company, Membership

CRM_PERMISSION_PREFIX = "crm."

LEAD_STAGES = [
    {
        "code": "new",
        "name": "New",
        "outcome": "open",
        "sort_order": 10,
        "probability_percent": 5,
        "allowed_next_codes": ["contacted", "qualified", "disqualified"],
        "is_initial": True,
    },
    {
        "code": "contacted",
        "name": "Contacted",
        "outcome": "open",
        "sort_order": 20,
        "probability_percent": 15,
        "allowed_next_codes": ["qualified", "disqualified"],
    },
    {
        "code": "qualified",
        "name": "Qualified",
        "outcome": "qualified",
        "sort_order": 30,
        "probability_percent": 30,
        "allowed_next_codes": ["converted", "disqualified"],
        "allows_conversion": True,
    },
    {
        "code": "converted",
        "name": "Converted",
        "outcome": "converted",
        "sort_order": 90,
        "probability_percent": 100,
        "allowed_next_codes": [],
    },
    {
        "code": "disqualified",
        "name": "Disqualified",
        "outcome": "disqualified",
        "sort_order": 100,
        "probability_percent": 0,
        "allowed_next_codes": [],
    },
]

OPPORTUNITY_STAGES = [
    {
        "code": "qualification",
        "name": "Qualification",
        "outcome": "open",
        "sort_order": 10,
        "probability_percent": 20,
        "allowed_next_codes": ["proposal", "lost"],
        "is_initial": True,
    },
    {
        "code": "proposal",
        "name": "Proposal",
        "outcome": "open",
        "sort_order": 20,
        "probability_percent": 45,
        "allowed_next_codes": ["negotiation", "lost"],
    },
    {
        "code": "negotiation",
        "name": "Negotiation",
        "outcome": "open",
        "sort_order": 30,
        "probability_percent": 70,
        "allowed_next_codes": ["won", "lost"],
    },
    {
        "code": "won",
        "name": "Won",
        "outcome": "won",
        "sort_order": 90,
        "probability_percent": 100,
        "allowed_next_codes": [],
    },
    {
        "code": "lost",
        "name": "Lost",
        "outcome": "lost",
        "sort_order": 100,
        "probability_percent": 0,
        "allowed_next_codes": [],
    },
]


class Command(BaseCommand):
    help = "Initialize configurable CRM stages and grant Phase 4 permissions explicitly."

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
        self._install_stages(company, PipelineStage.EntityType.LEAD, LEAD_STAGES, now)
        self._install_stages(
            company,
            PipelineStage.EntityType.OPPORTUNITY,
            OPPORTUNITY_STAGES,
            now,
        )
        role_ids = membership.role_assignments.filter(
            effective_from__lte=now,
        ).filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now)).values_list(
            "role_public_id", flat=True
        )
        roles = list(
            Role.objects.filter(
                company_public_id=company.public_id,
                public_id__in=role_ids,
                retired_at__isnull=True,
            )
        )
        if not roles:
            raise CommandError("Administrator has no active role assignment")
        permissions = list(Permission.objects.filter(code__startswith=CRM_PERMISSION_PREFIX))
        if not permissions:
            raise CommandError("CRM permissions are missing; apply migrations first")
        created_grants = 0
        for role in roles:
            for permission in permissions:
                _, created = RolePermission.objects.get_or_create(
                    role=role,
                    permission=permission,
                )
                created_grants += int(created)
        self.stdout.write(self.style.SUCCESS("PHASE 4 CRM INITIALIZATION COMPLETED"))
        self.stdout.write(f"Company: {company.display_name} ({company.code})")
        self.stdout.write(f"Lead stages: {len(LEAD_STAGES)}")
        self.stdout.write(f"Opportunity stages: {len(OPPORTUNITY_STAGES)}")
        self.stdout.write(f"CRM permissions available: {len(permissions)}")
        self.stdout.write(f"New role grants: {created_grants}")

    def _install_stages(
        self,
        company: Company,
        entity_type: str,
        definitions: list[dict[str, object]],
        now: datetime,
    ) -> None:
        pipeline = default_pipeline(company, entity_type)
        PipelineStage.objects.filter(
            company=company,
            pipeline=pipeline,
            entity_type=entity_type,
            is_initial=True,
        ).update(is_initial=False)
        for definition in definitions:
            PipelineStage.objects.update_or_create(
                company=company,
                pipeline=pipeline,
                code=definition["code"],
                defaults={
                    "entity_type": entity_type,
                    "name": definition["name"],
                    "outcome": definition["outcome"],
                    "sort_order": definition["sort_order"],
                    "probability_percent": definition["probability_percent"],
                    "allowed_next_codes": definition["allowed_next_codes"],
                    "is_initial": bool(definition.get("is_initial", False)),
                    "allows_conversion": bool(definition.get("allows_conversion", False)),
                    "is_active": True,
                    "effective_from": now - timedelta(seconds=1),
                    "effective_to": None,
                },
            )
