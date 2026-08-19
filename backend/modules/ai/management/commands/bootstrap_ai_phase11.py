from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from modules.ai.models import AIModelPolicy, AIProviderProfile
from modules.identity.models import Permission, Role, RolePermission, User
from modules.notifications.models import Notification
from modules.tenant.models import Company, Membership

POLICIES = [
    {
        "code": "BUILD360_ASSISTANT",
        "name": "Build360 grounded assistant",
        "purpose": AIModelPolicy.Purpose.ASSISTANT,
        "system_instruction": (
            "Summarize only authorized Build360 records, cite every material claim, "
            "state uncertainty, and never execute business actions."
        ),
        "allowed_source_types": ["reporting.metric"],
        "allowed_data_classifications": ["internal", "confidential", "restricted"],
        "allowed_tool_codes": ["notification.draft", "workflow.comment.draft"],
        "max_context_records": 20,
        "max_output_characters": 6000,
        "human_review_required": True,
        "citations_required": True,
        "retention_days": 30,
    },
    {
        "code": "BUILD360_EXTRACTION",
        "name": "Build360 extraction reviewer",
        "purpose": AIModelPolicy.Purpose.EXTRACTION,
        "system_instruction": (
            "Extract only explicitly requested fields. Do not infer missing values. "
            "All extracted data requires human review before downstream use."
        ),
        "allowed_source_types": ["document.text", "file.metadata"],
        "allowed_data_classifications": ["internal", "confidential"],
        "allowed_tool_codes": [],
        "max_context_records": 10,
        "max_output_characters": 8000,
        "human_review_required": True,
        "citations_required": False,
        "retention_days": 30,
    },
    {
        "code": "BUILD360_RISK",
        "name": "Build360 operational risk detector",
        "purpose": AIModelPolicy.Purpose.RISK,
        "system_instruction": (
            "Detect risk signals from governed metrics only. A signal is advisory and "
            "must not change project, safety, finance, or workflow state."
        ),
        "allowed_source_types": ["reporting.metric"],
        "allowed_data_classifications": ["internal", "confidential", "restricted"],
        "allowed_tool_codes": [],
        "max_context_records": 10,
        "max_output_characters": 4000,
        "human_review_required": True,
        "citations_required": True,
        "retention_days": 90,
    },
    {
        "code": "BUILD360_EVALUATION",
        "name": "Build360 AI guardrail evaluation",
        "purpose": AIModelPolicy.Purpose.EVALUATION,
        "system_instruction": "Evaluate provider and policy controls without business actions.",
        "allowed_source_types": [],
        "allowed_data_classifications": ["internal"],
        "allowed_tool_codes": [],
        "max_context_records": 5,
        "max_output_characters": 2000,
        "human_review_required": True,
        "citations_required": True,
        "retention_days": 365,
    },
]


class Command(BaseCommand):
    help = "Initialize Phase 11 governed AI foundations."

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

        provider, _ = AIProviderProfile.objects.update_or_create(
            company=company,
            code="LOCAL_GROUNDED",
            defaults={
                "display_name": "Build360 local governed adapter",
                "adapter_code": "local_grounded",
                "secret_reference": "",
                "data_residency": "local-development",
                "configuration": {
                    "network_access": False,
                    "persists_raw_prompts": False,
                    "executes_actions": False,
                },
                "supports_citations": True,
                "supports_extraction": True,
                "supports_tools": True,
                "is_active": True,
            },
        )

        policy_count = 0
        for item in POLICIES:
            _, created = AIModelPolicy.objects.update_or_create(
                company=company,
                code=item["code"],
                version=1,
                defaults={
                    **item,
                    "provider": provider,
                    "model_name": "build360-local-grounded-v1",
                    "effective_from": timezone.now(),
                    "is_active": True,
                },
            )
            policy_count += int(created)

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
        permissions = list(Permission.objects.filter(code__startswith="ai."))
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
            event_code="system.phase11.ready",
            defaults={
                "title": "Phase 11 governed AI foundations are active",
                "body": (
                    "Permission-aware retrieval, citations, extraction review, risk signals, "
                    "human-confirmed tool proposals and evaluation evidence are ready."
                ),
                "severity": Notification.Severity.SUCCESS,
                "action_path": "/ai-control",
                "source_type": "phase11_bootstrap",
            },
        )

        self.stdout.write(self.style.SUCCESS("PHASE 11 AI INITIALIZATION COMPLETED"))
        self.stdout.write(f"Company: {company.display_name} ({company.code})")
        self.stdout.write(f"Active provider: {provider.code}")
        self.stdout.write(f"AI policies available: {len(POLICIES)}")
        self.stdout.write(f"New AI policies created: {policy_count}")
        self.stdout.write(f"Phase 11 permissions available: {len(permissions)}")
        self.stdout.write(f"New role grants: {created_grants}")
