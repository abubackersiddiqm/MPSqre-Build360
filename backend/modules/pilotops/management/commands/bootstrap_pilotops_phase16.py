from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from modules.identity.models import Permission, Role, RolePermission, User
from modules.notifications.models import Notification
from modules.pilotops.models import (
    GoLivePlan,
    GoLiveSignoff,
    MasterDataReadiness,
    PilotChecklistItem,
    PilotProgram,
    TrainingCompletion,
    TrainingModule,
)
from modules.tenant.models import Company, Membership

CHECKLIST = [
    ("GOV_SCOPE", "governance", "Pilot scope and success criteria approved", True),
    ("GOV_OWNER", "governance", "Pilot owner and steering group assigned", True),
    ("IAM_USERS", "identity", "Pilot users and memberships provisioned", True),
    ("IAM_ROLES", "identity", "Pilot roles and segregation of duties reviewed", True),
    ("DATA_MASTER", "master_data", "Required master-data domains validated", True),
    ("DATA_IMPORT", "data", "Initial data imports previewed and reconciled", True),
    ("TRAIN_ADMIN", "training", "Administrator training completed", True),
    ("TRAIN_USERS", "training", "End-user training completed", True),
    ("PROC_UAT", "process", "Critical business journeys passed UAT", True),
    ("PROC_APPROVAL", "process", "Approval workflows validated", True),
    ("TECH_BROWSER", "technical", "Supported browser and device matrix validated", True),
    ("TECH_BACKUP", "technical", "Database backup and restore evidence recorded", True),
    ("SEC_ACCESS", "security", "Access and tenant-isolation review completed", True),
    ("SEC_SECRETS", "security", "Production secrets and environment boundaries reviewed", True),
    ("LIVE_CUTOVER", "go_live", "Cutover checklist reviewed", True),
    ("LIVE_ROLLBACK", "go_live", "Rollback path rehearsed", True),
    ("SUP_HELPDESK", "support", "Pilot support channels and escalation matrix published", True),
    ("SUP_HYPERCARE", "support", "Hypercare roster and monitoring window confirmed", True),
]

MASTER_DATA = [
    ("company_profile", "Company profile", 1, True),
    ("locations", "Branches and operating locations", 1, True),
    ("users", "Active users and memberships", 2, True),
    ("roles", "Roles and permissions", 2, True),
    ("projects", "Pilot projects", 1, True),
    ("vendors", "Approved vendors", 1, False),
    ("inventory_items", "Inventory item catalogue", 1, False),
    ("finance_periods", "Financial periods", 1, True),
    ("communication_channels", "Communication channel policies", 1, True),
    ("workflows", "Published workflows", 1, False),
]

TRAINING = [
    ("ADMIN_FOUNDATION", "Build360 administrator foundation", ["administrator"], True),
    (
        "SECURITY_TENANCY",
        "Security, tenancy and protected-data handling",
        ["administrator", "manager"],
        True,
    ),
    ("CRM_DELIVERY", "CRM to project delivery journey", ["sales", "project_manager"], True),
    ("SUPPLY_INVENTORY", "Procurement and inventory operations", ["procurement", "store"], True),
    ("FIELD_SAFETY", "Field, quality and safety operations", ["site", "safety"], True),
    ("FINANCE_CONTROLS", "Finance and commercial controls", ["finance"], True),
    (
        "REPORTS_SUPPORT",
        "Reports, support and incident escalation",
        ["administrator", "manager"],
        True,
    ),
]

SIGNOFFS = [
    ("BUSINESS", "business", "Business process owner approval", True),
    ("DATA", "data", "Data reconciliation approval", True),
    ("SECURITY", "security", "Security and access approval", True),
    ("TECHNICAL", "technical", "Technical readiness approval", True),
    ("SUPPORT", "support", "Support and hypercare approval", True),
    ("EXECUTIVE", "executive", "Executive go-live authorization", True),
]

CUTOVER_STEPS = [
    {"sequence": 10, "code": "BACKUP", "title": "Capture verified database backup"},
    {"sequence": 20, "code": "FREEZE", "title": "Confirm data-change freeze"},
    {"sequence": 30, "code": "MIGRATE", "title": "Apply approved migrations"},
    {"sequence": 40, "code": "SMOKE", "title": "Run production smoke tests"},
    {"sequence": 50, "code": "ENABLE", "title": "Enable pilot users"},
    {"sequence": 60, "code": "MONITOR", "title": "Start hypercare monitoring"},
]


