from __future__ import annotations

from datetime import time

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from modules.communication.models import (
    ChannelPolicy,
    CommunicationChannel,
    MessageTemplate,
    ProviderConfiguration,
)
from modules.identity.models import Permission, Role, RolePermission, User
from modules.notifications.models import Notification, NotificationDelivery, NotificationRule
from modules.tenant.models import Company, Membership

RULES = [
    (
        "system.welcome",
        "Welcome notification",
        "Welcome to {company_name}",
        "Your Build360 communication and notification controls are active.",
        "success",
    ),
    (
        "approval.requested",
        "Approval requested",
        "Approval required",
        "A governed workflow approval is waiting for your review.",
        "warning",
    ),
    (
        "finance.invoice.overdue",
        "Invoice overdue",
        "Invoice requires attention",
        "An invoice has passed its due date and requires commercial follow-up.",
        "warning",
    ),
    (
        "safety.incident.critical",
        "Critical safety incident",
        "Critical safety incident reported",
        "A critical safety incident requires immediate authorized review.",
        "critical",
    ),
]


class Command(BaseCommand):
    help = "Initialize Phase 9 communication policies, templates, rules and permissions."

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

        defaults = {
            CommunicationChannel.IN_APP: {
                "is_enabled": True,
                "consent_required": False,
                "quiet_hours_start": None,
                "quiet_hours_end": None,
                "timezone": company.timezone,
                "retry_limit": 3,
                "max_daily_per_subject": 100,
            },
            CommunicationChannel.EMAIL: {
                "is_enabled": False,
                "consent_required": True,
                "quiet_hours_start": time(21, 0),
                "quiet_hours_end": time(8, 0),
                "timezone": company.timezone,
                "retry_limit": 3,
                "max_daily_per_subject": 20,
            },
            CommunicationChannel.SMS: {
                "is_enabled": False,
                "consent_required": True,
                "quiet_hours_start": time(21, 0),
                "quiet_hours_end": time(8, 0),
                "timezone": company.timezone,
                "retry_limit": 3,
                "max_daily_per_subject": 10,
            },
            CommunicationChannel.WHATSAPP: {
                "is_enabled": False,
                "consent_required": True,
                "quiet_hours_start": time(21, 0),
                "quiet_hours_end": time(8, 0),
                "timezone": company.timezone,
                "retry_limit": 3,
                "max_daily_per_subject": 20,
            },
            CommunicationChannel.VOICE: {
                "is_enabled": False,
                "consent_required": True,
                "quiet_hours_start": time(20, 0),
                "quiet_hours_end": time(9, 0),
                "timezone": company.timezone,
                "retry_limit": 2,
                "max_daily_per_subject": 5,
            },
        }
        for channel, values in defaults.items():
            ChannelPolicy.objects.update_or_create(
                company=company,
                channel=channel,
                defaults=values,
            )

        ProviderConfiguration.objects.update_or_create(
            company=company,
            code="IN_APP",
            defaults={
                "channel": CommunicationChannel.IN_APP,
                "display_name": "Build360 in-app delivery",
                "adapter_code": "in_app",
                "priority": 1,
                "is_active": True,
                "supports_inbound": False,
                "supports_delivery_receipts": True,
                "configuration": {"mode": "native"},
            },
        )
        ProviderConfiguration.objects.update_or_create(
            company=company,
            code="LOCAL_NOOP",
            defaults={
                "channel": CommunicationChannel.EMAIL,
                "display_name": "Local development email adapter",
                "adapter_code": "local_noop",
                "priority": 999,
                "is_active": False,
                "supports_inbound": False,
                "supports_delivery_receipts": False,
                "configuration": {"local_only": True},
            },
        )

        template_count = 0
        for event_code, name, title, body, severity in RULES:
            template, _ = MessageTemplate.objects.get_or_create(
                company=company,
                code=event_code.upper(),
                channel=CommunicationChannel.IN_APP,
                locale=company.locale or "en-IN",
                version=1,
                defaults={
                    "name": name,
                    "status": MessageTemplate.Status.PUBLISHED,
                    "subject_template": "{title}",
                    "body_template": "{body}",
                    "variable_names": ["title", "body", "company_name"],
                    "purpose_code": event_code,
                    "created_by_public_id": user.public_id,
                    "published_by_public_id": user.public_id,
                    "published_at": timezone.now(),
                },
            )
            template_count += int(template.status == MessageTemplate.Status.PUBLISHED)
            NotificationRule.objects.update_or_create(
                company=company,
                event_code=event_code,
                defaults={
                    "name": name,
                    "default_title_template": title,
                    "default_body_template": body,
                    "severity": severity,
                    "channels": [CommunicationChannel.IN_APP],
                    "is_active": True,
                },
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
                Q(code__startswith="communication.")
                | Q(code__startswith="notification.")
            )
        )
        created_grants = 0
        for role in roles:
            for permission in permissions:
                _, was_created = RolePermission.objects.get_or_create(
                    role=role,
                    permission=permission,
                )
                created_grants += int(was_created)

        welcome = Notification.objects.filter(
            company=company,
            user_public_id=user.public_id,
            event_code="system.welcome",
        ).first()
        if welcome is None:
            welcome = Notification.objects.create(
                company=company,
                user_public_id=user.public_id,
                event_code="system.welcome",
                title=f"Welcome to {company.display_name}",
                body="Phase 9 communication and notification controls are active.",
                severity=Notification.Severity.SUCCESS,
                action_path="/communications",
                source_type="phase9_bootstrap",
            )
            NotificationDelivery.objects.create(
                company=company,
                notification=welcome,
                channel=CommunicationChannel.IN_APP,
                status=NotificationDelivery.Status.DELIVERED,
                attempted_at=timezone.now(),
                delivered_at=timezone.now(),
            )

        self.stdout.write(self.style.SUCCESS("PHASE 9 COMMUNICATION INITIALIZATION COMPLETED"))
        self.stdout.write(f"Company: {company.display_name} ({company.code})")
        self.stdout.write(f"Channel policies: {len(defaults)}")
        self.stdout.write(f"Published templates: {template_count}")
        self.stdout.write(f"Notification rules: {len(RULES)}")
        self.stdout.write(f"Phase 9 permissions available: {len(permissions)}")
        self.stdout.write(f"New role grants: {created_grants}")
