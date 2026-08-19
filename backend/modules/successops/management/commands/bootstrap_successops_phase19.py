from __future__ import annotations

import hashlib
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from modules.identity.models import Permission, Role, RolePermission, User
from modules.notifications.models import Notification
from modules.projects.models import Project
from modules.successops.models import (
    AdoptionSnapshot,
    BillingProfile,
    CustomerSuccessAccount,
    SuccessPlan,
    SupportSlaPolicy,
)
from modules.tenant.models import Company, Membership

SLA_POLICIES = [
    ("SLA_LOW", SupportSlaPolicy.Severity.LOW, 480, 4320, 2880, True),
    ("SLA_MEDIUM", SupportSlaPolicy.Severity.MEDIUM, 240, 1440, 960, True),
    ("SLA_HIGH", SupportSlaPolicy.Severity.HIGH, 60, 480, 240, False),
    ("SLA_CRITICAL", SupportSlaPolicy.Severity.CRITICAL, 15, 120, 60, False),
]


class Command(BaseCommand):
    help = "Initialize Phase 19 customer success, billing and support operations."

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

        today = timezone.localdate()
        account, _ = CustomerSuccessAccount.objects.update_or_create(
            company=company,
            code="PRIMARY",
            defaults={
                "display_name": company.display_name,
                "segment": CustomerSuccessAccount.Segment.PILOT,
                "status": CustomerSuccessAccount.Status.ACTIVE,
                "account_owner": membership,
                "customer_since": today,
                "renewal_on": today + timedelta(days=365),
                "health_score": 72,
                "risk_level": CustomerSuccessAccount.RiskLevel.LOW,
                "desired_outcomes": [
                    "Digitize the construction lifecycle",
                    "Complete pilot adoption and production launch",
                    "Establish measurable operational governance",
                ],
                "risk_summary": "Continue production-topology and adoption validation before broad rollout.",
            },
        )
        account.full_clean()
        account.save()

        BillingProfile.objects.update_or_create(
            company=company,
            account=account,
            defaults={
                "legal_name": company.legal_name,
                "billing_email": user.email,
                "tax_identifier_masked": "NOT-CONFIGURED",
                "currency": company.currency,
                "billing_cycle": BillingProfile.BillingCycle.ANNUAL,
                "payment_terms_days": 30,
                "status": BillingProfile.Status.ACTIVE,
            },
        )

        for code, severity, first_response, resolution, escalation, business_hours in SLA_POLICIES:
            SupportSlaPolicy.objects.update_or_create(
                company=company,
                code=code,
                defaults={
                    "severity": severity,
                    "first_response_minutes": first_response,
                    "resolution_minutes": resolution,
                    "escalation_minutes": escalation,
                    "business_hours_only": business_hours,
                    "is_active": True,
                },
            )

        SuccessPlan.objects.update_or_create(
            company=company,
            account=account,
            code="PILOT_SUCCESS_2026",
            defaults={
                "title": "Build360 pilot success plan",
                "objectives": [
                    {"code": "ADOPTION", "target": "Core teams use Build360 weekly"},
                    {"code": "READINESS", "target": "Critical go-live controls approved"},
                    {"code": "VALUE", "target": "Operational outcomes are measurable"},
                ],
                "owner_membership": membership,
                "status": SuccessPlan.Status.ACTIVE,
                "next_review_on": today + timedelta(days=30),
                "renewal_on": today + timedelta(days=365),
                "health_score": 72,
                "risk_summary": "Monitor adoption breadth and production operating evidence.",
            },
        )

        active_users = Membership.objects.filter(
            company=company,
            suspended_at__isnull=True,
            terminated_at__isnull=True,
        ).count()
        active_projects = Project.objects.filter(company=company).count()
        utilization = {
            "identity": 100,
            "project_delivery": 25 if active_projects else 0,
            "field_operations": 10,
            "finance": 10,
            "communications": 25,
            "reporting": 20,
            "ai": 10,
        }
        payload = (
            f"{company.public_id}:{today}:{active_users}:{active_projects}:"
            f"{sorted(utilization.items())}"
        )
        AdoptionSnapshot.objects.update_or_create(
            company=company,
            captured_on=today,
            defaults={
                "active_users": active_users,
                "active_projects": active_projects,
                "support_ticket_count": 0,
                "feature_utilization": utilization,
                "adoption_score": 45,
                "engagement_score": 50,
                "evidence_sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
            },
        )

        permissions = list(Permission.objects.filter(code__startswith="success."))
        now = timezone.now()
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
            event_code="system.phase19.ready",
            defaults={
                "title": "Phase 19 customer success operations is active",
                "body": (
                    "Account health, subscription billing, support SLAs, adoption evidence "
                    "and renewal governance are ready."
                ),
                "severity": Notification.Severity.SUCCESS,
                "action_path": "/customer-success",
                "source_type": "phase19_bootstrap",
            },
        )

        self.stdout.write(
            self.style.SUCCESS(
                "PHASE 19 CUSTOMER SUCCESS OPERATIONS INITIALIZATION COMPLETED"
            )
        )
        self.stdout.write("Customer success accounts: 1")
        self.stdout.write(f"Active SLA policies: {len(SLA_POLICIES)}")
        self.stdout.write("Success plans: 1")
        self.stdout.write("Adoption snapshots: 1")
        self.stdout.write(f"Phase 19 permissions available: {len(permissions)}")
        self.stdout.write(f"New administrator grants: {grants}")
