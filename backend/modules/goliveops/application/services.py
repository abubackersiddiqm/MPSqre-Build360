from __future__ import annotations

import uuid
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from modules.goliveops.models import (
    CutoverPlan,
    CutoverTask,
    GoLiveGate,
    GoLivePolicyVersion,
    GoLiveWave,
    HypercareIssue,
    MigrationBatch,
    MigrationIssue,
    TrainingCohort,
    TrainingEnrollment,
)
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.tenant.models import Company

DEFAULT_GATES = [
    ("MASTER_DATA_VALIDATED", "Master data migration validated", "DATA"),
    ("USER_ACCESS_READY", "User identities, roles and access are ready", "ACCESS"),
    ("TRAINING_COMPLETE", "Required user training is complete", "ENABLEMENT"),
    ("CUTOVER_PLAN_APPROVED", "Cutover plan and rollback path are approved", "CUTOVER"),
    ("BACKUP_RESTORE_READY", "Backup and restore evidence is current", "RECOVERY"),
    ("SUPPORT_ROSTER_READY", "Hypercare support roster is staffed", "SUPPORT"),
    ("COMMUNICATIONS_READY", "Stakeholder communications are ready", "COMMUNICATIONS"),
    ("SECURITY_SIGNOFF", "Security and tenant isolation sign-off is complete", "SECURITY"),
    ("PERFORMANCE_SIGNOFF", "Performance and stability sign-off is complete", "PERFORMANCE"),
    ("GO_LIVE_APPROVAL", "Independent go-live approval is recorded", "GOVERNANCE"),
]


def _record(
    *,
    company: Company,
    action: str,
    event_type: str,
    entity_type: str,
    entity_public_id: uuid.UUID,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    version: int,
    after: dict[str, Any],
    before: dict[str, Any] | None = None,
) -> None:
    append_audit(
        AuditRecord(
            action=action,
            entity_type=entity_type,
            entity_public_id=entity_public_id,
            actor_public_id=actor_public_id,
            company_public_id=company.public_id,
            request_id=correlation_id,
            correlation_id=correlation_id,
            before=before or {},
            after=after,
        )
    )
    append_event(
        EventRecord(
            event_type=event_type,
            aggregate_type=entity_type,
            aggregate_public_id=entity_public_id,
            aggregate_version=version,
            company_public_id=company.public_id,
            correlation_id=correlation_id,
            payload=after,
        )
    )


def seed_defaults(company: Company) -> dict[str, int]:
    policy, policy_created = GoLivePolicyVersion.objects.get_or_create(
        company=company,
        version=1,
        defaults={
            "status_code": "DRAFT",
            "configuration": {"phase": 35, "release": "v1-go-live-enablement"},
        },
    )
    gate_count = 0
    for code, name, category in DEFAULT_GATES:
        _, created = GoLiveGate.objects.get_or_create(
            company=company,
            code=code,
            defaults={
                "name": name,
                "category_code": category,
                "description": "Required Build360 production go-live control.",
                "is_required": True,
            },
        )
        gate_count += int(created)
    return {"policy": int(policy_created), "gates": gate_count, "policy_version": policy.version}


