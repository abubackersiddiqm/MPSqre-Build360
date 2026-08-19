from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from modules.dataops.models import ImportTemplate, RecoveryVerification, RetentionPolicy
from modules.identity.models import Permission, Role, RolePermission, User
from modules.notifications.models import Notification
from modules.portal.models import PortalAccessGrant, PortalScopeType, PortalType
from modules.reporting.models import MetricDefinition, SavedReport
from modules.tenant.models import Company, Membership

METRICS = [
    ("CRM_LEADS_TOTAL", "Total leads", "crm", "crm.leads.total", "count", "internal"),
    ("CRM_OPPORTUNITIES_OPEN", "Open opportunities", "crm", "crm.opportunities.open", "count", "internal"),
    ("PROJECTS_ACTIVE", "Active projects", "projects", "projects.active", "count", "internal"),
    ("PROJECT_TASKS_OVERDUE", "Overdue project tasks", "projects", "projects.tasks.overdue", "count", "confidential"),
    ("VENDORS_ACTIVE", "Active vendors", "supply", "supply.vendors.active", "count", "internal"),
    ("PURCHASE_ORDERS_TOTAL", "Purchase orders", "procurement", "procurement.purchase_orders", "count", "confidential"),
    ("INVENTORY_ITEMS_TOTAL", "Inventory items", "inventory", "inventory.items", "count", "internal"),
    ("SAFETY_INCIDENTS_OPEN", "Open safety incidents", "safety", "safety.incidents.open", "count", "restricted"),
    ("FINANCE_APPROVED_BUDGET", "Approved budget", "finance", "finance.approved_budget", "currency", "confidential"),
    ("FINANCE_OUTSTANDING", "Outstanding invoices", "finance", "finance.invoice.outstanding", "currency", "restricted"),
    ("NOTIFICATIONS_UNREAD", "Unread notifications", "notifications", "notifications.unread", "count", "internal"),
]

PROJECT_IMPORT_SCHEMA = {
    "max_rows": 500,
    "fields": [
        {"name": "code", "required": True, "type": "upper_string"},
        {"name": "name", "required": True, "type": "string"},
        {"name": "description", "required": False, "type": "string"},
        {"name": "currency", "required": False, "type": "upper_string"},
        {"name": "approved_budget", "required": False, "type": "decimal"},
    ],
}

VENDOR_IMPORT_SCHEMA = {
    "max_rows": 500,
    "fields": [
        {"name": "code", "required": True, "type": "upper_string"},
        {"name": "legal_name", "required": True, "type": "string"},
        {"name": "display_name", "required": False, "type": "string"},
        {"name": "categories", "required": False, "type": "list"},
        {"name": "service_regions", "required": False, "type": "list"},
    ],
}


