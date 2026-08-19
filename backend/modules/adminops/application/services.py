from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from modules.adminops.models import (
    FeatureFlag,
    HealthSnapshot,
    Incident,
    MaintenanceWindow,
    ReleaseCheck,
    ReleaseRecord,
    Runbook,
    RuntimeEnvironment,
    ServiceObjective,
)
from modules.platform.actors import RequestActor
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.tenant.models import Company


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



def adminops_summary(company: Company) -> dict[str, int]:
    return {
        "active_environments": RuntimeEnvironment.objects.filter(
            company=company, is_active=True
        ).count(),
        "pending_releases": ReleaseRecord.objects.filter(
            company=company,
            status__in=[
                ReleaseRecord.Status.DRAFT,
                ReleaseRecord.Status.VALIDATED,
                ReleaseRecord.Status.APPROVED,
            ],
        ).count(),
        "failed_checks": ReleaseCheck.objects.filter(
            company=company,
            status=ReleaseCheck.Status.FAILED,
        ).count(),
        "active_slos": ServiceObjective.objects.filter(company=company, is_active=True).count(),
        "open_incidents": Incident.objects.filter(company=company).exclude(
            status=Incident.Status.CLOSED
        ).count(),
        "enabled_flags": FeatureFlag.objects.filter(company=company, is_enabled=True).count(),
        "planned_maintenance": MaintenanceWindow.objects.filter(
            company=company,
            status__in=[MaintenanceWindow.Status.PLANNED, MaintenanceWindow.Status.APPROVED],
        ).count(),
    }


@transaction.atomic
def create_environment(
    *,
    company: Company,
    actor: RequestActor,
    code: str,
    name: str,
    environment_type: str,
    base_url: str = "",
    region: str = "",
    data_residency: str = "",
    production_data_allowed: bool = False,
    requires_change_approval: bool = True,
) -> RuntimeEnvironment:
    environment = RuntimeEnvironment(
        company=company,
        code=code.strip().upper(),
        name=name.strip(),
        environment_type=environment_type,
        base_url=base_url.strip(),
        region=region.strip(),
        data_residency=data_residency.strip(),
        production_data_allowed=production_data_allowed,
        requires_change_approval=requires_change_approval,
    )
    environment.full_clean()
    environment.save()
    _audit(
        actor=actor,
        company=company,
        action="adminops.environment.created",
        entity_type="runtime_environment",
        entity_public_id=environment.public_id,
        after={"code": environment.code, "type": environment.environment_type},
    )
    _event(
        actor=actor,
        company=company,
        event_type="adminops.environment.created",
        aggregate_type="runtime_environment",
        aggregate_public_id=environment.public_id,
        aggregate_version=environment.version,
        payload={"code": environment.code, "type": environment.environment_type},
    )
    return environment


@transaction.atomic
def create_release(
    *,
    company: Company,
    actor: RequestActor,
    environment_public_id: uuid.UUID,
    version_label: str,
    release_name: str,
    source_revision: str,
    artifact_sha256: str,
    migration_plan_sha256: str = "",
    change_summary: str = "",
) -> ReleaseRecord:
    environment = RuntimeEnvironment.objects.filter(
        company=company,
        public_id=environment_public_id,
        is_active=True,
    ).first()
    if environment is None:
        raise ValidationError("Runtime environment was not found")
    release = ReleaseRecord(
        company=company,
        environment=environment,
        version_label=version_label.strip(),
        release_name=release_name.strip(),
        source_revision=source_revision.strip(),
        artifact_sha256=artifact_sha256.strip().lower(),
        migration_plan_sha256=migration_plan_sha256.strip().lower(),
        change_summary=change_summary.strip(),
        requested_by_public_id=actor.user_public_id,
    )
    release.full_clean()
    release.save()
    _audit(
        actor=actor,
        company=company,
        action="adminops.release.created",
        entity_type="release_record",
        entity_public_id=release.public_id,
        after={"version": release.version_label, "environment": environment.code},
    )
    _event(
        actor=actor,
        company=company,
        event_type="adminops.release.created",
        aggregate_type="release_record",
        aggregate_public_id=release.public_id,
        aggregate_version=release.version,
        payload={"version": release.version_label, "environment": environment.code},
    )
    return release


