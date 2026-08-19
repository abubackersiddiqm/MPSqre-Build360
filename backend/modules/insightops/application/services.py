from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from modules.insightops.models import (
    BenefitMeasurement,
    BenefitPlan,
    BoardReport,
    ExecutiveAction,
    InsightPolicyVersion,
    KPIDefinition,
    KPIObservation,
    PortfolioSnapshot,
    StrategicObjective,
)
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.tenant.models import Company

DEFAULT_KPIS = [
    ("ON_TIME_MILESTONES", "On-time milestones", "PERCENT", "HIGHER_BETTER", Decimal("90.0000"), Decimal("80.0000")),
    ("COST_VARIANCE", "Cost variance", "PERCENT", "LOWER_BETTER", Decimal("5.0000"), Decimal("10.0000")),
    ("SAFETY_INCIDENT_RATE", "Safety incident rate", "RATE", "LOWER_BETTER", Decimal("0.0000"), Decimal("1.0000")),
    ("QUALITY_FIRST_PASS", "Quality first-pass acceptance", "PERCENT", "HIGHER_BETTER", Decimal("95.0000"), Decimal("85.0000")),
    ("CUSTOMER_SATISFACTION", "Customer satisfaction", "SCORE", "HIGHER_BETTER", Decimal("4.5000"), Decimal("4.0000")),
]


def _record(
    *, company: Company, action: str, event_type: str, entity_type: str,
    entity_public_id: uuid.UUID, actor_public_id: uuid.UUID, correlation_id: uuid.UUID,
    version: int, after: dict[str, Any], before: dict[str, Any] | None = None,
) -> None:
    append_audit(AuditRecord(
        action=action, entity_type=entity_type, entity_public_id=entity_public_id,
        actor_public_id=actor_public_id, company_public_id=company.public_id,
        request_id=correlation_id, correlation_id=correlation_id,
        before=before or {}, after=after,
    ))
    append_event(EventRecord(
        event_type=event_type, aggregate_type=entity_type, aggregate_public_id=entity_public_id,
        aggregate_version=version, company_public_id=company.public_id,
        correlation_id=correlation_id, payload=after,
    ))


def seed_defaults(company: Company) -> dict[str, int]:
    _, policy_created = InsightPolicyVersion.objects.get_or_create(
        company=company, version=1,
        defaults={"status_code": "DRAFT", "configuration": {"phase": 37, "release": "executive-portfolio-intelligence"}},
    )
    created = 0
    for code, name, unit, direction, target, warning in DEFAULT_KPIS:
        _, was_created = KPIDefinition.objects.get_or_create(
            company=company, code=code,
            defaults={
                "name": name, "unit_code": unit, "direction_code": direction,
                "target_value": target, "warning_value": warning, "frequency_code": "MONTHLY",
                "aggregation_code": "LATEST", "active": True,
            },
        )
        created += int(was_created)
    return {"policy": int(policy_created), "kpis": created}


def _create(model, *, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, event: str, **data: Any):
    item = model(company=company, **data)
    item.full_clean()
    item.save()
    version = getattr(item, "version", 1)
    code = getattr(item, "code", str(item.public_id))
    _record(
        company=company, action="CREATE", event_type=event, entity_type=model.__name__,
        entity_public_id=item.public_id, actor_public_id=actor_public_id, correlation_id=correlation_id,
        version=version, after={"code": code, "status": getattr(item, "status_code", "RECORDED")},
    )
    return item