class Command(BaseCommand):
    help = "Initialize Phase 16 pilot operations and go-live readiness controls."

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
        program, _ = PilotProgram.objects.update_or_create(
            company=company,
            cohort_code="PILOT_2026_01",
            defaults={
                "name": "Build360 controlled pilot launch",
                "status": PilotProgram.Status.PREPARING,
                "owner_membership": membership,
                "target_start_date": timezone.localdate(),
                "target_go_live_at": now + timedelta(days=30),
                "notes": "Governed Phase 16 pilot-readiness programme.",
            },
        )

        for sequence, (code, category, title, required) in enumerate(CHECKLIST, start=1):
            PilotChecklistItem.objects.update_or_create(
                company=company,
                program=program,
                code=code,
                defaults={
                    "category": category,
                    "title": title,
                    "description": (
                        "Capture objective evidence before marking this control complete."
                    ),
                    "is_required": required,
                    "sequence": sequence * 10,
                    "owner_membership": membership,
                    "due_at": now + timedelta(days=min(sequence + 5, 25)),
                },
            )

        for code, name, minimum, required in MASTER_DATA:
            MasterDataReadiness.objects.update_or_create(
                company=company,
                program=program,
                domain_code=code,
                defaults={
                    "domain_name": name,
                    "minimum_records": minimum,
                    "is_required": required,
                },
            )

        active_memberships = list(
            Membership.objects.filter(
                company=company,
                suspended_at__isnull=True,
                terminated_at__isnull=True,
                user__is_active=True,
            ).select_related("user")
        )
        module_count = 0
        assignment_count = 0
        for sequence, (code, title, audiences, required) in enumerate(TRAINING, start=1):
            module, _ = TrainingModule.objects.update_or_create(
                company=company,
                program=program,
                code=code,
                defaults={
                    "title": title,
                    "description": "Pilot-readiness training with completion evidence.",
                    "audience_codes": audiences,
                    "is_required": required,
                    "sequence": sequence * 10,
                    "status": TrainingModule.Status.PUBLISHED,
                },
            )
            module_count += 1
            for participant in active_memberships:
                _, created = TrainingCompletion.objects.get_or_create(
                    company=company,
                    module=module,
                    membership=participant,
                    defaults={"assigned_at": now},
                )
                assignment_count += int(created)

        plan, _ = GoLivePlan.objects.update_or_create(
            company=company,
            program=program,
            defaults={
                "target_at": program.target_go_live_at,
                "cutover_window_minutes": 120,
                "support_window_hours": 72,
                "rollback_reference": (
                    "Restore the pre-cutover PostgreSQL backup and v0.15.2 "
                    "source snapshot."
                ),
                "cutover_steps": CUTOVER_STEPS,
            },
        )
        for code, area, title, required in SIGNOFFS:
            GoLiveSignoff.objects.update_or_create(
                company=company,
                plan=plan,
                code=code,
                defaults={
                    "area": area,
                    "title": title,
                    "is_required": required,
                    "signer_membership": membership,
                },
            )

        permissions = list(Permission.objects.filter(code__startswith="pilot."))
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
        grants = 0
        for role in roles:
            for permission in permissions:
                _, created = RolePermission.objects.get_or_create(
                    role=role,
                    permission=permission,
                )
                grants += int(created)

        Notification.objects.get_or_create(
            company=company,
            user_public_id=user.public_id,
            event_code="system.phase16.ready",
            defaults={
                "title": "Phase 16 pilot operations is active",
                "body": (
                    "The guided pilot checklist, master-data validation, training, "
                    "readiness scoring, adoption evidence and go-live governance are ready."
                ),
                "severity": Notification.Severity.SUCCESS,
                "action_path": "/pilot-readiness",
                "source_type": "phase16_bootstrap",
            },
        )

        self.stdout.write(self.style.SUCCESS("PHASE 16 PILOT OPERATIONS INITIALIZATION COMPLETED"))
        self.stdout.write(f"Checklist items available: {len(CHECKLIST)}")
        self.stdout.write(f"Master-data domains available: {len(MASTER_DATA)}")
        self.stdout.write(f"Training modules available: {module_count}")
        self.stdout.write(f"New training assignments: {assignment_count}")
        self.stdout.write(f"Go-live sign-offs available: {len(SIGNOFFS)}")
        self.stdout.write(f"Phase 16 permissions available: {len(permissions)}")
        self.stdout.write(f"New administrator grants: {grants}")
