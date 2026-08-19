from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from modules.adminops.models import (
    FeatureFlag,
    HealthSnapshot,
    Runbook,
    RuntimeEnvironment,
    ServiceObjective,
)
from modules.identity.models import Permission, Role, RolePermission, User
from modules.notifications.models import Notification
from modules.tenant.models import Company, Membership

OBJECTIVES = [
    {
        "code": "API_AVAILABILITY",
        "name": "API availability",
        "service_code": "api",
        "indicator_type": ServiceObjective.IndicatorType.AVAILABILITY,
        "target_value": Decimal("99.9000"),
        "warning_threshold": Decimal("99.5000"),
        "critical_threshold": Decimal("99.0000"),
        "unit_code": "percent",
    },
    {
        "code": "API_P95_LATENCY",
        "name": "API p95 latency",
        "service_code": "api",
        "indicator_type": ServiceObjective.IndicatorType.LATENCY,
        "target_value": Decimal("500.0000"),
        "warning_threshold": Decimal("800.0000"),
        "critical_threshold": Decimal("1500.0000"),
        "unit_code": "milliseconds",
    },
    {
        "code": "AUTH_AVAILABILITY",
        "name": "Authentication availability",
        "service_code": "identity",
        "indicator_type": ServiceObjective.IndicatorType.AVAILABILITY,
        "target_value": Decimal("99.9500"),
        "warning_threshold": Decimal("99.7000"),
        "critical_threshold": Decimal("99.0000"),
        "unit_code": "percent",
    },
    {
        "code": "WEB_AVAILABILITY",
        "name": "Web application availability",
        "service_code": "frontend",
        "indicator_type": ServiceObjective.IndicatorType.AVAILABILITY,
        "target_value": Decimal("99.9000"),
        "warning_threshold": Decimal("99.5000"),
        "critical_threshold": Decimal("99.0000"),
        "unit_code": "percent",
    },
]

RUNBOOKS = [
    {
        "code": "AUTH_FAILURE",
        "title": "Authentication failure response",
        "category": "identity",
        "purpose": "Restore sign-in while preserving session and tenant isolation evidence.",
        "steps": [
            {"order": 1, "action": "Confirm API and database health."},
            {"order": 2, "action": "Correlate the failed request ID with structured logs."},
            {"order": 3, "action": "Validate cache or local no-Docker mode configuration."},
            {
                "order": 4,
                "action": "Apply the approved forward fix and run authentication smoke tests.",
            },
        ],
    },
    {
        "code": "DATABASE_OUTAGE",
        "title": "PostgreSQL outage response",
        "category": "database",
        "purpose": "Restore the authoritative database without unsafe writes.",
        "steps": [
            {"order": 1, "action": "Place write paths into controlled maintenance mode."},
            {"order": 2, "action": "Verify PostgreSQL service, storage and connection capacity."},
            {
                "order": 3,
                "action": "Use the latest verified backup only under approved recovery control.",
            },
            {
                "order": 4,
                "action": (
                    "Run tenant-isolation, migration and smoke checks "
                    "before reopening writes."
                ),
            },
        ],
    },
    {
        "code": "RELEASE_ROLLBACK",
        "title": "Versioned release rollback",
        "category": "release",
        "purpose": "Reverse a failed release while preserving evidence and database integrity.",
        "steps": [
            {"order": 1, "action": "Stop deployment and record incident and release identifiers."},
            {
                "order": 2,
                "action": "Determine whether database changes require forward-fix or restore.",
            },
            {"order": 3, "action": "Use the versioned rollback manifest for source restoration."},
            {"order": 4, "action": "Execute backend, frontend and tenant smoke tests."},
        ],
    },
    {
        "code": "BACKUP_RESTORE",
        "title": "Backup and restore verification",
        "category": "recovery",
        "purpose": "Prove that backups are restorable within approved RPO and RTO.",
        "steps": [
            {"order": 1, "action": "Select an approved backup and isolated restore target."},
            {"order": 2, "action": "Restore and verify schema, row counts and object references."},
            {
                "order": 3,
                "action": "Run Build360 health, tenant and critical business smoke tests.",
            },
            {
                "order": 4,
                "action": "Record measured RPO, RTO and evidence in recovery verification.",
            },
        ],
    },
]

FLAGS = [
    ("GOVERNED_AI", "Governed AI workspace", True, 100, False),
    ("EXTERNAL_PORTAL", "External portal", True, 100, False),
    ("EXTERNAL_COMMUNICATION_PROVIDERS", "External communication providers", False, 0, True),
    ("ASYNC_REPORT_EXPORTS", "Asynchronous report exports", False, 0, True),
]


