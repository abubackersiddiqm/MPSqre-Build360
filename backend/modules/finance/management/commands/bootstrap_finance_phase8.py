from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from modules.finance.models import CommercialStage, FinancePolicy, FinancialPeriod
from modules.identity.models import Permission, Role, RolePermission, User
from modules.tenant.models import Company, Membership

STAGES = {
    CommercialStage.EntityType.BUDGET: [
        ("draft", "Draft", "open", ["submitted", "cancelled"], True),
        ("submitted", "Submitted", "review", ["approved", "rejected"], False),
        ("approved", "Approved", "approved", ["closed"], False),
        ("rejected", "Rejected", "rejected", ["draft", "cancelled"], False),
        ("closed", "Closed", "closed", [], False),
        ("cancelled", "Cancelled", "cancelled", [], False),
    ],
    CommercialStage.EntityType.VARIATION: [
        ("draft", "Draft", "open", ["submitted", "cancelled"], True),
        ("submitted", "Submitted", "review", ["approved", "rejected"], False),
        ("approved", "Approved", "approved", [], False),
        ("rejected", "Rejected", "rejected", ["draft", "cancelled"], False),
        ("cancelled", "Cancelled", "cancelled", [], False),
    ],
    CommercialStage.EntityType.INVOICE: [
        ("draft", "Draft", "open", ["submitted", "cancelled"], True),
        ("submitted", "Submitted", "review", ["approved", "rejected"], False),
        ("approved", "Approved", "approved", ["posted", "cancelled"], False),
        ("posted", "Posted", "posted", ["paid", "reversed"], False),
        ("paid", "Paid", "paid", [], False),
        ("rejected", "Rejected", "rejected", ["draft", "cancelled"], False),
        ("reversed", "Reversed", "reversed", [], False),
        ("cancelled", "Cancelled", "cancelled", [], False),
    ],
    CommercialStage.EntityType.PAYMENT: [
        ("draft", "Draft", "open", ["posted", "cancelled"], True),
        ("posted", "Posted", "posted", ["reversed"], False),
        ("reversed", "Reversed", "reversed", [], False),
        ("cancelled", "Cancelled", "cancelled", [], False),
    ],
    CommercialStage.EntityType.RETENTION: [
        ("draft", "Draft", "open", ["approved", "cancelled"], True),
        ("approved", "Approved", "approved", ["posted"], False),
        ("posted", "Posted", "posted", [], False),
        ("cancelled", "Cancelled", "cancelled", [], False),
    ],
}


class Command(BaseCommand):
    help = "Initialize Phase 8 finance stages, policy, period and permissions."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--company-code", required=True)
        parser.add_argument("--admin-email", required=True)

    @transaction.atomic
    def handle(self, *args: object, **options: object) -> None:
        company = Company.objects.filter(
            code__iexact=str(options["company_code"]).strip(), is_active=True
        ).first()
        user = User.objects.filter(
            email__iexact=str(options["admin_email"]).strip().lower(), is_active=True
        ).first()
        if company is None or user is None:
            raise CommandError("Active company or administrator was not found")
        membership = Membership.objects.filter(
            company=company, user=user, suspended_at__isnull=True, terminated_at__isnull=True
        ).first()
        if membership is None:
            raise CommandError("Administrator has no active company membership")
        now = timezone.now()
        stage_count = 0
        for entity_type, definitions in STAGES.items():
            CommercialStage.objects.filter(
                company=company, entity_type=entity_type, is_initial=True
            ).update(is_initial=False)
            for order, (code, name, outcome, next_codes, is_initial) in enumerate(definitions, 1):
                CommercialStage.objects.update_or_create(
                    company=company,
                    entity_type=entity_type,
                    code=code,
                    defaults={
                        "name": name,
                        "outcome": outcome,
                        "sort_order": order * 10,
                        "allowed_next_codes": next_codes,
                        "is_initial": is_initial,
                        "is_active": True,
                        "effective_from": now - timedelta(seconds=1),
                        "effective_to": None,
                    },
                )
                stage_count += 1
        FinancePolicy.objects.get_or_create(
            company=company,
            defaults={
                "enforce_maker_checker": False,
                "allow_backdated_posting": False,
                "default_retention_percent": 0,
                "tax_configuration": {
                    "mode": "configuration_driven",
                    "jurisdiction": "unvalidated",
                },
            },
        )
        today = date.today()
        starts_on = today.replace(day=1)
        ends_on = today.replace(day=monthrange(today.year, today.month)[1])
        period_code = f"{today.year}-{today.month:02d}"
        FinancialPeriod.objects.get_or_create(
            company=company,
            code=period_code,
            defaults={"name": today.strftime("%B %Y"), "starts_on": starts_on, "ends_on": ends_on},
        )
        role_ids = (
            membership.role_assignments.filter(effective_from__lte=now)
            .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now))
            .values_list("role_public_id", flat=True)
        )
        roles = list(
            Role.objects.filter(
                company_public_id=company.public_id, public_id__in=role_ids, retired_at__isnull=True
            )
        )
        permissions = list(Permission.objects.filter(code__startswith="finance."))
        created = 0
        for role in roles:
            for permission in permissions:
                _, was_created = RolePermission.objects.get_or_create(
                    role=role, permission=permission
                )
                created += int(was_created)
        self.stdout.write(self.style.SUCCESS("PHASE 8 FINANCE INITIALIZATION COMPLETED"))
        self.stdout.write(f"Company: {company.display_name} ({company.code})")
        self.stdout.write(f"Configured stages: {stage_count}")
        self.stdout.write(f"Current financial period: {period_code}")
        self.stdout.write(f"Phase 8 permissions available: {len(permissions)}")
        self.stdout.write(f"New role grants: {created}")
