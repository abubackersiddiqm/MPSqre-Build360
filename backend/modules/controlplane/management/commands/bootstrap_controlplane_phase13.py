from __future__ import annotations

import uuid

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from modules.controlplane.application.context import PlatformActor
from modules.controlplane.application.services import (
    assign_subscription,
    collect_usage_snapshot,
    current_subscription,
)
from modules.controlplane.models import (
    PlatformOperatorAssignment,
    PlatformRole,
    PlatformRolePermission,
    TenantAccount,
)
from modules.identity.models import Permission, Role, RolePermission, User
from modules.notifications.models import Notification
from modules.subscription.models import CompanySubscription, PlanVersion
from modules.tenant.models import Company, Membership

PILOT_ENTITLEMENTS = {
    "crm": True,
    "project_delivery": True,
    "design": True,
    "estimation": True,
    "vendor": True,
    "procurement": True,
    "inventory": True,
    "field_operations": True,
    "finance": True,
    "communications": True,
    "reporting": True,
    "external_portal": True,
    "governed_ai": True,
    "enterprise_admin": True,
    "saas_controlplane": True,
}
PILOT_LIMITS = {
    "users": 25,
    "projects": 10,
    "storage_bytes": 5 * 1024 * 1024 * 1024,
    "ai_interactions_month": 500,
    "communications_month": 2000,
    "vendors": 100,
}
ENTERPRISE_LIMITS = {
    "users": None,
    "projects": None,
    "storage_bytes": None,
    "ai_interactions_month": None,
    "communications_month": None,
    "vendors": None,
}


