from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from modules.communication.models import ChannelPolicy
from modules.finance.models import FinancialPeriod
from modules.identity.models import AuthSession, Role
from modules.inventory.models import InventoryItem
from modules.pilotops.models import (
    AdoptionSnapshot,
    GoLivePlan,
    GoLiveSignoff,
    MasterDataReadiness,
    PilotChecklistItem,
    PilotProgram,
    ReadinessAssessment,
    TrainingCompletion,
    TrainingModule,
)
from modules.platform.actors import RequestActor
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.platform.models import AuditEvent
from modules.projects.models import Project
from modules.tenant.models import Company, Location, Membership
from modules.vendor.models import VendorProfile
from modules.workflow.models import WorkflowDefinition


def _audit(
    *,
    actor: RequestActor,
    company: Company,
    action: str,
    entity_type: str,
    entity_public_id: uuid.UUID,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason_code: str = "",
) -> None:
    append_audit(
        AuditRecord(
            action=action,
            entity_type=entity_type,
            entity_public_id=entity_public_id,
            actor_public_id=actor.user_public_id,
            company_public_id=company.public_id,
            request_id=actor.request_id,
            correlation_id=actor.request_id,
            ip_address=actor.ip_address,
            user_agent=actor.user_agent,
            before=before or {},
            after=after or {},
            reason_code=reason_code,
        )
    )


def _event(
    *,
    actor: RequestActor,
    company: Company,
    event_type: str,
    aggregate_type: str,
    aggregate_public_id: uuid.UUID,
    aggregate_version: int,
    payload: dict[str, Any],
) -> None:
    append_event(
        EventRecord(
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_public_id=aggregate_public_id,
            aggregate_version=aggregate_version,
            company_public_id=company.public_id,
            correlation_id=actor.request_id,
            payload=payload,
        )
    )


def _canonical_checksum(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def active_memberships(company: Company) -> QuerySet[Membership]:
    now = timezone.now()
    return (
        Membership.objects.filter(
            company=company,
            effective_from__lte=now,
            suspended_at__isnull=True,
            terminated_at__isnull=True,
            user__is_active=True,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now))
        .select_related("user")
    )


def current_program(company: Company) -> PilotProgram | None:
    return (
        PilotProgram.objects.filter(company=company)
        .exclude(status=PilotProgram.Status.COMPLETED)
        .select_related("owner_membership__user")
        .order_by("-created_at")
        .first()
    )


def readiness_metrics(program: PilotProgram) -> dict[str, Any]:
    checklist = program.checklist_items.all()
    required_checklist = checklist.filter(is_required=True)
    checklist_done = required_checklist.filter(
        status__in=[PilotChecklistItem.Status.COMPLETED, PilotChecklistItem.Status.WAIVED]
    ).count()
    checklist_total = required_checklist.count()

    master = program.master_data_domains.filter(is_required=True)
    master_ready = master.filter(status=MasterDataReadiness.Status.READY).count()
    master_total = master.count()

    modules = program.training_modules.filter(
        is_required=True,
        status=TrainingModule.Status.PUBLISHED,
    )
    membership_count = active_memberships(program.company).count()
    expected_training = modules.count() * membership_count
    completed_training = TrainingCompletion.objects.filter(
        company=program.company,
        module__program=program,
        module__in=modules,
        status__in=[TrainingCompletion.Status.COMPLETED, TrainingCompletion.Status.WAIVED],
    ).count()

    try:
        plan = program.go_live_plan
    except GoLivePlan.DoesNotExist:
        plan = None
    signoffs = plan.signoffs.filter(is_required=True) if plan else GoLiveSignoff.objects.none()
    signoff_done = signoffs.filter(
        status__in=[GoLiveSignoff.Status.APPROVED, GoLiveSignoff.Status.WAIVED]
    ).count()
    signoff_total = signoffs.count()

    def ratio(done: int, total: int) -> Decimal:
        return Decimal("1") if total == 0 else Decimal(done) / Decimal(total)

    score = (
        ratio(checklist_done, checklist_total) * Decimal("40")
        + ratio(master_ready, master_total) * Decimal("25")
        + ratio(completed_training, expected_training) * Decimal("20")
        + ratio(signoff_done, signoff_total) * Decimal("15")
    ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)

    blockers: list[dict[str, str]] = []
    for item in required_checklist.exclude(
        status__in=[PilotChecklistItem.Status.COMPLETED, PilotChecklistItem.Status.WAIVED]
    )[:100]:
        blockers.append({"type": "checklist", "code": item.code, "title": item.title})
    for item in master.exclude(status=MasterDataReadiness.Status.READY)[:100]:
        blockers.append(
            {"type": "master_data", "code": item.domain_code, "title": item.domain_name}
        )
    if completed_training < expected_training:
        blockers.append(
            {
                "type": "training",
                "code": "REQUIRED_TRAINING",
                "title": (
                    f"{expected_training - completed_training} required "
                    "training assignments remain"
                ),
            }
        )
    for item in signoffs.exclude(
        status__in=[GoLiveSignoff.Status.APPROVED, GoLiveSignoff.Status.WAIVED]
    )[:100]:
        blockers.append({"type": "signoff", "code": item.code, "title": item.title})

    warnings: list[dict[str, str]] = []
    overdue = checklist.filter(
        due_at__lt=timezone.now(),
    ).exclude(status__in=[PilotChecklistItem.Status.COMPLETED, PilotChecklistItem.Status.WAIVED])
    if overdue.exists():
        warnings.append(
            {
                "type": "overdue_checklist",
                "code": "OVERDUE_ITEMS",
                "title": f"{overdue.count()} checklist items are overdue",
            }
        )

    return {
        "score_percent": int(score),
        "ready": int(score) >= 85 and not blockers,
        "checklist": {"completed": checklist_done, "total": checklist_total},
        "master_data": {"ready": master_ready, "total": master_total},
        "training": {"completed": completed_training, "total": expected_training},
        "signoffs": {"approved": signoff_done, "total": signoff_total},
        "critical_blockers": blockers,
        "warnings": warnings,
    }