class Command(BaseCommand):
    help = "Initialize Phase 10 reporting, portals, imports and operational controls."

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

        metric_count = 0
        for code, name, domain, calculation, unit, classification in METRICS:
            _, created = MetricDefinition.objects.update_or_create(
                company=company,
                code=code,
                version=1,
                defaults={
                    "name": name,
                    "description": f"Build360 governed metric for {name.lower()}.",
                    "domain_code": domain,
                    "calculation_code": calculation,
                    "unit_code": unit,
                    "data_classification": classification,
                    "is_active": True,
                },
            )
            metric_count += int(created)

        executive_codes = [code for code, *_ in METRICS]
        SavedReport.objects.update_or_create(
            company=company,
            code="EXECUTIVE_OVERVIEW",
            defaults={
                "name": "Executive overview",
                "description": "Cross-domain executive KPI overview.",
                "report_type": "executive",
                "metric_codes": executive_codes,
                "filters": {},
                "columns": ["code", "name", "value", "unit"],
                "visibility": SavedReport.Visibility.COMPANY,
                "owner_user_public_id": user.public_id,
                "default_export_format": SavedReport.ExportFormat.PDF,
                "is_active": True,
            },
        )
        SavedReport.objects.update_or_create(
            company=company,
            code="OPERATIONS_CONTROL",
            defaults={
                "name": "Operations control report",
                "description": "Delivery, supply, safety and commercial control metrics.",
                "report_type": "operations",
                "metric_codes": [
                    "PROJECTS_ACTIVE",
                    "PROJECT_TASKS_OVERDUE",
                    "VENDORS_ACTIVE",
                    "PURCHASE_ORDERS_TOTAL",
                    "SAFETY_INCIDENTS_OPEN",
                    "FINANCE_OUTSTANDING",
                ],
                "filters": {},
                "columns": ["code", "name", "value", "unit"],
                "visibility": SavedReport.Visibility.COMPANY,
                "owner_user_public_id": user.public_id,
                "default_export_format": SavedReport.ExportFormat.XLSX,
                "is_active": True,
            },
        )

        ImportTemplate.objects.update_or_create(
            company=company,
            code="PROJECT_BASIC",
            version=1,
            defaults={
                "name": "Basic project import",
                "destination_code": "projects.project",
                "schema": PROJECT_IMPORT_SCHEMA,
                "is_active": True,
            },
        )
        ImportTemplate.objects.update_or_create(
            company=company,
            code="VENDOR_BASIC",
            version=1,
            defaults={
                "name": "Basic vendor import",
                "destination_code": "vendor.vendor",
                "schema": VENDOR_IMPORT_SCHEMA,
                "is_active": True,
            },
        )

        for record_type, days in [
            ("audit.event", 2555),
            ("finance.ledger", 3650),
            ("safety.incident", 3650),
            ("communication.delivery", 1095),
            ("import.staging", 90),
        ]:
            RetentionPolicy.objects.update_or_create(
                company=company,
                record_type=record_type,
                version=1,
                defaults={
                    "retention_days": days,
                    "legal_hold_default": record_type in {"finance.ledger", "safety.incident"},
                    "effective_from": timezone.now(),
                    "is_active": True,
                },
            )

        RecoveryVerification.objects.get_or_create(
            company=company,
            reference="PHASE10-BASELINE-RESTORE",
            defaults={
                "scope": RecoveryVerification.Scope.RESTORE,
                "status": RecoveryVerification.Status.PLANNED,
                "target_rpo_minutes": 1440,
                "target_rto_minutes": 240,
                "performed_by_public_id": user.public_id,
            },
        )

        portal_grant = PortalAccessGrant.objects.filter(
            company=company,
            user_public_id=user.public_id,
            portal_type=PortalType.CLIENT,
            scope_type=PortalScopeType.COMPANY,
            scope_public_id=None,
            revoked_at__isnull=True,
        ).first()
        if portal_grant is None:
            PortalAccessGrant.objects.create(
                company=company,
                user_public_id=user.public_id,
                portal_type=PortalType.CLIENT,
                scope_type=PortalScopeType.COMPANY,
                scope_public_id=None,
                permission_codes=[
                    "portal.dashboard.view",
                    "portal.project.view",
                    "portal.document.view",
                    "portal.invoice.view",
                ],
                effective_from=timezone.now(),
                granted_by_public_id=user.public_id,
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
        permissions = list(
            Permission.objects.filter(
                Q(code__startswith="reporting.")
                | Q(code__startswith="portal.")
                | Q(code__startswith="dataops.")
            )
        )
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
            event_code="system.phase10.ready",
            defaults={
                "title": "Phase 10 operations controls are active",
                "body": "Reporting, portals, governed imports, privacy and recovery controls are ready.",
                "severity": Notification.Severity.SUCCESS,
                "action_path": "/operations",
                "source_type": "phase10_bootstrap",
            },
        )

        self.stdout.write(self.style.SUCCESS("PHASE 10 OPERATIONS INITIALIZATION COMPLETED"))
        self.stdout.write(f"Company: {company.display_name} ({company.code})")
        self.stdout.write(f"Metrics available: {len(METRICS)}")
        self.stdout.write("Saved reports: 2")
        self.stdout.write("Import templates: 2")
        self.stdout.write("Retention policies: 5")
        self.stdout.write(f"Phase 10 permissions available: {len(permissions)}")
        self.stdout.write(f"New role grants: {created_grants}")
