from __future__ import annotations

import uuid
from typing import Any

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.migrations.recorder import MigrationRecorder
from django.urls import resolve
from django.utils import timezone

from modules.files.models import FileObject, FileVersion
from modules.identity.models import Permission
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.releaseops.models import (
    BackupSnapshot,
    DeploymentTarget,
    ReadinessRun,
    ReleaseCandidate,
    ReleaseGate,
    UATExecution,
    UATScenario,
)
from modules.tenant.models import Company

DEFAULT_GATES = [
    ("SOURCE_LOCK", "Source baseline locked", "SOURCE"),
    ("MIGRATIONS", "Database migrations validated", "DATABASE"),
    ("AUTOMATED_TESTS", "Automated test suite passed", "QUALITY"),
    ("SECURITY_REVIEW", "Security and tenant isolation reviewed", "SECURITY"),
    ("PERMISSIONS", "Role and object permission matrix validated", "SECURITY"),
    ("PERFORMANCE", "Performance and capacity baseline accepted", "RELIABILITY"),
    ("BACKUP", "Backup and restore evidence available", "RECOVERY"),
    ("UAT", "Required end-to-end UAT completed", "UAT"),
    ("OPERATIONS", "Monitoring and incident response ready", "OPERATIONS"),
    ("DOCUMENTATION", "Admin and user documentation approved", "DOCUMENTATION"),
    ("GO_LIVE", "Business owner go-live authorization", "GOVERNANCE"),
]

UAT_LIBRARY = [
    ("UAT-001", "Create a customer company and primary administrator", "ACCESS", "PLATFORM_OPERATOR"),
    ("UAT-002", "Activate the company administrator invitation", "ACCESS", "COMPANY_ADMIN"),
    ("UAT-003", "Create a role, invite an employee and assign access", "ACCESS", "COMPANY_ADMIN"),
    ("UAT-004", "Complete employee profile and reporting line", "PEOPLE", "HR_ADMIN"),
    ("UAT-005", "Create project, site and WBS", "PROJECT_WORK", "PROJECT_MANAGER"),
    ("UAT-006", "Create and assign governed work", "PROJECT_WORK", "PROJECT_MANAGER"),
    ("UAT-007", "Execute assigned work through My Work", "MY_WORK", "EMPLOYEE"),
    ("UAT-008", "Submit and approve a timesheet with maker-checker", "MY_WORK", "MANAGER"),
    ("UAT-009", "Invite a partner and grant project access", "COLLABORATION", "COMPANY_ADMIN"),
    ("UAT-010", "Submit and review a partner response", "COLLABORATION", "PARTNER"),
    ("UAT-011", "Create and govern a variation or claim", "COMMERCIAL", "COMMERCIAL_MANAGER"),
    ("UAT-012", "Manage a safety permit and corrective action", "SAFETY", "SAFETY_MANAGER"),
    ("UAT-013", "Complete QA/QC inspection and NCR workflow", "QUALITY", "QUALITY_MANAGER"),
    ("UAT-014", "Issue a document revision and transmittal", "DOCUMENT_CONTROL", "DOCUMENT_CONTROLLER"),
    ("UAT-015", "Create backup evidence and verify restore drill", "RECOVERY", "SYSTEM_ADMIN"),
    ("UAT-016", "Access Build360 from another device on LAN", "DEPLOYMENT", "SYSTEM_ADMIN"),
    ("UAT-017", "Verify cross-tenant data isolation", "SECURITY", "SECURITY_REVIEWER"),
    ("UAT-018", "Verify permission-driven navigation and direct URLs", "SECURITY", "SECURITY_REVIEWER"),
    ("UAT-019", "Revoke a session and confirm access termination", "IDENTITY", "COMPANY_ADMIN"),
    ("UAT-020", "Validate production live and readiness endpoints", "DEPLOYMENT", "RELEASE_MANAGER"),
    ("UAT-021", "Save a protected CRM contact and prevent accidental duplicate reuse", "CRM", "CRM_EXECUTIVE"),
    ("UAT-022", "Dial a protected CRM contact and record call follow-up evidence", "CRM", "CRM_EXECUTIVE"),
    ("UAT-023", "Qualify a lead and convert it into customer and opportunity", "CRM", "SALES_MANAGER"),
    ("UAT-024", "Start one preconstruction project per opportunity and reuse it after award", "CRM_PROJECT", "SALES_MANAGER"),
    ("UAT-025", "Register a design document and upload an immutable governed revision", "DESIGN", "ARCHITECT"),
    ("UAT-026", "Create estimate and BOQ then complete controlled approval and baseline", "ESTIMATION", "ESTIMATOR"),
    ("UAT-027", "Share only approved customer-facing records through governed portal access", "PORTAL", "COMMERCIAL_MANAGER"),
    ("UAT-028", "Complete CRM to preconstruction to design to estimate to client-share journey", "END_TO_END", "BUSINESS_OWNER"),
]