def pilot_summary(company: Company) -> dict[str, Any]:
    program = current_program(company)
    if program is None:
        return {
            "program": None,
            "score_percent": 0,
            "ready": False,
            "open_checklist": 0,
            "master_data_ready": 0,
            "master_data_total": 0,
            "training_completed": 0,
            "training_total": 0,
            "approved_signoffs": 0,
            "signoffs_total": 0,
            "latest_adoption": None,
        }
    metrics = readiness_metrics(program)
    latest_adoption = program.adoption_snapshots.order_by("-period_end").first()
    return {
        "program": program,
        "score_percent": metrics["score_percent"],
        "ready": metrics["ready"],
        "open_checklist": max(
            metrics["checklist"]["total"] - metrics["checklist"]["completed"], 0
        ),
        "master_data_ready": metrics["master_data"]["ready"],
        "master_data_total": metrics["master_data"]["total"],
        "training_completed": metrics["training"]["completed"],
        "training_total": metrics["training"]["total"],
        "approved_signoffs": metrics["signoffs"]["approved"],
        "signoffs_total": metrics["signoffs"]["total"],
        "latest_adoption": latest_adoption,
    }


@transaction.atomic
def transition_checklist_item(
    *,
    company: Company,
    actor: RequestActor,
    item_public_id: uuid.UUID,
    status: str,
    expected_version: int,
    evidence: dict[str, Any] | None = None,
    waiver_reason: str = "",
) -> PilotChecklistItem:
    item = (
        PilotChecklistItem.objects.select_for_update()
        .filter(company=company, public_id=item_public_id)
        .first()
    )
    if item is None:
        raise ValidationError("Pilot checklist item was not found")
    if item.version != expected_version:
        raise ValidationError("Checklist item version conflict")
    allowed = {
        PilotChecklistItem.Status.PENDING: {
            PilotChecklistItem.Status.IN_PROGRESS,
            PilotChecklistItem.Status.COMPLETED,
            PilotChecklistItem.Status.BLOCKED,
            PilotChecklistItem.Status.WAIVED,
        },
        PilotChecklistItem.Status.IN_PROGRESS: {
            PilotChecklistItem.Status.COMPLETED,
            PilotChecklistItem.Status.BLOCKED,
            PilotChecklistItem.Status.WAIVED,
        },
        PilotChecklistItem.Status.BLOCKED: {
            PilotChecklistItem.Status.IN_PROGRESS,
            PilotChecklistItem.Status.COMPLETED,
            PilotChecklistItem.Status.WAIVED,
        },
        PilotChecklistItem.Status.COMPLETED: {PilotChecklistItem.Status.IN_PROGRESS},
        PilotChecklistItem.Status.WAIVED: {PilotChecklistItem.Status.IN_PROGRESS},
    }
    if status not in allowed[item.status]:
        raise ValidationError("Checklist status transition is not allowed")
    before = {"status": item.status, "version": item.version}
    item.status = status
    item.evidence = evidence or {}
    item.waiver_reason = waiver_reason.strip()
    item.completed_by_public_id = (
        actor.user_public_id
        if status in [PilotChecklistItem.Status.COMPLETED, PilotChecklistItem.Status.WAIVED]
        else None
    )
    item.completed_at = (
        timezone.now()
        if status in [PilotChecklistItem.Status.COMPLETED, PilotChecklistItem.Status.WAIVED]
        else None
    )
    item.version += 1
    item.full_clean()
    item.save()
    _audit(
        actor=actor,
        company=company,
        action="pilotops.checklist.transitioned",
        entity_type="pilot_checklist_item",
        entity_public_id=item.public_id,
        before=before,
        after={"status": item.status, "version": item.version},
        reason_code=item.waiver_reason,
    )
    _event(
        actor=actor,
        company=company,
        event_type="pilotops.checklist.transitioned",
        aggregate_type="pilot_checklist_item",
        aggregate_public_id=item.public_id,
        aggregate_version=item.version,
        payload={"code": item.code, "status": item.status},
    )
    return item