def release_readiness(release: ReleaseRecord) -> dict[str, Any]:
    checks = release.checks.all()
    critical = checks.filter(is_critical=True)
    blocking = critical.exclude(status__in=[ReleaseCheck.Status.PASSED, ReleaseCheck.Status.WAIVED])
    ready = not blocking.exists()
    if settings.ADMINOPS_RELEASE_CHECKS_REQUIRED:
        ready = critical.exists() and ready
    return {
        "total_checks": checks.count(),
        "critical_checks": critical.count(),
        "passed_checks": checks.filter(status=ReleaseCheck.Status.PASSED).count(),
        "waived_checks": checks.filter(status=ReleaseCheck.Status.WAIVED).count(),
        "failed_checks": checks.filter(status=ReleaseCheck.Status.FAILED).count(),
        "blocking_checks": blocking.count(),
        "ready": ready,
    }


@transaction.atomic
def record_release_check(
    *,
    company: Company,
    actor: RequestActor,
    release_public_id: uuid.UUID,
    code: str,
    name: str,
    category: str,
    status: str,
    is_critical: bool,
    target_value: str = "",
    measured_value: str = "",
    evidence: str = "",
    waiver_reason: str = "",
) -> ReleaseCheck:
    release = ReleaseRecord.objects.filter(company=company, public_id=release_public_id).first()
    if release is None:
        raise ValidationError("Release was not found")
    now = timezone.now()
    item, _ = ReleaseCheck.objects.update_or_create(
        company=company,
        release=release,
        code=code.strip().upper(),
        defaults={
            "name": name.strip(),
            "category": category,
            "status": status,
            "is_critical": is_critical,
            "target_value": target_value.strip(),
            "measured_value": measured_value.strip(),
            "evidence": evidence.strip(),
            "waiver_reason": waiver_reason.strip(),
            "checked_by_public_id": actor.user_public_id
            if status != ReleaseCheck.Status.PENDING
            else None,
            "checked_at": now if status != ReleaseCheck.Status.PENDING else None,
        },
    )
    item.full_clean()
    item.save()
    _audit(
        actor=actor,
        company=company,
        action="adminops.release_check.recorded",
        entity_type="release_check",
        entity_public_id=item.public_id,
        after={"code": item.code, "status": item.status, "critical": item.is_critical},
    )
    return item


@transaction.atomic
def transition_release(
    *,
    company: Company,
    actor: RequestActor,
    release_public_id: uuid.UUID,
    target_status: str,
    expected_version: int,
    reason: str = "",
    rollback_reference: str = "",
) -> ReleaseRecord:
    release = ReleaseRecord.objects.select_for_update().select_related("environment").filter(
        company=company,
        public_id=release_public_id,
    ).first()
    if release is None:
        raise ValidationError("Release was not found")
    if release.version != expected_version:
        raise ValidationError("Release version conflict")
    allowed = {
        ReleaseRecord.Status.DRAFT: {ReleaseRecord.Status.VALIDATED, ReleaseRecord.Status.FAILED},
        ReleaseRecord.Status.VALIDATED: {
            ReleaseRecord.Status.APPROVED,
            ReleaseRecord.Status.FAILED,
        },
        ReleaseRecord.Status.APPROVED: {ReleaseRecord.Status.DEPLOYED, ReleaseRecord.Status.FAILED},
        ReleaseRecord.Status.DEPLOYED: {
            ReleaseRecord.Status.ROLLED_BACK,
            ReleaseRecord.Status.FAILED,
        },
        ReleaseRecord.Status.FAILED: {ReleaseRecord.Status.DRAFT},
        ReleaseRecord.Status.ROLLED_BACK: set(),
    }
    if target_status not in allowed[release.status]:
        raise ValidationError("Release status transition is not allowed")
    if target_status in {ReleaseRecord.Status.VALIDATED, ReleaseRecord.Status.APPROVED}:
        readiness = release_readiness(release)
        if not readiness["ready"]:
            raise ValidationError("Critical release checks are incomplete or failing")
    if target_status == ReleaseRecord.Status.APPROVED:
        if actor.user_public_id == release.requested_by_public_id:
            raise ValidationError("Release approval requires an independent reviewer")
        release.approved_by_public_id = actor.user_public_id
        release.approved_at = timezone.now()
    elif target_status == ReleaseRecord.Status.VALIDATED:
        release.validated_by_public_id = actor.user_public_id
        release.validated_at = timezone.now()
    elif target_status == ReleaseRecord.Status.DEPLOYED:
        release.deployed_by_public_id = actor.user_public_id
        release.deployed_at = timezone.now()
    elif target_status == ReleaseRecord.Status.ROLLED_BACK:
        if not rollback_reference.strip():
            raise ValidationError("Rollback evidence is required")
        release.rollback_reference = rollback_reference.strip()
    before_status = release.status
    release.status = target_status
    release.version += 1
    release.full_clean()
    release.save()
    _audit(
        actor=actor,
        company=company,
        action="adminops.release.transitioned",
        entity_type="release_record",
        entity_public_id=release.public_id,
        before={"status": before_status},
        after={"status": release.status, "version": release.version},
        reason_code=reason.strip(),
    )
    _event(
        actor=actor,
        company=company,
        event_type="adminops.release.transitioned",
        aggregate_type="release_record",
        aggregate_public_id=release.public_id,
        aggregate_version=release.version,
        payload={"from": before_status, "to": release.status},
    )
    return release