@transaction.atomic
def create_migration_batch(*, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> MigrationBatch:
    batch = MigrationBatch(company=company, created_by_public_id=actor_public_id, **data)
    batch.full_clean()
    batch.save()
    _record(
        company=company,
        action="CREATE",
        event_type="golive.migration_batch.created",
        entity_type="MigrationBatch",
        entity_public_id=batch.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=batch.version,
        after={"code": batch.code, "entity": batch.entity_code, "status": batch.status_code, "dry_run": batch.dry_run},
    )
    return batch


@transaction.atomic
def transition_migration_batch(
    *,
    batch: MigrationBatch,
    status_code: str,
    expected_version: int,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    **updates: Any,
) -> MigrationBatch:
    batch = MigrationBatch.objects.select_for_update().get(pk=batch.pk)
    if batch.version != expected_version:
        raise ValidationError("Migration batch changed. Refresh and retry.")
    allowed = {
        "DRAFT": {"VALIDATING", "CANCELLED"},
        "VALIDATING": {"VALIDATED", "FAILED", "CANCELLED"},
        "VALIDATED": {"APPROVED", "VALIDATING", "CANCELLED"},
        "FAILED": {"VALIDATING", "CANCELLED"},
        "APPROVED": {"IMPORTED", "CANCELLED"},
        "IMPORTED": set(),
        "CANCELLED": set(),
    }
    if status_code not in allowed.get(batch.status_code, set()):
        raise ValidationError(f"Invalid migration transition from {batch.status_code} to {status_code}.")
    for field in ("total_rows", "valid_rows", "invalid_rows", "warning_rows", "notes"):
        if field in updates:
            setattr(batch, field, updates[field])
    if batch.valid_rows > batch.total_rows or batch.invalid_rows > batch.total_rows or batch.warning_rows > batch.total_rows:
        raise ValidationError("Migration row counters cannot exceed total rows.")
    if status_code in {"VALIDATED", "APPROVED", "IMPORTED"} and batch.invalid_rows > 0:
        raise ValidationError("A migration batch with invalid rows cannot be validated, approved or imported.")
    if status_code == "APPROVED":
        if batch.created_by_public_id == actor_public_id:
            raise ValidationError("The migration creator cannot approve the same batch.")
        batch.approved_by_public_id = actor_public_id
    now = timezone.now()
    if status_code == "VALIDATING" and batch.started_at is None:
        batch.started_at = now
    if status_code in {"VALIDATED", "FAILED", "IMPORTED", "CANCELLED"}:
        batch.completed_at = now
    before = {"status": batch.status_code, "version": batch.version}
    batch.status_code = status_code
    batch.version += 1
    batch.full_clean()
    batch.save()
    _record(
        company=batch.company,
        action="TRANSITION",
        event_type="golive.migration_batch.transitioned",
        entity_type="MigrationBatch",
        entity_public_id=batch.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=batch.version,
        before=before,
        after={"code": batch.code, "status": batch.status_code, "valid_rows": batch.valid_rows, "invalid_rows": batch.invalid_rows},
    )
    return batch


@transaction.atomic
def create_migration_issue(
    *, company: Company, batch: MigrationBatch, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any
) -> MigrationIssue:
    if batch.company_id != company.id:
        raise ValidationError("Migration issue cannot cross companies")
    issue = MigrationIssue(company=company, batch=batch, **data)
    issue.full_clean()
    issue.save()
    _record(
        company=company,
        action="CREATE",
        event_type="golive.migration_issue.created",
        entity_type="MigrationIssue",
        entity_public_id=issue.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=issue.version,
        after={"batch": batch.code, "row": issue.row_number, "severity": issue.severity_code, "issue_code": issue.issue_code},
    )
    return issue


@transaction.atomic
def resolve_migration_issue(
    *, issue: MigrationIssue, expected_version: int, resolution_notes: str, actor_public_id: uuid.UUID, correlation_id: uuid.UUID
) -> MigrationIssue:
    issue = MigrationIssue.objects.select_for_update().get(pk=issue.pk)
    if issue.version != expected_version:
        raise ValidationError("Migration issue changed. Refresh and retry.")
    if not resolution_notes.strip():
        raise ValidationError("Resolution notes are required.")
    before = {"resolved": issue.resolved, "version": issue.version}
    issue.resolved = True
    issue.resolution_notes = resolution_notes
    issue.resolved_at = timezone.now()
    issue.resolved_by_public_id = actor_public_id
    issue.version += 1
    issue.full_clean()
    issue.save()
    _record(
        company=issue.company,
        action="RESOLVE",
        event_type="golive.migration_issue.resolved",
        entity_type="MigrationIssue",
        entity_public_id=issue.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=issue.version,
        before=before,
        after={"resolved": True, "issue_code": issue.issue_code},
    )
    return issue


@transaction.atomic
def create_training_cohort(*, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> TrainingCohort:
    cohort = TrainingCohort(company=company, created_by_public_id=actor_public_id, **data)
    cohort.full_clean()
    cohort.save()
    _record(
        company=company,
        action="CREATE",
        event_type="golive.training_cohort.created",
        entity_type="TrainingCohort",
        entity_public_id=cohort.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=cohort.version,
        after={"code": cohort.code, "title": cohort.title, "audience": cohort.audience_code},
    )
    return cohort


@transaction.atomic
def create_training_enrollment(
    *, company: Company, cohort: TrainingCohort, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any
) -> TrainingEnrollment:
    if cohort.company_id != company.id:
        raise ValidationError("Training enrollment cannot cross companies")
    enrollment = TrainingEnrollment(company=company, cohort=cohort, **data)
    enrollment.full_clean()
    enrollment.save()
    _record(
        company=company,
        action="CREATE",
        event_type="golive.training_enrollment.created",
        entity_type="TrainingEnrollment",
        entity_public_id=enrollment.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=enrollment.version,
        after={"cohort": cohort.code, "participant": enrollment.participant_name, "status": enrollment.status_code},
    )
    return enrollment


@transaction.atomic
def transition_training_enrollment(
    *, enrollment: TrainingEnrollment, status_code: str, expected_version: int, actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID, score_percent=None, evidence=None
) -> TrainingEnrollment:
    enrollment = TrainingEnrollment.objects.select_for_update().get(pk=enrollment.pk)
    if enrollment.version != expected_version:
        raise ValidationError("Training enrollment changed. Refresh and retry.")
    if status_code not in {"NOT_STARTED", "IN_PROGRESS", "COMPLETED", "FAILED", "WAIVED"}:
        raise ValidationError("Unsupported training status.")
    if status_code == "COMPLETED" and score_percent is None:
        raise ValidationError("Completed training requires a score.")
    before = {"status": enrollment.status_code, "version": enrollment.version}
    enrollment.status_code = status_code
    enrollment.score_percent = score_percent
    enrollment.evidence = evidence or {}
    enrollment.completed_at = timezone.now() if status_code in {"COMPLETED", "FAILED", "WAIVED"} else None
    enrollment.version += 1
    enrollment.full_clean()
    enrollment.save()
    _record(
        company=enrollment.company,
        action="TRANSITION",
        event_type="golive.training_enrollment.transitioned",
        entity_type="TrainingEnrollment",
        entity_public_id=enrollment.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=enrollment.version,
        before=before,
        after={"status": enrollment.status_code, "participant": enrollment.participant_name},
    )
    return enrollment


@transaction.atomic
def create_cutover_plan(*, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> CutoverPlan:
    plan = CutoverPlan(company=company, created_by_public_id=actor_public_id, **data)
    plan.full_clean()
    plan.save()
    _record(
        company=company,
        action="CREATE",
        event_type="golive.cutover_plan.created",
        entity_type="CutoverPlan",
        entity_public_id=plan.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=plan.version,
        after={"code": plan.code, "environment": plan.environment_code, "status": plan.status_code},
    )
    return plan


@transaction.atomic
def create_cutover_task(
    *, company: Company, plan: CutoverPlan, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any
) -> CutoverTask:
    if plan.company_id != company.id:
        raise ValidationError("Cutover task cannot cross companies")
    task = CutoverTask(company=company, plan=plan, **data)
    task.full_clean()
    task.save()
    _record(
        company=company,
        action="CREATE",
        event_type="golive.cutover_task.created",
        entity_type="CutoverTask",
        entity_public_id=task.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=task.version,
        after={"plan": plan.code, "code": task.code, "critical": task.critical, "status": task.status_code},
    )
    return task


@transaction.atomic
def transition_cutover_task(
    *, task: CutoverTask, status_code: str, expected_version: int, actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID, notes: str = "", evidence=None
) -> CutoverTask:
    task = CutoverTask.objects.select_for_update().get(pk=task.pk)
    if task.version != expected_version:
        raise ValidationError("Cutover task changed. Refresh and retry.")
    if status_code not in {"PENDING", "IN_PROGRESS", "BLOCKED", "DONE", "SKIPPED"}:
        raise ValidationError("Unsupported cutover task status.")
    if status_code == "SKIPPED" and task.critical:
        raise ValidationError("Critical cutover tasks cannot be skipped.")
    before = {"status": task.status_code, "version": task.version}
    task.status_code = status_code
    task.notes = notes
    task.evidence = evidence or {}
    task.completed_at = timezone.now() if status_code in {"DONE", "SKIPPED"} else None
    task.version += 1
    task.full_clean()
    task.save()
    _record(
        company=task.company,
        action="TRANSITION",
        event_type="golive.cutover_task.transitioned",
        entity_type="CutoverTask",
        entity_public_id=task.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=task.version,
        before=before,
        after={"status": task.status_code, "code": task.code},
    )
    return task


@transaction.atomic
def create_go_live_wave(
    *, company: Company, plan: CutoverPlan | None, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any
) -> GoLiveWave:
    if plan and plan.company_id != company.id:
        raise ValidationError("Go-live wave cannot cross companies")
    wave = GoLiveWave(company=company, plan=plan, created_by_public_id=actor_public_id, **data)
    wave.full_clean()
    wave.save()
    _record(
        company=company,
        action="CREATE",
        event_type="golive.wave.created",
        entity_type="GoLiveWave",
        entity_public_id=wave.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=wave.version,
        after={"code": wave.code, "status": wave.status_code},
    )
    return wave


@transaction.atomic
def transition_go_live_wave(
    *, wave: GoLiveWave, status_code: str, expected_version: int, actor_public_id: uuid.UUID, correlation_id: uuid.UUID
) -> GoLiveWave:
    wave = GoLiveWave.objects.select_for_update(of=("self",)).select_related("plan").get(pk=wave.pk)
    if wave.version != expected_version:
        raise ValidationError("Go-live wave changed. Refresh and retry.")
    allowed = {
        "DRAFT": {"READY"},
        "READY": {"APPROVED", "DRAFT"},
        "APPROVED": {"LIVE", "ROLLED_BACK"},
        "LIVE": {"HYPERCARE", "ROLLED_BACK"},
        "HYPERCARE": {"CLOSED", "ROLLED_BACK"},
        "CLOSED": set(),
        "ROLLED_BACK": set(),
    }
    if status_code not in allowed.get(wave.status_code, set()):
        raise ValidationError(f"Invalid go-live transition from {wave.status_code} to {status_code}.")
    if status_code == "APPROVED":
        if wave.created_by_public_id == actor_public_id:
            raise ValidationError("The wave creator cannot approve the same go-live wave.")
        wave.approved_by_public_id = actor_public_id
        failed_gates = GoLiveGate.objects.filter(company=wave.company, is_required=True).exclude(status_code="PASSED").exists()
        if failed_gates:
            raise ValidationError("All required go-live gates must pass before wave approval.")
    if status_code == "LIVE" and wave.plan_id:
        open_critical = wave.plan.tasks.filter(critical=True).exclude(status_code="DONE").exists()
        if open_critical:
            raise ValidationError("All critical cutover tasks must be complete before go-live activation.")
    before = {"status": wave.status_code, "version": wave.version}
    now = timezone.now()
    wave.status_code = status_code
    if status_code == "LIVE":
        wave.activated_at = now
        if wave.plan_id:
            wave.plan.actual_go_live_at = now
            wave.plan.status_code = "EXECUTING"
            wave.plan.version += 1
            wave.plan.save(update_fields=["actual_go_live_at", "status_code", "version", "updated_at"])
    if status_code in {"CLOSED", "ROLLED_BACK"}:
        wave.closed_at = now
    wave.version += 1
    wave.full_clean()
    wave.save()
    _record(
        company=wave.company,
        action="TRANSITION",
        event_type="golive.wave.transitioned",
        entity_type="GoLiveWave",
        entity_public_id=wave.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=wave.version,
        before=before,
        after={"status": wave.status_code, "code": wave.code},
    )
    return wave


@transaction.atomic
def create_hypercare_issue(
    *, company: Company, wave: GoLiveWave | None, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any
) -> HypercareIssue:
    if wave and wave.company_id != company.id:
        raise ValidationError("Hypercare issue cannot cross companies")
    issue = HypercareIssue(company=company, wave=wave, reported_by_public_id=actor_public_id, **data)
    issue.full_clean()
    issue.save()
    _record(
        company=company,
        action="CREATE",
        event_type="golive.hypercare_issue.created",
        entity_type="HypercareIssue",
        entity_public_id=issue.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=issue.version,
        after={"code": issue.code, "severity": issue.severity_code, "status": issue.status_code},
    )
    return issue


@transaction.atomic
def transition_hypercare_issue(
    *, issue: HypercareIssue, status_code: str, expected_version: int, actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID, resolution_summary: str = ""
) -> HypercareIssue:
    issue = HypercareIssue.objects.select_for_update().get(pk=issue.pk)
    if issue.version != expected_version:
        raise ValidationError("Hypercare issue changed. Refresh and retry.")
    allowed = {
        "OPEN": {"ACKNOWLEDGED", "MITIGATING", "RESOLVED"},
        "ACKNOWLEDGED": {"MITIGATING", "RESOLVED"},
        "MITIGATING": {"RESOLVED", "OPEN"},
        "RESOLVED": {"CLOSED", "OPEN"},
        "CLOSED": {"OPEN"},
    }
    if status_code not in allowed.get(issue.status_code, set()):
        raise ValidationError(f"Invalid hypercare transition from {issue.status_code} to {status_code}.")
    if status_code in {"RESOLVED", "CLOSED"} and not (resolution_summary or issue.resolution_summary).strip():
        raise ValidationError("Resolved hypercare issues require a resolution summary.")
    before = {"status": issue.status_code, "version": issue.version}
    issue.status_code = status_code
    if resolution_summary:
        issue.resolution_summary = resolution_summary
    issue.resolved_at = timezone.now() if status_code in {"RESOLVED", "CLOSED"} else None
    issue.version += 1
    issue.full_clean()
    issue.save()
    _record(
        company=issue.company,
        action="TRANSITION",
        event_type="golive.hypercare_issue.transitioned",
        entity_type="HypercareIssue",
        entity_public_id=issue.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=issue.version,
        before=before,
        after={"status": issue.status_code, "code": issue.code},
    )
    return issue


@transaction.atomic
def decide_gate(
    *, gate: GoLiveGate, status_code: str, notes: str, evidence: dict[str, Any], expected_version: int,
    actor_public_id: uuid.UUID, correlation_id: uuid.UUID
) -> GoLiveGate:
    gate = GoLiveGate.objects.select_for_update().get(pk=gate.pk)
    if gate.version != expected_version:
        raise ValidationError("Go-live gate changed. Refresh and retry.")
    if status_code not in {"PENDING", "PASSED", "FAILED", "WAIVED"}:
        raise ValidationError("Unsupported gate status.")
    if status_code == "WAIVED" and not notes.strip():
        raise ValidationError("Waived controls require a decision note.")
    before = {"status": gate.status_code, "version": gate.version}
    gate.status_code = status_code
    gate.notes = notes
    gate.evidence = evidence
    gate.decided_at = timezone.now()
    gate.decided_by_public_id = actor_public_id
    gate.version += 1
    gate.full_clean()
    gate.save()
    _record(
        company=gate.company,
        action="DECIDE",
        event_type="golive.gate.decided",
        entity_type="GoLiveGate",
        entity_public_id=gate.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=gate.version,
        before=before,
        after={"status": gate.status_code, "code": gate.code},
    )
    return gate