_MASTER_COUNTERS: dict[str, Callable[[Company], int]] = {
    "company_profile": lambda company: int(
        bool(company.legal_name and company.locale and company.timezone and company.currency)
    ),
    "locations": lambda company: Location.objects.filter(company=company).count(),
    "users": lambda company: active_memberships(company).count(),
    "roles": lambda company: Role.objects.filter(
        company_public_id=company.public_id,
        retired_at__isnull=True,
    ).count(),
    "projects": lambda company: Project.objects.filter(company=company).count(),
    "vendors": lambda company: VendorProfile.objects.filter(company=company).count(),
    "inventory_items": lambda company: InventoryItem.objects.filter(company=company).count(),
    "finance_periods": lambda company: FinancialPeriod.objects.filter(company=company).count(),
    "communication_channels": lambda company: ChannelPolicy.objects.filter(company=company).count(),
    "workflows": lambda company: WorkflowDefinition.objects.filter(
        company=company
    ).count(),
}


@transaction.atomic
def validate_master_data(
    *, company: Company, actor: RequestActor, program_public_id: uuid.UUID
) -> list[MasterDataReadiness]:
    program = PilotProgram.objects.filter(company=company, public_id=program_public_id).first()
    if program is None:
        raise ValidationError("Pilot program was not found")
    now = timezone.now()
    results: list[MasterDataReadiness] = []
    for item in program.master_data_domains.select_for_update().all():
        counter = _MASTER_COUNTERS.get(item.domain_code)
        count = counter(company) if counter else 0
        item.current_records = count
        item.status = (
            MasterDataReadiness.Status.READY
            if count >= item.minimum_records
            else MasterDataReadiness.Status.IN_PROGRESS
        )
        item.validation_summary = {
            "minimum_records": item.minimum_records,
            "current_records": count,
            "validated_by": str(actor.user_public_id),
        }
        item.last_validated_at = now
        item.version += 1
        item.full_clean()
        item.save()
        results.append(item)
    _audit(
        actor=actor,
        company=company,
        action="pilotops.master_data.validated",
        entity_type="pilot_program",
        entity_public_id=program.public_id,
        after={
            "domains": len(results),
            "ready": sum(item.status == MasterDataReadiness.Status.READY for item in results),
        },
    )
    return results


@transaction.atomic
def update_training_completion(
    *,
    company: Company,
    actor: RequestActor,
    completion_public_id: uuid.UUID,
    status: str,
    expected_version: int,
    score_percent: Decimal | None = None,
    evidence: dict[str, Any] | None = None,
) -> TrainingCompletion:
    item = (
        TrainingCompletion.objects.select_for_update()
        .filter(company=company, public_id=completion_public_id)
        .first()
    )
    if item is None:
        raise ValidationError("Training assignment was not found")
    if item.version != expected_version:
        raise ValidationError("Training assignment version conflict")
    if item.membership.user.public_id != actor.user_public_id:
        raise ValidationError("Training can only be completed by the assigned user")
    item.status = status
    item.score_percent = score_percent
    item.evidence = evidence or {}
    item.completed_at = (
        timezone.now()
        if status in [TrainingCompletion.Status.COMPLETED, TrainingCompletion.Status.WAIVED]
        else None
    )
    item.version += 1
    item.full_clean()
    item.save()
    _audit(
        actor=actor,
        company=company,
        action="pilotops.training.updated",
        entity_type="training_completion",
        entity_public_id=item.public_id,
        after={"status": item.status, "score_percent": str(item.score_percent)},
    )
    return item