@transaction.atomic
def create_objective(*, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> StrategicObjective:
    return _create(StrategicObjective, company=company, actor_public_id=actor_public_id, correlation_id=correlation_id, event="insight.objective.created", **data)


@transaction.atomic
def create_kpi(*, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> KPIDefinition:
    return _create(KPIDefinition, company=company, actor_public_id=actor_public_id, correlation_id=correlation_id, event="insight.kpi.created", **data)


@transaction.atomic
def record_observation(*, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> KPIObservation:
    data.setdefault("captured_by_public_id", actor_public_id)
    data.setdefault("captured_at", timezone.now())
    return _create(KPIObservation, company=company, actor_public_id=actor_public_id, correlation_id=correlation_id, event="insight.kpi.observed", **data)


@transaction.atomic
def create_snapshot(*, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> PortfolioSnapshot:
    data.setdefault("created_by_public_id", actor_public_id)
    data.setdefault("currency", company.currency)
    return _create(PortfolioSnapshot, company=company, actor_public_id=actor_public_id, correlation_id=correlation_id, event="insight.portfolio.created", **data)


@transaction.atomic
def transition_snapshot(*, snapshot: PortfolioSnapshot, status_code: str, expected_version: int, actor_public_id: uuid.UUID, correlation_id: uuid.UUID) -> PortfolioSnapshot:
    snapshot = PortfolioSnapshot.objects.select_for_update().get(pk=snapshot.pk)
    if snapshot.version != expected_version:
        raise ValidationError("Portfolio snapshot changed. Refresh and retry.")
    allowed = {"DRAFT": {"IN_REVIEW", "CANCELLED"}, "IN_REVIEW": {"APPROVED", "DRAFT", "CANCELLED"}, "APPROVED": {"PUBLISHED", "IN_REVIEW"}, "PUBLISHED": set(), "CANCELLED": set()}
    if status_code not in allowed.get(snapshot.status_code, set()):
        raise ValidationError(f"Invalid portfolio transition from {snapshot.status_code} to {status_code}.")
    if status_code == "APPROVED" and snapshot.created_by_public_id == actor_public_id:
        raise ValidationError("The snapshot creator cannot approve the same portfolio snapshot.")
    before = {"status": snapshot.status_code, "version": snapshot.version}
    if status_code == "APPROVED":
        snapshot.approved_by_public_id = actor_public_id
    if status_code == "PUBLISHED":
        if snapshot.approved_by_public_id is None:
            raise ValidationError("Portfolio snapshot must be independently approved before publication.")
        snapshot.published_at = timezone.now()
    snapshot.status_code = status_code
    snapshot.version += 1
    snapshot.full_clean()
    snapshot.save()
    _record(company=snapshot.company, action="TRANSITION", event_type="insight.portfolio.transitioned", entity_type="PortfolioSnapshot", entity_public_id=snapshot.public_id, actor_public_id=actor_public_id, correlation_id=correlation_id, version=snapshot.version, before=before, after={"code": snapshot.code, "status": status_code})
    return snapshot


@transaction.atomic
def create_benefit(*, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> BenefitPlan:
    data.setdefault("currency", company.currency)
    return _create(BenefitPlan, company=company, actor_public_id=actor_public_id, correlation_id=correlation_id, event="insight.benefit.created", **data)


@transaction.atomic
def record_benefit_measurement(*, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> BenefitMeasurement:
    data.setdefault("captured_by_public_id", actor_public_id)
    return _create(BenefitMeasurement, company=company, actor_public_id=actor_public_id, correlation_id=correlation_id, event="insight.benefit.measured", **data)


@transaction.atomic
def create_action(*, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> ExecutiveAction:
    return _create(ExecutiveAction, company=company, actor_public_id=actor_public_id, correlation_id=correlation_id, event="insight.action.created", **data)


@transaction.atomic
def transition_action(*, action: ExecutiveAction, status_code: str, expected_version: int, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, resolution_summary: str = "") -> ExecutiveAction:
    action = ExecutiveAction.objects.select_for_update().get(pk=action.pk)
    if action.version != expected_version:
        raise ValidationError("Executive action changed. Refresh and retry.")
    allowed = {"OPEN": {"IN_PROGRESS", "BLOCKED", "CANCELLED"}, "IN_PROGRESS": {"BLOCKED", "COMPLETED", "CANCELLED"}, "BLOCKED": {"IN_PROGRESS", "COMPLETED", "CANCELLED"}, "COMPLETED": {"IN_PROGRESS"}, "CANCELLED": set()}
    if status_code not in allowed.get(action.status_code, set()):
        raise ValidationError(f"Invalid action transition from {action.status_code} to {status_code}.")
    if status_code == "COMPLETED" and not (resolution_summary.strip() or action.resolution_summary.strip()):
        raise ValidationError("Resolution summary is required before completing an executive action.")
    before = {"status": action.status_code, "version": action.version}
    if resolution_summary.strip():
        action.resolution_summary = resolution_summary.strip()
    action.status_code = status_code
    action.completed_at = timezone.now() if status_code == "COMPLETED" else None
    action.version += 1
    action.full_clean()
    action.save()
    _record(company=action.company, action="TRANSITION", event_type="insight.action.transitioned", entity_type="ExecutiveAction", entity_public_id=action.public_id, actor_public_id=actor_public_id, correlation_id=correlation_id, version=action.version, before=before, after={"code": action.code, "status": status_code})
    return action


@transaction.atomic
def create_board_report(*, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> BoardReport:
    data.setdefault("prepared_by_public_id", actor_public_id)
    return _create(BoardReport, company=company, actor_public_id=actor_public_id, correlation_id=correlation_id, event="insight.board_report.created", **data)


@transaction.atomic
def transition_board_report(*, report: BoardReport, status_code: str, expected_version: int, actor_public_id: uuid.UUID, correlation_id: uuid.UUID) -> BoardReport:
    report = BoardReport.objects.select_for_update().get(pk=report.pk)
    if report.version != expected_version:
        raise ValidationError("Board report changed. Refresh and retry.")
    allowed = {"DRAFT": {"IN_REVIEW", "CANCELLED"}, "IN_REVIEW": {"APPROVED", "DRAFT", "CANCELLED"}, "APPROVED": {"PUBLISHED", "IN_REVIEW"}, "PUBLISHED": {"ARCHIVED"}, "ARCHIVED": set(), "CANCELLED": set()}
    if status_code not in allowed.get(report.status_code, set()):
        raise ValidationError(f"Invalid board-report transition from {report.status_code} to {status_code}.")
    if status_code == "APPROVED" and report.prepared_by_public_id == actor_public_id:
        raise ValidationError("The report preparer cannot approve the same board report.")
    before = {"status": report.status_code, "version": report.version}
    if status_code == "APPROVED":
        report.approved_by_public_id = actor_public_id
    if status_code == "PUBLISHED":
        if report.approved_by_public_id is None:
            raise ValidationError("Board report must be approved before publication.")
        report.published_at = timezone.now()
    report.status_code = status_code
    report.version += 1
    report.full_clean()
    report.save()
    _record(company=report.company, action="TRANSITION", event_type="insight.board_report.transitioned", entity_type="BoardReport", entity_public_id=report.public_id, actor_public_id=actor_public_id, correlation_id=correlation_id, version=report.version, before=before, after={"code": report.code, "status": status_code})
    return report
