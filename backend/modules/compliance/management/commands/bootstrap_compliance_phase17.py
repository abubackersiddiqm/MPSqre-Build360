from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from modules.compliance.models import (
    ComplianceControl,
    ComplianceFramework,
    RiskRegisterItem,
)
from modules.identity.models import Permission, Role, RolePermission, User
from modules.notifications.models import Notification
from modules.tenant.models import Company, Membership

FRAMEWORKS = [
    (
        "BUILD360_SECURITY_BASELINE",
        "Build360 Security and Operational Control Baseline",
        ComplianceFramework.FrameworkType.INTERNAL,
        "Global",
        "2026.1",
        "Internal security, privacy, resilience and secure-delivery readiness controls.",
    ),
    (
        "ISO27001_READINESS",
        "ISO/IEC 27001 Readiness Alignment",
        ComplianceFramework.FrameworkType.ISO_27001,
        "Global",
        "2022-aligned",
        "Readiness alignment only. This framework does not represent certification.",
    ),
    (
        "INDIA_PRIVACY_READINESS",
        "India Privacy and DPDP Readiness",
        ComplianceFramework.FrameworkType.PRIVACY,
        "India",
        "2026.1",
        "Operational privacy-readiness controls for India-first pilot deployments.",
    ),
]

CONTROLS = [
    ("GOV-01", "Security ownership and accountability", "governance", "high", 90),
    ("GOV-02", "Policy approval and annual review", "governance", "medium", 365),
    ("GOV-03", "Segregation of duties", "governance", "high", 90),
    ("IAM-01", "Tenant-scoped identity and membership", "access", "critical", 30),
    ("IAM-02", "Privileged access review", "access", "critical", 90),
    ("IAM-03", "Session rotation and revocation", "access", "high", 90),
    ("IAM-04", "Joiner, mover and leaver controls", "access", "high", 30),
    ("DAT-01", "Protected-data encryption", "data", "critical", 90),
    ("DAT-02", "Backup and restore evidence", "continuity", "critical", 30),
    ("DAT-03", "Retention and deletion governance", "data", "high", 90),
    ("DAT-04", "Data classification and handling", "data", "high", 90),
    ("DEV-01", "Dependency and vulnerability review", "secure_delivery", "high", 30),
    ("DEV-02", "Migration and rollback governance", "secure_delivery", "high", 30),
    ("DEV-03", "Secrets excluded from source control", "secure_delivery", "critical", 30),
    ("OPS-01", "Service objectives and health evidence", "operations", "high", 30),
    ("OPS-02", "Audit and event integrity", "operations", "critical", 30),
    ("OPS-03", "Release approval and evidence", "operations", "high", 30),
    ("INC-01", "Incident response and postmortem", "incident", "critical", 90),
    ("BCP-01", "Business continuity and disaster recovery", "continuity", "critical", 90),
    ("TPR-01", "Vendor and processor due diligence", "third_party", "high", 180),
    ("PRV-01", "Purpose and lawful-basis register", "privacy", "high", 90),
    ("PRV-02", "Privacy request handling", "privacy", "high", 30),
    ("PRV-03", "Cross-border transfer governance", "privacy", "high", 90),
    ("PRV-04", "Breach assessment and notification evidence", "privacy", "critical", 90),
]


class Command(BaseCommand):
    help = "Initialize Phase 17 security and compliance operations."

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
        framework_count = 0
        control_count = 0
        for code, name, framework_type, jurisdiction, version_label, description in FRAMEWORKS:
            framework, _ = ComplianceFramework.objects.update_or_create(
                company=company,
                code=code,
                version_label=version_label,
                defaults={
                    "name": name,
                    "framework_type": framework_type,
                    "jurisdiction": jurisdiction,
                    "description": description,
                    "status": ComplianceFramework.Status.PUBLISHED,
                    "effective_from": today,
                    "certification_claim": False,
                },
            )
            framework_count += 1
            if code != "BUILD360_SECURITY_BASELINE":
                continue
            for control_code, title, domain, severity, frequency in CONTROLS:
                ComplianceControl.objects.update_or_create(
                    company=company,
                    framework=framework,
                    code=control_code,
                    defaults={
                        "title": title,
                        "description": (
                            "Capture objective evidence, assigned ownership and remediation "
                            "before this control is assessed as compliant."
                        ),
                        "domain": domain,
                        "severity": severity,
                        "evidence_frequency_days": frequency,
                        "status": ComplianceControl.Status.ACTIVE,
                        "owner_membership": membership,
                    },
                )
                control_count += 1

        RiskRegisterItem.objects.update_or_create(
            company=company,
            risk_code="RISK-INITIAL-PILOT",
            defaults={
                "title": "Pilot production environment remains locally hosted",
                "description": (
                    "Native Windows mode is appropriate for local validation but must not be "
                    "treated as the final multi-instance production topology."
                ),
                "category": RiskRegisterItem.Category.AVAILABILITY,
                "likelihood": 3,
                "impact": 4,
                "score": 12,
                "treatment": RiskRegisterItem.Treatment.MITIGATE,
                "treatment_plan": (
                    "Complete staging deployment, managed backups, shared cache, worker "
                    "topology and monitored restore rehearsal before customer production use."
                ),
                "owner_membership": membership,
                "due_at": timezone.now() + timedelta(days=45),
            },
        )

        permissions = list(Permission.objects.filter(code__startswith="compliance."))
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
            event_code="system.phase17.ready",
            defaults={
                "title": "Phase 17 security and compliance operations is active",
                "body": (
                    "Compliance frameworks, control assessments, risk governance, security "
                    "exceptions and access-review campaigns are ready."
                ),
                "severity": Notification.Severity.SUCCESS,
                "action_path": "/compliance",
                "source_type": "phase17_bootstrap",
            },
        )

        self.stdout.write(
            self.style.SUCCESS(
                "PHASE 17 SECURITY AND COMPLIANCE INITIALIZATION COMPLETED"
            )
        )
        self.stdout.write(f"Published readiness frameworks: {framework_count}")
        self.stdout.write(f"Baseline controls available: {control_count}")
        self.stdout.write(f"Phase 17 permissions available: {len(permissions)}")
        self.stdout.write(f"New administrator grants: {grants}")