class Command(BaseCommand):
    help = "Initialize Phase 13 SaaS control-plane and tenant lifecycle controls."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--company-code", required=True)
        parser.add_argument("--admin-email", required=True)

    @transaction.atomic
    def handle(self, *args: object, **options: object) -> None:
        company = Company.objects.filter(
            code__iexact=str(options["company_code"]).strip(),
        ).first()
        user = User.objects.filter(
            email__iexact=str(options["admin_email"]).strip().lower(),
            is_active=True,
        ).first()
        if company is None or user is None:
            raise CommandError("Company or active administrator was not found")
        membership = Membership.objects.filter(
            company=company,
            user=user,
            suspended_at__isnull=True,
            terminated_at__isnull=True,
        ).first()
        if membership is None:
            raise CommandError("Administrator has no active company membership")

        now = timezone.now()
        platform_role, _ = PlatformRole.objects.get_or_create(
            code="PLATFORM_ADMIN",
            version=1,
            defaults={
                "name": "Platform administrator",
                "effective_from": now,
            },
        )
        permissions = list(Permission.objects.filter(code__startswith="controlplane."))
        for permission in permissions:
            PlatformRolePermission.objects.get_or_create(
                role=platform_role,
                permission=permission,
            )
        assignment = PlatformOperatorAssignment.objects.filter(
            user=user,
            role=platform_role,
            suspended_at__isnull=True,
        ).first()
        if assignment is None:
            assignment = PlatformOperatorAssignment.objects.create(
                user=user,
                role=platform_role,
                assigned_by_public_id=user.public_id,
                effective_from=now,
            )

        tenant_count = 0
        target_tenant: TenantAccount | None = None
        for item in Company.objects.all().order_by("code"):
            if item.closed_at:
                lifecycle = TenantAccount.LifecycleStatus.CLOSED
            elif item.suspended_at or not item.is_active:
                lifecycle = TenantAccount.LifecycleStatus.SUSPENDED
            else:
                lifecycle = TenantAccount.LifecycleStatus.PILOT
            tenant, _ = TenantAccount.objects.get_or_create(
                company=item,
                defaults={
                    "lifecycle_status": lifecycle,
                    "onboarding_status": (
                        TenantAccount.OnboardingStatus.LIVE
                        if item == company
                        else TenantAccount.OnboardingStatus.DISCOVERY
                    ),
                    "segment_code": "construction",
                    "deployment_region": "local",
                    "data_residency": "local-development",
                    "pilot_started_at": (
                        now
                        if lifecycle == TenantAccount.LifecycleStatus.PILOT
                        else None
                    ),
                    "suspended_at": (
                        item.suspended_at
                        if lifecycle == TenantAccount.LifecycleStatus.SUSPENDED
                        else None
                    ) or (now if lifecycle == TenantAccount.LifecycleStatus.SUSPENDED else None),
                    "closed_at": (
                        item.closed_at
                        if lifecycle == TenantAccount.LifecycleStatus.CLOSED
                        else None
                    ) or (now if lifecycle == TenantAccount.LifecycleStatus.CLOSED else None),
                },
            )
            tenant_count += 1
            if item == company:
                target_tenant = tenant

        pilot_plan, _ = PlanVersion.objects.get_or_create(
            code="PILOT_360",
            version=1,
            defaults={
                "name": "Build360 Pilot",
                "status": PlanVersion.Status.PUBLISHED,
                "entitlements": PILOT_ENTITLEMENTS,
                "limits": PILOT_LIMITS,
                "effective_from": now,
                "published_at": now,
            },
        )
        PlanVersion.objects.get_or_create(
            code="ENTERPRISE_360",
            version=1,
            defaults={
                "name": "Build360 Enterprise",
                "status": PlanVersion.Status.PUBLISHED,
                "entitlements": PILOT_ENTITLEMENTS,
                "limits": ENTERPRISE_LIMITS,
                "effective_from": now,
                "published_at": now,
            },
        )

        actor = PlatformActor(
            user_public_id=user.public_id,
            operator_assignment_public_id=assignment.public_id,
            request_id=uuid.uuid4(),
            ip_address=None,
            user_agent="phase13-bootstrap",
        )
        if target_tenant is None:
            raise CommandError("Target tenant account was not created")
        subscription = current_subscription(company)
        if subscription is None:
            subscription = assign_subscription(
                tenant_public_id=target_tenant.public_id,
                plan_public_id=pilot_plan.public_id,
                status=CompanySubscription.Status.ACTIVE,
                starts_at=now,
                ends_at=None,
                grace_until=None,
                reason="phase13.pilot_activation",
                actor=actor,
            )
        usage = collect_usage_snapshot(
            tenant_public_id=target_tenant.public_id,
            actor=actor,
        )

        role_ids = membership.role_assignments.filter(
            effective_from__lte=now,
        ).filter(
            Q(effective_to__isnull=True) | Q(effective_to__gt=now)
        ).values_list("role_public_id", flat=True)
        tenant_roles = list(
            Role.objects.filter(
                company_public_id=company.public_id,
                public_id__in=role_ids,
                retired_at__isnull=True,
            )
        )
        support_permission = Permission.objects.get(code="controlplane.support.approve")
        tenant_grants = 0
        for role in tenant_roles:
            _, created = RolePermission.objects.get_or_create(
                role=role,
                permission=support_permission,
            )
            tenant_grants += int(created)

        Notification.objects.get_or_create(
            company=company,
            user_public_id=user.public_id,
            event_code="system.phase13.ready",
            defaults={
                "title": "Phase 13 SaaS control plane is active",
                "body": (
                    "Platform operator governance, tenant lifecycle, subscriptions, usage quotas "
                    "and support-access requests are ready."
                ),
                "severity": Notification.Severity.SUCCESS,
                "action_path": "/control-plane",
                "source_type": "phase13_bootstrap",
            },
        )

        self.stdout.write(self.style.SUCCESS("PHASE 13 CONTROL PLANE INITIALIZATION COMPLETED"))
        self.stdout.write(f"Platform operator: {user.email}")
        self.stdout.write(f"Tenant accounts available: {tenant_count}")
        self.stdout.write("Published plans available: 2")
        self.stdout.write(
            "Active subscription: "
            f"{subscription.plan_version.code} v{subscription.plan_version.version}"
        )
        self.stdout.write(f"Usage snapshot: {usage.period_start} to {usage.period_end}")
        self.stdout.write(f"Control-plane permissions available: {len(permissions)}")
        self.stdout.write(f"New tenant support approval grants: {tenant_grants}")