def _record(*, company: Company, action: str, event_type: str, entity_type: str, entity_public_id: uuid.UUID,
            actor_public_id: uuid.UUID, correlation_id: uuid.UUID, version: int, after: dict[str, Any],
            before: dict[str, Any] | None = None) -> None:
    append_audit(AuditRecord(
        action=action,
        entity_type=entity_type,
        entity_public_id=entity_public_id,
        actor_public_id=actor_public_id,
        company_public_id=company.public_id,
        request_id=correlation_id,
        correlation_id=correlation_id,
        before=before or {},
        after=after,
    ))
    append_event(EventRecord(
        event_type=event_type,
        aggregate_type=entity_type,
        aggregate_public_id=entity_public_id,
        aggregate_version=version,
        company_public_id=company.public_id,
        correlation_id=correlation_id,
        payload=after,
    ))


def seed_uat_library(company: Company) -> int:
    count = 0
    for code, title, module, persona in UAT_LIBRARY:
        _, created = UATScenario.objects.get_or_create(
            company=company,
            code=code,
            version=1,
            defaults={
                "title": title,
                "module_code": module,
                "persona_code": persona,
                "preconditions": "Required master data, permissions and test identities are available.",
                "steps": ["Prepare test data", "Execute the business journey", "Capture evidence", "Verify audit history"],
                "expected_result": "The complete journey succeeds with correct authorization, tenant isolation and audit evidence.",
                "is_required": True,
                "status_code": "ACTIVE",
            },
        )
        count += int(created)
    return count