@transaction.atomic
def assess_readiness(
    *, company: Company, actor: RequestActor, program_public_id: uuid.UUID
) -> ReadinessAssessment:
    program = PilotProgram.objects.filter(company=company, public_id=program_public_id).first()
    if program is None:
        raise ValidationError("Pilot program was not found")
    metrics = readiness_metrics(program)
    payload = {
        "program_public_id": str(program.public_id),
        "assessed_at": timezone.now().isoformat(),
        "score_percent": metrics["score_percent"],
        "critical_blockers": metrics["critical_blockers"],
        "warnings": metrics["warnings"],
        "metrics": {
            key: value
            for key, value in metrics.items()
            if key not in {"critical_blockers", "warnings", "score_percent", "ready"}
        },
    }
    assessment = ReadinessAssessment.objects.create(
        company=company,
        program=program,
        assessed_at=timezone.now(),
        assessed_by_public_id=actor.user_public_id,
        score_percent=metrics["score_percent"],
        critical_blockers=metrics["critical_blockers"],
        warnings=metrics["warnings"],
        metrics=payload["metrics"],
        checksum_sha256=_canonical_checksum(payload),
    )
    if metrics["ready"] and program.status in {
        PilotProgram.Status.DRAFT,
        PilotProgram.Status.PREPARING,
    }:
        program.status = PilotProgram.Status.READY
        program.version += 1
        program.save(update_fields=["status", "version", "updated_at"])
    _audit(
        actor=actor,
        company=company,
        action="pilotops.readiness.assessed",
        entity_type="readiness_assessment",
        entity_public_id=assessment.public_id,
        after={"score_percent": assessment.score_percent, "ready": metrics["ready"]},
    )
    return assessment


@transaction.atomic
def signoff_go_live(
    *,
    company: Company,
    actor: RequestActor,
    signoff_public_id: uuid.UUID,
    status: str,
    expected_version: int,
    evidence: dict[str, Any] | None = None,
    reason: str = "",
) -> GoLiveSignoff:
    item = (
        GoLiveSignoff.objects.select_for_update()
        .select_related("plan__program", "signer_membership")
        .filter(company=company, public_id=signoff_public_id)
        .first()
    )
    if item is None:
        raise ValidationError("Go-live sign-off was not found")
    if item.version != expected_version:
        raise ValidationError("Go-live sign-off version conflict")
    if item.signer_membership_id and item.signer_membership.user.public_id != actor.user_public_id:
        raise ValidationError("This sign-off is assigned to another user")
    item.status = status
    item.evidence = evidence or {}
    item.reason = reason.strip()
    item.signed_by_public_id = actor.user_public_id
    item.signed_at = timezone.now()
    item.version += 1
    item.full_clean()
    item.save()
    _audit(
        actor=actor,
        company=company,
        action="pilotops.golive.signoff",
        entity_type="go_live_signoff",
        entity_public_id=item.public_id,
        after={"code": item.code, "status": item.status, "version": item.version},
        reason_code=item.reason,
    )
    return item