class Command(BaseCommand):
    help = "Initialize Phase 12 enterprise administration and reliability controls."

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

        local_environment, _ = RuntimeEnvironment.objects.update_or_create(
            company=company,
            code="LOCAL",
            defaults={
                "name": "Local Windows development",
                "environment_type": RuntimeEnvironment.EnvironmentType.LOCAL,
                "base_url": "http://localhost:3000",
                "region": "local",
                "data_residency": "local-development",
                "production_data_allowed": False,
                "requires_change_approval": False,
                "is_active": True,
            },
        )
        RuntimeEnvironment.objects.update_or_create(
            company=company,
            code="STAGING",
            defaults={
                "name": "Controlled staging",
                "environment_type": RuntimeEnvironment.EnvironmentType.STAGING,
                "base_url": "",
                "region": "unassigned",
                "data_residency": "unassigned",
                "production_data_allowed": False,
                "requires_change_approval": True,
                "is_active": True,
            },
        )
        RuntimeEnvironment.objects.update_or_create(
            company=company,
            code="PRODUCTION",
            defaults={
                "name": "Production placeholder",
                "environment_type": RuntimeEnvironment.EnvironmentType.PRODUCTION,
                "base_url": "https://build360.example.invalid",
                "region": "unassigned",
                "data_residency": "unassigned",
                "production_data_allowed": True,
                "requires_change_approval": True,
                "is_active": False,
            },
        )

        for item in OBJECTIVES:
            ServiceObjective.objects.update_or_create(
                company=company,
                code=item["code"],
                defaults={**item, "window_days": 30, "is_active": True},
            )

        review_due = timezone.now() + timedelta(days=180)
        for item in RUNBOOKS:
            Runbook.objects.update_or_create(
                company=company,
                code=item["code"],
                defaults={
                    **item,
                    "owner_membership_public_id": membership.public_id,
                    "review_due_at": review_due,
                    "is_active": True,
                },
            )

        for code, name, enabled, rollout, approval in FLAGS:
            FeatureFlag.objects.update_or_create(
                company=company,
                code=code,
                defaults={
                    "name": name,
                    "description": f"Build360 governed feature flag for {name.lower()}.",
                    "is_enabled": enabled,
                    "rollout_percent": rollout,
                    "scope": {"company_code": company.code},
                    "requires_approval": approval,
                    "requested_by_public_id": user.public_id if not approval else None,
                    "approved_by_public_id": user.public_id if enabled else None,
                    "approved_at": timezone.now() if enabled else None,
                },
            )

        for service_code in ("api", "identity", "frontend", "postgresql"):
            HealthSnapshot.objects.create(
                company=company,
                environment=local_environment,
                service_code=service_code,
                status=HealthSnapshot.Status.HEALTHY,
                latency_ms=0 if service_code == "postgresql" else None,
                source="phase12-bootstrap",
                details={"mode": "native-windows", "docker_required": False},
                checked_at=timezone.now(),
            )

        role_ids = membership.role_assignments.filter(
            effective_from__lte=timezone.now(),
        ).filter(
            Q(effective_to__isnull=True) | Q(effective_to__gt=timezone.now())
        ).values_list("role_public_id", flat=True)
        roles = list(
            Role.objects.filter(
                company_public_id=company.public_id,
                public_id__in=role_ids,
                retired_at__isnull=True,
            )
        )
        permissions = list(Permission.objects.filter(code__startswith="adminops."))
        created_grants = 0
        for role in roles:
            for permission in permissions:
                _, created = RolePermission.objects.get_or_create(
                    role=role,
                    permission=permission,
                )
                created_grants += int(created)

        Notification.objects.get_or_create(
            company=company,
            user_public_id=user.public_id,
            event_code="system.phase12.ready",
            defaults={
                "title": "Phase 12 enterprise readiness controls are active",
                "body": (
                    "Release governance, readiness checks, SLOs, incidents, runbooks, "
                    "feature flags and maintenance controls are ready."
                ),
                "severity": Notification.Severity.SUCCESS,
                "action_path": "/enterprise-admin",
                "source_type": "phase12_bootstrap",
            },
        )

        self.stdout.write(self.style.SUCCESS("PHASE 12 ADMINOPS INITIALIZATION COMPLETED"))
        self.stdout.write(f"Company: {company.display_name} ({company.code})")
        self.stdout.write("Runtime environments available: 3")
        self.stdout.write(f"Service objectives available: {len(OBJECTIVES)}")
        self.stdout.write(f"Runbooks available: {len(RUNBOOKS)}")
        self.stdout.write(f"Feature flags available: {len(FLAGS)}")
        self.stdout.write(f"Phase 12 permissions available: {len(permissions)}")
        self.stdout.write(f"New role grants: {created_grants}")
