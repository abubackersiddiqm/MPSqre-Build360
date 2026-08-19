from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from modules.identity.models import Permission, Role, RolePermission, User
from modules.tenant.models import Company, Membership
from modules.vendor.models import SupplyStage

STAGES = {
    SupplyStage.EntityType.VENDOR: [
        ("registered", "Registered", "open", ["under_review", "retired"], True),
        ("under_review", "Under review", "review", ["qualified", "rejected"], False),
        ("qualified", "Qualified", "approved", ["suspended", "retired"], False),
        ("rejected", "Rejected", "rejected", ["under_review", "retired"], False),
        ("suspended", "Suspended", "cancelled", ["qualified", "retired"], False),
        ("retired", "Retired", "complete", [], False),
    ],
    SupplyStage.EntityType.PURCHASE_REQUEST: [
        ("draft", "Draft", "open", ["submitted", "cancelled"], True),
        ("submitted", "Submitted", "review", ["approved", "rejected"], False),
        ("approved", "Approved", "approved", ["rfq_created", "cancelled"], False),
        ("rejected", "Rejected", "rejected", ["draft", "cancelled"], False),
        ("rfq_created", "RFQ created", "issued", ["ordered", "cancelled"], False),
        ("ordered", "Ordered", "issued", ["closed"], False),
        ("closed", "Closed", "complete", [], False),
        ("cancelled", "Cancelled", "cancelled", [], False),
    ],
    SupplyStage.EntityType.RFQ: [
        ("draft", "Draft", "open", ["issued", "cancelled"], True),
        ("issued", "Issued", "issued", ["closed", "cancelled"], False),
        ("closed", "Closed", "review", ["awarded", "no_award"], False),
        ("awarded", "Awarded", "approved", [], False),
        ("no_award", "No award", "complete", [], False),
        ("cancelled", "Cancelled", "cancelled", [], False),
    ],
    SupplyStage.EntityType.QUOTE: [
        ("submitted", "Submitted", "review", ["accepted", "rejected", "withdrawn"], True),
        ("accepted", "Accepted", "approved", [], False),
        ("rejected", "Rejected", "rejected", [], False),
        ("withdrawn", "Withdrawn", "cancelled", [], False),
    ],
    SupplyStage.EntityType.PURCHASE_ORDER: [
        ("draft", "Draft", "open", ["approved", "cancelled"], True),
        ("approved", "Approved", "approved", ["issued", "cancelled"], False),
        ("issued", "Issued", "issued", ["partially_received", "received", "cancelled"], False),
        ("partially_received", "Partially received", "open", ["received", "cancelled"], False),
        ("received", "Received", "complete", ["closed"], False),
        ("closed", "Closed", "complete", [], False),
        ("cancelled", "Cancelled", "cancelled", [], False),
    ],
    SupplyStage.EntityType.RECEIPT: [
        ("draft", "Draft", "open", ["posted", "cancelled"], True),
        ("posted", "Posted", "complete", [], False),
        ("cancelled", "Cancelled", "cancelled", [], False),
    ],
}


class Command(BaseCommand):
    help = "Initialize Phase 6 supply stages and grant vendor/procurement/inventory permissions."

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
        count = 0
        for entity_type, definitions in STAGES.items():
            SupplyStage.objects.filter(
                company=company, entity_type=entity_type, is_initial=True
            ).update(is_initial=False)
            for order, (code, name, outcome, next_codes, is_initial) in enumerate(definitions, 1):
                SupplyStage.objects.update_or_create(
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
                count += 1
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
        permissions = list(
            Permission.objects.filter(
                Q(code__startswith="vendor.")
                | Q(code__startswith="procurement.")
                | Q(code__startswith="inventory.")
            )
        )
        created = 0
        for role in roles:
            for permission in permissions:
                _, was_created = RolePermission.objects.get_or_create(
                    role=role, permission=permission
                )
                created += int(was_created)
        self.stdout.write(self.style.SUCCESS("PHASE 6 SUPPLY INITIALIZATION COMPLETED"))
        self.stdout.write(f"Company: {company.display_name} ({company.code})")
        self.stdout.write(f"Configured stages: {count}")
        self.stdout.write(f"Phase 6 permissions available: {len(permissions)}")
        self.stdout.write(f"New role grants: {created}")