@transaction.atomic
def create_service_objective(
    *,
    company: Company,
    actor: RequestActor,
    code: str,
    name: str,
    service_code: str,
    indicator_type: str,
    target_value: Decimal,
    warning_threshold: Decimal,
    critical_threshold: Decimal,
    window_days: int,
    unit_code: str,
) -> ServiceObjective:
    objective = ServiceObjective(
        company=company,
        code=code.strip().upper(),
        name=name.strip(),
        service_code=service_code.strip().lower(),
        indicator_type=indicator_type,
        target_value=target_value,
        warning_threshold=warning_threshold,
        critical_threshold=critical_threshold,
        window_days=window_days,
        unit_code=unit_code.strip().lower(),
    )
    objective.full_clean()
    objective.save()
    _audit(
        actor=actor,
        company=company,
        action="adminops.slo.created",
        entity_type="service_objective",
        entity_public_id=objective.public_id,
        after={"code": objective.code, "service": objective.service_code},
    )
    return objective


@transaction.atomic
def record_health_snapshot(
    *,
    company: Company,
    actor: RequestActor,
    environment_public_id: uuid.UUID,
    service_code: str,
    status: str,
    latency_ms: int | None,
    observed_value: Decimal | None,
    source: str,
    details: dict[str, Any],
) -> HealthSnapshot:
    environment = RuntimeEnvironment.objects.filter(
        company=company,
        public_id=environment_public_id,
    ).first()
    if environment is None:
        raise ValidationError("Runtime environment was not found")
    snapshot = HealthSnapshot(
        company=company,
        environment=environment,
        service_code=service_code.strip().lower(),
        status=status,
        latency_ms=latency_ms,
        observed_value=observed_value,
        source=source.strip() or "manual",
        details=details,
        checked_at=timezone.now(),
    )
    snapshot.full_clean()
    snapshot.save()
    _event(
        actor=actor,
        company=company,
        event_type="adminops.health.recorded",
        aggregate_type="health_snapshot",
        aggregate_public_id=snapshot.public_id,
        aggregate_version=1,
        payload={"service": snapshot.service_code, "status": snapshot.status},
    )
    return snapshot


@transaction.atomic
def create_incident(
    *,
    company: Company,
    actor: RequestActor,
    environment_public_id: uuid.UUID,
    number: str,
    severity: str,
    title: str,
    summary: str = "",
    customer_impact: str = "",
    postmortem_required: bool = False,
) -> Incident:
    environment = RuntimeEnvironment.objects.filter(
        company=company,
        public_id=environment_public_id,
    ).first()
    if environment is None:
        raise ValidationError("Runtime environment was not found")
    incident = Incident(
        company=company,
        environment=environment,
        number=number.strip().upper(),
        severity=severity,
        title=title.strip(),
        summary=summary.strip(),
        customer_impact=customer_impact.strip(),
        postmortem_required=postmortem_required,
        owner_membership_public_id=actor.membership_public_id,
        detected_at=timezone.now(),
    )
    incident.full_clean()
    incident.save()
    _audit(
        actor=actor,
        company=company,
        action="adminops.incident.created",
        entity_type="incident",
        entity_public_id=incident.public_id,
        after={"number": incident.number, "severity": incident.severity},
    )
    _event(
        actor=actor,
        company=company,
        event_type="adminops.incident.created",
        aggregate_type="incident",
        aggregate_public_id=incident.public_id,
        aggregate_version=incident.version,
        payload={"number": incident.number, "severity": incident.severity},
    )
    return incident