@transaction.atomic
def create_target(*, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> DeploymentTarget:
    data["code"] = data["code"].strip().upper().replace(" ", "_")
    target = DeploymentTarget(company=company, **data)
    target.full_clean()
    target.save()
    _record(company=company, action="CREATE", event_type="release.target.created", entity_type="DeploymentTarget",
            entity_public_id=target.public_id, actor_public_id=actor_public_id, correlation_id=correlation_id,
            version=target.version, after={"code": target.code, "environment": target.environment_code})
    return target


@transaction.atomic
def create_release(*, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID,
                   target: DeploymentTarget | None = None, **data: Any) -> ReleaseCandidate:
    if target and target.company_id != company.id:
        raise ValidationError("Deployment target cannot cross companies")
    data["release_code"] = data["release_code"].strip().upper().replace(" ", "_")
    release = ReleaseCandidate(company=company, target=target, created_by_public_id=actor_public_id, **data)
    release.full_clean()
    release.save()
    for code, name, category in DEFAULT_GATES:
        ReleaseGate.objects.create(
            company=company,
            release=release,
            code=code,
            name=name,
            category_code=category,
            is_required=True,
        )
    seed_uat_library(company)
    for scenario in UATScenario.objects.filter(company=company, status_code="ACTIVE"):
        UATExecution.objects.get_or_create(company=company, release=release, scenario=scenario)
    _record(company=company, action="CREATE", event_type="release.candidate.created", entity_type="ReleaseCandidate",
            entity_public_id=release.public_id, actor_public_id=actor_public_id, correlation_id=correlation_id,
            version=release.version, after={"release_code": release.release_code, "version_label": release.version_label})
    return release


@transaction.atomic
def decide_gate(*, gate: ReleaseGate, status_code: str, notes: str, evidence: dict[str, Any], expected_version: int,
                actor_public_id: uuid.UUID, correlation_id: uuid.UUID) -> ReleaseGate:
    gate = ReleaseGate.objects.select_for_update().get(pk=gate.pk)
    if gate.version != expected_version:
        raise ValidationError("Release gate changed. Refresh and retry.")
    if gate.release.status_code in ["PUBLISHED", "CANCELLED"]:
        raise ValidationError("Published or cancelled releases cannot be changed")
    before = {"status": gate.status_code, "version": gate.version}
    gate.status_code = status_code
    gate.notes = notes
    gate.evidence = evidence
    gate.decided_at = timezone.now()
    gate.decided_by_public_id = actor_public_id
    gate.version += 1
    gate.full_clean()
    gate.save()
    _record(company=gate.company, action="DECIDE", event_type="release.gate.decided", entity_type="ReleaseGate",
            entity_public_id=gate.public_id, actor_public_id=actor_public_id, correlation_id=correlation_id,
            version=gate.version, before=before, after={"status": gate.status_code, "code": gate.code})
    return gate


@transaction.atomic
def execute_uat(*, execution: UATExecution, status_code: str, notes: str, evidence: dict[str, Any],
                defect_reference: str, expected_version: int, actor_public_id: uuid.UUID,
                correlation_id: uuid.UUID) -> UATExecution:
    execution = UATExecution.objects.select_for_update().get(pk=execution.pk)
    if execution.version != expected_version:
        raise ValidationError("UAT execution changed. Refresh and retry.")
    if execution.release.status_code in ["PUBLISHED", "CANCELLED"]:
        raise ValidationError("Published or cancelled releases cannot be changed")
    if status_code == "PASSED" and defect_reference:
        raise ValidationError("Passed UAT cannot retain an open defect reference")
    before = {"status": execution.status_code, "version": execution.version}
    execution.status_code = status_code
    execution.notes = notes
    execution.evidence = evidence
    execution.defect_reference = defect_reference
    execution.tester_public_id = actor_public_id
    execution.executed_at = timezone.now()
    execution.version += 1
    execution.full_clean()
    execution.save()
    _record(company=execution.company, action="EXECUTE", event_type="release.uat.executed", entity_type="UATExecution",
            entity_public_id=execution.public_id, actor_public_id=actor_public_id, correlation_id=correlation_id,
            version=execution.version, before=before, after={"status": execution.status_code, "scenario": execution.scenario.code})
    return execution


@transaction.atomic
def register_backup(*, company: Company, release: ReleaseCandidate | None, target: DeploymentTarget | None,
                    actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> BackupSnapshot:
    backup = BackupSnapshot(
        company=company,
        release=release,
        target=target,
        captured_by_public_id=actor_public_id,
        **data,
    )
    backup.full_clean()
    backup.save()
    _record(company=company, action="CREATE", event_type="release.backup.registered", entity_type="BackupSnapshot",
            entity_public_id=backup.public_id, actor_public_id=actor_public_id, correlation_id=correlation_id,
            version=backup.version, after={"reference": backup.reference, "restore_tested": backup.restore_tested})
    return backup


def _check(name: str, passed: bool, detail: str, critical: bool = True) -> dict[str, object]:
    return {"code": name, "passed": bool(passed), "critical": critical, "detail": detail}


@transaction.atomic
def run_readiness(*, company: Company, release: ReleaseCandidate | None, actor_public_id: uuid.UUID,
                  correlation_id: uuid.UUID) -> ReadinessRun:
    started = timezone.now()
    run = ReadinessRun.objects.create(
        company=company,
        release=release,
        started_at=started,
        executed_by_public_id=actor_public_id,
    )
    results: list[dict[str, object]] = []
    try:
        connection.ensure_connection()
        results.append(_check("DATABASE", True, "Database connection is available."))
    except Exception as exc:  # pragma: no cover - environment dependent
        results.append(_check("DATABASE", False, f"Database connection failed: {exc}"))

    required_apps = [
        "crm", "projects", "design", "estimation", "files", "communication",
        "accessops", "orgops", "workops", "myworkops", "collabops", "commercialops",
        "safetyops", "qualityops", "documentops", "releaseops",
    ]
    missing_apps = [label for label in required_apps if not apps.is_installed(f"modules.{label}")]
    results.append(_check("APPLICATIONS", not missing_apps, "All required apps installed." if not missing_apps else f"Missing apps: {', '.join(missing_apps)}"))

    routes = [
        "/api/v1/health/live",
        "/api/v1/health/ready",
        "/api/v1/crm/summary",
        "/api/v1/projects/summary",
        "/api/v1/design/summary",
        "/api/v1/estimation/summary",
        "/api/v1/files/uploads",
        "/api/v1/communications/summary",
        "/api/v1/release-readiness/overview",
        "/api/v1/project-work/overview",
        "/api/v1/external-collaboration/overview",
    ]
    unresolved = []
    for route in routes:
        try:
            resolve(route)
        except Exception:
            unresolved.append(route)
    results.append(_check("ROUTES", not unresolved, "Critical routes resolve." if not unresolved else f"Unresolved routes: {', '.join(unresolved)}"))

    applied = set(MigrationRecorder(connection).applied_migrations())
    required_migrations = {
        ("releaseops", "0001_initial"),
        ("releaseops", "0002_seed_permissions"),
        ("projects", "0002_project_opportunity_idempotency"),
    }
    missing_migrations = sorted(required_migrations - applied)
    results.append(_check("MIGRATIONS", not missing_migrations, "Release migrations applied." if not missing_migrations else f"Missing migrations: {missing_migrations}"))

    permission_codes = set(Permission.objects.filter(code__startswith="release.").values_list("code", flat=True))
    results.append(_check("PERMISSIONS", len(permission_codes) == 9, f"Release permission inventory: {len(permission_codes)}/9."))

    active_targets = DeploymentTarget.objects.filter(company=company, status_code="ACTIVE")
    target_urls_ok = active_targets.exclude(frontend_url="").exclude(backend_url="").exists()
    results.append(_check("TARGETS", target_urls_ok, "Active target URLs configured." if target_urls_ok else "No active deployment target with frontend and backend URLs."))

    if release is not None:
        required_gates = release.gates.filter(is_required=True)
        results.append(_check("RELEASE_GATES", required_gates.exists() and not required_gates.exclude(status_code="PASSED").exists(), "All required release gates passed." if required_gates.exists() and not required_gates.exclude(status_code="PASSED").exists() else "Required release gates remain incomplete."))
        required_uat = release.uat_executions.filter(scenario__is_required=True)
        results.append(_check("UAT", required_uat.exists() and not required_uat.exclude(status_code="PASSED").exists(), "All required UAT scenarios passed." if required_uat.exists() and not required_uat.exclude(status_code="PASSED").exists() else "Required UAT scenarios remain incomplete."))
        backup_ok = release.backups.filter(status_code="AVAILABLE", restore_tested=True).exists()
        results.append(_check("BACKUP_RESTORE", backup_ok, "Restore-tested backup available." if backup_ok else "No restore-tested backup is registered for this release."))
    else:
        results.append(_check("RELEASE_SELECTED", False, "Select a release candidate for full readiness validation."))

    passed = sum(1 for item in results if item["passed"])
    failed = len(results) - passed
    run.results = results
    run.checks_total = len(results)
    run.checks_passed = passed
    run.checks_failed = failed
    run.status_code = "PASSED" if failed == 0 else "FAILED"
    run.completed_at = timezone.now()
    run.version += 1
    run.save()
    _record(company=company, action="EXECUTE", event_type="release.readiness.completed", entity_type="ReadinessRun",
            entity_public_id=run.public_id, actor_public_id=actor_public_id, correlation_id=correlation_id,
            version=run.version, after={"status": run.status_code, "passed": passed, "failed": failed})
    return run


def _validate_release_for_approval(release: ReleaseCandidate) -> None:
    required_gates = release.gates.filter(is_required=True)
    if not required_gates.exists() or required_gates.exclude(status_code="PASSED").exists():
        raise ValidationError("All required release gates must pass before approval")
    required_uat = release.uat_executions.filter(scenario__is_required=True)
    if not required_uat.exists() or required_uat.exclude(status_code="PASSED").exists():
        raise ValidationError("All required UAT scenarios must pass before approval")
    if not release.backups.filter(status_code="AVAILABLE", restore_tested=True).exists():
        raise ValidationError("A restore-tested backup is required before approval")
    if not release.readiness_runs.filter(status_code="PASSED", checks_failed=0).exists():
        raise ValidationError("A successful readiness run is required before approval")


@transaction.atomic
def approve_release(*, release: ReleaseCandidate, expected_version: int, actor_public_id: uuid.UUID,
                    correlation_id: uuid.UUID) -> ReleaseCandidate:
    release = ReleaseCandidate.objects.select_for_update().get(pk=release.pk)
    if release.version != expected_version:
        raise ValidationError("Release candidate changed. Refresh and retry.")
    if release.created_by_public_id == actor_public_id:
        raise ValidationError("Release creator cannot approve the same release")
    if release.status_code not in ["DRAFT", "IN_REVIEW", "READY"]:
        raise ValidationError("Only an active release candidate can be approved")
    _validate_release_for_approval(release)
    release.status_code = "APPROVED"
    release.approved_at = timezone.now()
    release.approved_by_public_id = actor_public_id
    release.version += 1
    release.save()
    _record(company=release.company, action="APPROVE", event_type="release.candidate.approved", entity_type="ReleaseCandidate",
            entity_public_id=release.public_id, actor_public_id=actor_public_id, correlation_id=correlation_id,
            version=release.version, after={"status": release.status_code, "release_code": release.release_code})
    return release


@transaction.atomic
def publish_release(*, release: ReleaseCandidate, expected_version: int, actor_public_id: uuid.UUID,
                    correlation_id: uuid.UUID) -> ReleaseCandidate:
    release = ReleaseCandidate.objects.select_for_update().select_related("target").get(pk=release.pk)
    if release.version != expected_version:
        raise ValidationError("Release candidate changed. Refresh and retry.")
    if release.status_code != "APPROVED":
        raise ValidationError("Only approved releases can be published")
    if release.target is None or release.target.status_code != "ACTIVE":
        raise ValidationError("An active deployment target is required")
    release.status_code = "PUBLISHED"
    release.published_at = timezone.now()
    release.published_by_public_id = actor_public_id
    release.version += 1
    release.save()
    _record(company=release.company, action="PUBLISH", event_type="release.candidate.published", entity_type="ReleaseCandidate",
            entity_public_id=release.public_id, actor_public_id=actor_public_id, correlation_id=correlation_id,
            version=release.version, after={"status": release.status_code, "target": release.target.code})
    return release



def _clean_evidence_file(*, company: Company, file_public_id: uuid.UUID) -> tuple[FileObject, FileVersion]:
    file_object = FileObject.objects.filter(
        company=company,
        public_id=file_public_id,
        status=FileObject.Status.ACTIVE,
    ).first()
    if file_object is None:
        raise ValidationError("Evidence file was not found")
    version = FileVersion.objects.filter(
        file_object=file_object,
        upload_status=FileVersion.UploadStatus.FINALIZED,
        scan_status=FileVersion.ScanStatus.CLEAN,
    ).order_by("-version").first()
    if version is None:
        raise ValidationError("Evidence file must be FINALIZED and CLEAN before attachment")
    return file_object, version


def _append_evidence_attachment(evidence: dict[str, Any], attachment: dict[str, Any]) -> dict[str, Any]:
    payload = dict(evidence or {})
    attachments = list(payload.get("attachments") or [])
    if not any(
        isinstance(item, dict) and str(item.get("file_public_id")) == attachment["file_public_id"]
        for item in attachments
    ):
        attachments.append(attachment)
    payload["attachments"] = attachments
    return payload


@transaction.atomic
def attach_gate_evidence_file(
    *,
    gate: ReleaseGate,
    file_public_id: uuid.UUID,
    note: str,
    expected_version: int,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> ReleaseGate:
    gate = ReleaseGate.objects.select_for_update().get(pk=gate.pk)
    if gate.version != expected_version:
        raise ValidationError("Release gate changed. Refresh and retry.")
    if gate.release.status_code in ["PUBLISHED", "CANCELLED"]:
        raise ValidationError("Published or cancelled releases cannot be changed")
    file_object, version = _clean_evidence_file(company=gate.company, file_public_id=file_public_id)
    before = {"version": gate.version, "evidence": gate.evidence}
    gate.evidence = _append_evidence_attachment(
        gate.evidence,
        {
            "file_public_id": str(file_object.public_id),
            "version_public_id": str(version.public_id),
            "original_name": version.original_name,
            "content_type": version.content_type,
            "sha256": version.actual_sha256 or version.expected_sha256,
            "note": note.strip(),
            "attached_at": timezone.now().isoformat(),
            "attached_by_public_id": str(actor_public_id),
        },
    )
    gate.version += 1
    gate.save(update_fields=["evidence", "version", "updated_at"])
    _record(
        company=gate.company,
        action="ATTACH_EVIDENCE",
        event_type="release.gate.evidence.attached",
        entity_type="ReleaseGate",
        entity_public_id=gate.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=gate.version,
        before=before,
        after={"code": gate.code, "attachment_file_public_id": str(file_object.public_id)},
    )
    return gate


@transaction.atomic
def attach_uat_evidence_file(
    *,
    execution: UATExecution,
    file_public_id: uuid.UUID,
    note: str,
    expected_version: int,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> UATExecution:
    execution = UATExecution.objects.select_for_update().get(pk=execution.pk)
    if execution.version != expected_version:
        raise ValidationError("UAT execution changed. Refresh and retry.")
    if execution.release.status_code in ["PUBLISHED", "CANCELLED"]:
        raise ValidationError("Published or cancelled releases cannot be changed")
    file_object, version = _clean_evidence_file(company=execution.company, file_public_id=file_public_id)
    before = {"version": execution.version, "evidence": execution.evidence}
    execution.evidence = _append_evidence_attachment(
        execution.evidence,
        {
            "file_public_id": str(file_object.public_id),
            "version_public_id": str(version.public_id),
            "original_name": version.original_name,
            "content_type": version.content_type,
            "sha256": version.actual_sha256 or version.expected_sha256,
            "note": note.strip(),
            "attached_at": timezone.now().isoformat(),
            "attached_by_public_id": str(actor_public_id),
        },
    )
    execution.version += 1
    execution.save(update_fields=["evidence", "version", "updated_at"])
    _record(
        company=execution.company,
        action="ATTACH_EVIDENCE",
        event_type="release.uat.evidence.attached",
        entity_type="UATExecution",
        entity_public_id=execution.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=execution.version,
        before=before,
        after={"scenario_code": execution.scenario.code, "attachment_file_public_id": str(file_object.public_id)},
    )
    return execution
