from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from modules.fieldops.models import FieldStage
from modules.identity.models import Permission, Role, RolePermission, User
from modules.tenant.models import Company, Membership

STAGES: dict[str, list[tuple[str, str, str, list[str], bool]]] = {
    FieldStage.EntityType.LABOUR_ALLOCATION: [
        ("planned", "Planned", "open", ["active", "cancelled"], True),
        ("active", "Active", "active", ["completed", "cancelled"], False),
        ("completed", "Completed", "complete", [], False),
        ("cancelled", "Cancelled", "cancelled", [], False),
    ],
    FieldStage.EntityType.ATTENDANCE: [
        ("draft", "Draft", "open", ["submitted", "cancelled"], True),
        ("submitted", "Submitted", "review", ["approved", "rejected"], False),
        ("approved", "Approved", "approved", [], False),
        ("rejected", "Rejected", "rejected", ["draft", "cancelled"], False),
        ("cancelled", "Cancelled", "cancelled", [], False),
    ],
    FieldStage.EntityType.EQUIPMENT: [
        ("available", "Available", "open", ["allocated", "maintenance", "retired"], True),
        ("allocated", "Allocated", "active", ["available", "maintenance", "retired"], False),
        ("maintenance", "Under maintenance", "blocked", ["available", "retired"], False),
        ("retired", "Retired", "complete", [], False),
    ],
    FieldStage.EntityType.EQUIPMENT_ALLOCATION: [
        ("planned", "Planned", "open", ["active", "cancelled"], True),
        ("active", "Active", "active", ["returned", "cancelled"], False),
        ("returned", "Returned", "complete", [], False),
        ("cancelled", "Cancelled", "cancelled", [], False),
    ],
    FieldStage.EntityType.MAINTENANCE: [
        ("open", "Open", "open", ["in_progress", "cancelled"], True),
        ("in_progress", "In progress", "active", ["completed", "blocked"], False),
        ("blocked", "Blocked", "blocked", ["in_progress", "cancelled"], False),
        ("completed", "Completed", "complete", [], False),
        ("cancelled", "Cancelled", "cancelled", [], False),
    ],
    FieldStage.EntityType.INSPECTION: [
        ("scheduled", "Scheduled", "open", ["in_progress", "cancelled"], True),
        ("in_progress", "In progress", "active", ["submitted", "cancelled"], False),
        ("submitted", "Submitted", "review", ["approved", "rejected"], False),
        ("approved", "Approved", "approved", [], False),
        ("rejected", "Rejected", "rejected", ["in_progress", "cancelled"], False),
        ("cancelled", "Cancelled", "cancelled", [], False),
    ],
    FieldStage.EntityType.NCR: [
        ("open", "Open", "open", ["investigating", "cancelled"], True),
        ("investigating", "Investigating", "review", ["corrective_action", "cancelled"], False),
        ("corrective_action", "Corrective action", "active", ["verification", "cancelled"], False),
        ("verification", "Verification", "review", ["closed", "corrective_action"], False),
        ("closed", "Closed", "complete", [], False),
        ("cancelled", "Cancelled", "cancelled", [], False),
    ],
    FieldStage.EntityType.INCIDENT: [
        ("reported", "Reported", "open", ["investigating", "cancelled"], True),
        ("investigating", "Investigating", "review", ["action_open", "cancelled"], False),
        ("action_open", "Corrective action open", "active", ["verification", "cancelled"], False),
        ("verification", "Verification", "review", ["closed", "action_open"], False),
        ("closed", "Closed", "complete", [], False),
        ("cancelled", "Cancelled", "cancelled", [], False),
    ],
    FieldStage.EntityType.OFFLINE_OPERATION: [
        ("received", "Received", "open", ["applied", "conflict", "rejected"], True),
        ("applied", "Applied", "complete", [], False),
        ("conflict", "Conflict", "blocked", ["applied", "rejected"], False),
        ("rejected", "Rejected", "rejected", [], False),
    ],
}


class Command(BaseCommand):
    help = "Initialize Phase 7 field stages and grant field permissions."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--company-code", required=True)
        parser.add_argument("--admin-email", required=True)

    @transaction.atomic
    def handle(self, *args: object, **options: object) -> None:
        company = Company.objects.filter(
            code__iexact=str(options["company_code"]).strip(),
            is_active=True,
        ).first()
        user = User.objects.filter(
            email__iexact=str(options["admin_email"]).strip().lower(),
            is_active=True,
        ).first()
        if company is None or user is None:
            raise CommandError("Active company or administrator was not found")
        membership = Membership.objects.filter(
            company=company,
            user=user,
            suspended_at__isnull=True,
            terminated_at__isnull=True,
        ).first()
        if membership is None:
            raise CommandError("Administrator has no active company membership")

        now = timezone.now()
        stage_count = 0
        for entity_type, definitions in STAGES.items():
            FieldStage.objects.filter(
                company=company,
                entity_type=entity_type,
                is_initial=True,
            ).update(is_initial=False)
            for order, (code, name, outcome, next_codes, is_initial) in enumerate(
                definitions,
                1,
            ):
                FieldStage.objects.update_or_create(
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

        role_ids = membership.role_assignments.filter(
            effective_from__lte=now
        ).filter(
            Q(effective_to__isnull=True) | Q(effective_to__gt=now)
        ).values_list("role_public_id", flat=True)
        roles = list(
            Role.objects.filter(
                company_public_id=company.public_id,
                public_id__in=role_ids,
                retired_at__isnull=True,
            )
        )
        permissions = list(
            Permission.objects.filter(
                Q(code__startswith="field.")
                | Q(code__startswith="labour.")
                | Q(code__startswith="equipment.")
                | Q(code__startswith="quality.")
                | Q(code__startswith="safety.")
            )
        )
        created = 0
        for role in roles:
            for permission in permissions:
                _, was_created = RolePermission.objects.get_or_create(
                    role=role,
                    permission=permission,
                )
                created += int(was_created)

        self.stdout.write(self.style.SUCCESS("PHASE 7 FIELD INITIALIZATION COMPLETED"))
        self.stdout.write(f"Company: {company.display_name} ({company.code})")
        self.stdout.write(f"Configured stages: {stage_count}")
        self.stdout.write(f"Phase 7 permissions available: {len(permissions)}")
        self.stdout.write(f"New role grants: {created}")