@transaction.atomic
def transition_incident(
    *,
    company: Company,
    actor: RequestActor,
    incident_public_id: uuid.UUID,
    target_status: str,
    expected_version: int,
    root_cause: str = "",
    corrective_actions: list[dict[str, Any]] | None = None,
    postmortem_reference: str = "",
) -> Incident:
    incident = Incident.objects.select_for_update().filter(
        company=company,
        public_id=incident_public_id,
    ).first()
    if incident is None:
        raise ValidationError("Incident was not found")
    if incident.version != expected_version:
        raise ValidationError("Incident version conflict")
    allowed = {
        Incident.Status.IDENTIFIED: {Incident.Status.INVESTIGATING},
        Incident.Status.INVESTIGATING: {Incident.Status.MITIGATED, Incident.Status.RESOLVED},
        Incident.Status.MITIGATED: {Incident.Status.RESOLVED},
        Incident.Status.RESOLVED: {Incident.Status.CLOSED, Incident.Status.INVESTIGATING},
        Incident.Status.CLOSED: set(),
    }
    if target_status not in allowed[incident.status]:
        raise ValidationError("Incident status transition is not allowed")
    now = timezone.now()
    if target_status == Incident.Status.INVESTIGATING and not incident.acknowledged_at:
        incident.acknowledged_at = now
    elif target_status == Incident.Status.MITIGATED:
        incident.mitigated_at = now
    elif target_status == Incident.Status.RESOLVED:
        incident.resolved_at = now
        incident.root_cause = root_cause.strip() or incident.root_cause
        if corrective_actions is not None:
            incident.corrective_actions = corrective_actions
    elif target_status == Incident.Status.CLOSED:
        incident.closed_at = now
        incident.postmortem_reference = postmortem_reference.strip()
    before_status = incident.status
    incident.status = target_status
    incident.version += 1
    incident.full_clean()
    incident.save()
    _audit(
        actor=actor,
        company=company,
        action="adminops.incident.transitioned",
        entity_type="incident",
        entity_public_id=incident.public_id,
        before={"status": before_status},
        after={"status": incident.status, "version": incident.version},
    )
    _event(
        actor=actor,
        company=company,
        event_type="adminops.incident.transitioned",
        aggregate_type="incident",
        aggregate_public_id=incident.public_id,
        aggregate_version=incident.version,
        payload={"from": before_status, "to": incident.status},
    )
    return incident


@transaction.atomic
def create_runbook(
    *,
    company: Company,
    actor: RequestActor,
    code: str,
    title: str,
    category: str,
    purpose: str,
    steps: list[dict[str, Any]],
    review_due_at: Any = None,
) -> Runbook:
    runbook = Runbook(
        company=company,
        code=code.strip().upper(),
        title=title.strip(),
        category=category.strip().lower(),
        purpose=purpose.strip(),
        steps=steps,
        owner_membership_public_id=actor.membership_public_id,
        review_due_at=review_due_at,
    )
    runbook.full_clean()
    runbook.save()
    _audit(
        actor=actor,
        company=company,
        action="adminops.runbook.created",
        entity_type="runbook",
        entity_public_id=runbook.public_id,
        after={"code": runbook.code, "category": runbook.category},
    )
    return runbook


@transaction.atomic
def create_feature_flag(
    *,
    company: Company,
    actor: RequestActor,
    code: str,
    name: str,
    description: str,
    scope: dict[str, Any],
    requires_approval: bool = True,
) -> FeatureFlag:
    flag = FeatureFlag(
        company=company,
        code=code.strip().upper(),
        name=name.strip(),
        description=description.strip(),
        scope=scope,
        requires_approval=requires_approval,
        requested_by_public_id=actor.user_public_id,
    )
    flag.full_clean()
    flag.save()
    _audit(
        actor=actor,
        company=company,
        action="adminops.feature_flag.created",
        entity_type="feature_flag",
        entity_public_id=flag.public_id,
        after={"code": flag.code},
    )
    return flag