@transaction.atomic
def transition_go_live(
    *,
    company: Company,
    actor: RequestActor,
    plan_public_id: uuid.UUID,
    target_status: str,
    expected_version: int,
    reason: str = "",
) -> GoLivePlan:
    plan = (
        GoLivePlan.objects.select_for_update()
        .select_related("program__owner_membership__user")
        .filter(company=company, public_id=plan_public_id)
        .first()
    )
    if plan is None:
        raise ValidationError("Go-live plan was not found")
    if plan.version != expected_version:
        raise ValidationError("Go-live plan version conflict")
    allowed = {
        GoLivePlan.Status.DRAFT: {GoLivePlan.Status.IN_REVIEW, GoLivePlan.Status.CANCELLED},
        GoLivePlan.Status.IN_REVIEW: {GoLivePlan.Status.APPROVED, GoLivePlan.Status.DRAFT},
        GoLivePlan.Status.APPROVED: {GoLivePlan.Status.IN_PROGRESS, GoLivePlan.Status.CANCELLED},
        GoLivePlan.Status.IN_PROGRESS: {GoLivePlan.Status.LIVE, GoLivePlan.Status.ROLLED_BACK},
        GoLivePlan.Status.LIVE: {GoLivePlan.Status.ROLLED_BACK},
        GoLivePlan.Status.ROLLED_BACK: set(),
        GoLivePlan.Status.CANCELLED: set(),
    }
    if target_status not in allowed[plan.status]:
        raise ValidationError("Go-live status transition is not allowed")
    if target_status == GoLivePlan.Status.APPROVED:
        if plan.program.owner_membership.user.public_id == actor.user_public_id:
            raise ValidationError("Pilot owner cannot independently approve go-live")
        metrics = readiness_metrics(plan.program)
        if not metrics["ready"]:
            raise ValidationError("Pilot readiness must pass before go-live approval")
        plan.approved_by_public_id = actor.user_public_id
        plan.approved_at = timezone.now()
    if target_status == GoLivePlan.Status.IN_PROGRESS:
        plan.started_at = timezone.now()
    if target_status == GoLivePlan.Status.LIVE:
        plan.completed_at = timezone.now()
        plan.program.status = PilotProgram.Status.LIVE
        plan.program.actual_go_live_at = plan.completed_at
        plan.program.version += 1
        plan.program.save()
    if target_status == GoLivePlan.Status.ROLLED_BACK:
        plan.program.status = PilotProgram.Status.PAUSED
        plan.program.version += 1
        plan.program.save()
    before = {"status": plan.status, "version": plan.version}
    plan.status = target_status
    plan.version += 1
    plan.full_clean()
    plan.save()
    _audit(
        actor=actor,
        company=company,
        action="pilotops.golive.transitioned",
        entity_type="go_live_plan",
        entity_public_id=plan.public_id,
        before=before,
        after={"status": plan.status, "version": plan.version},
        reason_code=reason.strip(),
    )
    _event(
        actor=actor,
        company=company,
        event_type="pilotops.golive.transitioned",
        aggregate_type="go_live_plan",
        aggregate_public_id=plan.public_id,
        aggregate_version=plan.version,
        payload={"status": plan.status, "program": plan.program.cohort_code},
    )
    return plan


@transaction.atomic
def collect_adoption_snapshot(
    *,
    company: Company,
    actor: RequestActor,
    program_public_id: uuid.UUID,
    period_end: date | None = None,
) -> AdoptionSnapshot:
    program = PilotProgram.objects.filter(company=company, public_id=program_public_id).first()
    if program is None:
        raise ValidationError("Pilot program was not found")
    end = period_end or timezone.localdate()
    start = end - timedelta(days=29)
    memberships = active_memberships(company)
    user_ids = list(memberships.values_list("user_id", flat=True))
    total_users = len(user_ids)
    active_users = (
        AuthSession.objects.filter(
            user_id__in=user_ids,
            created_at__date__gte=start,
            created_at__date__lte=end,
        )
        .values("user_id")
        .distinct()
        .count()
    )
    training_total = TrainingCompletion.objects.filter(
        company=company,
        module__program=program,
    ).count()
    training_completed = TrainingCompletion.objects.filter(
        company=company,
        module__program=program,
        status__in=[TrainingCompletion.Status.COMPLETED, TrainingCompletion.Status.WAIVED],
    ).count()
    training_percent = (
        Decimal("100")
        if training_total == 0
        else (Decimal(training_completed) * Decimal("100") / Decimal(training_total)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    )
    checklist_total = program.checklist_items.count()
    checklist_completed = program.checklist_items.filter(
        status__in=[PilotChecklistItem.Status.COMPLETED, PilotChecklistItem.Status.WAIVED]
    ).count()
    key_activity_count = AuditEvent.objects.filter(
        company_public_id=company.public_id,
        occurred_at__date__gte=start,
        occurred_at__date__lte=end,
    ).count()
    payload = {
        "period_start": start,
        "period_end": end,
        "active_users": active_users,
        "total_users": total_users,
        "training_completion_percent": str(training_percent),
        "completed_checklist_items": checklist_completed,
        "total_checklist_items": checklist_total,
        "key_activity_count": key_activity_count,
    }
    item, created = AdoptionSnapshot.objects.get_or_create(
        company=company,
        program=program,
        period_end=end,
        defaults={
            "period_start": start,
            "active_users": active_users,
            "total_users": total_users,
            "training_completion_percent": training_percent,
            "completed_checklist_items": checklist_completed,
            "total_checklist_items": checklist_total,
            "key_activity_count": key_activity_count,
            "metrics": payload,
            "generated_at": timezone.now(),
            "checksum_sha256": _canonical_checksum(payload),
        },
    )
    if not created:
        return item
    _audit(
        actor=actor,
        company=company,
        action="pilotops.adoption.collected",
        entity_type="adoption_snapshot",
        entity_public_id=item.public_id,
        after=payload,
    )
    return item
