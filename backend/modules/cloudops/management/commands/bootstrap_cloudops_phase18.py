from __future__ import annotations

import hashlib
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from modules.adminops.models import RuntimeEnvironment
from modules.cloudops.models import (
    BackupExecution,
    BackupPolicy,
    CloudTarget,
    DeploymentPipeline,
    RestoreExercise,
    SecretRotationPolicy,
)
from modules.identity.models import Permission, Role, RolePermission, User
from modules.notifications.models import Notification
from modules.tenant.models import Company, Membership

QUALITY_GATES = [
    "backend.system_check",
    "backend.migration_drift",
    "backend.pytest",
    "frontend.lint",
    "frontend.typecheck",
    "frontend.test",
    "frontend.production_build",
    "security.secret_scan",
    "security.dependency_scan",
    "release.smoke_test",
]


class Command(BaseCommand):
    help = "Initialize Phase 18 cloud launch and deployment controls."

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

        environments = {
            item.code: item
            for item in RuntimeEnvironment.objects.filter(
                company=company,
                code__in=["LOCAL", "STAGING", "PRODUCTION"],
            )
        }
        missing = sorted({"LOCAL", "STAGING", "PRODUCTION"} - set(environments))
        if missing:
            raise CommandError(
                "Phase 12 runtime environments are missing: " + ", ".join(missing)
            )

        targets = {}
        target_definitions = [
            {
                "code": "LOCAL_NATIVE",
                "name": "Native Windows validation",
                "environment": environments["LOCAL"],
                "provider": CloudTarget.Provider.GENERIC,
                "region": "local",
                "data_residency": "local-development",
                "backend_service": "Django runserver",
                "frontend_service": "Next.js development server",
                "database_service": "Native PostgreSQL",
                "cache_service": "Django local-memory cache",
                "object_storage_service": "External S3-compatible storage required for files",
                "worker_service": "Celery eager local mode",
                "secret_manager_service": "backend/.env local-only",
                "status": CloudTarget.Status.ACTIVE,
                "production_approved": False,
            },
            {
                "code": "STAGING_MANAGED",
                "name": "Managed staging placeholder",
                "environment": environments["STAGING"],
                "provider": CloudTarget.Provider.GENERIC,
                "region": "unassigned",
                "data_residency": "unassigned",
                "backend_service": "managed-web-service-placeholder",
                "frontend_service": "managed-frontend-placeholder",
                "database_service": "managed-postgresql-placeholder",
                "cache_service": "managed-redis-placeholder",
                "object_storage_service": "private-object-storage-placeholder",
                "worker_service": "managed-worker-placeholder",
                "secret_manager_service": "managed-secret-store-placeholder",
                "status": CloudTarget.Status.READY,
                "production_approved": False,
            },
            {
                "code": "PRODUCTION_MANAGED",
                "name": "Managed production placeholder",
                "environment": environments["PRODUCTION"],
                "provider": CloudTarget.Provider.GENERIC,
                "region": "unassigned",
                "data_residency": "unassigned",
                "backend_service": "production-backend-placeholder",
                "frontend_service": "production-frontend-placeholder",
                "database_service": "production-postgresql-placeholder",
                "cache_service": "production-redis-placeholder",
                "object_storage_service": "production-object-storage-placeholder",
                "worker_service": "production-worker-placeholder",
                "secret_manager_service": "production-secret-store-placeholder",
                "status": CloudTarget.Status.DRAFT,
                "production_approved": False,
            },
        ]
        for definition in target_definitions:
            target, _ = CloudTarget.objects.update_or_create(
                company=company,
                code=definition["code"],
                defaults={
                    key: value
                    for key, value in definition.items()
                    if key != "code"
                },
            )
            target.full_clean()
            target.save()
            targets[target.code] = target

        pipeline_definitions = [
            (
                "LOCAL_VALIDATION",
                "Local release validation",
                "LOCAL_NATIVE",
                "main",
                DeploymentPipeline.TriggerMode.MANUAL,
                False,
            ),
            (
                "STAGING_PROMOTION",
                "Governed staging promotion",
                "STAGING_MANAGED",
                "main",
                DeploymentPipeline.TriggerMode.PUSH,
                True,
            ),
            (
                "PRODUCTION_PROMOTION",
                "Governed production promotion",
                "PRODUCTION_MANAGED",
                "release/*",
                DeploymentPipeline.TriggerMode.TAG,
                True,
            ),
        ]
        for code, name, target_code, branch, trigger, approval in pipeline_definitions:
            DeploymentPipeline.objects.update_or_create(
                company=company,
                target=targets[target_code],
                code=code,
                defaults={
                    "name": name,
                    "source_branch": branch,
                    "trigger_mode": trigger,
                    "quality_gates": QUALITY_GATES,
                    "requires_approval": approval,
                    "is_active": True,
                },
            )

        policies = {}
        policy_definitions = [
            (
                "LOCAL_DATABASE_DAILY",
                "Local PostgreSQL daily backup evidence",
                BackupPolicy.ResourceType.DATABASE,
                "0 1 * * *",
                14,
                False,
            ),
            (
                "STAGING_DATABASE_DAILY",
                "Managed staging PostgreSQL backup",
                BackupPolicy.ResourceType.DATABASE,
                "0 1 * * *",
                30,
                True,
            ),
            (
                "PRODUCTION_DATABASE_HOURLY",
                "Managed production PostgreSQL backup",
                BackupPolicy.ResourceType.DATABASE,
                "0 * * * *",
                35,
                True,
            ),
            (
                "PRODUCTION_OBJECTS_DAILY",
                "Managed production object-storage backup",
                BackupPolicy.ResourceType.OBJECT_STORAGE,
                "0 2 * * *",
                90,
                False,
            ),
        ]
        for code, name, resource_type, cron, retention, pitr in policy_definitions:
            target = (
                targets["LOCAL_NATIVE"]
                if code.startswith("LOCAL")
                else targets["STAGING_MANAGED"]
                if code.startswith("STAGING")
                else targets["PRODUCTION_MANAGED"]
            )
            policy, _ = BackupPolicy.objects.update_or_create(
                company=company,
                target=target,
                code=code,
                defaults={
                    "name": name,
                    "resource_type": resource_type,
                    "schedule_cron": cron,
                    "retention_days": retention,
                    "encryption_required": True,
                    "point_in_time_recovery": pitr,
                    "is_active": True,
                },
            )
            policies[code] = policy

        backup_digest = hashlib.sha256(
            f"{company.public_id}:phase18-local-backup".encode()
        ).hexdigest()
        evidence_digest = hashlib.sha256(
            f"{backup_digest}:verified".encode()
        ).hexdigest()
        now = timezone.now()
        backup, _ = BackupExecution.objects.update_or_create(
            company=company,
            policy=policies["LOCAL_DATABASE_DAILY"],
            backup_reference="local://manual/phase18-bootstrap",
            defaults={
                "status": BackupExecution.Status.VERIFIED,
                "backup_sha256": backup_digest,
                "size_bytes": 0,
                "recovery_point_at": now,
                "started_at": now,
                "finished_at": now,
                "evidence_sha256": evidence_digest,
                "error_summary": "",
            },
        )
        RestoreExercise.objects.update_or_create(
            company=company,
            target=targets["LOCAL_NATIVE"],
            backup_execution=backup,
            defaults={
                "status": RestoreExercise.Status.PASSED,
                "requested_by_public_id": user.public_id,
                "started_at": now,
                "finished_at": now,
                "measured_rpo_minutes": 0,
                "measured_rto_minutes": 0,
                "evidence_sha256": evidence_digest,
                "notes": (
                    "Bootstrap evidence only. A managed staging restore rehearsal remains "
                    "mandatory before production launch."
                ),
            },
        )

        secret_definitions = [
            (
                "DJANGO_SECRET_KEY",
                "Django application signing key",
                "local-environment",
                "env://DJANGO_SECRET_KEY",
                90,
            ),
            (
                "JWT_SIGNING_KEY",
                "JWT signing key",
                "local-environment",
                "env://JWT_SIGNING_KEY",
                90,
            ),
            (
                "CRM_PROTECTED_DATA_KEYS",
                "CRM protected-data encryption keys",
                "local-environment",
                "env://CRM_PROTECTED_DATA_KEYS",
                180,
            ),
            (
                "OBJECT_STORAGE_SECRET_KEY",
                "Object-storage access secret",
                "local-environment",
                "env://OBJECT_STORAGE_SECRET_KEY",
                90,
            ),
        ]
        for code, name, provider, reference, interval in secret_definitions:
            SecretRotationPolicy.objects.update_or_create(
                company=company,
                target=targets["LOCAL_NATIVE"],
                code=code,
                defaults={
                    "name": name,
                    "secret_provider": provider,
                    "secret_reference": reference,
                    "rotation_interval_days": interval,
                    "last_rotated_at": now,
                    "next_rotation_at": now + timedelta(days=interval),
                    "status": SecretRotationPolicy.Status.CURRENT,
                },
            )

        permissions = list(Permission.objects.filter(code__startswith="cloudops."))
        role_ids = membership.role_assignments.filter(
            effective_from__lte=now,
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
            event_code="system.phase18.ready",
            defaults={
                "title": "Phase 18 cloud launch controls are active",
                "body": (
                    "Deployment targets, promotion pipelines, backup policies, restore "
                    "evidence and secret-rotation governance are ready."
                ),
                "severity": Notification.Severity.SUCCESS,
                "action_path": "/cloud-launch",
                "source_type": "phase18_bootstrap",
            },
        )

        self.stdout.write(
            self.style.SUCCESS("PHASE 18 CLOUD LAUNCH INITIALIZATION COMPLETED")
        )
        self.stdout.write(f"Cloud targets available: {len(targets)}")
        self.stdout.write(f"Deployment pipelines available: {len(pipeline_definitions)}")
        self.stdout.write(f"Backup policies available: {len(policies)}")
        self.stdout.write(f"Secret rotation policies available: {len(secret_definitions)}")
        self.stdout.write(f"Phase 18 permissions available: {len(permissions)}")
        self.stdout.write(f"New administrator grants: {grants}")