@transaction.atomic
def update_feature_flag(
    *,
    company: Company,
    actor: RequestActor,
    flag_public_id: uuid.UUID,
    is_enabled: bool,
    rollout_percent: int,
    expected_version: int,
) -> FeatureFlag:
    flag = FeatureFlag.objects.select_for_update().filter(
        company=company,
        public_id=flag_public_id,
    ).first()
    if flag is None:
        raise ValidationError("Feature flag was not found")
    if flag.version != expected_version:
        raise ValidationError("Feature flag version conflict")
    if flag.requires_approval and is_enabled:
        if flag.requested_by_public_id == actor.user_public_id:
            raise ValidationError("Feature enablement requires an independent approver")
        flag.approved_by_public_id = actor.user_public_id
        flag.approved_at = timezone.now()
    before = {"enabled": flag.is_enabled, "rollout_percent": flag.rollout_percent}
    flag.is_enabled = is_enabled
    flag.rollout_percent = rollout_percent
    flag.version += 1
    flag.full_clean()
    flag.save()
    _audit(
        actor=actor,
        company=company,
        action="adminops.feature_flag.updated",
        entity_type="feature_flag",
        entity_public_id=flag.public_id,
        before=before,
        after={"enabled": flag.is_enabled, "rollout_percent": flag.rollout_percent},
    )
    _event(
        actor=actor,
        company=company,
        event_type="adminops.feature_flag.updated",
        aggregate_type="feature_flag",
        aggregate_public_id=flag.public_id,
        aggregate_version=flag.version,
        payload={"code": flag.code, "enabled": flag.is_enabled},
    )
    return flag


@transaction.atomic
def create_maintenance_window(
    *,
    company: Company,
    actor: RequestActor,
    environment_public_id: uuid.UUID,
    reference: str,
    title: str,
    reason: str,
    starts_at: Any,
    ends_at: Any,
    affected_services: list[str],
) -> MaintenanceWindow:
    environment = RuntimeEnvironment.objects.filter(
        company=company,
        public_id=environment_public_id,
    ).first()
    if environment is None:
        raise ValidationError("Runtime environment was not found")
    item = MaintenanceWindow(
        company=company,
        environment=environment,
        reference=reference.strip().upper(),
        title=title.strip(),
        reason=reason.strip(),
        starts_at=starts_at,
        ends_at=ends_at,
        affected_services=affected_services,
        requested_by_public_id=actor.user_public_id,
    )
    item.full_clean()
    item.save()
    _audit(
        actor=actor,
        company=company,
        action="adminops.maintenance.created",
        entity_type="maintenance_window",
        entity_public_id=item.public_id,
        after={"reference": item.reference, "environment": environment.code},
    )
    return item


@transaction.atomic
def transition_maintenance_window(
    *,
    company: Company,
    actor: RequestActor,
    window_public_id: uuid.UUID,
    target_status: str,
    expected_version: int,
) -> MaintenanceWindow:
    item = MaintenanceWindow.objects.select_for_update().filter(
        company=company,
        public_id=window_public_id,
    ).first()
    if item is None:
        raise ValidationError("Maintenance window was not found")
    if item.version != expected_version:
        raise ValidationError("Maintenance window version conflict")
    allowed = {
        MaintenanceWindow.Status.PLANNED: {
            MaintenanceWindow.Status.APPROVED,
            MaintenanceWindow.Status.CANCELLED,
        },
        MaintenanceWindow.Status.APPROVED: {
            MaintenanceWindow.Status.IN_PROGRESS,
            MaintenanceWindow.Status.CANCELLED,
        },
        MaintenanceWindow.Status.IN_PROGRESS: {MaintenanceWindow.Status.COMPLETED},
        MaintenanceWindow.Status.COMPLETED: set(),
        MaintenanceWindow.Status.CANCELLED: set(),
    }
    if target_status not in allowed[item.status]:
        raise ValidationError("Maintenance status transition is not allowed")
    if target_status == MaintenanceWindow.Status.APPROVED:
        if item.requested_by_public_id == actor.user_public_id:
            raise ValidationError("Maintenance approval requires an independent reviewer")
        item.approved_by_public_id = actor.user_public_id
        item.approved_at = timezone.now()
    before_status = item.status
    item.status = target_status
    item.version += 1
    item.full_clean()
    item.save()
    _audit(
        actor=actor,
        company=company,
        action="adminops.maintenance.transitioned",
        entity_type="maintenance_window",
        entity_public_id=item.public_id,
        before={"status": before_status},
        after={"status": item.status, "version": item.version},
    )
    return item
